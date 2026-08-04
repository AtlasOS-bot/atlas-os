#!/usr/bin/env bash
# Local dev runner for the FastAPI app - NOT used by Vercel (which
# uses api/index.py directly). Convenience only, for `vercel dev` or
# manual `uvicorn` testing. Never commit real secret values here -
# override every one of these in your own shell/.env for anything but
# a throwaway local smoke test.
set -euo pipefail
cd "$(dirname "$0")/.."

export ATLAS_PASSWORD_HASH="${ATLAS_PASSWORD_HASH:?set ATLAS_PASSWORD_HASH first (scripts/generate_password_hash.py)}"
export ATLAS_SESSION_SECRET="${ATLAS_SESSION_SECRET:-local-dev-secret-not-for-production}"
export SUPABASE_URL="${SUPABASE_URL:-https://example.invalid}"
export SUPABASE_SERVICE_KEY="${SUPABASE_SERVICE_KEY:-local-dev-fake-key}"
export ATLAS_ENABLE_DEMO="${ATLAS_ENABLE_DEMO:-true}"
export ATLAS_PUBLIC_ORIGIN="${ATLAS_PUBLIC_ORIGIN:-http://localhost:8743}"

exec .venv/bin/uvicorn api.index:app --host 0.0.0.0 --port 8743
