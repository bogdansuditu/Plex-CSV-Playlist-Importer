Run Natively on macOS

  - Ensure Python 3.12+: python3 --version (install via Homebrew if needed: brew install python@3.12).
  - Create virtualenv:

    cd /Users/bogdansuditu/Documents/Projects/Web/plex-smart
    python3 -m venv .venv
    source .venv/bin/activate
  - Upgrade pip/tools: pip install --upgrade pip setuptools wheel.
  - Install deps: pip install -r requirements.txt.
  - Configure env: copy .env.example if you haven’t already (cp .env.example .env) and edit PLEX_URL, PLEX_TOKEN, etc., to your real values.
  - Run the app:

    uvicorn app.main:app --reload --host 0.0.0.0 --port ${APP_PORT:-8080}
    (If APP_PORT is set in .env, uvicorn will pick it up; otherwise use --port 8080 or similar.)
  - Access UI: open http://localhost:8080 in your browser; the form will be prefilled from .env.
  - Stop server: Ctrl+C, then deactivate to exit the virtualenv when done.