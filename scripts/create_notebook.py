#!/usr/bin/env python3
"""
Create a new NotebookLM notebook via browser automation
"""

import argparse
import sys
import re
from pathlib import Path

from patchright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))

from auth_manager import AuthManager
from browser_utils import BrowserFactory, StealthUtils
from notebook_config import set_last_notebook


NOTEBOOKLM_HOME = "https://notebooklm.google.com/"


def create_notebook(name: str = None, headless: bool = True) -> dict:
    """
    Create a new NotebookLM notebook

    Args:
        name: Optional name for the notebook
        headless: Run browser in headless mode

    Returns:
        Dict with status and notebook info
    """
    auth = AuthManager()

    if not auth.is_authenticated():
        return {"status": "error", "error": "Not authenticated. Run: python auth_manager.py setup"}

    print("📝 Creating new notebook...")

    playwright = None
    context = None

    try:
        playwright = sync_playwright().start()
        context = BrowserFactory.launch_persistent_context(playwright, headless=headless)

        page = context.new_page()
        print("  🌐 Opening NotebookLM...")
        page.goto(NOTEBOOKLM_HOME, wait_until="domcontentloaded")

        # Wait for page to load
        page.wait_for_url(re.compile(r"^https://notebooklm\.google\.com/"), timeout=15000)
        StealthUtils.random_delay(2000, 3000)

        # Click "New notebook" button
        print("  🔍 Looking for 'New notebook' button...")
        new_notebook_selectors = [
            'button:has-text("New notebook")',
            'button:has-text("Create")',
            '[aria-label="Create new notebook"]',
            '[aria-label="New notebook"]',
            'button:has(mat-icon:has-text("add"))',
            '.create-notebook-button',
            # FAB button
            'button.mdc-fab',
            '[data-test-id="create-notebook"]',
        ]

        clicked = False
        for selector in new_notebook_selectors:
            try:
                element = page.wait_for_selector(selector, timeout=5000, state="visible")
                if element:
                    StealthUtils.random_delay(200, 500)
                    element.click()
                    print(f"  ✓ Clicked: {selector}")
                    clicked = True
                    break
            except Exception:
                continue

        if not clicked:
            return {"status": "error", "error": "Could not find 'New notebook' button"}

        StealthUtils.random_delay(2000, 3000)

        # Wait for navigation to new notebook
        print("  ⏳ Waiting for new notebook to be created...")
        try:
            page.wait_for_url(re.compile(r"notebooklm\.google\.com/notebook/[a-f0-9-]+"), timeout=15000)
        except Exception:
            # Maybe there's a dialog to name the notebook first
            pass

        # Check if we're on a notebook page now
        current_url = page.url
        notebook_match = re.search(r'/notebook/([a-f0-9-]+)', current_url)

        if notebook_match:
            notebook_id = notebook_match.group(1)
            notebook_url = f"https://notebooklm.google.com/notebook/{notebook_id}"

            # If name provided, try to set it
            if name:
                print(f"  📝 Setting notebook name: {name}")
                # Wait for page to fully load
                StealthUtils.random_delay(2000, 3000)

                try:
                    # First, close any open dialog (like the "Add sources" dialog)
                    page.keyboard.press("Escape")
                    StealthUtils.random_delay(500, 1000)

                    # The title input (input.title-input) is in the DOM
                    # Try to find and interact with it directly
                    title_input = page.query_selector('input.title-input')
                    if title_input:
                        # Focus the input
                        title_input.focus()
                        StealthUtils.random_delay(200, 400)

                        # Select all existing text using keyboard
                        page.keyboard.press("Meta+a")  # Mac: Cmd+A
                        StealthUtils.random_delay(100, 200)

                        # Type the new name
                        page.keyboard.type(name, delay=50)
                        StealthUtils.random_delay(300, 500)

                        # Press Enter to confirm (or Tab to blur)
                        page.keyboard.press("Tab")
                        StealthUtils.random_delay(500, 1000)

                        print(f"  ✓ Set name: {name}")
                    else:
                        # Fallback: try clicking on the editable-project-title element
                        title_el = page.query_selector('editable-project-title')
                        if title_el:
                            title_el.click()
                            StealthUtils.random_delay(500, 800)
                            page.keyboard.press("Meta+a")
                            StealthUtils.random_delay(100, 200)
                            page.keyboard.type(name, delay=50)
                            page.keyboard.press("Tab")
                            StealthUtils.random_delay(500, 1000)
                            print(f"  ✓ Set name: {name}")
                        else:
                            print(f"  ⚠️ Could not find title input element")
                except Exception as e:
                    print(f"  ⚠️ Could not set name: {e}")

            # Auto-save as last used notebook
            set_last_notebook(notebook_id, name or "")

            print(f"  ✅ Created notebook: {notebook_id}")
            return {
                "status": "success",
                "notebook_id": notebook_id,
                "notebook_url": notebook_url,
                "name": name or ""
            }
        else:
            return {"status": "error", "error": f"Unexpected URL after creation: {current_url}"}

    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}

    finally:
        if context:
            try:
                context.close()
            except Exception:
                pass
        if playwright:
            try:
                playwright.stop()
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description='Create a new NotebookLM notebook')

    parser.add_argument('--name', help='Name for the new notebook')
    parser.add_argument('--show-browser', action='store_true', help='Show browser for debugging')

    args = parser.parse_args()

    result = create_notebook(
        name=args.name,
        headless=not args.show_browser
    )

    if result["status"] == "success":
        print(f"\n✅ Created notebook!")
        print(f"   ID: {result['notebook_id']}")
        print(f"   URL: {result['notebook_url']}")
        if result.get('name'):
            print(f"   Name: {result['name']}")
        return 0
    else:
        print(f"\n❌ Failed: {result.get('error', 'Unknown error')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
