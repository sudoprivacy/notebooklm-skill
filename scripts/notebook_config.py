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


def find_notebook_url(notebook_name: str = None, notebook_id: str = None, notebook_url: str = None) -> str:
    """
    Resolve notebook URL from name, ID, or URL.
    Priority: url > id > name > last used

    Args:
        notebook_name: Notebook name (fuzzy match)
        notebook_id: Notebook UUID
        notebook_url: Direct notebook URL

    Returns:
        Notebook URL string

    Raises:
        Exception if notebook cannot be found
    """
    if notebook_url:
        return notebook_url

    if notebook_id:
        return f"https://notebooklm.google.com/notebook/{notebook_id}"

    if notebook_name:
        # Lazy import to avoid circular dependency
        from list_notebooks import list_notebooks

        result = list_notebooks(headless=True, output_format="json")
        if result["status"] != "success":
            raise Exception(f"Failed to list notebooks: {result.get('error')}")

        notebooks = result["notebooks"]
        notebook_name_lower = notebook_name.lower()

        # Try exact match first
        for nb in notebooks:
            if nb.get("name", "").lower() == notebook_name_lower:
                return nb["url"]

        # Try partial match
        for nb in notebooks:
            if notebook_name_lower in nb.get("name", "").lower():
                return nb["url"]

        raise Exception(f"Notebook not found: {notebook_name}")

    # Try last used notebook
    last = get_last_notebook()
    if last:
        return last["url"]

    raise Exception("No notebook specified. Use --notebook-name, --notebook-id, or --notebook-url")
