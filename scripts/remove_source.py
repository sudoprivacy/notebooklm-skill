#!/usr/bin/env python3
"""
Remove source from a NotebookLM notebook
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


def remove_source(
    source_name: str,
    notebook_url: str = None,
    notebook_name: str = None,
    notebook_id: str = None,
    headless: bool = True,
    debug: bool = False,
    confirm: bool = True
) -> dict:
    """
    Remove source from a NotebookLM notebook

    Args:
        source_name: Name of the source to remove (partial match supported)
        notebook_url: Direct notebook URL
        notebook_name: Notebook name (fuzzy match)
        notebook_id: Notebook UUID
        headless: Run browser in headless mode
        debug: Save screenshot for debugging
        confirm: If True, confirm deletion in dialog

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

    print(f"🗑️ Removing source: {source_name}")
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

        # Find the source by name in the sources list
        print(f"  🔍 Looking for source: {source_name}...")

        # Find the source row and its more options menu (without clicking the source itself)
        found_source = page.evaluate('''(sourceName) => {
            const sourceNameLower = sourceName.toLowerCase();
            const bodyText = document.body.innerText;
            const lines = bodyText.split(String.fromCharCode(10));

            // Find the source in visible text
            for (const line of lines) {
                if (line.toLowerCase().indexOf(sourceNameLower) >= 0 &&
                    line.toLowerCase().indexOf('select all') === -1 &&
                    line.length > 10) {
                    return { found: true, name: line.trim() };
                }
            }
            return { found: false };
        }''', source_name)

        if not found_source.get("found"):
            print(f"  ❌ Source not found: {source_name}")
            return {"status": "error", "error": f"Source not found: {source_name}"}

        actual_source_name = found_source.get("name", source_name)
        print(f"  ✓ Found source: {actual_source_name[:60]}...")

        StealthUtils.random_delay(500, 1000)

        # Look for delete option - hover over source row to reveal menu button
        print("  🔍 Looking for delete option...")

        delete_clicked = False

        # Try to hover over the source row to reveal the more options button
        try:
            # Find the source row element by its text content
            hover_result = page.evaluate('''(sourceName) => {
                const sourceNameLower = sourceName.toLowerCase();

                // Find elements containing the source name
                const allElements = document.querySelectorAll('*');

                for (const el of allElements) {
                    const text = el.innerText || el.textContent || '';
                    if (text.toLowerCase().indexOf(sourceNameLower) >= 0 &&
                        text.toLowerCase().indexOf('select all') === -1 &&
                        text.length < 500) {  // Not too long (not the whole page)

                        // Find the row/container element
                        const row = el.closest('[class*="source"], [class*="row"], [class*="item"], mat-checkbox')?.parentElement ||
                                   el.closest('div') ||
                                   el;

                        // Get bounding rect for hover
                        const rect = row.getBoundingClientRect();
                        if (rect.width > 50 && rect.height > 20) {
                            return {
                                found: true,
                                x: rect.x + rect.width - 30,  // Right side where menu button usually is
                                y: rect.y + rect.height / 2
                            };
                        }
                    }
                }
                return { found: false };
            }''', source_name)

            if hover_result.get("found"):
                # Hover to reveal the menu button
                page.mouse.move(hover_result["x"], hover_result["y"])
                StealthUtils.random_delay(800, 1200)
                print("  ✓ Hovering over source row...")
        except Exception as e:
            print(f"  ⚠️ Hover failed: {e}")

        # Now try to find and click the more options menu
        more_menu_selectors = [
            'button[aria-label*="More"]',
            'button[aria-label*="more"]',
            'button[aria-label*="Options"]',
            'button:has(mat-icon:has-text("more_vert"))',
            'mat-icon:has-text("more_vert")',
        ]

        for selector in more_menu_selectors:
            try:
                more_btn = page.wait_for_selector(selector, timeout=2000, state="visible")
                if more_btn:
                    more_btn.click()
                    print(f"  ✓ Clicked more options menu")
                    StealthUtils.random_delay(500, 1000)

                    # Look for delete option in the menu
                    delete_menu_selectors = [
                        'button:has-text("Delete")',
                        'button:has-text("Remove")',
                        '[role="menuitem"]:has-text("Delete")',
                        '[role="menuitem"]:has-text("Remove")',
                    ]

                    for del_selector in delete_menu_selectors:
                        try:
                            delete_option = page.wait_for_selector(del_selector, timeout=2000, state="visible")
                            if delete_option:
                                delete_option.click()
                                delete_clicked = True
                                print(f"  ✓ Clicked Delete in menu")
                                StealthUtils.random_delay(500, 1000)
                                break
                        except Exception:
                            continue

                    if delete_clicked:
                        break

                    page.keyboard.press("Escape")
                    StealthUtils.random_delay(300, 500)
            except Exception:
                continue

        # Try right-click context menu
        if not delete_clicked:
            print("  🔍 Trying right-click context menu...")
            try:
                source_el = page.locator(f'text="{source_name[:30]}"').first
                source_el.click(button="right")
                StealthUtils.random_delay(500, 1000)

                delete_option = page.wait_for_selector(
                    '[role="menuitem"]:has-text("Delete"), [role="menuitem"]:has-text("Remove"), button:has-text("Delete")',
                    timeout=2000,
                    state="visible"
                )
                if delete_option:
                    delete_option.click()
                    delete_clicked = True
                    print(f"  ✓ Clicked Delete in context menu")
            except Exception:
                pass

        if not delete_clicked:
            if debug:
                debug_dir = Path(__file__).parent.parent / "data" / "debug"
                debug_dir.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(debug_dir / "remove_source_no_delete.png"))
                print(f"  📸 Debug screenshot saved")

            return {
                "status": "error",
                "error": "Could not find delete option. Source panel may need to be opened manually.",
                "source": actual_source_name
            }

        # Handle confirmation dialog
        if confirm:
            StealthUtils.random_delay(500, 1000)
            confirm_selectors = [
                'button:has-text("Delete")',
                'button:has-text("Confirm")',
                'button:has-text("Yes")',
                'button:has-text("OK")',
                '[data-test-id="confirm-delete"]',
            ]

            for selector in confirm_selectors:
                try:
                    confirm_btn = page.wait_for_selector(selector, timeout=2000, state="visible")
                    if confirm_btn:
                        confirm_btn.click()
                        print(f"  ✓ Confirmed deletion")
                        break
                except Exception:
                    continue

        StealthUtils.random_delay(1000, 2000)

        if debug:
            debug_dir = Path(__file__).parent.parent / "data" / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            try:
                page.screenshot(path=str(debug_dir / "remove_source.png"))
                print(f"  📸 Screenshot saved to: {debug_dir / 'remove_source.png'}")
            except Exception as e:
                print(f"  ⚠️ Could not save screenshot: {e}")

        print(f"  ✅ Source removed: {actual_source_name[:60]}...")

        set_last_notebook(resolved_url)

        return {
            "status": "success",
            "source": actual_source_name,
            "removed": True,
            "notebook_url": resolved_url
        }

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
    parser = argparse.ArgumentParser(description='Remove source from a NotebookLM notebook')

    # Source to remove
    parser.add_argument('source_name', help='Name of the source to remove (partial match)')

    # Notebook selection
    parser.add_argument('--notebook-url', help='Direct notebook URL')
    parser.add_argument('--notebook-id', help='Notebook UUID')
    parser.add_argument('--notebook-name', help='Notebook name (fuzzy match)')

    # Options
    parser.add_argument('--show-browser', action='store_true', help='Show browser for debugging')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--debug', action='store_true', help='Save screenshot for debugging')
    parser.add_argument('--no-confirm', action='store_true', help='Skip confirmation dialog')

    args = parser.parse_args()

    result = remove_source(
        source_name=args.source_name,
        notebook_url=args.notebook_url,
        notebook_name=args.notebook_name,
        notebook_id=args.notebook_id,
        headless=not args.show_browser,
        debug=args.debug,
        confirm=not args.no_confirm
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
