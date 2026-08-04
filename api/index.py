"""
Vercel's required Python entrypoint (see server/app.py's module
docstring for why the real app logic lives there, not here). This file
is the ONLY place that calls load_config_from_env() - the real,
service-key-backed SupabaseClient gets built here for the actual
deployed app; every test builds its own Config and FakeSupabaseClient
instead and never imports this file.
"""

from server.app import create_app
from server.config import load_config_from_env

app = create_app(load_config_from_env())
