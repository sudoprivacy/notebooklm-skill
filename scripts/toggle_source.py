#!/usr/bin/env python3
"""
Toggle source activation in a NotebookLM notebook (check/uncheck)
"""

import argparse
import json
import sys
import re
import time
from pathlib import Path

from patchright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))

from auth_manager import AuthManager
from notebook_config import get_last_notebook, set_last_notebook
from browser_utils import BrowserFactory, StealthUtils
from list_notebooks import list_notebooks


def find_notebook_url(notebook_name: str = None, notebook_id: str = None, notebook_url: str = None) -> str:
    """Resolve notebook URL from name, ID, or URL"""
    if notebook_url:
        return notebook_url

    if notebook_id:
        return f"https://notebooklm.google.com/notebook/{notebook_id}"

    if notebook_name:
        result = list_notebooks(headless=True, output_format="json")
        if result["status"] != "success":
            raise Exception(f"Failed to list notebooks: {result.get('error')}")

        notebooks = result["notebooks"]
        notebook_name_lower = notebook_name.lower()

        for nb in notebooks:
            if nb.get("name", "").lower() == notebook_name_lower:
                return nb["url"]

        for nb in notebooks:
            if notebook_name_lower in nb.get("name", "").lower():
                return nb["url"]

        raise Exception(f"Notebook not found: {notebook_name}")

    last_notebook = get_last_notebook()
    if last_notebook:
        return last_notebook

    raise Exception("No notebook specified. Use --notebook-name, --notebook-id, or --notebook-url")


def toggle_source(
    source_name: str,
    notebook_url: str = None,
    notebook_name: str = None,
    notebook_id: str = None,
    activate: bool = None,  # None = toggle, True = activate, False = deactivate
    headless: bool = True,
    debug: bool = False
) -> dict:
    """
    Toggle source activation in a NotebookLM notebook

    Args:
        source_name: Name of the source to toggle (partial match supported)
        notebook_url: Direct notebook URL
        notebook_name: Notebook name (fuzzy match)
        notebook_id: Notebook UUID
        activate: True to activate, False to deactivate, None to toggle
        headless: Run browser in headless mode
        debug: Save screenshot for debugging

    Returns:
        Dict with status and result
    """
    auth = AuthManager()

    if not auth.is_authenticated():
        return {"status": "error", "error": "Not authenticated. Run: python auth_manager.py setup"}

    try:
        resolved_url = find_notebook_url(notebook_name, notebook_id, notebook_url)
    except Exception as e:
        return {"status": "error", "error": str(e)}

    action = "Toggling"
    if activate is True:
        action = "Activating"
    elif activate is False:
        action = "Deactivating"

    print(f"🔄 {action} source: {source_name}")
    print(f"  📚 Notebook: {resolved_url}")

    playwright = None
    context = None

    try:
        playwright = sync_playwright().start()
        context = BrowserFactory.launch_persistent_context(playwright, headless=headless)

        page = context.new_page()
        print("  🌐 Opening notebook...")
        page.goto(resolved_url, wait_until="domcontentloaded")

        page.wait_for_url(re.compile(r"^https://notebooklm\.google\.com/"), timeout=15000)
        StealthUtils.random_delay(2000, 3000)

        # Click on Sources tab
        print("  🔍 Clicking Sources tab...")
        sources_tab_selectors = [
            'button:has-text("Sources")',
            '[role="tab"]:has-text("Sources")',
        ]
        for selector in sources_tab_selectors:
            try:
                tab = page.wait_for_selector(selector, timeout=5000, state="visible")
                if tab:
                    tab.click()
                    StealthUtils.random_delay(1500, 2500)
                    break
            except Exception:
                continue

        # Find the source by name and click its checkbox
        print(f"  🔍 Looking for source: {source_name}...")

        # Use JavaScript to find and click the checkbox for the matching source
        result = page.evaluate('''(args) => {
            const { sourceName, activateMode } = args;
            const sourceNameLower = sourceName.toLowerCase();

            // Find all mat-checkbox elements
            const checkboxes = document.querySelectorAll('mat-checkbox');

            for (const checkbox of checkboxes) {
                // Get the parent row to find the source name
                const row = checkbox.closest('[class*="source"]') || checkbox.parentElement?.parentElement;
                if (!row) continue;

                const rowText = row.innerText || row.textContent || '';

                // Check if this row contains the source name
                if (rowText.toLowerCase().indexOf(sourceNameLower) >= 0) {
                    // Skip "Select all sources"
                    if (rowText.toLowerCase().indexOf('select all') >= 0) continue;

                    // Find the checkbox input or clickable element
                    const input = checkbox.querySelector('input[type="checkbox"]');
                    const isChecked = input ? input.checked : checkbox.classList.contains('mat-checkbox-checked');

                    // Determine if we should click
                    let shouldClick = false;
                    if (activateMode === null) {
                        // Toggle mode
                        shouldClick = true;
                    } else if (activateMode === true && !isChecked) {
                        // Activate mode, currently unchecked
                        shouldClick = true;
                    } else if (activateMode === false && isChecked) {
                        // Deactivate mode, currently checked
                        shouldClick = true;
                    }

                    if (shouldClick) {
                        // Click the checkbox
                        const clickTarget = checkbox.querySelector('.mat-checkbox-inner-container') ||
                                          checkbox.querySelector('.mat-checkbox-frame') ||
                                          checkbox;
                        clickTarget.click();

                        return {
                            found: true,
                            clicked: true,
                            sourceName: rowText.split('\\n').filter(l => l.trim().length > 10)[0] || sourceName,
                            wasChecked: isChecked,
                            nowChecked: !isChecked
                        };
                    } else {
                        return {
                            found: true,
                            clicked: false,
                            sourceName: rowText.split('\\n').filter(l => l.trim().length > 10)[0] || sourceName,
                            wasChecked: isChecked,
                            nowChecked: isChecked,
                            reason: activateMode === true ? 'Already activated' : 'Already deactivated'
                        };
                    }
                }
            }

            return { found: false, error: 'Source not found' };
        }''', {"sourceName": source_name, "activateMode": activate})

        if debug:
            debug_dir = Path(__file__).parent.parent / "data" / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            try:
                page.screenshot(path=str(debug_dir / "toggle_source.png"))
                print(f"  📸 Screenshot saved to: {debug_dir / 'toggle_source.png'}")
            except Exception as e:
                print(f"  ⚠️ Could not save screenshot: {e}")

        if result.get("found"):
            if result.get("clicked"):
                status_emoji = "✅" if result.get("nowChecked") else "⬜"
                print(f"  {status_emoji} Source '{result.get('sourceName', source_name)}' is now {'activated' if result.get('nowChecked') else 'deactivated'}")
            else:
                print(f"  ℹ️ {result.get('reason', 'No action needed')}")

            set_last_notebook(resolved_url)

            return {
                "status": "success",
                "source": result.get("sourceName", source_name),
                "activated": result.get("nowChecked"),
                "changed": result.get("clicked", False),
                "notebook_url": resolved_url
            }
        else:
            print(f"  ❌ Source not found: {source_name}")
            return {"status": "error", "error": f"Source not found: {source_name}"}

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
    parser = argparse.ArgumentParser(description='Toggle source activation in a NotebookLM notebook')

    # Source to toggle
    parser.add_argument('source_name', help='Name of the source to toggle (partial match)')

    # Notebook selection
    parser.add_argument('--notebook-url', help='Direct notebook URL')
    parser.add_argument('--notebook-id', help='Notebook UUID')
    parser.add_argument('--notebook-name', help='Notebook name (fuzzy match)')

    # Action
    parser.add_argument('--activate', action='store_true', help='Activate the source (check)')
    parser.add_argument('--deactivate', action='store_true', help='Deactivate the source (uncheck)')

    # Options
    parser.add_argument('--show-browser', action='store_true', help='Show browser for debugging')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--debug', action='store_true', help='Save screenshot for debugging')

    args = parser.parse_args()

    # Determine activate mode
    activate = None
    if args.activate:
        activate = True
    elif args.deactivate:
        activate = False

    result = toggle_source(
        source_name=args.source_name,
        notebook_url=args.notebook_url,
        notebook_name=args.notebook_name,
        notebook_id=args.notebook_id,
        activate=activate,
        headless=not args.show_browser,
        debug=args.debug
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
