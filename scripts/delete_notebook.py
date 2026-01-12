#!/usr/bin/env python3
"""
Delete a NotebookLM notebook via browser automation
"""

import argparse
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from browser_utils import browser_session, StealthUtils
from list_notebooks import list_notebooks


NOTEBOOKLM_HOME = "https://notebooklm.google.com/"


def find_notebook_by_name(name: str) -> dict | None:
    """Find notebook by name (fuzzy match)"""
    result = list_notebooks(headless=True)
    if result["status"] != "success":
        return None
    for nb in result["notebooks"]:
        if name.lower() in nb.get("name", "").lower():
            return nb
    return None


def delete_notebook(notebook_url: str = None, notebook_id: str = None, notebook_name: str = None,
                   headless: bool = True, confirm: bool = False) -> dict:
    """
    Delete a NotebookLM notebook

    Args:
        notebook_url: Full NotebookLM notebook URL
        notebook_id: Notebook UUID
        notebook_name: Notebook name (fuzzy match)
        headless: Run browser in headless mode
        confirm: Actually delete (if False, just preview)

    Returns:
        Dict with status and details
    """

    # Resolve notebook
    resolved_id = None
    resolved_name = None

    if notebook_url:
        match = re.search(r'/notebook/([a-f0-9-]+)', notebook_url)
        if match:
            resolved_id = match.group(1)

    if not resolved_id and notebook_id:
        resolved_id = notebook_id

    if not resolved_id and notebook_name:
        print(f"🔍 Looking for notebook: {notebook_name}")
        nb = find_notebook_by_name(notebook_name)
        if nb:
            resolved_id = nb["id"]
            resolved_name = nb.get("name", "")
            print(f"📚 Found: {resolved_name}")
        else:
            return {"status": "error", "error": f"No notebook found matching: {notebook_name}"}

    if not resolved_id:
        return {"status": "error", "error": "No notebook specified. Use --notebook-url, --notebook-id, or --notebook-name"}

    if not confirm:
        print(f"⚠️  Would delete notebook: {resolved_name or resolved_id}")
        print(f"   ID: {resolved_id}")
        print(f"   Use --confirm to actually delete")
        return {"status": "preview", "notebook_id": resolved_id, "name": resolved_name}

    print(f"🗑️  Deleting notebook: {resolved_name or resolved_id}")

    try:
        with browser_session(headless=headless) as page:
            print("  🌐 Opening NotebookLM...")
            page.goto(NOTEBOOKLM_HOME, wait_until="domcontentloaded")

            # Wait for page to load
            page.wait_for_url(re.compile(r"^https://notebooklm\.google\.com/"), timeout=15000)
            StealthUtils.random_delay(2000, 3000)

            # Click on "All" tab to see user's notebooks
            print("  🔍 Clicking 'All' tab...")
            all_tab_selectors = [
                'button:has-text("All")',
                '[role="tab"]:has-text("All")',
            ]
            for selector in all_tab_selectors:
                try:
                    tab = page.wait_for_selector(selector, timeout=5000, state="visible")
                    if tab:
                        tab.click()
                        StealthUtils.random_delay(1500, 2500)
                        break
                except Exception:
                    continue

            # Find the notebook card by ID
            print(f"  🔍 Looking for notebook: {resolved_id}")

            # Look for the project-button element containing this notebook
            notebook_card = None
            try:
                all_cards = page.query_selector_all('project-button')
                for card in all_cards:
                    try:
                        button = card.query_selector('button[aria-labelledby]')
                        if button:
                            aria = button.get_attribute('aria-labelledby') or ""
                            if resolved_id in aria:
                                notebook_card = card
                                break
                    except Exception:
                        continue
            except Exception:
                pass

            if not notebook_card:
                return {"status": "error", "error": f"Could not find notebook card for: {resolved_id}"}

            print("  ✓ Found notebook card")

            # Find and click the menu button (three dots) on the notebook card
            print("  🔍 Opening menu...")
            menu_button = None
            menu_selectors = [
                'button[aria-label="More options"]',
                'button[aria-label*="menu" i]',
                'button:has(mat-icon:has-text("more_vert"))',
                'button:has(mat-icon:has-text("more_horiz"))',
                '.menu-button',
                '[data-test-id="notebook-menu"]',
            ]

            # First try within the notebook card
            for selector in menu_selectors:
                try:
                    menu_button = notebook_card.query_selector(selector)
                    if menu_button:
                        break
                except Exception:
                    continue

            # If not found in card, try hovering first to reveal menu
            if not menu_button:
                try:
                    notebook_card.hover()
                    StealthUtils.random_delay(500, 1000)
                    for selector in menu_selectors:
                        try:
                            menu_button = notebook_card.query_selector(selector)
                            if menu_button:
                                break
                        except Exception:
                            continue
                except Exception:
                    pass

            if not menu_button:
                return {"status": "error", "error": "Could not find menu button on notebook card"}

            menu_button.click()
            print("  ✓ Clicked menu button")
            StealthUtils.random_delay(500, 1000)

            # Click "Delete" option in the menu
            print("  🔍 Looking for 'Delete' option...")
            delete_selectors = [
                'button:has-text("Delete")',
                '[role="menuitem"]:has-text("Delete")',
                'mat-menu-item:has-text("Delete")',
                '[data-test-id="delete-notebook"]',
            ]

            deleted = False
            for selector in delete_selectors:
                try:
                    delete_btn = page.wait_for_selector(selector, timeout=3000, state="visible")
                    if delete_btn:
                        delete_btn.click()
                        print("  ✓ Clicked 'Delete'")
                        deleted = True
                        break
                except Exception:
                    continue

            if not deleted:
                return {"status": "error", "error": "Could not find 'Delete' option in menu"}

            StealthUtils.random_delay(500, 1000)

            # Confirm deletion in dialog
            print("  🔍 Confirming deletion...")
            confirm_selectors = [
                'button:has-text("Delete")',  # Confirm button in dialog
                'button:has-text("Confirm")',
                'button:has-text("Yes")',
                '[data-test-id="confirm-delete"]',
                'mat-dialog-actions button:has-text("Delete")',
            ]

            confirmed = False
            for selector in confirm_selectors:
                try:
                    confirm_btn = page.wait_for_selector(selector, timeout=3000, state="visible")
                    if confirm_btn:
                        confirm_btn.click()
                        print("  ✓ Confirmed deletion")
                        confirmed = True
                        break
                except Exception:
                    continue

            if not confirmed:
                # Maybe no confirmation needed
                print("  ⚠️ No confirmation dialog found, deletion may have completed")

            StealthUtils.random_delay(2000, 3000)

            print(f"  ✅ Deleted notebook: {resolved_name or resolved_id}")
            return {
                "status": "success",
                "notebook_id": resolved_id,
                "name": resolved_name
            }

    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description='Delete a NotebookLM notebook')

    parser.add_argument('--notebook-url', help='Full NotebookLM notebook URL')
    parser.add_argument('--notebook-id', help='Notebook UUID')
    parser.add_argument('--notebook-name', help='Notebook name (fuzzy match)')
    parser.add_argument('--confirm', action='store_true', help='Actually delete (without this, just preview)')
    parser.add_argument('--show-browser', action='store_true', help='Show browser for debugging')

    args = parser.parse_args()

    if not any([args.notebook_url, args.notebook_id, args.notebook_name]):
        print("❌ Must specify one of: --notebook-url, --notebook-id, --notebook-name")
        return 1

    result = delete_notebook(
        notebook_url=args.notebook_url,
        notebook_id=args.notebook_id,
        notebook_name=args.notebook_name,
        headless=not args.show_browser,
        confirm=args.confirm
    )

    if result["status"] == "success":
        print(f"\n✅ Deleted notebook!")
        print(f"   ID: {result['notebook_id']}")
        if result.get('name'):
            print(f"   Name: {result['name']}")
        return 0
    elif result["status"] == "preview":
        return 0
    else:
        print(f"\n❌ Failed: {result.get('error', 'Unknown error')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
