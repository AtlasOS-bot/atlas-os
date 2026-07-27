-- Atlas v21: Collector Intelligence Engine - Module 8
--
-- Creates new, additive tables only. Does not alter, rename, or drop
-- collector_opportunities (Module 1), or any legacy table
-- (opportunities, notifications, raw_drops, etc.).
--
-- This repository has no migration tooling - apply this file
-- manually via the Supabase SQL editor (or `psql`) against the
-- target project, same as 0001.
--
-- SECURITY NOTE - READ BEFORE APPLYING
-- =====================================
-- The dashboard (dashboard/app.js) writes to the tables below
-- directly from the browser using Supabase's anon key, the same
-- pattern the existing dashboard/index.html already uses for reads.
-- That key must never be paired with a service-role key or any
-- credential capable of bypassing Row Level Security.
--
-- Whether anon-key writes are actually SAFE depends entirely on the
-- RLS policies attached to these tables in the live Supabase
-- project, which this repository cannot see or verify. The policies
-- below are a STARTING RECOMMENDATION for a single-user personal
-- tool (unrestricted read/write for anon, since there is no
-- authenticated-user concept anywhere in this codebase) - they are
-- NOT applied automatically, and you should tighten them (e.g. to an
-- authenticated role, or a Supabase Edge Function boundary) before
-- relying on this in any multi-user or public deployment. Until you
-- have confirmed appropriate policies are in place, treat the
-- dashboard's write features (heart/unheart, notes, overrides,
-- manual items) as NOT SECURE for anything beyond local/personal use.

create table if not exists public.opportunity_user_overrides (
    id uuid primary key default gen_random_uuid(),
    opportunity_id text not null,

    market_strength_override text,
    market_trend_override text,
    demand_tags_override jsonb,
    collector_classification_override text,
    image_override_url text,
    tags_override jsonb,

    reason text,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    constraint opportunity_user_overrides_market_strength_check check (
        market_strength_override is null
        or market_strength_override in ('STRONG', 'MEDIUM', 'WEAK', 'UNKNOWN')
    ),
    constraint opportunity_user_overrides_market_trend_check check (
        market_trend_override is null
        or market_trend_override in ('RISING', 'STABLE', 'FALLING', 'UNKNOWN')
    )
);

create unique index if not exists
    opportunity_user_overrides_opportunity_id_unique
    on public.opportunity_user_overrides (opportunity_id);


create table if not exists public.opportunity_override_history (
    id uuid primary key default gen_random_uuid(),
    opportunity_id text not null,
    field_name text not null,
    atlas_value_snapshot jsonb,
    previous_override_value jsonb,
    new_override_value jsonb,
    reason text,
    changed_at timestamptz not null default now()
);

create index if not exists
    opportunity_override_history_opportunity_id_idx
    on public.opportunity_override_history (opportunity_id, changed_at desc);


create table if not exists public.opportunity_notes (
    id uuid primary key default gen_random_uuid(),
    opportunity_id text not null,
    body text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists
    opportunity_notes_opportunity_id_idx
    on public.opportunity_notes (opportunity_id);


create table if not exists public.hearted_items (
    id uuid primary key default gen_random_uuid(),

    -- NULL means this is a fully manual entry (no Atlas opportunity
    -- required); the manual_* fields below are then the source of
    -- truth for display.
    opportunity_id text,

    status text not null default 'SAVED',
    target_price numeric,
    quantity integer,
    priority text,
    category text,
    tags jsonb not null default '[]'::jsonb,

    product_name text,
    image_url text,
    product_link text,
    ebay_sold_link text,
    msrp numeric,
    last_sold_price numeric,
    market_strength text,

    hearted_at timestamptz not null default now(),
    archived_at timestamptz,

    constraint hearted_items_status_check check (
        status in ('SAVED', 'APPROVED', 'DENIED', 'PURCHASED', 'SOLD', 'ARCHIVED')
    ),
    constraint hearted_items_manual_identity_check check (
        opportunity_id is not null or product_name is not null
    )
);

create index if not exists
    hearted_items_opportunity_id_idx
    on public.hearted_items (opportunity_id);

create index if not exists
    hearted_items_status_idx
    on public.hearted_items (status);


create table if not exists public.hearted_item_notes (
    id uuid primary key default gen_random_uuid(),
    hearted_item_id uuid not null references public.hearted_items (id) on delete cascade,
    body text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists
    hearted_item_notes_hearted_item_id_idx
    on public.hearted_item_notes (hearted_item_id);


create table if not exists public.opportunity_images (
    id uuid primary key default gen_random_uuid(),
    opportunity_id text not null,
    primary_image_url text,
    image_source_url text,
    image_source_name text,
    image_alt_text text,
    image_last_verified_at timestamptz
);

create unique index if not exists
    opportunity_images_opportunity_id_unique
    on public.opportunity_images (opportunity_id);


create table if not exists public.user_external_links (
    id uuid primary key default gen_random_uuid(),
    owner_type text not null,
    owner_id text not null,
    link_type text not null,
    url text not null,
    label text,
    created_at timestamptz not null default now(),

    constraint user_external_links_owner_type_check check (
        owner_type in ('opportunity', 'hearted_item')
    ),
    constraint user_external_links_link_type_check check (
        link_type in ('product', 'official_source', 'ebay_sold', 'current_listings', 'evidence')
    )
);

create index if not exists
    user_external_links_owner_idx
    on public.user_external_links (owner_type, owner_id);


-- =====================================================================
-- RECOMMENDED (NOT APPLIED) Row Level Security policies.
-- Uncomment and apply only after reviewing them against your own
-- security requirements - see the SECURITY NOTE at the top of this
-- file. These assume a single personal user accessing via the anon
-- key, with no authentication system in this codebase.
-- =====================================================================

-- alter table public.opportunity_user_overrides enable row level security;
-- create policy "anon full access" on public.opportunity_user_overrides
--     for all using (true) with check (true);
--
-- alter table public.opportunity_override_history enable row level security;
-- create policy "anon full access" on public.opportunity_override_history
--     for all using (true) with check (true);
--
-- alter table public.opportunity_notes enable row level security;
-- create policy "anon full access" on public.opportunity_notes
--     for all using (true) with check (true);
--
-- alter table public.hearted_items enable row level security;
-- create policy "anon full access" on public.hearted_items
--     for all using (true) with check (true);
--
-- alter table public.hearted_item_notes enable row level security;
-- create policy "anon full access" on public.hearted_item_notes
--     for all using (true) with check (true);
--
-- alter table public.opportunity_images enable row level security;
-- create policy "anon full access" on public.opportunity_images
--     for all using (true) with check (true);
--
-- alter table public.user_external_links enable row level security;
-- create policy "anon full access" on public.user_external_links
--     for all using (true) with check (true);
