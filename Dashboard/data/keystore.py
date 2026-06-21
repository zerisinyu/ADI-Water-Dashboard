"""Local persistent key/value store for the dashboard.

Used by the MajiBot settings panel to remember API keys across browser
sessions without committing secrets to the repo. The file lives under
the user's home directory (`~/.adi_water_dashboard/keys.json`) and is
created on first write with permission 0600.

The values stored here are not encrypted at rest — they sit in the
same trust boundary as `.streamlit/secrets.toml`. If a key needs to
roam between machines, drop it into Streamlit secrets instead.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

_STORE_DIR = Path.home() / ".adi_water_dashboard"
_STORE_PATH = _STORE_DIR / "keys.json"


def _read_store() -> dict:
    if not _STORE_PATH.exists():
        return {}
    try:
        return json.loads(_STORE_PATH.read_text())
    except Exception:
        return {}


def _write_store(data: dict) -> None:
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
