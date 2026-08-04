"""
Atlas web server - the login page.

Plain Python string templating, matching how the rest of the dashboard
is rendered (see collector_intelligence/dashboard_render.py) rather
than adding a template engine dependency. The only variable content is
a fixed boolean (show the generic error line or not) - nothing here
ever echoes back anything a visitor typed, so there is no reflected
input to escape.

CSS lives in its own string (LOGIN_CSS), served through a dedicated
/login.css route (see routes_pages.py) rather than an inline <style>
block. That's the only reason this file is split this way: an inline
<style> block would require 'unsafe-inline' in the CSP's style-src,
and this is the one place in the whole app where that would otherwise
be necessary (see server/security_headers.py) - removing it entirely
was simpler than carving out a narrower exception.
"""

LOGIN_CSS = """
:root {
  color-scheme: dark;
  --color-bg: #14161c;
  --color-surface: #1c1f27;
  --color-border: #2c303c;
  --color-text: #e7e9ee;
  --color-text-muted: #9298a8;
  --color-accent: #7c8fd6;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg);
  color: var(--color-text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
}
.login-card {
  width: 100%;
  max-width: 320px;
  padding: 32px 28px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 10px;
  text-align: center;
}
h1 {
  margin: 0 0 24px;
  font-size: 20px;
  letter-spacing: 0.08em;
}
label {
  display: block;
  text-align: left;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-muted);
  margin-bottom: 6px;
}
input[type="password"] {
  width: 100%;
  padding: 9px 11px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-bg);
  color: var(--color-text);
  font-size: 14px;
  margin-bottom: 16px;
}
input[type="password"]:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 1px;
}
button {
  width: 100%;
  padding: 10px;
  border: 1px solid var(--color-accent);
  border-radius: 6px;
  background: var(--color-accent);
  color: #14161c;
  font-weight: 700;
  font-size: 14px;
  cursor: pointer;
}
.error {
  color: #e37b6c;
  font-size: 13px;
  margin: -6px 0 16px;
  text-align: left;
}
"""

_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Atlas</title>
  <link rel="stylesheet" href="/login.css">
</head>
<body>
  <div class="login-card">
    <h1>ATLAS</h1>
    <form method="post" action="/login">
      <label for="password">Password</label>
      <input id="password" name="password" type="password" autocomplete="current-password" autofocus required>
      {error_html}
      <button type="submit">Enter</button>
    </form>
  </div>
</body>
</html>
"""

_ERROR_HTML = '<p class="error" role="alert">Incorrect password, or too many attempts. Try again shortly.</p>'


def render_login_page(show_error=False):
    return _PAGE.format(error_html=_ERROR_HTML if show_error else "")
