# Playwright PoC — Local Setup (Temporary)

Run these from the project root on your Mac.

```bash
# 1. Activate the project's virtual environment
source .venv/bin/activate

# 2. Install Playwright temporarily (not added to requirements.txt)
pip install playwright

# 3. Install the Chromium browser binary
playwright install chromium

# 4. Run the proof of concept
python -m scouts.pokemon.poc_playwright_fetch

# 5. If you decide not to keep Playwright, remove it afterward
pip uninstall -y playwright
```

## Result (recorded)

Local headed Chromium returned **INCAPSULA_ERROR** when visiting the
Pokémon Center TCG category page. The user's normal browser/network was
already experiencing Pokémon Center access restrictions that same day,
independent of this script.

Playwright is **not approved for integration** into the Atlas pipeline
at this time. `requirements.txt` must remain unchanged.
