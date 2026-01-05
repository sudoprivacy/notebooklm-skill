#!/usr/bin/env python3
"""
Auto-remember last used notebook.
No CLI commands needed - just internal get/set functions.
"""

import json
from pathlib import Path


CONFIG_FILE = Path(__file__).parent.parent / "data" / "config.json"


def _load_config() -> dict:
    """Load config from disk"""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_config(config: dict):
    """Save config to disk"""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_last_notebook() -> dict | None:
    """Get the last used notebook (id, url, name)"""
    config = _load_config()
    if config.get("last_notebook_id"):
        return {
            "id": config["last_notebook_id"],
            "url": f"https://notebooklm.google.com/notebook/{config['last_notebook_id']}",
            "name": config.get("last_notebook_name", ""),
        }
    return None


def set_last_notebook(notebook_id: str, name: str = ""):
    """Remember the last used notebook (called automatically after successful operations)"""
    config = _load_config()
    config["last_notebook_id"] = notebook_id
    config["last_notebook_name"] = name
    _save_config(config)
