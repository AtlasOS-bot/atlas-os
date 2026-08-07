# Pokémon Pipeline Decision

Date: 2026-07-18
Status: Phase 1 investigation — **no files were modified, staged, or committed to produce this document.**

Method: every claim cites an exact file path, function name, and line range read directly from the repository in this session. Where a claim is about "what runs automatically," it is backed by the literal contents of `.github/workflows/*.yml`, not inference. Where a claim is about "what writes where," it is backed by grepping for every caller of the relevant function, not by filename assumption.

---

## 1. Current execution map

```
GITHUB ACTIONS (scheduled, real automation today)
──────────────────────────────────────────────────
atlas-pipeline.yml (cron */30min)
  1. scouts/universal.py            → Supabase raw_drops
  2. atlas/scorer.py                → Supabase opportunities   (keyword scoring)
  3. atlas/research_engine.py       → Supabase opportunities   (patches retailer/category)
  4. atlas/ebay_research.py         → Supabase opportunities   (adds eBay link)
  5. atlas/market_signals.py        → Supabase opportunities   (not read this session; out of scope)
  6. atlas/create_notifications.py  → Supabase notifications
  7. atlas/alerts.py                → Discord webhook

create-alerts.yml        (cron */20min) → atlas/alerts.py               (redundant with step 7 above)
score-opportunities.yml  (cron */20min) → atlas/scorer.py               (redundant with step 2 above)
ebay-research.yml        (cron */30min) → atlas/ebay_research.py        (redundant with step 4 above)
starbucks-scout.yml      (cron */15min) → scouts/universal.py           (redundant with step 1 above — see §11)
morning-brief.yml        (cron daily 15:00 UTC) → atlas/morning_brief.py → Discord webhook
pattern-lab.yml          (cron every 6h) → atlas/pattern_lab.py
market-signals.yml       (manual only) → atlas/market_signals.py
research-engine.yml      (manual only) → atlas/research_engine.py
roi-tracker.yml          (manual only) → atlas/roi_tracker.py
.github/workflows/.github/workflows/create-notifications.yml → never runs (wrong path, confirmed §11)

NOT SCHEDULED ANYWHERE (verified: zero references in any .yml or any atlas/*.py)
──────────────────────────────────────────────────────────────────────────────
scouts/pokemon/collector.py       (PokemonScout)        — run manually only
scouts/pokemon/live_monitor.py    (PokemonLiveMonitor)  — run manually only
scouts/tcg/alert_runner.py, money_board_runner.py, daily_brief_runner.py — run manually only
```

Evidence: `grep -rln "PokemonScout\|scouts.pokemon.collector\|scouts.pokemon.live_monitor\|scouts.tcg" .github/workflows/*.yml atlas/*.py` returns **zero matches**. Confirmed by reading all 10 workflow files in full (§11) and all `atlas/*.py` entry points named in the pipeline.

---

## 2. `scouts/pokemon/collector.py` — data flow

```
PokemonScout.__init__()                                    [collector.py:39-56]
  ├─ super().__init__()  → AtlasScout.__init__              [atlas_scout.py:13-16]
  │    reads SUPABASE_URL / SUPABASE_SERVICE_KEY (hard crash if unset, unrelated to Phase 0 fix)
  │    instantiates LearningEngine()
  ├─ self.state_tracker  = PokemonStateTracker()
  ├─ self.alert_store    = PokemonAlertStore()
  ├─ self.release_store  = PokemonReleaseStore()
  └─ self.catalog_store  = TcgCatalogStore()

PokemonScout.run()                                          [collector.py:68-606]
  1. items = self.collect()                                 [collector.py:58-66]
       collect_official_pokemon_items()  → raw scrape+consensus   [internet_scout.py]
       enrich_pokemon_item(item) for each                          [enrichment.py]
       ── NO try/except anywhere in collect() or run() ──
  2. release_calendar = self.release_store.save(items)      [collector.py:80-84]
       → writes .atlas_data/pokemon_release_calendar.json
  3. for item in items[:50]:                                [collector.py:91]  ← hard cap, first 50 only
       a. state_change = self.state_tracker.observe(item)   [collector.py:92-96]
            → reads/writes .atlas_data/pokemon_product_states.json
       b. alert = calculate_alert_intelligence(item)         [collector.py:110-114]
       c. self.alert_store.save(item, alert)                 [collector.py:120-125]
            → writes .atlas_data/pokemon_alerts.json (skipped if alert_exists() dedup hit)
       d. ~40 print() statements (console report)
       e. saved = self.save_opportunity(item)                [collector.py:419-423]
            → AtlasScout.save_opportunity()                   [atlas_scout.py:76-132]
               ├─ opportunity_exists() GET Supabase opportunities (dedup by official_url, else brand+item_name)
               ├─ AtlasBrain.analyze(item, category="pokemon") → full reasoning/engine.py pipeline
               ├─ POST Supabase opportunities  (payload in §6)
               └─ self.learning_engine.record(item, analysis)  → .atlas_data/learning_history.json
  4. catalog_result = self.catalog_store.upsert_many(items)  [collector.py:431-435]
       → writes .atlas_data/tcg_live_catalog.json  (ALL items, not just first 50)
  5. active_alerts = self.alert_store.active()
     top_pokemon    = self.catalog_store.top(limit=10, category="pokemon")
  6. print console summary + PokemonAlertBrief.generate() + PokemonReleaseBrief.generate()
  7. return items
```

Failure behavior: **none.** No `try`/`except` exists anywhere in `collector.py`. An exception raised while enriching item #30 of 200 aborts the entire run — no partial state is saved beyond whatever `state_tracker`/`alert_store` had already flushed to disk for items 1–29, and `catalog_store.upsert_many(items)` (step 4) never executes at all since it runs after the loop.

---

## 3. `scouts/pokemon/live_monitor.py` — data flow

```
PokemonLiveMonitor.__init__(scan_path=None, history_directory=None,
                              collector=None, enricher=None)         [live_monitor.py:32-59]
  → collector/enricher are dependency-injectable, default to
     collect_official_pokemon_items / enrich_pokemon_item
  → NO AtlasScout, NO Supabase credentials required to construct

PokemonLiveMonitor.scan()                                            [live_monitor.py:61-190]
  1. try: raw_items = self.collector()                                [live_monitor.py:75-93]
       except Exception → raw_items = [], log to scan_errors[], CONTINUE (does not raise)
  2. for raw_item in raw_items:                                       [live_monitor.py:97-137]
       try: enriched = self.enricher(raw_item); normalize_live_item(enriched)
       except Exception → log to scan_errors[], SKIP this item, CONTINUE
  3. unique_items = deduplicate_live_items(enriched_items)             [live_monitor.py:139-143]
  4. snapshot = { scan_id, started_at, completed_at, status: SUCCESS|PARTIAL|FAILED,
                  raw_item_count, product_count, error_count, errors[], summary, items[] }
  5. self.save(snapshot)                                               [live_monitor.py:192-228]
       → atomic write .atlas_data/pokemon_live_scan.json (current)
       → atomic write .atlas_data/pokemon_live_history/<scan_id>.json (history)
  6. self.print_summary(...)                                           console report only
  7. return snapshot
```

Failure behavior: **every stage is fault-isolated.** A total scrape failure produces `status: "FAILED"` with an empty item list and a populated `errors[]` array, not a crash. A single bad item produces `status: "PARTIAL"` and the other items still save. This is verified directly by `tests/test_pokemon_live_monitor.py`, which injects a fake collector/enricher and asserts on `snapshot["status"]`.

**What `live_monitor.py` does NOT touch:** `PokemonStateTracker`, `PokemonAlertStore`, `PokemonReleaseStore`, `TcgCatalogStore`, `AtlasScout`/`save_opportunity`, Supabase, `AtlasBrain`/`reasoning.engine.reason`, `LearningEngine`. Confirmed by reading the full 1097-line file — none of these names appear.

---

## 4. `scouts/universal.py` — data flow (legacy, scheduled)

```
main()                                                                [universal.py:186-213]
  for brand in config/brands.json:  (Disney, Pokémon, LEGO, Funko, Mattel)
    find_latest_article(source_url, keyword)                          [universal.py:141-183]
      GET source_url with bare requests.get() — NO retry, NO acquisition/ layer
      BeautifulSoup <a> tag scan, keyword substring match, one candidate returned
    save_to_supabase(brand, title, url, raw_text, published_at)       [universal.py:96-121]
      is_recent() (≤30 days) or is_drop_like() (keyword match) gate
      drop_already_exists(url) dedup check
      POST Supabase raw_drops
```

No identity resolution, no consensus, no state tracking, no classification, no scoring — it hands off unscored `raw_drops` rows to `atlas/scorer.py` downstream. This is the entire "intelligence" of the scheduled Pokémon-adjacent path: a keyword match plus a recency window.

---

## 5. Are they duplicates, complementary layers, or competing entry points?

**Both, in different respects — not a single clean answer:**

- **Duplicated implementation, not duplicated purpose.** Both files independently call `collect_official_pokemon_items()` + `enrich_pokemon_item()` (`collector.py:59-65`, `live_monitor.py:76,99`), both reimplement `format_price()` (`collector.py:609-637`, `live_monitor.py:957-987` — byte-for-byte identical logic), and both reimplement item-merging/dedup (`collector.py` relies on `internet_scout.py:merge_items/deduplicate_items` at L306-387; `live_monitor.py:merge_items/deduplicate_live_items` at L537-621 is a separate, differently-keyed implementation).
- **Complementary in capability.** `collector.py` owns everything stateful and externally visible (state-change detection, alerting, release calendar, TCG catalog, Supabase writes, learning records). `live_monitor.py` owns something `collector.py` does not have at all: a fault-tolerant, fully dependency-injected, atomically-persisted snapshot mechanism.
- **Competing entry points.** Both have `if __name__ == "__main__"` (`collector.py:652`, `live_monitor.py:1097`) and both are described in commit history as run manually by hand — nothing in the repo designates one as "the" way to run a Pokémon scan. A new contributor has no signal for which to invoke.

---

## 6. Which exercises more of the advanced Pokémon intelligence?

**`collector.py`, decisively.** Side-by-side:

| Capability | collector.py | live_monitor.py |
|---|---|---|
| Collection + consensus | ✅ `collect()` | ✅ `self.collector()` |
| Enrichment (classifier, product_details, popularity, collector/investment intelligence) | ✅ `enrich_pokemon_item` | ✅ `self.enricher()` (same function) |
| State-change detection (`NEW_PRODUCT`/`RESTOCK`/`SOLD_OUT`/...) | ✅ `state_tracker.observe()` | ❌ not called |
| Alert scoring | ✅ `calculate_alert_intelligence()` | ❌ not called |
| Alert persistence + dedup | ✅ `alert_store.save()` | ❌ not called |
| Release calendar | ✅ `release_store.save()` | ❌ not called |
| Cross-game TCG catalog | ✅ `catalog_store.upsert_many()` | ❌ not called |
| Reasoning/decision engine (signals, market, ROI, BUY/WATCH/SKIP) | ✅ via `save_opportunity → AtlasBrain.analyze` | ❌ not called |
| Learning record | ✅ `learning_engine.record()` | ❌ not called |
| Supabase `opportunities` write | ✅ | ❌ |
| Fault isolation per stage | ❌ none | ✅ try/except at both stages |
| Dependency-injectable for testing | ❌ (no constructor params) | ✅ `collector=`, `enricher=` |
| Partial-success status reporting | ❌ | ✅ `SUCCESS`/`PARTIAL`/`FAILED` |

---

## 7. Which has better tests and safer failure behavior?

**Split result — this is the central tension driving the recommendation.**

- **Feature coverage in tests:** `collector.py`'s *sub-modules* are extensively tested (`identity.py`, `consensus.py`, `classifier.py`, `state_tracker.py`, `alert_intelligence.py`, `alert_store.py`, `release_calendar.py`, etc. — 16 of 18 Pokémon test files target pieces `collector.py` orchestrates). But **`PokemonScout.collect()` and `PokemonScout.run()` themselves have no dedicated test file** — `tests/test_pokemon_pipeline_offline.py` calls the same underlying functions (`state_tracker.observe`, `calculate_alert_intelligence`, `alert_store.save`) directly, bypassing `PokemonScout` entirely (confirmed by reading the full file — it never imports `scouts.pokemon.collector`).
- **Entry-point-level testing:** `live_monitor.py`'s actual public entry point, `scan()`, **is** directly tested end-to-end in `tests/test_pokemon_live_monitor.py` via injected fakes, asserting on `status`, `product_count`, and `summary` fields of the real return value.
- **Failure behavior:** as detailed in §2–3, `collector.py.run()` has zero exception handling anywhere; `live_monitor.py.scan()` isolates failures at both the collection and per-item enrichment stages and reports a graduated status instead of crashing.

**Conclusion: `live_monitor.py` is safer and better-tested at the entry-point level; `collector.py` is more thoroughly tested at the component level but its orchestration layer (`run()`) is the least-tested, least-safe code path in the entire Pokémon module.**

---

## 8. Which writes to Supabase / opportunities / notifications?

- **`collector.py`:** writes Supabase `opportunities` via `AtlasScout.save_opportunity()` (`atlas_scout.py:76-132`), called once per item (capped at first 50) inside `run()` (`collector.py:419-423`). Nothing in the Pokémon module writes to `notifications` directly — that table is only ever written by `atlas/create_notifications.py` (`create_notifications.py:60-79`), which reads **all** rows in `opportunities` with no brand filter (`create_notifications.py:17-27`) and is brand-agnostic. Confirmed: `grep -rln "/notifications" --include="*.py" .` returns only `atlas/create_notifications.py` and `atlas/alerts.py`.
- **`live_monitor.py`:** writes nothing to Supabase. Confirmed: no `requests`, `SUPABASE_URL`, or `AtlasScout` reference anywhere in the file.
- **Consequence (important, previously undocumented):** because `atlas/create_notifications.py` reads the *entire* `opportunities` table with no source filter, any row `collector.py` writes via `save_opportunity()` **will** be picked up by the existing scheduled `atlas-pipeline.yml` step 6/7 and **will** reach Discord via `atlas/alerts.py` — *if* `collector.py` is ever run (manually or scheduled) with real credentials. The two systems already share a write surface even though nothing currently schedules `collector.py`.

---

## 9. Exact payload/schema each pipeline produces

**`collector.py` → Supabase `opportunities` (via `AtlasScout.save_opportunity`, `atlas_scout.py:89-103`):**
```json
{
  "brand": "Pokemon",
  "item_name": "<item['title']>",
  "official_url": "<item['url']>",
  "confidence_score": "<reasoning.engine.reason()['score']>",
  "recommended_action": "<reasoning.engine.reason()['decision']>",
  "atlas_reason": "<reasoning.engine.reason()['explanation']>",
  "market_signal_status": "watch"
}
```
Missing fields relative to what `atlas/research_engine.py` later patches: `retailer`, `release_status`, `category`, `exclusive`, `research_complete` (left at DB default — see risk in §12). Missing relative to `atlas/scorer.py`'s legacy payload (`atlas/scorer.py:76-99`): `hype_score`, `worth_trip`, `resale_signal`, `alert_level`, `raw_drop_id`.

**`collector.py` → local JSON stores (never reaches Supabase):**
- `.atlas_data/pokemon_alerts.json` — schema at `alert_store.py:56-109`: `alert_id, product_key, event, priority, score, action, reason, best_strategy, flip_score, hold_score, sleeper_score, collector_score, popularity_score, consensus_score, release_urgency, reasons[], status`.
- `.atlas_data/pokemon_release_calendar.json` — schema from `build_release_entry()` (`release_calendar.py:97-142`): `title, url, product_type, release_date, days_until_release, action_window, urgency_score, reason, recommended_action, collector_score, flip_score, hold_score, popularity_score, availability`.
- `.atlas_data/tcg_live_catalog.json` — schema owned by `scouts/tcg/catalog_store.py` (not read in full this session; out of scope).

**`live_monitor.py` → `.atlas_data/pokemon_live_scan.json` + `pokemon_live_history/*.json`:**
```json
{
  "scan_id": "...", "started_at": "...", "completed_at": "...",
  "source": "pokemon_official",
  "status": "SUCCESS|PARTIAL|FAILED",
  "raw_item_count": 0, "product_count": 0, "error_count": 0,
  "errors": [{"stage": "collection|enrichment", "error_type": "...", "message": "...", "title": "..."}],
  "summary": {"in_stock_count": 0, "out_of_stock_count": 0, "preorder_count": 0,
              "unknown_availability_count": 0, "known_price_count": 0,
              "exclusive_count": 0, "product_types": {}},
  "items": [ {"...normalized item via normalize_live_item()..."} ]
}
```
This schema shares no fields 1:1 with the Supabase `opportunities` table — it is a self-contained snapshot format, not designed to feed the same downstream consumers.

---

## 10. Which downstream modules consume each payload?

**`collector.py` output consumers (verified via grep of each store/table name):**
- Supabase `opportunities` → `dashboard/index.html:142` (read-only, anon key), `atlas/research_engine.py:opportunities()` (patches rows), `atlas/create_notifications.py:opportunities()` (all rows, brand-agnostic), `atlas/alerts.py` (via `notifications` join) → Discord.
- `.atlas_data/tcg_live_catalog.json` (via `TcgCatalogStore`) → also written/read by `scouts/tcg/alert_runner.py`, `money_board_store.py`, `daily_brief_runner.py`, `state_tracker.py`, and the sibling `scouts/one_piece/collector.py` / `scouts/lorcana/collector.py` (shared cross-game catalog). None of these TCG runners are scheduled either (§1), but the data structurally feeds a real cross-brand layer.
- `.atlas_data/pokemon_alerts.json`, `pokemon_release_calendar.json` → read only by their own store classes (`alert_store.active()`, `release_store.load()`) and their own tests. No other module consumes them.

**`live_monitor.py` output consumers:** `grep -rln "pokemon_live_scan\|pokemon_live_history"` returns **only `live_monitor.py` itself and its test file.** Nothing else in the repository reads `pokemon_live_scan.json` or the history directory. It is a complete dead end today — valuable for a human operator watching scan health, consumed by no other code.

---

## 11. What does `scouts/universal.py` do that the advanced pipeline does not?

Read all 10 workflow files in full this session (contents reproduced in §1). Findings:

1. **It is actually scheduled and running today** (`atlas-pipeline.yml` cron `*/30 * * * *`, plus a second redundant trigger via `starbucks-scout.yml` — misleadingly named "Atlas Universal Scout" internally, cron `*/15 * * * *` — both run the identical `python scouts/universal.py`, meaning it currently runs on overlapping 15/30-minute schedules from two separate workflows).
2. **It covers 5 brands** (Disney, Pokémon, LEGO, Funko, Mattel) from a single generic script driven by `config/brands.json`, vs. the Pokémon module which only covers Pokémon.
3. **It has a complete, working, if crude, path all the way to a human** (raw_drops → opportunities → notifications → Discord), because every step downstream of it (`atlas/scorer.py` through `atlas/alerts.py`) is also scheduled. The sophisticated pipeline has no such complete scheduled path.
4. **Nested orphaned workflow, re-confirmed:** `.github/workflows/.github/workflows/create-notifications.yml` (content read this session, `name: Create Notifications`, runs `atlas/create_notifications.py`) sits two directories too deep and is not discovered by GitHub Actions. Not a functional gap in practice, since `atlas-pipeline.yml` step 6 already runs the same script — but it is dead YAML that should eventually be removed or relocated, unrelated to the collector/live_monitor decision.

---

## 12. What would be lost if `universal.py` were immediately replaced?

- **Immediate loss of all non-Pokémon brand coverage** (Disney, LEGO, Funko, Mattel) — nothing in `scouts/pokemon/` or `scouts/tcg/` covers any other brand; those would go dark with no replacement scout running.
- **Loss of the only currently-working end-to-end path to a human.** Even though it's crude, `universal.py → scorer.py → ... → alerts.py` is the only chain that is *provably* running unattended today. Replacing it with the unscheduled `collector.py` without first scheduling something is a regression from "runs every 15–30 min, imperfectly" to "runs never, perfectly."
- **Loss of the `raw_drops` staging table's role** as a durable, re-processable queue — `collector.py` has no equivalent staging concept; it goes straight from scrape to a finished `opportunities` row in one pass, so a downstream scoring change can't be re-applied to already-collected-but-unscored items the way `atlas/scorer.py` can re-run against `raw_drops` where `already_scored=false`.

This audit does **not** recommend replacing `universal.py` in this phase — see §14.

---

## 13. Duplicate writes, notification risk, schema mismatch, double-alert paths

- **Double alert risk if `collector.py` were scheduled today without changes:** `AtlasScout.opportunity_exists()` (`atlas_scout.py:28-74`) dedups by `official_url`, then by `brand`+`item_name`. A **RESTOCK** event on a product Atlas has seen before (same URL/title) would be correctly detected by `state_tracker.observe()` and scored by `calculate_alert_intelligence()` and saved to `pokemon_alerts.json` — but `save_opportunity()` would see the URL already exists in `opportunities` and **skip creating a new row entirely** (`atlas_scout.py:77-82`, prints `"Duplicate skipped"` and returns `False`). Since Discord notifications are only ever generated from new `opportunities` rows (`atlas/create_notifications.py` creates one notification per opportunity id, `notification_exists()` dedups by `opportunity_id` not by event), **a restock alert that Atlas's own alert-intelligence layer correctly flags as `VERY HIGH` importance would never reach Discord.** This is a real, evidence-backed gap in layer 14 (alert escalation) already flagged qualitatively in `CURRENT_STATE_AUDIT.md` §2 — this session found the exact mechanism.
- **Schema mismatch between the two `opportunities` writers**, confirmed by comparing payloads directly: `atlas/research_engine.py:create_opportunity` (via `atlas/scorer.py`, `atlas/scorer.py:76-99`) writes `hype_score`, `worth_trip`, `resale_signal`, `alert_level`, `raw_drop_id` — none of which `AtlasScout.save_opportunity()` ever sets. `dashboard/index.html` only reads fields both writers happen to share (`brand`, `item_name`, `confidence_score`, `market_signal_status`, `recommended_action`, `ebay_sold_comps_url`, `official_url`) so the dashboard degrades gracefully (blank cells), but any future dashboard feature built against `hype_score` or `alert_level` would silently show nothing for Pokémon-collector-sourced rows.
- **`research_complete` filter risk (unverified without DB access):** `atlas/research_engine.py:opportunities()` filters `research_complete: eq.false` (`research_engine.py:17-25`). `AtlasScout.save_opportunity()` never sets this field. If the Supabase column default is `NULL` rather than `false`, Postgres's `eq.false` will **not** match those rows (`NULL != false` in SQL three-valued logic), meaning `collector.py`-sourced opportunities would silently never receive the `research_engine.py` enrichment pass. Flagged as a risk to verify against the actual schema before scheduling `collector.py`, not asserted as fact.
- **Redundant scheduled triggers**, re-confirmed by reading every workflow file: `atlas/alerts.py` is scheduled by both `atlas-pipeline.yml` (step 7, every 30 min) and `create-alerts.yml` (every 20 min) independently — two separate GitHub Actions runners could invoke `atlas/alerts.py` within minutes of each other. `notification_exists`-style dedup isn't present in `alerts.py` (it dedups by *sending*, marking `sent: true` after Discord POST succeeds, `alerts.py:95-103`), so a race between two concurrent runs reading the same unsent notification before either marks it sent could send the same Discord message twice. Similarly `atlas/scorer.py` is triggered by both `atlas-pipeline.yml` (step 2) and `score-opportunities.yml` independently. This is a pre-existing risk in the legacy pipeline, not something the Pokémon module introduces — noted because it affects the shared `opportunities`/`notifications` tables both systems write to.

---

## 14. Recommended architecture: **A — `collector.py` is canonical, `live_monitor.py` becomes a supporting service**

Not C, because leaving both as permanently co-equal, separately-invoked pipelines (as they are today) is the exact duplication `CURRENT_STATE_AUDIT.md` already flagged as a risk — two things that both call `collect_official_pokemon_items()`+`enrich_pokemon_item()` and both have a `__main__` block invite a new contributor to pick the wrong one, or run both and get inconsistent state.

Not B, because `live_monitor.py` structurally cannot become canonical without absorbing state tracking, alerting, release calendar, catalog writes, and Supabase/reasoning integration — at which point it *is* `collector.py` with a different name, and none of that logic currently lives in `live_monitor.py` or would transfer for free.

Not D, because a coordinator that calls both without duplicating their logic doesn't resolve the actual problem: `collector.py.run()` needs the fault-isolation and testability `live_monitor.py.scan()` already has. A third file wrapping two unfixed files just adds an extra hop; it doesn't make `collector.py` safe to schedule.

**A is correct because the mission's 16-layer reference architecture needs exactly the capability set that only `collector.py` has** (state, alerting, release calendar, catalog, Supabase, reasoning/decision) — that is the module actually being built toward. `live_monitor.py`'s real, proven value — dependency-injectable fault isolation, partial-success snapshotting — should be **absorbed into `collector.py`'s failure behavior**, not kept as a second, mostly-unconsumed pipeline. Concretely: `live_monitor.py` continues to exist as the lightweight "is the scrape healthy right now" diagnostic tool (its snapshot output has genuine value for a health-check use case, layer 16), while `collector.py` gets the safety properties it currently lacks.

---

## 15. Smallest safe implementation commit after approval

**Scope: make `PokemonScout` fault-tolerant and independently testable, using `PokemonLiveMonitor` as the reference pattern. No behavior change to what gets saved on the happy path. No workflow, schema, or Supabase changes. `live_monitor.py` is not modified or removed.**

1. Add optional `collector=` and `enricher=` constructor parameters to `PokemonScout.__init__` (mirroring `live_monitor.py:32-59`), defaulting to the current `collect_official_pokemon_items` / `enrich_pokemon_item`, so the class becomes testable without network access or real Supabase credentials — the same pattern already proven in `live_monitor.py`.
2. Wrap the collection call in `collect()` in a `try/except`, matching `live_monitor.py:75-93`'s pattern: on failure, return `[]` and record the error instead of letting the exception propagate out of `run()`.
3. Wrap the per-item body of the `for item in items[:50]:` loop in `run()` in a `try/except`: on failure for a single item, log it and `continue` to the next item instead of aborting the whole run (matching `live_monitor.py:97-137`'s per-item isolation).
4. Do **not** touch `save_opportunity()`, the Supabase payload shape, `alert_store`, `release_store`, or `catalog_store` internals — this commit is failure-handling only.

This is intentionally the smallest slice: it does not schedule `collector.py`, does not merge it with `live_monitor.py`, does not fix the restock/double-alert gap in §13, and does not touch the `research_complete` schema question — each of those is a separate follow-up decision once this safety foundation is in place.

## 16. Exact tests required for that implementation

New file `tests/test_pokemon_collector.py`, following the fake-injection style already used in `tests/test_pokemon_live_monitor.py`:

1. `test_collector_scout_accepts_injectable_collector_and_enricher` — construct `PokemonScout` with fake `collector=`/`enricher=` callables (no real network, no real Supabase env vars needed for construction) and assert `collect()` returns the enriched fakes.
2. `test_run_continues_when_single_item_enrichment_fails` — inject an enricher that raises for one specific item and returns normally for others; assert `run()` completes, the failing item is excluded/logged, and the remaining items still reach `alert_store`/`release_store`/`catalog_store`.
3. `test_run_reports_collection_failure_without_crashing` — inject a `collector=` that raises; assert `run()` does not propagate the exception and returns an empty/well-defined result instead of crashing the process.
4. `test_run_still_persists_partial_results_when_later_stage_fails` — verify that a failure isolated to one item does not prevent `catalog_store.upsert_many()` (currently only reached if the entire loop completes without exception) from running on the successfully-processed subset.
5. Regression guard: run the existing `tests/test_pokemon_pipeline_offline.py` unchanged — it exercises `state_tracker`/`alert_intelligence`/`alert_store` directly and must continue passing untouched, confirming this commit doesn't alter the underlying scoring/state logic, only `PokemonScout`'s orchestration.

All five should use `tmp_path`-scoped stores (`PokemonStateTracker(path=...)`, `PokemonAlertStore(path=...)`, `PokemonReleaseStore(path=...)`) exactly as `tests/test_pokemon_pipeline_offline.py` already does, and should not require `SUPABASE_URL`/`SUPABASE_SERVICE_KEY` to be set except where a test specifically targets the `save_opportunity` path (which can itself be avoided by injecting a fake `save_opportunity` or by scoping these tests to `collect()`/pre-Supabase behavior only — final call left to implementation, but no test in this set should require real network or real Supabase credentials to pass).

---

## Summary (≤10 lines)

`collector.py` and `live_monitor.py` are not true duplicates: `collector.py` owns all the stateful intelligence (state tracking, alerting, release calendar, catalog, Supabase, reasoning/decision) that the mission's reference architecture needs, while `live_monitor.py` is a smaller, fault-tolerant, well-tested scan/snapshot utility that nothing else consumes. Neither runs automatically today — the only scheduled Pokémon-adjacent path is the cruder `scouts/universal.py → atlas/*.py` chain, which should not be replaced yet since it's the only thing provably running unattended and covers 4 other brands. The single sharpest risk found this session: because `save_opportunity()` dedups by URL/title, a correctly-detected RESTOCK alert never produces a new Discord notification — layer 14 is silently incomplete. Recommended architecture: **A** — `collector.py` becomes canonical, `live_monitor.py` stays as a supporting diagnostic service, and `collector.py` first needs `live_monitor.py`'s fault-isolation pattern before it's safe to schedule at all. Proposed smallest next commit: add dependency injection + per-stage/per-item error isolation to `PokemonScout`, with a new `tests/test_pokemon_collector.py` — no Supabase, schema, or workflow changes. Waiting for approval before touching any code.
