# Pokémon Reference Architecture

This document describes the target shape of the Pokémon module as the reference implementation every future category (One Piece, Lorcana, Starbucks, Costco, Disney, ...) will copy. It is written against what actually exists today (see [CURRENT_STATE_AUDIT.md](CURRENT_STATE_AUDIT.md)) — it extends and wires existing modules rather than proposing new ones wherever an existing module can do the job.

Principle: **one pipeline, one schedule, one output schema.** Today there are two disconnected pipelines (legacy `atlas/` + `scouts/universal.py`, and the sophisticated but unscheduled `scouts/pokemon/`). The reference architecture has exactly one.

---

## 1. Target data flow

```
                        ┌─────────────────────────────┐
                        │   scouts/pokemon/sources.py   │  static source config
                        └───────────────┬─────────────┘
                                        ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │ ACQUISITION  (layer 16 — health, retry, rate limit, secrets)      │
 │ acquisition/service.py + requests_retriever.py                    │
 └───────────────────────────────┬──────────────────────────────────┘
                                  ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │ COLLECT     scouts/pokemon/internet_scout.py + structured_data.py │
 │             → raw item candidates (HTML + JSON-LD)                │
 └───────────────────────────────┬──────────────────────────────────┘
                                  ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │ IDENTITY RESOLUTION  (layer 1)  scouts/pokemon/identity.py         │
 │  canonical_product_key / same_product / identity_similarity       │
 └───────────────────────────────┬──────────────────────────────────┘
                                  ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │ CONSENSUS   scouts/pokemon/consensus.py                            │
 │  groups duplicate candidates → one record + source_consensus       │
 └───────────────────────────────┬──────────────────────────────────┘
                                  ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │ CLASSIFY    scouts/pokemon/classifier.py                           │
 │  product_type, sealed_product, collector_tier                      │
 └───────────────────────────────┬──────────────────────────────────┘
                                  ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │ ENRICH      scouts/pokemon/enrichment.py (orchestrator)            │
 │   ├─ product_details.py        (pack/promo/accessory detail)       │
 │   ├─ CARD INTELLIGENCE (layer 10, NEW — see §3)                    │
 │   ├─ popularity/pokemon.py      (layer 6 — demand/hype score)      │
 │   ├─ collector_intelligence.py  (collector interest score)         │
 │   └─ investment_intelligence.py (flip/hold/sleeper score)          │
 └───────────────────────────────┬──────────────────────────────────┘
                                  ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │ STATE CHANGE DETECTION (layer 4)  scouts/pokemon/state_tracker.py │
 │  NEW_PRODUCT / RESTOCK / SOLD_OUT / PRICE_DROP / ...               │
 └───────────────────────────────┬──────────────────────────────────┘
                                  ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │ PATTERN MATCH (layer 5)  patterns/engine.py + pokemon_patterns.py  │
 │  requires seeded patterns/history.py (currently empty — see gap)   │
 └───────────────────────────────┬──────────────────────────────────┘
                                  ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │ SIGNALS      signals/engine.py → 12 registered AtlasSignal impls   │
 └───────────────────────────────┬──────────────────────────────────┘
                                  ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │ MARKET       market/engine.py → market/router.py → providers       │
 │  (ebay/stockx/tcgplayer/pricecharting — needs real data, see gap)  │
 │  → market/aggregator.py → market/roi.py  (layer 7: comps/fees/ROI) │
 └───────────────────────────────┬──────────────────────────────────┘
                                  ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │ REASONING    reasoning/engine.py: reason()   (layer 15)            │
 │  evidence → score → confidence → opportunity → urgency → decide()  │
 │  + CAPITAL ALLOCATION (layer 8, NEW — see §3)                      │
 └───────────────────────────────┬──────────────────────────────────┘
                                  ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │ ALERT INTELLIGENCE (layer 14) scouts/pokemon/alert_intelligence.py │
 │  event score + escalation/wave grouping (NEW — see §3)             │
 │  → alert_store.py (dedup) → alert_queue.py (rank) → alert_brief.py │
 └───────────────────────────────┬──────────────────────────────────┘
                                  ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │ NORMALIZED OPPORTUNITY RECORD  (the shared output — see §2)        │
 │  written to: scouts/tcg/catalog_store.py  +  Supabase opportunities│
 └───────────────────────────────┬──────────────────────────────────┘
                                  ▼
                    dashboard/index.html · Discord alerts · morning brief
```

Cross-cutting, called at every stage rather than sitting in the linear flow:
- **LOCAL RELEVANCE (layer 12, NEW)** — attaches drive-decision context to any item flagged in-store-only or LA-relevant.
- **USER SIGHTING REPORTS (layer 13, NEW)** — an independent input that can create or corroborate a state-change event, feeding into consensus/state_tracker alongside official sources.
- **LEARNING** — `learning/engine.py` records every `reason()` output after the fact; `learning/statistics.py` aggregates it. Target: feed `LearningStatistics.summarize()` back into `reasoning/engine.py` so a category with a historically low buy-rate lowers its own confidence over time.
- **SCOUT HEALTH (layer 16)** — every acquisition attempt logged with outcome, feeding a health dashboard.

---

## 2. The normalized Pokémon opportunity record

This is the contract other modules (One Piece, Lorcana, Starbucks, Costco) reuse. It's not a new format — it's the existing `reason()` output ([reasoning/engine.py:174-192](reasoning/engine.py#L174-L192)) plus the enrichment fields already produced upstream, made explicit as a schema:

```
{
  # Identity (layer 1)
  "canonical_key": str,            # from identity.py
  "title": str, "url": str, "sku": str | None,
  "brand": str, "category": str,   # e.g. "pokemon"

  # Product facts (layers 2, 9, 10)
  "product_type": str, "sealed_product": bool, "collector_tier": str,
  "release_date": str | None, "action_window": str, "release_confidence": str,  # NEW: confirmed/likely/rumored
  "card_detail": {...} | None,     # NEW layer 10, null for sealed-only items

  # Consensus & state (layers 1, 4, 5)
  "source_consensus": {score, level, confidence, source_count},
  "state_event": {event, importance, reason},
  "pattern_matches": [...],

  # Demand & investment (layers 6, 8, 9)
  "popularity": {score, level, confidence, reasons},
  "collector_intelligence": {score, level, hold_profile},
  "investment_intelligence": {flip_score, hold_score, sleeper_score, best_strategy},
  "allocation": {recommended_quantity, capital_at_risk, reasoning} | None,  # NEW layer 8

  # Market & finance (layer 7)
  "market": {summary, providers},
  "roi": {profit, roi_percent, fees, shipping} | None,

  # Local context (layer 12) — optional, only for LA-relevant items
  "local": {nearby_stores: [...], drive_worth_it: bool, reasoning} | None,  # NEW

  # Decision & explanation (layer 15)
  "score": int, "decision": str, "confidence": str,
  "evidence": [...], "reasons": [...], "explanation": str,

  # Provenance (layers 13, 16)
  "sighting_reports": [...],        # NEW — user corroboration, if any
  "freshness": {observed_at, source_count, last_confirmed_at},
  "scout_meta": {source, fetched_at, retry_count},  # NEW
}
```

Every field above already has a producing module except the ones marked NEW. The record is assembled by `PokemonScout.run()` today and should become the literal return value of a `build_opportunity_record()` function so other brands call the same assembly function with different collector/classifier inputs.

---

## 3. Module boundaries — what's reused vs. what's genuinely new

| Layer | Reused as-is | Extended | New |
|---|---|---|---|
| 1. Identity & dedup | `identity.py`, `consensus.py` | Unify the 3 duplicate merge implementations (internet_scout.py, live_monitor.py, consensus.py) into one | — |
| 2. Release calendar | `release_calendar.py`, `release_store.py` | Add `release_confidence` (confirmed/likely/rumored) derived from `consensus_level` | — |
| 3. Retailer adapter interface | `scouts/base/atlas_scout.py` | Get `lorcana`, `one_piece`, `starbucks` to actually extend it | — |
| 4. State-change detection | `state_tracker.py` | — | — |
| 5. Drop-pattern history | `patterns/engine.py`, `matcher.py`, `scorer.py` | Seed `patterns/history.py` with real historical drop data (currently empty dict) | — |
| 6. Demand / hype scoring | `popularity/pokemon.py` | — | — |
| 7. Comps, fees, payout, ROI | `market/aggregator.py`, `market/roi.py` | Connect real StockX/TCGPlayer/PriceCharting APIs (currently stubs); add per-marketplace fee schedules instead of one flat rate | — |
| 8. Buy-qty / capital allocation | `decision/decision_engine.py` (decision only) | — | `decision/allocation_engine.py`: turns `decide()`'s BUY + ROI + collector_tier into a recommended quantity and $ at risk, given a budget input |
| 9. Sealed vs open | `classifier.py` (sealed side) | — | Raw/open-box counterpart classification, if in scope |
| 10. Card / illustrator / grading | `product_details.py` (sealed-box detail only) | — | `scouts/pokemon/card_details.py`: card_number, rarity, set_code, illustrator; grading tier awareness (PSA/CGC/BGS) as metadata on individual-card items |
| 11. Image ID integration point | — | — | A defined hook (e.g. `card_details.py: identify_from_image(image_bytes) -> card_candidate`) that raises `NotImplementedError` today but gives future CV work a contract to implement against |
| 12. LA local-store / drive-decision | — | — | `knowledge/pokemon_stores_la.py` (static store list) + `decision/local_relevance.py` (drive-worth-it heuristic) |
| 13. User sighting reports | `state_tracker.py` (can accept the shape) | Accept a `source="user_sighting"` item alongside official sources | `scouts/pokemon/sighting_reports.py`: reliability scoring per reporter + time-decay weighting |
| 14. Alert dedup/escalation/waves | `alert_store.py` (dedup only) | Add escalation: repeated RESTOCK within a window bumps priority instead of creating a flat duplicate; add wave detection across the catalog | — |
| 15. Explainable scoring | `reasoning/engine.py`, `decision_engine.py`, `explanation_engine.py` | Feed `learning/statistics.py` output back in as a confidence adjustment | — |
| 16. Scout health / retries / secrets / audit | `acquisition/` | Add retry/backoff, structured audit log, central secrets loader; get `lorcana`/`one_piece`/`starbucks` onto it instead of their own ad hoc retry code | — |

---

## 4. Non-goals for this pass

Explicitly out of scope until the audit's "risky"/"broken" items are resolved and the pipeline is actually scheduled:
- No new scout categories (Disney, Costco, etc.) until Pokémon's own automation gap (Section 0 of the audit) is closed — a second unscheduled pipeline helps no one.
- No new Supabase tables/schema changes — CLAUDE.md forbids this without explicit request, and the two-pipeline schema mismatch needs reconciling first, not growing.
- No image-identification implementation — only the integration *point* (layer 11) is in scope now.
