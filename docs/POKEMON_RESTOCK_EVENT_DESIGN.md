# Pokémon Restock Deduplication — Design Audit

Date: 2026-07-18
Status: design-only. No files were modified, staged, or committed to produce this document.

Method: every claim cites an exact file path and function/line, read directly from the repository in this session (building on [docs/POKEMON_PIPELINE_DECISION.md](POKEMON_PIPELINE_DECISION.md) and [CURRENT_STATE_AUDIT.md](../CURRENT_STATE_AUDIT.md), re-verified against the current state of `scouts/pokemon/collector.py` after the fault-isolation and acquisition-isolation commits). A repo-wide search for Supabase schema/migration/setup files (`find . -iname "*schema*" -o -iname "*migration*" -o -iname "*.sql"`, plus a grep for `CREATE TABLE`/`ALTER TABLE`) returned **zero results** — the `opportunities`/`notifications` table shapes exist only as implicit contracts inferred from the Python payloads that write and read them. There is no migration tooling in this repository.

---

## 1. Current end-to-end data flow

```
scouts/pokemon/internet_scout.py:collect_official_pokemon_items()
    → acquisition layer (per-source retrieval + extraction, now fault-isolated)
    → scouts/pokemon/consensus.py:build_consensus()  [merges duplicate candidates]
        ↓
scouts/pokemon/enrichment.py:enrich_pokemon_item()
    [classifier, product_details, popularity, collector_intelligence, investment_intelligence]
        ↓
PokemonScout.collect()                                    [collector.py:87-116]
        ↓
PokemonScout.run()  — per item (collector.py:154-580):

  1. OBSERVATION            item = enriched dict (in-memory only)

  2. STATE TRANSITION       state_tracker.observe(item)          [collector.py:170-186]
                             → PokemonStateTracker.observe()       [state_tracker.py:28-61]
                             → keyed by canonical_product_key(item) [identity.py:133-158]
                             → compares to LATEST persisted snapshot only
                               (.atlas_data/pokemon_product_states.json)
                             → returns {event, importance, reason}
                               event ∈ {NEW_PRODUCT, RESTOCK, SOLD_OUT, PRICE_DROP,
                                         PRICE_INCREASE, NEW_CONFIRMATION, NO_CHANGE}
                             → OVERWRITES the stored snapshot (collector.py:188-199);
                               the previous state is discarded, not logged as history

  3. ALERT SCORING          calculate_alert_intelligence(item)     [collector.py:201-217]
                             → alert_intelligence.py:12-158
                             → reads item["state_change"]["event"]
                             → returns {event, score, priority, action, should_alert, reasons}

  4. ALERT PERSISTENCE      alert_store.save(item, alert)          [collector.py:221-243]
                             → PokemonAlertStore.save()             [alert_store.py:29-115]
                             → dedup key: (product_key, event, status ∈ {NEW, ACTIVE})
                               [alert_store.py:117-134]
                             → writes .atlas_data/pokemon_alerts.json
                             → status never auto-transitions away from NEW/ACTIVE —
                               mark_resolved() exists [alert_store.py:170-194] but is
                               called from NOWHERE else in the repo (verified by
                               repo-wide grep — only its own definition and its own
                               unit test reference it)

  5. OPPORTUNITY CREATION   save_opportunity(item)                 [collector.py:552-571]
                             → AtlasScout.save_opportunity()        [atlas_scout.py:76-132]

  6. DUPLICATE CHECK        opportunity_exists(item)                [atlas_scout.py:28-74]
                             → *** THE FAILURE POINT — see §3 ***
                             → GET Supabase opportunities WHERE official_url = item.url
                               (or brand+item_name if no url)
                             → TRUE/FALSE with NO awareness of event type or time

  7. SUPABASE WRITE         POST Supabase opportunities             [atlas_scout.py:105-115]
                             → only reached if step 6 returned False
                             → payload: brand, item_name, official_url, confidence_score,
                               recommended_action, atlas_reason, market_signal_status
                             → skipped entirely for a suppressed restock

  8. NOTIFICATION CREATION  atlas/create_notifications.py:main()    [create_notifications.py:82-89]
                             → runs on its OWN schedule (atlas-pipeline.yml step 6),
                               fully decoupled from step 5-7 above
                             → GETs ALL opportunities rows (no filter)  [:17-27]
                             → per row: notification_exists(id) checks notifications
                               table by opportunity_id                  [:30-43]
                             → creates a notification row only for opportunity ids
                               that don't already have one                [:60-79]
                             → NEVER reads .atlas_data/pokemon_alerts.json — the
                               Pokémon alert layer (steps 3-4) is invisible to it

  9. DISCORD DELIVERY       atlas/alerts.py:main()                   [alerts.py:106-119]
                             → reads unsent notifications (sent=eq.false), joined to
                               opportunities                            [:26-38]
                             → posts to Discord, marks sent              [:82-103]
```

**Net effect:** a restock that never produces a new `opportunities` row (step 7 skipped) can never produce a `notifications` row (step 8 has nothing new to see) and therefore never reaches Discord (step 9 has nothing new to send).

---

## 2. Current identity and deduplication model

Four different "is this the same product/event" definitions currently coexist, and they disagree with each other:

| Model | Location | Basis |
|---|---|---|
| Canonical product identity | `identity.py:canonical_product_key()` (L133-158) | `sku:` prefix if SKU present, else `product_type:token1-token2-...` from normalized title tokens |
| Product fuzzy match | `identity.py:same_product()` (L217-238) | SKU match, or Jaccard token overlap ≥ 0.72 |
| State/alert dedup key | used by `state_tracker.py:31-35` and `alert_store.py:38-42` | `canonical_product_key(item)` (same as above) |
| **Opportunity dedup key** | `atlas_scout.py:opportunity_exists()` (L28-74) | **raw `item["url"]` exact string match**, falling back to raw `brand`+`title` exact string match — does **not** use `canonical_product_key` at all |
| Cross-game catalog identity | `scouts/tcg/catalog_store.py:product_key()` (L311-326) | `category:sku:<code>` |

The opportunity-layer identity is the odd one out: it is coarser (URL/title only, no event awareness) and structurally disconnected from `identity.py`, which every other layer already uses.

---

## 3. Exact failure point

**File:** `scouts/base/atlas_scout.py`
**Function:** `opportunity_exists()`, lines 28-74; consumed by `save_opportunity()`, lines 76-82:

```python
def save_opportunity(self, item):
    if self.opportunity_exists(item):
        print("Duplicate skipped:", item["title"])
        return False
    ...
```

`opportunity_exists()` returns `True` the moment **any** prior Supabase `opportunities` row shares the item's URL (or brand+title) — with no check of `item.get("state_event")`, no timestamp comparison, and no distinction between "we already told you about this product once, ever" and "we already told you about *this specific restock*." Called from `scouts/pokemon/collector.py:554` inside `PokemonScout.run()`'s per-item loop, once per scan, for every item including ones whose `state_event` is freshly `"RESTOCK"`.

---

## 4. Table / payload field inventory

**`.atlas_data/pokemon_product_states.json`** (via `PokemonStateTracker`, `state_tracker.py:63-84`) — keyed by `canonical_product_key`, **one row per product, overwritten every scan**:
`title, url, sku, retail_price, availability, release_date, sources, observed_at`

**`.atlas_data/pokemon_alerts.json`** (via `PokemonAlertStore`, `alert_store.py:56-109`) — append-only list:
`alert_id, product_key, created_at, title, url, sku, product_type, event, priority, score, action, reason, best_strategy, flip_score, hold_score, sleeper_score, collector_score, popularity_score, consensus_score, release_urgency, reasons, status`

**Supabase `opportunities`** (external, no schema file — inferred from writers):
- Written by `AtlasScout.save_opportunity()` (`atlas_scout.py:89-103`): `brand, item_name, official_url, confidence_score, recommended_action, atlas_reason, market_signal_status`
- Also written/patched by legacy `atlas/scorer.py` (`atlas/scorer.py:76-99`, additional fields: `raw_drop_id, category, alert_level, worth_trip, hype_score, urgency_score, resale_signal, status`) and `atlas/research_engine.py` (`retailer, release_status, category, exclusive, research_complete`)
- Read by `dashboard/index.html:142-171` (`brand, item_name, confidence_score, market_signal_status, recommended_action, ebay_sold_comps_url`)
- **No column exists anywhere for**: canonical product key, state-change event type, or an observation timestamp tied to a specific transition.

**Supabase `notifications`** (external, no schema file): `opportunity_id, alert_level, message, sent` (`atlas/create_notifications.py:64-69`), plus `id`/`created_at` (implied by `order=created_at.desc` at `atlas/alerts.py:34`).

---

## 5. Product identity vs. event identity

The bug is a category error: **the code that should be checking event identity is checking product identity.**

- **Product identity** answers "have we ever seen this product before" — correctly modeled by `identity.py:canonical_product_key()` and already used consistently by `state_tracker.py`, `alert_store.py`, and `catalog_store.py`.
- **Event identity** answers "have we already told the user about *this specific state transition*" — this concept exists implicitly in `alert_store.py`'s dedup key (`product_key` + `event` + `status`), but does not exist at all at the opportunity/Supabase layer, which only ever checks product identity (via URL/title).

A correct fix must key the opportunity-layer dedup check on **(product identity, event identity)**, not product identity alone — exactly the same shape `alert_store.py` already implements, minus its one remaining gap (§6 below).

---

## 6. Direct answers

**1. What currently represents product identity?** `identity.py:canonical_product_key()` (SKU-based or product-type+token-based). Used inconsistently — `opportunity_exists()` bypasses it entirely in favor of raw URL/title strings (§2).

**2. What represents observation / state transition / alert / opportunity / notification?** See §1 inline annotations and §4. Observation = the in-memory enriched item dict, never persisted on its own. State transition = the `{event, importance, reason}` dict from `state_tracker.observe()`, persisted only as the latest snapshot (no transition history). Alert = a record in `pokemon_alerts.json`. Opportunity = a Supabase `opportunities` row. Notification = a Supabase `notifications` row.

**3. Which tables/stores persist each?** See §4.

**4. Exact conditions causing `opportunity_exists()` to return true?** A Supabase `opportunities` row exists with `official_url` exactly equal to `item["url"]`, or (no URL) `brand` + `item_name` exactly equal to the item's brand/title. No event or time dimension (`atlas_scout.py:28-74`).

**5. Exact line/function where a legitimate restock is suppressed?** `scouts/base/atlas_scout.py:77-82`, inside `save_opportunity()`, gated by `opportunity_exists()` (`atlas_scout.py:28-74`); triggered from `scouts/pokemon/collector.py:552-571`.

**6. Does alert persistence already preserve the restock even when opportunity persistence rejects it?** Only for the **first** restock on a given product. `alert_store.save()` runs independently of and before `save_opportunity()` in `collector.py`'s per-item sequence, so it does persist the first RESTOCK alert correctly. But because `mark_resolved()` is never called automatically anywhere (confirmed by repo-wide grep), the alert record's `status` stays `NEW`/`ACTIVE` forever, so a **second, later, genuinely new** restock on the same product is *also* suppressed — this time by `alert_store.py:117-134`'s own dedup. This is a second instance of the same category of bug, one layer over, and is not fixed by patching `opportunity_exists()` alone.

**7. Does notification creation depend on a new opportunity row, an alert row, or both?** Only a new opportunity row (`atlas/create_notifications.py:17-27`). It never reads the alert store. The correctly-scored Pokémon alert layer (event, priority, reasons) is invisible to the notification/Discord pipeline.

**8. Could the same restock currently produce duplicate alerts through any alternate path?** Structurally possible but not active today: `scouts/tcg/` has its own parallel `TcgStateTracker`/`alert_intelligence.py`/`alert_store.py`/`alert_runner.py` over the same catalog data (`catalog_store.upsert_many(items)` runs unconditionally at `collector.py:582-597`, independent of per-item dedup), using a *different* product-key scheme (`catalog_store.py:product_key()`). Per `POKEMON_PIPELINE_DECISION.md` §1, none of the `scouts/tcg/*_runner.py` files are scheduled today, so this is a latent risk, not an active duplicate-alert path.

**9. What fields already exist that could form an event identity?** Nearly everything needed is already computed in-memory during a single scan pass: `canonical_product_key(item)`, `state_change["event"]`, `state_tracker.py`'s `observed_at`, `item.get("sources")`, `item.get("retail_price")`, and (transiently, then discarded) the previous snapshot inside `state_tracker.observe()` (`state_tracker.py:41`, never persisted). The gap is that nothing combines these into a stable, persisted key that `opportunity_exists()` can check, and no per-transition history is kept (only the latest snapshot).

**10. Is a schema change required?** No. See §8 — the recommended option requires zero Supabase schema changes; it moves the dedup decision client-side, before `save_opportunity()` is ever called, reusing the exact pattern `alert_store.py` already proves works.

**11. How should repeated observations during the same restock wave be deduplicated?** `state_tracker.py` already only fires `RESTOCK` on the unavailable→available transition edge; a subsequent poll while still in stock yields `NO_CHANGE`, which `alert_intelligence.py:should_alert()` (L161-165) already refuses to alert on. So "the same wave" is already naturally bounded by `state_tracker.py`'s own transition detection — no new wave concept needs to be invented, it needs to be *trusted* by the opportunity layer instead of being overridden by a coarser URL check.

**12. How should a later, genuinely new restock be allowed through?** By keying the opportunity-layer dedup on `(canonical_product_key, event, transition marker)` instead of raw URL — where "transition marker" can be as simple as the `observed_at` timestamp of the transition that produced this specific `state_change`, or a small monotonically increasing counter. Since `state_tracker.py` already returns a fresh `state_change` dict only when a real transition occurs, any transition-derived marker is automatically distinct per genuine event and identical (or absent) for repeats within a wave.

**13. How should price changes, new listings, sellouts, restocks differ semantically?** They already do, via `state_change["event"]` and `alert_intelligence.py`'s `EVENT_BASE_SCORES` (`RESTOCK=45` highest actionable weight, `PRICE_INCREASE=8` lowest, `alert_intelligence.py:1-9`). The fix must preserve this by including `event` in the dedup key — a `NEW_PRODUCT` and a later `RESTOCK` on the same URL are different notification-worthy moments and must not suppress each other. This is already true in `alert_store.py` and must become true at the opportunity layer too.

**14. Safest migration/backward-compatibility strategy?** Since there is no schema/migration tooling in this repo, prefer a fix that changes *behavior*, not *table structure*. Old `opportunities` rows written before the fix simply won't match the new, more specific dedup key — worst case is one extra (correct, not spurious) opportunity row gets created the first time the fix runs for a product last touched before the change. That is a safe direction to fail in (§9).

**15. Tests to prove no missed restocks and no alert spam?** See §11 test matrix.

---

## 7. At least three solution options

### Option A — Composite dedup value written into the existing `official_url` field

Change what `opportunity_exists()`/`save_opportunity()` check and write: instead of the raw product URL, compose and check a value like `f"{item['url']}#{event}#{transition_marker}"`, reusing the existing `official_url` column verbatim.

- **Schema impact:** none — no new Supabase column.
- **Pros:** smallest possible diff to `atlas_scout.py`; no other file needs to change.
- **Cons:** `official_url` stops being a real, clickable URL for restock-triggered rows — semantically dishonest column reuse. Confirmed low *functional* risk (`dashboard/index.html:166` links via `ebay_sold_comps_url`, not `official_url`; `atlas/research_engine.py` doesn't treat `official_url` as a link either) but it's a smell that would confuse a future reader or any future dashboard feature that assumes `official_url` is a real URL. Also couples this Pokémon-specific fix into the *shared* `AtlasScout` base class, silently changing dedup behavior for Nike and any future scout that reuses it.
- **Alert-spam risk:** low, provided the transition marker is stable and monotonic.

### Option B — New `product_key` / `event_key` columns on Supabase `opportunities`

Add two real columns; change `opportunity_exists()` to query on them instead of URL.

- **Schema impact:** real — `ALTER TABLE opportunities ADD COLUMN ...`, applied outside this repo (no migration tooling exists here), plus backfill/NULL handling for existing rows.
- **Pros:** cleanest long-term semantics; `official_url` stays a real URL; `product_key`/`event_key` are brand-agnostic column names, directly reusable by Lorcana/One Piece/Nike/Starbucks without inventing anything new.
- **Cons:** requires a schema change, which `CLAUDE.md`'s Database Rules explicitly gate behind explicit user request; also still touches the shared `AtlasScout` base class, affecting every scout that inherits it, not just Pokémon.
- **Alert-spam risk:** low, same mechanism as A, cleaner data model.

### Option C — Client-side event-forwarding gate, isolated to the Pokémon module (recommended, see §8)

Before `collector.py` calls `self.save_opportunity(item)`, consult a small local store (new file, or an extension of the existing `PokemonAlertStore` record) that already knows — via the same `(canonical_product_key, event, status)` logic `alert_store.py` uses today — whether this exact transition has already been forwarded. Only call `save_opportunity()` when that check says "this is new." `scouts/base/atlas_scout.py` is not touched at all.

- **Schema impact:** none — purely a new/extended local JSON store plus one call-site change in `collector.py`.
- **Pros:** zero changes to the shared `AtlasScout` base class (so Nike and any other current/future scout using it is completely unaffected); zero Supabase schema change; reuses a pattern already proven correct in `alert_store.py`; naturally reusable per-category the same way `alert_store.py`/`state_tracker.py` already are (each brand gets its own store).
- **Cons:** if implemented as a brand-new store rather than an extension of `PokemonAlertStore`, it duplicates the "have we already surfaced this event" concept across two files — mitigated by extending `PokemonAlertStore` instead of adding a fully separate store (see §8).
- **Alert-spam risk:** low, and this option is also positioned to fix the compounding bug in §6 (Q6) — the missing `mark_resolved()` wiring — as an immediate, clearly separated follow-up, since the same store already has the machinery for it.

---

## 8. Recommended design: Option C

Option C is the only one of the three that satisfies every constraint in the prompt simultaneously:

- **Preserves one canonical product identity** — reuses `identity.py:canonical_product_key()` unchanged; does not introduce a competing identity scheme.
- **Allows genuinely new restock events** — keys forwarding on `(product_key, event)` freshly computed each scan from `state_tracker.py`'s own transition detection, exactly mirroring the semantics `alert_store.py` already gets right.
- **Suppresses same-wave polling noise** — for free, because `state_tracker.py` already only emits a non-`NO_CHANGE` event on a genuine transition; nothing new needs to be invented for "wave" boundaries (§6, Q11).
- **Avoids duplicate Discord notifications** — by construction: if `save_opportunity()` is only called once per genuine transition, `atlas/create_notifications.py` and `atlas/alerts.py` need **zero changes** and continue to work exactly as they do today, just against opportunity rows that now actually appear for restocks.
- **Minimizes schema changes** — zero Supabase changes; the entire fix lives client-side, in the Pokémon module.
- **Reusable for other categories** — the pattern (a per-brand local store gating calls to the shared `save_opportunity()`) is the same shape as `alert_store.py`/`state_tracker.py`, which Lorcana, One Piece, Nike, and Starbucks can each adopt independently without touching `scouts/base/atlas_scout.py`.

### Repeated-restock-wave deduplication rule

Forward to `save_opportunity()` only when **both** are true:
1. `state_change["event"] != "NO_CHANGE"` (already guarantees a real transition occurred — `state_tracker.py`'s own logic), and
2. no existing forwarding record has `product_key == canonical_product_key(item)` and `event == state_change["event"]` and `status` in `{"NEW", "ACTIVE"}` — identical shape to `alert_store.py:alert_exists()` (`alert_store.py:117-134`).

A later, genuinely new restock is allowed through the moment the *prior* RESTOCK record for that product has moved out of `{"NEW", "ACTIVE"}` — which requires the `mark_resolved()` gap (§6, Q6) to be closed as a **follow-up**, not bundled into the smallest commit below, to keep this change narrowly scoped per the established pattern from the last two commits.

### Backward-compatibility plan

- No Supabase schema change, so no migration to write or apply.
- Old `pokemon_alerts.json`/Supabase `opportunities` rows written before this fix are simply not consulted by the new local gate (which starts empty) — the very first scan after deployment may forward one already-known product's *current* state once more (safe: it produces one legitimate, non-duplicate opportunity row, not data loss).
- `scouts/base/atlas_scout.py`, `atlas/research_engine.py`, `atlas/scorer.py`, `atlas/create_notifications.py`, `atlas/alerts.py`, `universal.py`, and all GitHub workflows remain untouched.
- `alert_store.py`'s existing dedup and its two current tests (`test_pokemon_alert_deduplication.py`) are unaffected whether Option C extends `PokemonAlertStore` or adds a sibling store — either way its public methods keep their current signatures and return shapes.

---

## 9. Smallest safe implementation commit

Scope: gate `PokemonScout.run()`'s call to `save_opportunity()` behind a new, narrowly-defined "has this (product, event) already been forwarded" check, without touching `AtlasScout`, Supabase, or notifications.

1. Extend `scouts/pokemon/alert_store.py`'s existing record shape with a way to answer "has an opportunity already been forwarded for this alert record" — the cleanest option is a new boolean field on the alert record (e.g. `opportunity_forwarded`) set the first time `save_opportunity()` succeeds for that alert, checked before calling `save_opportunity()` on subsequent scans for the same `(product_key, event, status)`. This reuses `alert_store.py`'s existing dedup key instead of introducing a second one.
2. Add one small method to `PokemonAlertStore`, e.g. `mark_opportunity_forwarded(alert_id)`, following the exact pattern already used by `mark_resolved()` (`alert_store.py:170-194`).
3. In `scouts/pokemon/collector.py`'s per-item loop, only call `self.save_opportunity(item)` when the just-saved (or already-active) alert record has not yet been marked forwarded; call `mark_opportunity_forwarded()` immediately after a successful `save_opportunity()` call.
4. Do **not** touch `scouts/base/atlas_scout.py`, `atlas/*.py`, any workflow, or Supabase — this commit only changes which items reach `save_opportunity()` and when, not what it does once called.
5. Do **not** implement `mark_resolved()` auto-wiring in this commit — flagged explicitly as the next follow-up (§6, Q6), kept separate to preserve narrow scope.

### Files this implementation would touch

- `scouts/pokemon/alert_store.py` — new field + one new method.
- `scouts/pokemon/collector.py` — the `save_opportunity` call site in `run()`'s per-item loop, gated by the new check.
- `tests/test_pokemon_alert_store.py` and/or `tests/test_pokemon_alert_deduplication.py` — new focused tests for the new field/method.
- `tests/test_pokemon_collector.py` — new focused tests for the gating behavior in `run()`.

No other file needs to change.

---

## 10. Exact focused test matrix

**`alert_store.py` additions:**
1. A freshly saved alert record defaults to not-yet-forwarded.
2. `mark_opportunity_forwarded(alert_id)` flips the flag and persists it; returns `True`/`False` matching `mark_resolved()`'s existing contract.
3. Marking forwarded does not change `status` (`NEW`/`ACTIVE`/`RESOLVED` stay independent of the forwarded flag).

**`collector.py` gating (in `tests/test_pokemon_collector.py`):**
4. **First observation of a product (`NEW_PRODUCT`)** → `save_opportunity()` is called exactly once; forwarded flag set afterward.
5. **Second scan, same product, no state change (`NO_CHANGE`)** → `save_opportunity()` is *not* called again (already covered indirectly by `opportunity_exists()` today, but must remain true after the gate is added).
6. **Product goes `NEW_PRODUCT` → `SOLD_OUT` → `RESTOCK` across three scans** → `save_opportunity()` is called for `NEW_PRODUCT` and again for `RESTOCK` (two calls, not one) — this is the regression test that directly proves the reported bug is fixed.
7. **`RESTOCK` observed twice in a row before the first is resolved** (simulating repeated polling mid-wave) → `save_opportunity()` is called only once for that `RESTOCK` — proves no alert-spam regression.
8. **`save_opportunity()` itself raises** (already-isolated per the prior fault-isolation commit) → the forwarded flag is *not* set, so a transient Supabase failure doesn't permanently suppress a real event on the next scan — this is a new, important edge case the gate must get right.
9. **Alert scoring fails for an item (`alert is None`, per the existing fault-isolation path)** → the gate falls back to *not* suppressing `save_opportunity()` (fail open toward visibility, not silently toward suppression) — must be asserted explicitly given this design's whole purpose is to stop legitimate opportunities from disappearing.

---

## Summary (≤12 lines)

The restock-suppression bug is real and precisely located: `AtlasScout.opportunity_exists()` (`scouts/base/atlas_scout.py:28-74`) dedups purely by product URL/title with no event awareness, so a correctly-detected `RESTOCK` on a previously-seen product never reaches Supabase, and therefore never reaches Discord — confirmed end-to-end through `atlas/create_notifications.py` and `atlas/alerts.py`, which depend entirely on new `opportunities` rows and never see the Pokémon alert layer at all. A second, compounding bug was found: `PokemonAlertStore`'s own otherwise-correct `(product_key, event, status)` dedup never resolves, since `mark_resolved()` is called nowhere in the pipeline, so even a *second* genuine restock would eventually be silently dropped at the alert layer too. Of three options evaluated — reusing `official_url` for a composite key, adding real Supabase columns, or a client-side forwarding gate — the recommended fix (**Option C**) adds a small `opportunity_forwarded` flag to existing Pokémon alert records and gates `collector.py`'s call to `save_opportunity()` on it, touching only `scouts/pokemon/alert_store.py` and `scouts/pokemon/collector.py`. It requires zero Supabase schema changes, leaves `scouts/base/atlas_scout.py` (and therefore Nike) untouched, and is directly reusable by Lorcana/One Piece/Starbucks. The `mark_resolved()` gap is intentionally left as a separate follow-up commit to keep this one narrowly scoped. Waiting for approval before implementing.
