"""
Atlas web server - end-to-end integration tests via FastAPI's
TestClient. Uses FakeSupabaseClient throughout - no network access, no
applied migrations required to run this file.

Cookies are passed explicitly on each request rather than relying on
TestClient's cookie jar: httpx's TestClient appends ".local" to the
bare "testserver" hostname internally, which silently breaks
domain-matching for cookies set without an explicit domain (the
correct, host-only way to set them). This is a test-harness quirk, not
a bug in server/ - in a real deployment the domain is a normal
multi-label hostname and cookies behave normally. Confirmed by
comparing TestClient's own cookie jar contents against the Set-Cookie
header directly.
"""

import re

from fastapi.testclient import TestClient

from server.app import create_app
from server.config import Config
from server.passwords import hash_password
from server.supabase_client import FakeSupabaseClient

PASSWORD = "test-password-123"


def make_client(**config_overrides):
    pw_hash = hash_password(PASSWORD, iterations=1000)
    defaults = dict(
        password_hash=pw_hash,
        session_secret="test-secret",
        supabase_url="https://example.test",
        supabase_service_key="fake-key",
        # development: TestClient doesn't send Vercel's IP headers, so
        # production mode here would make every request's IP "unknown"
        # (correctly - see server/client_ip.py) and neuter per-IP
        # lockout tests. development uses the real (fake) connection
        # address instead, same as a real non-Vercel deployment would.
        environment="development",
        public_origin="http://testserver",
        lockout_threshold=5,
        global_lockout_threshold=20,
        lockout_window_seconds=900,
        cleanup_probability=0.0,  # opportunistic cleanup off by default in tests
    )
    defaults.update(config_overrides)
    config = Config(**defaults)
    fake = FakeSupabaseClient()
    app = create_app(config, supabase=fake)
    return TestClient(app), fake


def login(client, password=PASSWORD):
    response = client.post(
        "/login", data={"password": password},
        headers={"Origin": "http://testserver"}, follow_redirects=False,
    )
    return response.cookies.get("atlas_session")


def _extract_csrf_token(html):
    match = re.search(r'<meta name="csrf-token" content="([^"]+)">', html)
    return match.group(1) if match else None


class TestLoginFlow:
    def test_login_page_loads(self):
        client, _ = make_client()
        response = client.get("/login")
        assert response.status_code == 200
        assert "ATLAS" in response.text

    def test_wrong_password_rejected(self):
        client, _ = make_client()
        response = client.post(
            "/login", data={"password": "wrong"}, headers={"Origin": "http://testserver"},
        )
        assert response.status_code == 401
        assert "Incorrect password" in response.text

    def test_correct_password_sets_cookie_and_redirects(self):
        client, _ = make_client()
        response = client.post(
            "/login", data={"password": PASSWORD},
            headers={"Origin": "http://testserver"}, follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/"
        assert "atlas_session" in response.cookies

    def test_cross_origin_login_post_rejected(self):
        client, _ = make_client()
        response = client.post(
            "/login", data={"password": PASSWORD}, headers={"Origin": "https://evil.example.com"},
        )
        assert response.status_code == 403

    def test_lockout_after_repeated_failures(self):
        client, _ = make_client(lockout_threshold=3, lockout_window_seconds=900)
        for _ in range(3):
            client.post("/login", data={"password": "wrong"}, headers={"Origin": "http://testserver"})

        # Even the CORRECT password is rejected once locked out.
        response = client.post(
            "/login", data={"password": PASSWORD}, headers={"Origin": "http://testserver"},
        )
        assert response.status_code == 401
        assert "atlas_session" not in response.cookies

    def test_wrong_password_and_lockout_show_identical_response(self):
        """Never reveal *why* a login failed."""
        client, fake = make_client(lockout_threshold=2, lockout_window_seconds=900)
        wrong_password_response = client.post(
            "/login", data={"password": "wrong"}, headers={"Origin": "http://testserver"},
        )

        for _ in range(2):
            client.post("/login", data={"password": "wrong"}, headers={"Origin": "http://testserver"})
        locked_out_response = client.post(
            "/login", data={"password": PASSWORD}, headers={"Origin": "http://testserver"},
        )

        assert wrong_password_response.status_code == locked_out_response.status_code
        assert wrong_password_response.text == locked_out_response.text


class TestProtectedPages:
    def test_unauthenticated_root_redirects_to_login(self):
        client, _ = make_client()
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"

    def test_authenticated_root_serves_dashboard(self):
        client, _ = make_client()
        cookie = login(client)
        response = client.get("/", cookies={"atlas_session": cookie})
        assert response.status_code == 200
        assert "csrf-token" in response.text

    def test_authenticated_hearted_page_served(self):
        client, _ = make_client()
        cookie = login(client)
        response = client.get("/hearted.html", cookies={"atlas_session": cookie})
        assert response.status_code == 200
        assert "Hearted Items" in response.text

    def test_index_html_and_root_serve_same_content(self):
        client, _ = make_client()
        cookie = login(client)
        root = client.get("/", cookies={"atlas_session": cookie})
        index = client.get("/index.html", cookies={"atlas_session": cookie})
        assert root.text == index.text

    def test_revoked_cookie_redirects_to_login(self):
        client, _ = make_client()
        cookie = login(client)
        client.get("/logout", cookies={"atlas_session": cookie})
        response = client.get("/", cookies={"atlas_session": cookie}, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"

    def test_garbage_cookie_redirects_to_login(self):
        client, _ = make_client()
        response = client.get("/", cookies={"atlas_session": "not-a-real-cookie"}, follow_redirects=False)
        assert response.status_code == 303


class TestDemoGating:
    def test_demo_disabled_by_default_returns_404(self):
        client, _ = make_client(enable_demo=False)
        cookie = login(client)
        response = client.get("/demo-index.html", cookies={"atlas_session": cookie})
        assert response.status_code == 404

    def test_demo_enabled_serves_page(self):
        client, _ = make_client(enable_demo=True)
        cookie = login(client)
        response = client.get("/demo-index.html", cookies={"atlas_session": cookie})
        assert response.status_code == 200
        assert "DEMO" in response.text


class TestProtectedStaticAssets:
    def test_app_js_served_with_correct_content_type(self):
        client, _ = make_client()
        cookie = login(client)
        response = client.get("/app.js", cookies={"atlas_session": cookie})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/javascript")

    def test_styles_css_served_with_correct_content_type(self):
        client, _ = make_client()
        cookie = login(client)
        response = client.get("/styles.css", cookies={"atlas_session": cookie})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/css")

    def test_svg_asset_served(self):
        client, _ = make_client()
        cookie = login(client)
        response = client.get("/assets/placeholder.svg", cookies={"atlas_session": cookie})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/svg+xml")

    def test_unauthenticated_asset_request_redirects(self):
        client, _ = make_client()
        response = client.get("/app.js", follow_redirects=False)
        assert response.status_code == 303

    def test_path_traversal_blocked(self):
        client, _ = make_client()
        cookie = login(client)
        for attempt in ["/assets/../app.py", "/assets/../../server/app.py", "/assets/%2e%2e/%2e%2e/server/app.py"]:
            response = client.get(attempt, cookies={"atlas_session": cookie})
            assert response.status_code == 404, attempt

    def test_non_svg_extension_rejected(self):
        client, _ = make_client()
        cookie = login(client)
        response = client.get("/assets/placeholder.png", cookies={"atlas_session": cookie})
        assert response.status_code == 404


class TestApiAuthentication:
    def test_unauthenticated_api_request_returns_401_json(self):
        client, _ = make_client()
        response = client.get("/api/whoami", follow_redirects=False)
        assert response.status_code == 401
        assert response.json() == {"error": "unauthorized"}

    def test_authenticated_api_request_succeeds(self):
        client, _ = make_client()
        cookie = login(client)
        response = client.get("/api/whoami", cookies={"atlas_session": cookie})
        assert response.status_code == 200
        assert response.json() == {"authenticated": True}


class TestApiCsrfAndOriginProtection:
    def _authenticated(self):
        client, fake = make_client()
        cookie = login(client)
        page = client.get("/", cookies={"atlas_session": cookie})
        csrf_token = _extract_csrf_token(page.text)
        return client, fake, cookie, csrf_token

    def test_mutation_without_csrf_token_rejected(self):
        client, fake, cookie, _ = self._authenticated()
        response = client.post(
            "/api/hearted", cookies={"atlas_session": cookie},
            headers={"Origin": "http://testserver", "Content-Type": "application/json"},
            json={"opportunity_id": "opp-1"},
        )
        assert response.status_code == 403

    def test_mutation_with_wrong_csrf_token_rejected(self):
        client, fake, cookie, _ = self._authenticated()
        response = client.post(
            "/api/hearted", cookies={"atlas_session": cookie},
            headers={
                "Origin": "http://testserver", "Content-Type": "application/json",
                "X-CSRF-Token": "wrong-token",
            },
            json={"opportunity_id": "opp-1"},
        )
        assert response.status_code == 403

    def test_mutation_with_wrong_origin_rejected(self):
        client, fake, cookie, csrf_token = self._authenticated()
        response = client.post(
            "/api/hearted", cookies={"atlas_session": cookie},
            headers={
                "Origin": "https://evil.example.com", "Content-Type": "application/json",
                "X-CSRF-Token": csrf_token,
            },
            json={"opportunity_id": "opp-1"},
        )
        assert response.status_code == 403

    def test_mutation_with_wrong_content_type_rejected(self):
        client, fake, cookie, csrf_token = self._authenticated()
        response = client.post(
            "/api/hearted", cookies={"atlas_session": cookie},
            headers={
                "Origin": "http://testserver", "Content-Type": "text/plain",
                "X-CSRF-Token": csrf_token,
            },
            content=b'{"opportunity_id": "opp-1"}',
        )
        assert response.status_code == 415

    def test_valid_mutation_succeeds(self):
        client, fake, cookie, csrf_token = self._authenticated()
        response = client.post(
            "/api/hearted", cookies={"atlas_session": cookie},
            headers={
                "Origin": "http://testserver", "Content-Type": "application/json",
                "X-CSRF-Token": csrf_token,
            },
            json={"opportunity_id": "opp-1"},
        )
        assert response.status_code == 200
        assert fake.tables["hearted_items"][0]["opportunity_id"] == "opp-1"

    def test_oversized_body_rejected(self):
        client, fake, cookie, csrf_token = self._authenticated()
        big_payload = {"opportunity_id": "x" * (2 * 1024 * 1024)}  # 2MB, over the 1MB default
        response = client.post(
            "/api/hearted", cookies={"atlas_session": cookie},
            headers={
                "Origin": "http://testserver", "Content-Type": "application/json",
                "X-CSRF-Token": csrf_token,
            },
            json=big_payload,
        )
        assert response.status_code == 413


class TestApiHeartedFlow:
    def _authenticated(self):
        client, fake = make_client()
        cookie = login(client)
        page = client.get("/", cookies={"atlas_session": cookie})
        csrf_token = _extract_csrf_token(page.text)
        return client, fake, cookie, csrf_token

    def _headers(self, csrf_token, content_type="application/json"):
        return {"Origin": "http://testserver", "Content-Type": content_type, "X-CSRF-Token": csrf_token}

    def test_heart_then_unheart_by_opportunity(self):
        client, fake, cookie, csrf_token = self._authenticated()
        client.post(
            "/api/hearted", cookies={"atlas_session": cookie}, headers=self._headers(csrf_token),
            json={"opportunity_id": "opp-1"},
        )
        assert len(fake.tables["hearted_items"]) == 1

        response = client.delete(
            "/api/hearted/by-opportunity/opp-1", cookies={"atlas_session": cookie},
            headers=self._headers(csrf_token),
        )
        assert response.status_code == 200
        assert len(fake.tables["hearted_items"]) == 0

    def test_create_manual_item_and_fetch_it(self):
        client, fake, cookie, csrf_token = self._authenticated()
        response = client.post(
            "/api/hearted/manual", cookies={"atlas_session": cookie}, headers=self._headers(csrf_token),
            json={"product_name": "Test Item", "target_price": 42.5, "tags": ["a", "b"]},
        )
        assert response.status_code == 200
        item = response.json()
        assert item["product_name"] == "Test Item"
        assert item["status"] == "SAVED"

        fetched = client.get(f"/api/hearted/{item['id']}", cookies={"atlas_session": cookie})
        assert fetched.status_code == 200
        assert fetched.json()["product_name"] == "Test Item"

    def test_archive_toggle(self):
        client, fake, cookie, csrf_token = self._authenticated()
        created = client.post(
            "/api/hearted/manual", cookies={"atlas_session": cookie}, headers=self._headers(csrf_token),
            json={"product_name": "Test Item"},
        ).json()

        response = client.patch(
            f"/api/hearted/{created['id']}/archive", cookies={"atlas_session": cookie},
            headers=self._headers(csrf_token), json={"archived": True},
        )
        assert response.status_code == 200
        assert fake.tables["hearted_items"][0]["archived_at"] is not None

    def test_edit_manual_item_full_identity(self):
        client, fake, cookie, csrf_token = self._authenticated()
        created = client.post(
            "/api/hearted/manual", cookies={"atlas_session": cookie}, headers=self._headers(csrf_token),
            json={"product_name": "Original Name"},
        ).json()

        response = client.patch(
            f"/api/hearted/{created['id']}", cookies={"atlas_session": cookie}, headers=self._headers(csrf_token),
            json={"product_name": "Renamed", "priority": "high", "tags": [], "include_identity": True},
        )
        assert response.status_code == 200
        assert response.json()["product_name"] == "Renamed"
        assert response.json()["priority"] == "high"

    def test_edit_atlas_linked_item_ignores_identity_fields(self):
        client, fake, cookie, csrf_token = self._authenticated()
        fake.insert("hearted_items", {
            "opportunity_id": "opp-1", "product_name": None, "status": "SAVED",
        })
        item_id = fake.tables["hearted_items"][0]["id"]

        response = client.patch(
            f"/api/hearted/{item_id}", cookies={"atlas_session": cookie}, headers=self._headers(csrf_token),
            json={
                "product_name": "Should be ignored", "priority": "high", "tags": [],
                "include_identity": False,
            },
        )
        assert response.status_code == 200
        # product_name was never sent since include_identity=False.
        stored = fake.tables["hearted_items"][0]
        assert stored["product_name"] is None
        assert stored["priority"] == "high"


class TestApiNotesFlow:
    def _authenticated(self):
        client, fake = make_client()
        cookie = login(client)
        page = client.get("/", cookies={"atlas_session": cookie})
        csrf_token = _extract_csrf_token(page.text)
        return client, fake, cookie, csrf_token

    def _headers(self, csrf_token):
        return {"Origin": "http://testserver", "Content-Type": "application/json", "X-CSRF-Token": csrf_token}

    def test_add_list_delete_opportunity_note(self):
        client, fake, cookie, csrf_token = self._authenticated()
        created = client.post(
            "/api/notes", cookies={"atlas_session": cookie}, headers=self._headers(csrf_token),
            json={"scope": "opportunity", "subject_id": "opp-1", "body": "Check price next week"},
        ).json()

        listed = client.get(
            "/api/notes?scope=opportunity&subject_id=opp-1", cookies={"atlas_session": cookie},
        ).json()
        assert len(listed) == 1
        assert listed[0]["body"] == "Check price next week"

        response = client.delete(
            f"/api/notes/{created['id']}?scope=opportunity", cookies={"atlas_session": cookie},
            headers=self._headers(csrf_token),
        )
        assert response.status_code == 200
        assert fake.tables["opportunity_notes"] == []


class TestApiOverridesFlow:
    def _authenticated(self):
        client, fake = make_client()
        cookie = login(client)
        page = client.get("/", cookies={"atlas_session": cookie})
        csrf_token = _extract_csrf_token(page.text)
        return client, fake, cookie, csrf_token

    def _headers(self, csrf_token):
        return {"Origin": "http://testserver", "Content-Type": "application/json", "X-CSRF-Token": csrf_token}

    def test_save_override_records_history(self):
        client, fake, cookie, csrf_token = self._authenticated()
        response = client.put(
            "/api/overrides/opp-1", cookies={"atlas_session": cookie}, headers=self._headers(csrf_token),
            json={
                "market_strength_override": "STRONG", "market_trend_override": None,
                "reason": "insider info", "atlas_market_strength": "WEAK", "atlas_market_trend": "RISING",
            },
        )
        assert response.status_code == 200
        assert fake.tables["opportunity_user_overrides"][0]["market_strength_override"] == "STRONG"
        history = fake.tables["opportunity_override_history"]
        assert len(history) == 1
        assert history[0]["atlas_value_snapshot"] == "WEAK"
        assert history[0]["new_override_value"] == "STRONG"

    def test_invalid_market_strength_rejected(self):
        client, fake, cookie, csrf_token = self._authenticated()
        response = client.put(
            "/api/overrides/opp-1", cookies={"atlas_session": cookie}, headers=self._headers(csrf_token),
            json={"market_strength_override": "NOT_A_REAL_VALUE"},
        )
        assert response.status_code == 422

    def test_reset_override_records_history_and_deletes_row(self):
        client, fake, cookie, csrf_token = self._authenticated()
        client.put(
            "/api/overrides/opp-1", cookies={"atlas_session": cookie}, headers=self._headers(csrf_token),
            json={"market_strength_override": "STRONG", "atlas_market_strength": "WEAK"},
        )
        response = client.request(
            "DELETE", "/api/overrides/opp-1", cookies={"atlas_session": cookie}, headers=self._headers(csrf_token),
            json={"atlas_market_strength": "WEAK"},
        )
        assert response.status_code == 200
        assert fake.tables["opportunity_user_overrides"] == []
        history = fake.tables["opportunity_override_history"]
        assert history[-1]["new_override_value"] is None
        assert history[-1]["reason"] == "Reset to Atlas assessment"

    def test_get_override_returns_none_when_absent(self):
        client, fake, cookie, _ = self._authenticated()
        response = client.get("/api/overrides/opp-nonexistent", cookies={"atlas_session": cookie})
        assert response.status_code == 200
        assert response.json() is None


class TestSecurityHeaders:
    EXPECTED_HEADERS = (
        "content-security-policy", "x-content-type-options",
        "x-frame-options", "referrer-policy", "permissions-policy",
    )

    def _assert_all_present(self, response):
        for header in self.EXPECTED_HEADERS:
            assert header in response.headers, f"missing {header}"
        assert response.headers["x-content-type-options"] == "nosniff"
        csp = response.headers["content-security-policy"]
        assert "frame-ancestors 'none'" in csp
        assert "base-uri 'none'" in csp
        assert "form-action 'self'" in csp
        assert "unsafe-inline" not in csp
        assert "unsafe-eval" not in csp

    def test_headers_on_login_page(self):
        client, _ = make_client()
        self._assert_all_present(client.get("/login"))

    def test_headers_on_login_css(self):
        client, _ = make_client()
        self._assert_all_present(client.get("/login.css"))

    def test_headers_on_authenticated_dashboard(self):
        client, _ = make_client()
        cookie = login(client)
        self._assert_all_present(client.get("/", cookies={"atlas_session": cookie}))

    def test_headers_on_static_assets(self):
        client, _ = make_client()
        cookie = login(client)
        self._assert_all_present(client.get("/app.js", cookies={"atlas_session": cookie}))
        self._assert_all_present(client.get("/styles.css", cookies={"atlas_session": cookie}))
        self._assert_all_present(client.get("/assets/placeholder.svg", cookies={"atlas_session": cookie}))

    def test_headers_on_api_response(self):
        client, _ = make_client()
        cookie = login(client)
        self._assert_all_present(client.get("/api/whoami", cookies={"atlas_session": cookie}))

    def test_headers_on_redirect(self):
        client, _ = make_client()
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 303
        self._assert_all_present(response)

    def test_headers_on_401_error_response(self):
        client, _ = make_client()
        response = client.get("/api/whoami", follow_redirects=False)
        assert response.status_code == 401
        self._assert_all_present(response)

    def test_headers_on_403_error_response(self):
        client, fake = make_client()
        cookie = login(client)
        response = client.post(
            "/api/hearted", cookies={"atlas_session": cookie},
            headers={"Origin": "https://evil.example.com", "Content-Type": "application/json"},
            json={"opportunity_id": "opp-1"},
        )
        assert response.status_code == 403
        self._assert_all_present(response)

    def test_headers_on_404_error_response(self):
        client, _ = make_client()
        cookie = login(client)
        response = client.get("/nonexistent-route-xyz", cookies={"atlas_session": cookie})
        assert response.status_code == 404
        self._assert_all_present(response)

    def test_headers_on_413_error_response(self):
        client, fake = make_client()
        cookie = login(client)
        page = client.get("/", cookies={"atlas_session": cookie})
        csrf_token = _extract_csrf_token(page.text)
        big_payload = {"opportunity_id": "x" * (2 * 1024 * 1024)}
        response = client.post(
            "/api/hearted", cookies={"atlas_session": cookie},
            headers={
                "Origin": "http://testserver", "Content-Type": "application/json",
                "X-CSRF-Token": csrf_token,
            },
            json=big_payload,
        )
        assert response.status_code == 413
        self._assert_all_present(response)

    def test_csp_allows_https_images(self):
        client, _ = make_client()
        response = client.get("/login")
        csp = response.headers["content-security-policy"]
        assert "img-src 'self' https:" in csp

    def test_csp_restricts_connect_src_to_self(self):
        client, _ = make_client()
        response = client.get("/login")
        csp = response.headers["content-security-policy"]
        assert "connect-src 'self'" in csp


class TestIpSpoofingResistance:
    def test_spoofed_forwarded_for_does_not_bypass_per_ip_lockout(self):
        """development mode (this test harness's default) never trusts
        X-Forwarded-For - every attempt here resolves to the same real
        connection IP no matter what the header claims, so rotating a
        spoofed header can't reset the per-IP counter."""
        client, fake = make_client(lockout_threshold=3, global_lockout_threshold=1000)

        for i in range(3):
            client.post(
                "/login", data={"password": "wrong"},
                headers={"Origin": "http://testserver", "X-Forwarded-For": f"203.0.113.{i}"},
            )

        response = client.post(
            "/login", data={"password": PASSWORD},
            headers={"Origin": "http://testserver", "X-Forwarded-For": "9.9.9.9"},
        )
        assert response.status_code == 401
        assert "atlas_session" not in response.cookies

        recorded_ips = {row["ip_address"] for row in fake.tables["auth_login_attempts"]}
        # Every recorded attempt used the same real IP, proving the
        # X-Forwarded-For values above were never read.
        assert len(recorded_ips) == 1

    def test_production_mode_reads_the_documented_vercel_header(self):
        """The flip side: when config says requests really do arrive
        via Vercel, the documented header IS read (and used for
        per-IP attribution) - this isn't "never trust forwarding
        headers," it's "only trust the one Vercel itself controls.\""""
        client, fake = make_client(environment="production", lockout_threshold=2, global_lockout_threshold=1000)

        client.post(
            "/login", data={"password": "wrong"},
            headers={"Origin": "http://testserver", "X-Forwarded-For": "203.0.113.5"},
        )
        client.post(
            "/login", data={"password": "wrong"},
            headers={"Origin": "http://testserver", "X-Forwarded-For": "203.0.113.5"},
        )
        # This specific IP is now locked out...
        locked = client.post(
            "/login", data={"password": PASSWORD},
            headers={"Origin": "http://testserver", "X-Forwarded-For": "203.0.113.5"},
        )
        assert locked.status_code == 401

        # ...but a genuinely different IP is not affected by it.
        different_ip = client.post(
            "/login", data={"password": PASSWORD},
            headers={"Origin": "http://testserver", "X-Forwarded-For": "198.51.100.200"},
            follow_redirects=False,
        )
        assert different_ip.status_code == 303
        assert "atlas_session" in different_ip.cookies
