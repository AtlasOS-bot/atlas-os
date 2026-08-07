# Safari WebDriver PoC — Local Setup (Temporary)

## One-time macOS/Safari setup

1. Show Safari's developer features: **Safari → Settings → Advanced** →
   enable "Show features for web developers" (older Safari: "Show Develop
   menu in menu bar").
2. Enable automation: **Safari → Develop menu → Allow Remote Automation**.
3. Authorize the driver at the OS level (prompts for your password):
   ```bash
   safaridriver --enable
   ```
4. Quit and reopen Safari so the settings take effect.

## Running the proof of concept

Run these from the project root on your Mac.

```bash
# 1. Activate the project's virtual environment
source .venv/bin/activate

# 2. Install Selenium temporarily (not added to requirements.txt)
pip install selenium

# 3. Run the proof of concept
python -m scouts.pokemon.poc_safari_webdriver_fetch

# 4. If you decide not to keep Selenium, remove it afterward
pip uninstall -y selenium
```

No browser binary download is needed — this drives the Safari already
installed on your Mac.
