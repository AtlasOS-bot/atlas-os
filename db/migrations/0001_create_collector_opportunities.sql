-- Atlas v21: Collector Intelligence Engine - Module 1
--
-- Creates a new, additive table only. Does not alter, rename, or
-- drop any existing table (opportunities, notifications, raw_drops,
-- etc.).
--
-- This repository has no migration tooling (no Supabase CLI project,
-- no Alembic/ORM) - every other Supabase table in this codebase was
-- created by hand against the live project. Apply this file manually
-- via the Supabase SQL editor (or `psql`) against the target
-- project. Nothing in this repository executes it automatically.

create table if not exists public.collector_opportunities (
    -- Database bookkeeping
    id uuid primary key default gen_random_uuid(),
    opportunity_id text not null,
    dedup_key text not null,
    created_at timestamptz not null default now(),
    -- No trigger keeps this current on UPDATE - deliberate. This
    -- repo's write path is Module 4's finalize_collector_opportunities()
    -- (collector_intelligence/finalization.py), which already computes
    -- everything about a merge in Python and would simply set this
    -- field itself alongside every other changed column. A trigger
    -- would be a second, redundant place enforcing the same thing.
    -- Revisit only if a write path appears that updates this table
    -- without going through that Python layer.
    updated_at timestamptz not null default now(),

    -- Identity
    product_name text not null,
    normalized_product_name text,
    brand text not null,
    franchise text,
    product_line text,
    category text,
    subcategory text,
    collaboration_partner text,
    edition_name text,
    release_region text,

    -- Release information
    announcement_date date,
    release_date date,
    release_time text,
    purchase_window_start timestamptz,
    purchase_window_end timestamptz,
    -- No CHECK constraint here on purpose: collector_intelligence/enums.py
    -- states this is "intentionally left as free text rather than a
    -- closed enum" - its VALID_STATUSES set is explicitly "for optional
    -- reference/validation, not enforcement," because new ecosystems are
    -- expected to need statuses not yet anticipated. A DB constraint
    -- would be stricter than the Python model it's meant to match.
    status text,

    -- Purchase information
    retail_price numeric,
    required_spend numeric,
    currency text,
    purchase_method text,
    retailer text,
    purchase_limit integer,
    membership_required boolean not null default false,
    lottery_required boolean not null default false,
    event_attendance_required boolean not null default false,
    bundle_required boolean not null default false,
    regional_exclusive boolean not null default false,
    online_available boolean,
    in_store_available boolean,
    purchase_url text,

    -- Collector characteristics
    limited_quantity boolean not null default false,
    stated_quantity integer,
    numbered boolean not null default false,
    first_edition boolean not null default false,
    first_collaboration boolean not null default false,
    anniversary_release boolean not null default false,
    exclusive_promo boolean not null default false,
    exclusive_artwork boolean not null default false,
    exclusive_character boolean not null default false,
    event_exclusive boolean not null default false,
    convention_exclusive boolean not null default false,
    retailer_exclusive boolean not null default false,
    region_exclusive boolean not null default false,
    membership_exclusive boolean not null default false,
    tournament_exclusive boolean not null default false,
    artist_name text,
    character_names jsonb not null default '[]'::jsonb,
    set_or_series text,
    sealed_product boolean,
    redeemable_reward boolean not null default false,
    acquisition_difficulty text, -- constrained below (matches AcquisitionDifficulty)

    -- Market information
    current_market_price numeric,
    recent_sold_price numeric,
    estimated_market_price numeric,
    peak_market_price numeric,
    sales_velocity numeric,
    sellout_speed text,
    active_listing_count integer,
    sold_listing_count integer,
    demand_direction text, -- constrained below (matches DemandDirection)
    -- No CHECK constraint on supply_direction: unlike demand_direction,
    -- it is declared `str | None` in models.py with no enum, no
    -- coerce_enum_value call, and no vocabulary defined anywhere in
    -- this codebase (confirmed by a full-repo search). There is
    -- nothing to match here - a constraint would be inventing one.
    supply_direction text,

    -- Scoring (0-100, nullable - a missing score means "not yet
    -- evidenced", never an invented number)
    collector_score numeric,
    flip_score numeric,
    hold_score numeric,
    scarcity_score numeric,
    demand_score numeric,
    hype_score numeric,
    acquisition_score numeric,
    risk_score numeric,
    confidence_score numeric,
    opportunity_score numeric,

    -- Recommendation
    recommendation text, -- constrained below (matches Recommendation)
    recommended_quantity integer,
    target_buy_price numeric,
    target_sell_price numeric,
    -- estimated_profit/estimated_roi_percent are NOT constrained to be
    -- non-negative: decision_engine.py computes both as a direct,
    -- unclamped `sell_price - buy_price` (and a ratio of that) with no
    -- max(0, ...) anywhere near them - unlike recommended_quantity,
    -- which the same file explicitly clamps to max(quantity, 0). A
    -- losing deal is meant to produce a real negative number here.
    estimated_profit numeric,
    estimated_roi_percent numeric,
    flip_time_horizon text,
    hold_time_horizon text,
    primary_strategy text, -- constrained below (matches PrimaryStrategy)
    reasoning jsonb not null default '[]'::jsonb,
    risks jsonb not null default '[]'::jsonb,
    catalyst_signals jsonb not null default '[]'::jsonb,

    -- Source tracking
    source_name text,
    source_type text, -- constrained below (matches SourceType)
    source_url text,
    source_published_at timestamptz,
    discovered_at timestamptz,
    last_verified_at timestamptz,
    -- No CHECK constraint on source_confidence: declared `str | None`
    -- in models.py with no enum and no vocabulary defined anywhere in
    -- this codebase (confirmed by a full-repo search) - same reasoning
    -- as supply_direction above.
    source_confidence text,
    raw_source_text text,
    evidence jsonb not null default '[]'::jsonb,

    -- Free-form provenance / scoring rationale, not modeled as
    -- individual columns
    raw_metadata jsonb not null default '{}'::jsonb,
    score_explanation jsonb not null default '{}'::jsonb,

    -- Score-range guardrails matching CollectorOpportunity's own
    -- validation, so bad data can't reach this table even from a
    -- future write path that bypasses the Python model.
    constraint collector_opportunities_score_ranges check (
        (collector_score is null or (collector_score between 0 and 100)) and
        (flip_score is null or (flip_score between 0 and 100)) and
        (hold_score is null or (hold_score between 0 and 100)) and
        (scarcity_score is null or (scarcity_score between 0 and 100)) and
        (demand_score is null or (demand_score between 0 and 100)) and
        (hype_score is null or (hype_score between 0 and 100)) and
        (acquisition_score is null or (acquisition_score between 0 and 100)) and
        (risk_score is null or (risk_score between 0 and 100)) and
        (confidence_score is null or (confidence_score between 0 and 100)) and
        (opportunity_score is null or (opportunity_score between 0 and 100))
    ),

    -- Enum guardrails for the fields collector_intelligence/enums.py
    -- actually enforces in Python (ENUM_FIELDS + coerce_enum_value).
    -- Exact same value sets, nothing added or removed. status,
    -- supply_direction, and source_confidence are deliberately NOT
    -- constrained here - see the comments on those columns above for
    -- why each one has no Python-enforced vocabulary to match.
    constraint collector_opportunities_acquisition_difficulty_check check (
        acquisition_difficulty is null or acquisition_difficulty in (
            'EASY', 'MODERATE', 'HARD', 'VERY_HARD', 'EXTREME'
        )
    ),
    constraint collector_opportunities_demand_direction_check check (
        demand_direction is null or demand_direction in (
            'FALLING', 'FLAT', 'RISING', 'SURGING', 'UNKNOWN'
        )
    ),
    constraint collector_opportunities_recommendation_check check (
        recommendation is null or recommendation in (
            'CRITICAL_BUY', 'STRONG_BUY', 'BUY', 'CONDITIONAL_BUY', 'WATCH', 'SKIP', 'AVOID'
        )
    ),
    constraint collector_opportunities_primary_strategy_check check (
        primary_strategy is null or primary_strategy in (
            'FLIP_NOW', 'QUICK_FLIP', 'HOLD_SHORT', 'HOLD_MEDIUM', 'HOLD_LONG', 'COLLECT_ONLY', 'WATCH', 'AVOID'
        )
    ),
    constraint collector_opportunities_source_type_check check (
        source_type is null or source_type in (
            'OFFICIAL', 'RETAILER', 'PRESS_RELEASE', 'SOCIAL', 'COMMUNITY', 'MARKETPLACE', 'NEWS', 'EVENT', 'OTHER'
        )
    ),

    -- Non-negative guardrails for fields that are always real-world
    -- amounts/counts in the Python model (prices, limits, quantities,
    -- listing counts) - never a computed delta that could legitimately
    -- go negative. estimated_profit/estimated_roi_percent are excluded
    -- on purpose - see the comment on those columns above.
    constraint collector_opportunities_nonnegative_amounts check (
        (retail_price is null or retail_price >= 0) and
        (required_spend is null or required_spend >= 0) and
        (purchase_limit is null or purchase_limit >= 0) and
        (stated_quantity is null or stated_quantity >= 0) and
        (current_market_price is null or current_market_price >= 0) and
        (recent_sold_price is null or recent_sold_price >= 0) and
        (estimated_market_price is null or estimated_market_price >= 0) and
        (peak_market_price is null or peak_market_price >= 0) and
        (active_listing_count is null or active_listing_count >= 0) and
        (sold_listing_count is null or sold_listing_count >= 0) and
        (recommended_quantity is null or recommended_quantity >= 0) and
        (target_buy_price is null or target_buy_price >= 0) and
        (target_sell_price is null or target_sell_price >= 0)
    )
);

-- One row per stable opportunity_id.
create unique index if not exists
    collector_opportunities_opportunity_id_unique
    on public.collector_opportunities (opportunity_id);

-- The actual deduplication guard: two reports of the same real-world
-- product/drop (same brand + franchise + product name + partner +
-- release date + retailer, normalized) must resolve to one row, not
-- a new one per source that mentions it.
create unique index if not exists
    collector_opportunities_dedup_key_unique
    on public.collector_opportunities (dedup_key);

create index if not exists
    collector_opportunities_brand_idx
    on public.collector_opportunities (brand);

create index if not exists
    collector_opportunities_status_idx
    on public.collector_opportunities (status);

create index if not exists
    collector_opportunities_created_at_idx
    on public.collector_opportunities (created_at desc);
