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
    acquisition_difficulty text,

    -- Market information
    current_market_price numeric,
    recent_sold_price numeric,
    estimated_market_price numeric,
    peak_market_price numeric,
    sales_velocity numeric,
    sellout_speed text,
    active_listing_count integer,
    sold_listing_count integer,
    demand_direction text,
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
    recommendation text,
    recommended_quantity integer,
    target_buy_price numeric,
    target_sell_price numeric,
    estimated_profit numeric,
    estimated_roi_percent numeric,
    flip_time_horizon text,
    hold_time_horizon text,
    primary_strategy text,
    reasoning jsonb not null default '[]'::jsonb,
    risks jsonb not null default '[]'::jsonb,
    catalyst_signals jsonb not null default '[]'::jsonb,

    -- Source tracking
    source_name text,
    source_type text,
    source_url text,
    source_published_at timestamptz,
    discovered_at timestamptz,
    last_verified_at timestamptz,
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
