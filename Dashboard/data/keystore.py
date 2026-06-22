"""Local persistent key/value store for the dashboard.

Used by the MajiBot settings panel to remember API keys across browser
sessions without committing secrets to the repo. The file lives under
the user's home directory (`~/.adi_water_dashboard/keys.json`) and is
created on first write with permission 0600.

The values stored here are not encrypted at rest — they sit in the
same trust boundary as `.streamlit/secrets.toml`. If a key needs to
roam between machines, drop it into Streamlit secrets instead.

Deployment safety
-----------------
On a shared/multi-tenant host (e.g. Streamlit Community Cloud) the on-disk
store is a single server-wide file, so persisting one visitor's API key
there would expose it to every other visitor. To prevent that, persistence
is automatically disabled on such hosts: reads return empty and writes are
no-ops, so keys live only in per-session `st.session_state` and never leak
between visitors. Locally, persistence stays on so keys are remembered.
Override with ADI_KEYSTORE_PERSIST=1 (force on) or =0 (force off).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

_STORE_DIR = Path.home() / ".adi_water_dashboard"
_STORE_PATH = _STORE_DIR / "keys.json"


def persistence_enabled() -> bool:
    """Whether API keys / preferences may be written to the shared on-disk store.

    Disabled on shared/cloud hosts so one visitor's key can never be read by
    another; enabled locally so keys are remembered across sessions.
    """
    override = os.environ.get("ADI_KEYSTORE_PERSIST")
    if override is not None:
        return override.strip().lower() in ("1", "true", "yes", "on")
    # Streamlit Community Cloud markers: apps run from /mount/src as adminuser.
    if os.path.isdir("/mount/src"):
        return False
    if os.environ.get("HOME", "").startswith("/home/adminuser"):
        return False
    return True


def _read_store() -> dict:
    if not persistence_enabled():
        return {}
    if not _STORE_PATH.exists():
        return {}
    try:
        return json.loads(_STORE_PATH.read_text())
    except Exception:
        return {}


def _write_store(data: dict) -> None:
    if not persistence_enabled():
        return
    _STORE_DIR.mkdir(parents=True, exist_ok=True)
    _STORE_PATH.write_text(json.dumps(data, indent=2))
    try:
        os.chmod(_STORE_PATH, 0o600)
    except OSError:
        pass


def get_api_key(provider: str) -> Optional[str]:
    """Return the persisted API key for `provider`, or None if not set."""
    return _read_store().get(f"api_key:{provider}")


def set_api_key(provider: str, value: str) -> None:
    data = _read_store()
    data[f"api_key:{provider}"] = value
    _write_store(data)


def clear_api_key(provider: str) -> None:
    data = _read_store()
    data.pop(f"api_key:{provider}", None)
    _write_store(data)


def has_api_key(provider: str) -> bool:
    key = get_api_key(provider)
    return bool(key and key.strip())


# ---------------------------------------------------------------------------
# Generic preferences (default provider, default model, etc.)
# ---------------------------------------------------------------------------

def get_preference(key: str, default=None):
    """Return a persisted preference, or `default` if not set."""
    return _read_store().get(f"pref:{key}", default)


def set_preference(key: str, value) -> None:
    """Persist a preference value (string-serialisable)."""
    data = _read_store()
    data[f"pref:{key}"] = value
    _write_store(data)


def clear_preference(key: str) -> None:
    data = _read_store()
    data.pop(f"pref:{key}", None)
    _write_store(data)
