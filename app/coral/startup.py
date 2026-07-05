"""
coral_startup.py — Drop this in your ~/Abra/ folder.
Run once at app start: python3 coral_startup.py
Or import it at the top of main.py: import coral_startup

Automatically:
1. Registers all .yml/.yaml source specs in the sources/ folder with Coral
2. Refreshes Strava OAuth token if expired (needs refresh token in .env)
3. Writes the fresh Strava token back into the Strava source
"""

import os
import subprocess
import json
import logging
import glob

from app import PROJECT_ROOT
from pathlib import Path

logger = logging.getLogger("abra.startup")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


# ─────────────────────────────────────────────
# 1. CORAL SOURCE AUTO-REGISTRATION
# ─────────────────────────────────────────────

def get_registered_sources() -> list[str]:
    """Returns list of source names already registered with Coral."""
    try:
        result = subprocess.run(
            ["coral", "source", "list", "--format", "json"],
            capture_output=True, text=True, timeout=8
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            # coral source list --format json returns list of {name: ...} objects
            return [s.get("name", "") for s in data]
    except Exception:
        pass

    # Fallback: plain text parse (coral source list outputs a table)
    try:
        result = subprocess.run(
            ["coral", "source", "list"],
            capture_output=True, text=True, timeout=8
        )
        names = []
        for line in result.stdout.strip().splitlines():
            line = line.strip()
            # Skip empty, header-separator, and "No sources" lines
            if not line or line.startswith("---") or line.startswith("No sources"):
                continue
            # Skip the header row (contains "Source" or "Version")
            if "Version" in line and "Origin" in line:
                continue
            # First column is the source name
            source_name = line.split()[0]
            if source_name:
                names.append(source_name)
        return names
    except Exception:
        return []


def register_all_sources(sources_dir: str = None) -> dict[str, bool]:
    """
    Scans the sources/ directory and registers any .yml/.yaml files
    that aren't already registered with Coral. Returns {source_name: success}.
    """
    if sources_dir is None:
        sources_dir = PROJECT_ROOT / "sources"

    sources_dir = Path(sources_dir)
    if not sources_dir.exists():
        logger.warning(f"Sources directory not found: {sources_dir}")
        return {}

    already_registered = get_registered_sources()
    logger.info(f"Currently registered Coral sources: {already_registered or 'none'}")

    results = {}
    spec_files = list(sources_dir.glob("*.yml")) + list(sources_dir.glob("*.yaml"))

    if not spec_files:
        logger.warning(f"No .yml/.yaml source specs found in {sources_dir}")
        return {}

    for spec_path in spec_files:
        # Read the source name from the file
        source_name = _read_source_name(spec_path)
        if not source_name:
            logger.warning(f"Could not read source name from {spec_path.name}, skipping.")
            continue

        if source_name in already_registered:
            logger.info(f"✓ {source_name} already registered, skipping.")
            results[source_name] = True
            continue

        logger.info(f"→ Registering source: {source_name} from {spec_path.name}")
        success = _add_source(spec_path)
        
        # If add failed, it might already exist with old spec — remove and retry
        if not success:
            logger.info(f"  Retrying: removing old {source_name} and re-adding...")
            subprocess.run(["coral", "source", "remove", source_name],
                           capture_output=True, timeout=8)
            success = _add_source(spec_path)
        
        results[source_name] = success
        if success:
            logger.info(f"✓ {source_name} registered successfully.")
        else:
            logger.warning(f"✗ {source_name} failed to register — check spec or Coral version.")


    return results


def _read_source_name(spec_path: Path) -> str | None:
    """Reads the 'name:' field from a YAML source spec without importing yaml."""
    try:
        with open(spec_path, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("name:"):
                    return line.split(":", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return None


def _add_source(spec_path: Path) -> bool:
    """Runs: coral source add --file <path>"""
    try:
        result = subprocess.run(
            ["coral", "source", "add", "--file", str(spec_path)],
            capture_output=True, text=True, timeout=15
        )
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Error running coral source add: {e}")
        return False


# ─────────────────────────────────────────────
# 2. STRAVA OAUTH TOKEN AUTO-REFRESH
# ─────────────────────────────────────────────
# Strava tokens expire every 6 hours. This refreshes automatically
# using the refresh_token stored in your .env and writes the fresh
# access token back, both to .env and to the Strava Coral source.

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"


def refresh_strava_token() -> str | None:
    """
    Uses STRAVA_REFRESH_TOKEN from .env to get a fresh access token.
    Writes it back to .env as STRAVA_ACCESS_TOKEN.
    Returns the new token string, or None if refresh failed.
    """
    import httpx

    client_id = os.getenv("STRAVA_CLIENT_ID")
    client_secret = os.getenv("STRAVA_CLIENT_SECRET")
    refresh_token = os.getenv("STRAVA_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        logger.warning(
            "Strava OAuth env vars missing. Need: STRAVA_CLIENT_ID, "
            "STRAVA_CLIENT_SECRET, STRAVA_REFRESH_TOKEN. Skipping refresh."
        )
        return None

    try:
        resp = httpx.post(STRAVA_TOKEN_URL, data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }, timeout=10)

        if resp.status_code != 200:
            logger.error(f"Strava token refresh failed: {resp.status_code} — {resp.text}")
            return None

        data = resp.json()
        new_access_token = data.get("access_token")
        new_refresh_token = data.get("refresh_token")  # Strava rotates refresh tokens too
        expires_at = data.get("expires_at")

        if not new_access_token:
            logger.error("Strava response had no access_token field.")
            return None

        logger.info(f"✓ Strava token refreshed. Expires at epoch: {expires_at}")

        # Write updated tokens back to .env
        _update_env_var("STRAVA_ACCESS_TOKEN", new_access_token)
        if new_refresh_token:
            _update_env_var("STRAVA_REFRESH_TOKEN", new_refresh_token)

        # Also set in current process environment so Coral picks it up immediately
        os.environ["STRAVA_ACCESS_TOKEN"] = new_access_token

        return new_access_token

    except Exception as e:
        logger.error(f"Strava token refresh exception: {e}")
        return None


def _update_env_var(key: str, value: str):
    """Updates or adds a KEY=VALUE line in .env file."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        env_path.write_text(f"{key}={value}\n")
        return

    lines = env_path.read_text().splitlines()
    updated = False
    new_lines = []
    for line in lines:
        if line.startswith(f"{key}=") or line.startswith(f"{key} ="):
            new_lines.append(f'{key}="{value}"')
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        new_lines.append(f'{key}="{value}"')

    env_path.write_text("\n".join(new_lines) + "\n")
    logger.info(f"Updated {key} in .env")


def setup_strava_source():
    """
    Full Strava setup flow:
    1. Check if STRAVA_ACCESS_TOKEN is set and not expired
    2. If missing or expired, refresh via OAuth
    3. Re-register the strava Coral source with the fresh token
    """
    import time

    # Check token expiry using STRAVA_TOKEN_EXPIRES_AT (epoch int) in .env
    expires_at = os.getenv("STRAVA_TOKEN_EXPIRES_AT")
    current_token = os.getenv("STRAVA_ACCESS_TOKEN")

    needs_refresh = True
    if current_token and expires_at:
        try:
            if int(expires_at) > int(time.time()) + 300:  # 5-min buffer
                needs_refresh = False
                logger.info("Strava access token is still valid, no refresh needed.")
        except ValueError:
            pass

    if needs_refresh:
        logger.info("Strava token missing or expired. Refreshing...")
        new_token = refresh_strava_token()
        if not new_token:
            logger.warning("Strava token refresh failed. Strava data will be unavailable.")
            return False

        # Re-register strava source with fresh token env var in scope
        strava_spec = PROJECT_ROOT / "sources" / "strava.yml"
        if strava_spec.exists():
            # Remove old registration first
            subprocess.run(["coral", "source", "remove", "strava"],
                           capture_output=True, timeout=8)
            success = _add_source(strava_spec)
            if success:
                logger.info("✓ Strava source re-registered with fresh token.")
            else:
                logger.warning("✗ Strava source re-registration failed.")
            return success

    return True


# ─────────────────────────────────────────────
# 3. FIRST-TIME STRAVA OAUTH SETUP HELPER
# ─────────────────────────────────────────────
# Run this once manually: python3 coral_startup.py --strava-auth
# Opens a local server, gets the code from Strava redirect, exchanges it.

def run_strava_first_auth():
    """
    One-time OAuth flow. Run once from terminal:
        python3 coral_startup.py --strava-auth

    Prerequisites — add to .env:
        STRAVA_CLIENT_ID=your_app_client_id
        STRAVA_CLIENT_SECRET=your_app_client_secret

    Get these from: https://www.strava.com/settings/api
    """
    import httpx
    import threading
    import webbrowser
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from urllib.parse import urlparse, parse_qs

    client_id = os.getenv("STRAVA_CLIENT_ID")
    client_secret = os.getenv("STRAVA_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("\n[ERROR] Set STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET in .env first.")
        print("Get them from: https://www.strava.com/settings/api")
        print("Set Authorization Callback Domain to: localhost")
        return

    auth_code_holder = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            if "code" in params:
                auth_code_holder["code"] = params["code"][0]
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"<html><body><h2>Abra: Strava connected!</h2><p>You can close this tab.</p></body></html>")
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"<html><body><h2>No auth code received.</h2></body></html>")

        def log_message(self, *args):
            pass  # Suppress server logs

    # Start local callback server on port 8765
    server = HTTPServer(("localhost", 8765), CallbackHandler)
    thread = threading.Thread(target=server.handle_request)
    thread.daemon = True
    thread.start()

    auth_url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&redirect_uri=http://localhost:8765/callback"
        f"&approval_prompt=force"
        f"&scope=activity:read_all"
    )

    print(f"\n→ Opening Strava auth page in browser...")
    print(f"  If it doesn't open, go to:\n  {auth_url}\n")
    webbrowser.open(auth_url)

    thread.join(timeout=120)  # Wait up to 2 minutes
    server.server_close()

    code = auth_code_holder.get("code")
    if not code:
        print("[ERROR] No auth code received. Did you complete the Strava authorization?")
        return

    # Exchange code for tokens
    resp = httpx.post(STRAVA_TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
    })

    if resp.status_code != 200:
        print(f"[ERROR] Token exchange failed: {resp.status_code} — {resp.text}")
        return

    data = resp.json()
    _update_env_var("STRAVA_ACCESS_TOKEN", data["access_token"])
    _update_env_var("STRAVA_REFRESH_TOKEN", data["refresh_token"])
    _update_env_var("STRAVA_TOKEN_EXPIRES_AT", str(data["expires_at"]))

    print(f"\n✓ Strava connected! Tokens saved to .env")
    print(f"  Athlete: {data.get('athlete', {}).get('firstname', 'Unknown')}")
    print(f"  Access token expires at epoch: {data['expires_at']}")
    print(f"\nNow run your app normally — token auto-refreshes from here.")


# ─────────────────────────────────────────────
# 4. MAIN BOOTSTRAP — called at app startup
# ─────────────────────────────────────────────

def bootstrap():
    """
    Call this once at the top of main.py:
        from app.coral.startup import bootstrap
        bootstrap()

    Handles everything automatically every time the app starts.
    """
    logger.info("═══ ABRA STARTUP BOOTSTRAP ═══")

    # Step 1: Refresh Strava token if needed (before registering sources,
    # because the strava.yml reads STRAVA_ACCESS_TOKEN from env at register time)
    logger.info("── Strava OAuth ──")
    setup_strava_source()

    # Step 2: Register all Coral sources
    logger.info("── Coral Sources ──")
    results = register_all_sources()

    if results:
        ok = [k for k, v in results.items() if v]
        fail = [k for k, v in results.items() if not v]
        if ok:
            logger.info(f"Sources registered/confirmed: {', '.join(ok)}")
        if fail:
            logger.warning(f"Sources failed to register: {', '.join(fail)}")
    else:
        logger.warning("No source specs found or Coral not installed.")

    logger.info("═══ BOOTSTRAP COMPLETE ═══")


if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    load_dotenv()

    if "--strava-auth" in sys.argv:
        # One-time Strava OAuth setup
        run_strava_first_auth()
    else:
        bootstrap()
