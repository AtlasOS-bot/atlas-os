# Atlas — Current State Audit (Pokémon Module)

Date: 2026-07-18
Scope: entire repository, with emphasis on everything the Pokémon module touches (scouts/pokemon, scouts/tcg, market, signals, patterns, popularity, reasoning, decision, brain, learning, memory, knowledge, acquisition, .github/workflows).

Method: every claim below cites an exact file path (and line numbers where useful). Nothing is listed as "done" unless it was read directly. Test status: `python -m pytest tests/ -q` → **99 passed, 3 failed** (failures explained under Broken).

---

## 0. The single most important finding

**There are two separate, disconnected pipelines, and only the cruder one is wired into automation.**

- **Pipeline A — "legacy/universal", actually scheduled:** [.github/workflows/atlas-pipeline.yml](.github/workflows/atlas-pipeline.yml) runs on a cron (`*/30 * * * *`) and chains `scouts/universal.py` → `atlas/scorer.py` → `atlas/research_engine.py` → `atlas/ebay_research.py` → `atlas/market_signals.py` → `atlas/create_notifications.py` → `atlas/alerts.py`. This path is brand-agnostic (reads [config/brands.json](config/brands.json): Disney, Pokémon, LEGO, Funko, Mattel), scrapes press-release pages, and scores items with hardcoded keyword tables in [atlas/scorer.py:7-17](atlas/scorer.py#L7-L17) (`STRONG`/`BAD` dicts, e.g. `"pokemon center": 22`). It writes directly to Supabase tables `raw_drops` and `opportunities` via raw `requests` calls ([scouts/universal.py:9-10](scouts/universal.py#L9-L10), [atlas/scorer.py:4-5](atlas/scorer.py#L4-L5)). None of this touches the Pokémon-specific intelligence described below.

- **Pipeline B — "scouts/pokemon", the sophisticated one, NOT scheduled:** [scouts/pokemon/collector.py](scouts/pokemon/collector.py) (`PokemonScout`, extends `AtlasScout`) and [scouts/pokemon/live_monitor.py](scouts/pokemon/live_monitor.py) (`PokemonLiveMonitor`) implement everything described in sections 1–3 below — identity resolution, consensus, state tracking, classification, investment scoring, alerting, release calendar. Both files only run via `if __name__ == "__main__"` ([collector.py:652](scouts/pokemon/collector.py#L652), [live_monitor.py:1097](scouts/pokemon/live_monitor.py#L1097)). Grepping every `.github/workflows/*.yml` and every `atlas/*.py` file for `PokemonScout`, `scouts.pokemon.collector`, or `scouts.pokemon.live_monitor` returns **zero matches**. `PokemonScout.run()` does call `self.save_opportunity()` ([collector.py:420](scouts/pokemon/collector.py#L420), inherited from [scouts/base/atlas_scout.py:76-132](scouts/base/atlas_scout.py#L76-L132)), which routes through `AtlasBrain.analyze` → the full reasoning/decision engine → Supabase `opportunities` table — so the plumbing is correct, it's just never triggered automatically. Evidence it has been run manually: `.atlas_data/pokemon_live_scan.json`, `.atlas_data/pokemon_alerts.json`, `.atlas_data/pokemon_release_calendar.json`, `.atlas_data/pokemon_product_states.json` all exist locally.

Consequence: if you're asking "does the Pokémon module work," the answer is "yes, extensively, but only when run by hand." If you're asking "does the automated GitHub Actions pipeline use it," the answer is "no." Fixing this wiring gap is higher-leverage than adding any new layer.

---

## 1. Complete (implemented, tested, wired to something real)

| Capability | Layer | Evidence |
|---|---|---|
| Canonical product identity + fuzzy duplicate matching | 1 | [scouts/pokemon/identity.py](scouts/pokemon/identity.py) — `canonical_product_key` (L133-158), `identity_similarity` (L161-214, Jaccard token overlap + product-type bonus), `same_product` (L217-238). Tested: `tests/test_pokemon_identity.py`. Used by `state_tracker.py`, `alert_store.py`, `consensus.py`. |
| Multi-source consensus / duplicate-title resolution | 1 | [scouts/pokemon/consensus.py](scouts/pokemon/consensus.py) — groups items via `same_product`, merges fields, computes a trust-weighted `consensus_score`/`level`/`confidence` (L14-244). Tested: `tests/test_pokemon_consensus.py`. |
| Release calendar with urgency tiers | 2 | [scouts/pokemon/release_calendar.py](scouts/pokemon/release_calendar.py) — `build_release_calendar`/`determine_action_window` maps days-to-release into 7 action windows (RELEASE DAY → PAST RELEASE) with urgency scores. Persistence: [release_store.py](scouts/pokemon/release_store.py). Report: [release_brief.py](scouts/pokemon/release_brief.py). Tests: `test_pokemon_release_calendar.py`, `test_pokemon_release_store.py`, `test_pokemon_release_brief.py`. **Note:** confidence tiers here are *urgency* tiers (RELEASE DAY/PREORDER NOW/…), not the requested confirmed/likely/rumored *source-confidence* taxonomy — see Partial, below. |
| Standard retailer-adapter interface | 3 | [scouts/base/atlas_scout.py](scouts/base/atlas_scout.py) — `AtlasScout` base class defines `run()` (abstract, L134-136), `save_opportunity()`, `opportunity_exists()`. `PokemonScout` ([collector.py:33-56](scouts/pokemon/collector.py#L33-L56)) and `scouts/nike/*` extend it. **But** `scouts/starbucks.py`, `scouts/lorcana/*`, `scouts/one_piece/*` do **not** extend it (grep confirms no `AtlasScout` reference) — the interface exists but isn't universally adopted, contradicting [docs/adding_a_scout.md](docs/adding_a_scout.md). |
| Inventory state-change detection | 4 | [scouts/pokemon/state_tracker.py](scouts/pokemon/state_tracker.py) — `PokemonStateTracker.observe()` detects `NEW_PRODUCT`/`RESTOCK`/`SOLD_OUT`/`PRICE_DROP`/`PRICE_INCREASE`/`NEW_CONFIRMATION`/`NO_CHANGE` by diffing JSON snapshots keyed on `canonical_product_key`. Tested: `test_pokemon_state_tracker.py`. Parallel cross-game version exists: `scouts/tcg/state_tracker.py` (654 lines, tested by `test_tcg_state_tracker.py`). |
| Product classification (sealed vs. accessory, tier) | — | [scouts/pokemon/classifier.py](scouts/pokemon/classifier.py) — `classify_pokemon_product` (10 product types, `SEALED_PRODUCT_TYPES` set, `PRODUCT_TIER` map), `calculate_release_urgency`. Tested: `test_pokemon_classifier.py`. |
| Demand / hype-velocity scoring | 6 | [popularity/pokemon.py](popularity/pokemon.py) (381 lines) — real scoring: source-confirmation bonuses, demand-term dictionaries, availability bonus, `freshness_signal` based on release-date recency (L301-350). Dispatched via [popularity/engine.py:20](popularity/engine.py#L20) only for `category=="pokemon"`; every other category gets a hardcoded placeholder ([popularity/engine.py:26-38](popularity/engine.py#L26-L38)). Tested: `test_popularity.py`, `test_popularity_reasoning.py`. |
| Sold-comps aggregation math, fees, payout, profit, ROI | 7 | [market/aggregator.py](market/aggregator.py) (real averaging/confidence logic), [market/roi.py](market/roi.py) (flat 13% eBay-style fee + $8 shipping → profit/ROI, L1-46). Brand-agnostic, wired through `reasoning/engine.py:103-131`. Tested: `test_market.py`, `test_market_roi.py`, `test_roi.py`, `test_roi_decision.py`. **Caveat:** the comps *data* feeding this math is largely stubbed — see Broken/Partial. |
| Explainable scoring / evidence / confidence / decision | 15 | [reasoning/engine.py:16-199](reasoning/engine.py#L16-L199) `reason()` composes signals → evidence → score → confidence → opportunity → urgency → market/ROI → decision → resale → explanation, in that order. [reasoning/confidence.py](reasoning/confidence.py), [reasoning/evidence.py](reasoning/evidence.py), [decision/decision_engine.py](decision/decision_engine.py) (`decide()`, cascading ROI/score thresholds), [brain/explanation_engine.py](brain/explanation_engine.py) (renders human-readable explanation). All brand-agnostic, all exercised by tests (`test_pattern_reasoning.py`, `test_popularity_reasoning.py`, `test_roi_decision.py`, plus 3 currently-failing — see Broken). |
| Signal engine (12 reusable signals) | — | [signals/__init__.py:39-52](signals/__init__.py#L39-L52) registers all 12 signals; [signals/engine.py](signals/engine.py) evaluates them uniformly. Tested: `test_signals.py`, `test_collector_value_signal.py`, `test_investment_strategy_signal.py`, `test_source_consensus_signal.py`. |
| Alert dedup + persistence | 14 (partial) | [scouts/pokemon/alert_store.py](scouts/pokemon/alert_store.py) — dedups by canonical key + event type, `mark_resolved()`. Tested: `test_pokemon_alert_store.py`, `test_pokemon_alert_deduplication.py`. Scoring: [alert_intelligence.py](scouts/pokemon/alert_intelligence.py). Ranking: [alert_queue.py](scouts/pokemon/alert_queue.py). Report: [alert_brief.py](scouts/pokemon/alert_brief.py). All individually tested. |
| Cross-brand normalized "opportunity" surface (partial) | final output | `scouts/tcg/catalog_store.py` (`TcgCatalogStore`, tested) already accepts Pokémon + Lorcana + One Piece items into one store; `scouts/tcg/money_board.py` ranks across all three. This is the closest thing that exists today to the "normalized Pokémon opportunity record reusable by other modules" the mission asks for — but it is a *TCG-only* board (three card games), not a brand-agnostic Atlas-wide schema, and it's fed by TCG-specific collectors only. |
| HTTP acquisition layer with basic pacing | 16 (partial) | [acquisition/](acquisition/) (added in the most recent commit, `c8b8c09`) — `RequestsRetriever.fetch()` ([requests_retriever.py](acquisition/requests_retriever.py), 30s timeout, spoofed browser headers), `AcquisitionService.collect()` ([service.py](acquisition/service.py), 1s pacing sleep between sources). Wired into `scouts/pokemon/internet_scout.py:5-9`. Tested: `test_acquisition_service.py` (180 lines). |

---

## 2. Partial (real logic exists but is incomplete, narrow, or only half-wired)

- **Release-calendar confidence tiers (layer 2 as literally specified).** The spec asks for confirmed/likely/rumored *confidence*. What exists is *urgency* windowing ([release_calendar.py](scouts/pokemon/release_calendar.py)), not a source-reliability confidence label. The closest real confidence concept is `consensus_level`/`consensus_confidence` in [consensus.py:247-279](scouts/pokemon/consensus.py#L247-L279) (VERY HIGH/HIGH/MEDIUM/LOW based on source count), but it isn't merged into the release calendar entries today — `release_calendar.py` doesn't read `consensus_score`.

- **Sold-comps data sources (layer 7).** The ROI *math* is complete, but real market data is thin:
  - `market/ebay.py:8-33` calls `market/ebay_live.py`, whose `fetch_ebay_sold_data()` **unconditionally returns `None`** — falls back to a constructed search-URL with `confidence="LINK_ONLY"`, i.e. no real sold-comp numbers.
  - `market/stockx.py`, `market/tcgplayer.py`, `market/pricecharting.py` each hardcode a `MarketResult` with every price field `None` and a note literally saying `"... integration not connected yet."` (e.g. [market/stockx.py:10-17](market/stockx.py#L10-L17)).
  - `market/normalizers/stockx.py`, `pricecharting.py`, `tcgplayer.py` are **0-byte empty files**.
  - Only `market/manual.py` (operator-supplied data) and the eBay link-fallback produce any usable signal today.

- **Drop-pattern history (layer 5).** [patterns/matcher.py](patterns/matcher.py) and [patterns/scorer.py](patterns/scorer.py) contain real matching/scoring logic, but the data they match against — [patterns/history.py:1](patterns/history.py#L1) `PATTERN_HISTORY = {}` — is an empty dict at runtime, populated only inside tests. In production this layer always returns no matches. Separately, [patterns/pokemon_patterns.py](patterns/pokemon_patterns.py) generates canned observation strings from `memory.pokemon_memory` (a different, unrelated mechanism, dynamically loaded by `reasoning/engine.py:356-373`) — real but shallow (4 keyword-count thresholds).

- **Learning (layer feeding future decisions).** [learning/statistics.py](learning/statistics.py) computes real per-category/brand aggregates (buy rate, profitable rate, average ROI) from [learning/storage.py](learning/storage.py)'s flat JSON file. But `LearningStatistics.summarize()` output is **not consumed anywhere** in `reasoning/engine.py` or `decision/decision_engine.py` — it's write-only telemetry, not a feedback loop.

- **Sealed-vs-open analysis (layer 9).** Sealed-product detection is real (`SEALED_PRODUCT_TYPES` in [classifier.py:91-97](scouts/pokemon/classifier.py#L91-L97), also referenced in `investment_intelligence.py`, `collector_intelligence.py`). But there is no "open"/raw-card counterpart — see Missing, layer 10.

- **Alert intelligence event scoring (layer 14).** Solid scoring exists ([alert_intelligence.py](scouts/pokemon/alert_intelligence.py)), and dedup exists, but grepping `alert_intelligence.py` and `alert_queue.py` for "escalat" or "wave" returns nothing — a second RESTOCK event for the same product produces a new alert, not an escalation of the first, and there is no concept of a "restock wave" (many products restocking together).

- **Acquisition layer resiliency (layer 16).** Real timeout + a flat pacing delay exist, but there is no retry/backoff (`acquisition/requests_retriever.py` catches `RequestException` and gives up, no retry loop), no rate-limit-aware throttling, and no secret handling to audit (the layer makes no authenticated calls). It's also only adopted by `scouts/pokemon/` — `scouts/one_piece/internet_scout.py` independently rolled its own `HTTPAdapter`/`Retry` retry logic instead of reusing this new layer, and `scouts/lorcana/`, `scouts/starbucks.py` use bare `requests` with no retry at all.

---

## 3. Missing (not found anywhere in the repo — confirmed by targeted grep, not assumed)

- **Individual card / illustrator / grading intelligence (layer 10).** [scouts/pokemon/product_details.py](scouts/pokemon/product_details.py) and [structured_data.py](scouts/pokemon/structured_data.py) model only sealed-product attributes (pack count, promo-card count, bundled accessories, box/ETB set name). No `card_number`, `rarity`, or `set_code` fields exist. Grepped repo-wide for `PSA`, `CGC`, `BGS`, `grading`, `grade`, `graded`, `illustrator`, `artist` — **zero matches** anywhere in `.py` files.
- **Image-identification integration points (layer 11).** Grepped for `cv2`, `ocr`, `identify_card`, `vision` — **zero matches**. All existing `image`/`img` references are just `<img>` tag scraping for thumbnail URLs.
- **Los Angeles local-store / drive-decision support (layer 12).** Grepped `los angeles`, `local_store`, `nearby`, `zip.?code`, `store_locator`, `\bdrive\b` — **zero matches** anywhere.
- **User sighting reports with reliability/time-decay (layer 13).** Grepped `sighting`, `reliability`, `decay`, `crowdsource`, `user_report` — **zero matches**. No user-submitted-data model exists at all.
- **Buy-quantity / capital-allocation recommendations (layer 8).** Grepped `quantity`, `budget`, `capital` across `decision/` and `reasoning/` — **zero matches**. `decision/decision_engine.py:decide()` returns a BUY/WATCH/SKIP action string only; there is no sizing/allocation output field anywhere in the `reason()` result dict.
- **Scout health / rate-limit telemetry / audit log (layer 16, the monitoring half).** No health-check endpoint, no per-scout success/failure metrics store, no structured audit log — only `print()` statements in `acquisition/service.py` and `requests_retriever.py`.
- **Central secrets/config module.** No single place loads `SUPABASE_URL`/`SUPABASE_SERVICE_KEY` — see Risky, below.

---

## 4. Broken

- **3 failing tests, all the same root cause:** `tests/test_market_roi.py::test_market_data_flows_into_roi_and_mission`, `tests/test_pattern_reasoning.py::test_pattern_match_flows_into_reasoning`, `tests/test_popularity_reasoning.py::test_popularity_flows_into_reasoning` all fail with `KeyError: 'SUPABASE_URL'`. Cause: `reasoning/engine.py:load_memory()` (L334-353) dynamically imports `memory.<category>_memory`, and [memory/pokemon_memory.py:4](memory/pokemon_memory.py#L4) does `os.environ["SUPABASE_URL"]` **at module import time**, outside any function, with no default and no try/except around the read itself. `load_memory()`'s try/except only catches `ImportError`/`AttributeError`, not the `KeyError` raised during import — so it propagates. Any test or script that reaches `reason()` without `SUPABASE_URL` set in the environment breaks, even though the test isn't exercising Supabase at all. This is a real bug, not environment misconfiguration — a scoring/reasoning call should not hard-require a database credential to run.
- **Orphaned nested workflow file.** [.github/workflows/.github/workflows/create-notifications.yml](.github/workflows/.github/workflows/create-notifications.yml) lives two directories too deep (inside a `.github` folder nested inside `.github/workflows/`). GitHub Actions only discovers workflows directly under the top-level `.github/workflows/`, so this file **never runs**. It is not a duplicate of `create-alerts.yml` (different script: `atlas/create_notifications.py` vs `atlas/alerts.py`, confirmed by diff) — it looks like a real, intended workflow that was miscommitted (`git log`: single commit `fef60f6`, 2026-07-06) and then never fixed. The underlying script (`atlas/create_notifications.py`) does still run as step 6 of `atlas-pipeline.yml`, so nothing is silently missing from the pipeline — but the standalone on-demand trigger for it doesn't exist.
- **`scouts/pokemon/rules.py` and `scouts/pokemon/scorer.py` are dead code.** Grepped the entire repo: the only references to either are the generic import-smoke-test in [tests/test_imports.py:73-74](tests/test_imports.py#L73-L74). Neither is imported by `collector.py`, `enrichment.py`, `classifier.py`, or `live_monitor.py`. `scorer.py`'s `score_pokemon_item()` duplicates what `collector_intelligence.py` + `investment_intelligence.py` now do in much more detail — it looks like an early-phase file that was superseded but never deleted.
- **`scouts/pokemon/collector.py` and `live_monitor.py` have no dedicated unit test file**, unlike every other file of comparable size in the module (see table below). `test_pokemon_pipeline_offline.py` (added most recently, `e92d44c`) exercises *some* end-to-end path offline, but there is no `test_pokemon_collector.py` isolating `PokemonScout`'s own logic (duplicate counting, catalog upsert wiring, brief generation).

---

## 5. Obsolete or duplicated

- **Two independent "score this item" systems that never talk to each other:** `atlas/scorer.py` (hardcoded keyword dict, L7-17, L41-74) vs. `brain/atlas_brain.py` → `reasoning/engine.py` (the sophisticated evidence/signal engine). Both write to the same Supabase `opportunities` table shape (compare [atlas/research_engine.py](atlas/research_engine.py) `create_opportunity` payload fields vs. [scouts/base/atlas_scout.py:89-103](scouts/base/atlas_scout.py#L89-L103) payload fields — they're not even identical field sets, e.g. `atlas/research_engine.py` writes `hype_score`/`worth_trip`/`resale_signal`, `atlas_scout.py` writes `confidence_score`/`recommended_action`/`market_signal_status`). Running both against the same table risks incompatible/duplicate rows with different schemas-of-convenience for the same conceptual record.
- **`format_price()` / `display_value()` duplicated** between [scouts/pokemon/collector.py:609-645](scouts/pokemon/collector.py#L609-L645) and [scouts/pokemon/live_monitor.py:957-987](scouts/pokemon/live_monitor.py#L957-L987) — identical formatting helpers, copy-pasted rather than shared.
- **`merge_items`/`deduplicate_items` logic duplicated three times** with slightly different semantics: `scouts/pokemon/internet_scout.py:306-387`, `scouts/pokemon/live_monitor.py:537-621`, and effectively re-derived again via `consensus.py`'s grouping. Three different "what counts as the same product" implementations in one module is a real duplicate-title-resolution risk (layer 1's whole purpose), since they can disagree.
- **`collector.py` and `live_monitor.py` are two parallel top-level pipelines** doing collect → enrich → persist → summarize, targeting different storage (`alert_store`/`release_store`/`catalog_store` vs. a standalone `pokemon_live_scan.json` + history directory). It's unclear which one is meant to be canonical going forward; today neither is scheduled (see Section 0).
- **Two POC scraping scripts** ([poc_playwright_fetch.py](scouts/pokemon/poc_playwright_fetch.py), [poc_safari_webdriver_fetch.py](scouts/pokemon/poc_safari_webdriver_fetch.py)) reimplement the same `classify_page`/`find_candidate_products`/`extract_product` logic for two different browser drivers. Both explicitly document themselves as standalone feasibility probes, not pipeline code (confirmed: nothing imports them, they write nothing to `.atlas_data` or Supabase) — not currently harmful, but worth a decision on whether either graduates into `acquisition/` or both get deleted once the bot-detection question is answered.
- **`scouts/tcg/state_tracker.py` and `scouts/tcg/alert_store.py`/`alert_intelligence.py` duplicate the shape of `scouts/pokemon/state_tracker.py` and `scouts/pokemon/alert_store.py`/`alert_intelligence.py`** at the cross-game level. This may be intentional layering (brand-specific + cross-brand), but it means a behavior change (e.g. a new event type) has to be made in two places today, and nothing enforces they stay in sync.
- **`README.md` and `signals/__init__.py` formatting bugs already self-corrected** in commit `7986324` (tripled README content deduped, trailing newline fixed) — mentioned only for completeness; no outstanding action.

---

## 6. Risky

- **No central secrets/config module.** `SUPABASE_URL`/`SUPABASE_SERVICE_KEY` are read via `os.environ[...]` independently in **at least 13 files** (`memory/pokemon_memory.py`, `memory/nike_memory.py`, `scouts/universal.py`, `scouts/starbucks.py`, `scouts/base/atlas_scout.py`, and 8 files under `atlas/`). Every one of them does a hard, exception-raising dict-index lookup at import or instantiation time with no shared validation, no `.env` loader, and no single point to rotate/audit credential usage.
- **Supabase anon key committed in plaintext to `dashboard/index.html`** ([dashboard/index.html:127-128](dashboard/index.html#L127-L128)). This is a *publishable* (`sb_publishable_...`) key, which is designed to be public and safe under Row Level Security — it is not the service-role key. Still worth confirming RLS is actually enabled on the `opportunities`/`raw_drops` tables before treating this as fine, since a client-side anon key with no RLS is effectively an open read/write API.
- **Two schedulers can write to the same Supabase tables concurrently** (Section 5) with different payload shapes — if `PokemonScout` were scheduled today without reconciling with `atlas/research_engine.py`'s `create_opportunity`, you'd get inconsistent rows for what should be one canonical "opportunity" schema.
- **`patterns/history.py`'s empty `PATTERN_HISTORY = {}`** means the "drop-pattern history" layer silently degrades to a no-op in production with no warning surfaced to the operator — it will never error, it will just never contribute evidence. Worth an explicit "no pattern data available" signal if this is intentional for now.
- **No automated schedule currently exercises the well-tested Pokémon-specific code at all** (Section 0) — meaning the 99 passing unit tests give real confidence in the *logic*, but zero confidence that the *system* is producing opportunities day-to-day, since it isn't running unattended.

---

## Appendix: Pokémon-module file → test-file correlation

| File | Test file | Notes |
|---|---|---|
| identity.py | test_pokemon_identity.py | ✅ |
| consensus.py | test_pokemon_consensus.py | ✅ |
| classifier.py | test_pokemon_classifier.py | ✅ |
| state_tracker.py | test_pokemon_state_tracker.py | ✅ |
| release_calendar.py | test_pokemon_release_calendar.py | ✅ |
| release_store.py | test_pokemon_release_store.py | ✅ |
| release_brief.py | test_pokemon_release_brief.py | ✅ |
| product_details.py | test_pokemon_product_details.py | ✅ |
| structured_data.py | test_pokemon_structured_data.py | ✅ |
| investment_intelligence.py | test_pokemon_investment_intelligence.py | ✅ |
| alert_store.py | test_pokemon_alert_store.py, test_pokemon_alert_deduplication.py | ✅ |
| alert_intelligence.py | test_pokemon_alert_intelligence.py | ✅ |
| alert_queue.py | test_pokemon_alert_queue.py | ✅ (small test, small file) |
| alert_brief.py | test_pokemon_alert_brief.py | ✅ (small test, small file) |
| internet_scout.py | test_pokemon_internet_scout.py | ✅ |
| live_monitor.py | test_pokemon_live_monitor.py | ✅ |
| **collector.py** | none dedicated | ⚠️ only covered indirectly via test_pokemon_pipeline_offline.py |
| **collector_intelligence.py** | none | ⚠️ |
| **enrichment.py** | none | ⚠️ covered indirectly through other tests |
| rules.py | test_imports.py only | dead code (Section 4) |
| scorer.py | test_imports.py only | dead code (Section 4) |
| parser.py | none | thin (8 lines), low risk |
| sources.py | none | static config, low risk |
| poc_playwright_fetch.py | none (by design) | standalone probe |
| poc_safari_webdriver_fetch.py | none (by design) | standalone probe |
