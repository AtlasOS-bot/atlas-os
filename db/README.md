# Database migrations

This repository has no migration runner (no Supabase CLI project, no
Alembic, no ORM). Every Supabase table used by Atlas today, including
`opportunities` and `notifications`, was created by hand against the
live project - there is nothing here that applies SQL automatically.

Files in `db/migrations/` are plain SQL, numbered in the order they
should be applied. Apply a file by pasting it into the Supabase SQL
editor (or running it via `psql`) against the target project.

## Applied so far

- `0001_create_collector_opportunities.sql` - adds the
  `collector_opportunities` table for Atlas v21's Collector
  Intelligence Engine (Module 1). Purely additive: creates one new
  table, does not alter or drop any existing table.
