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

sys.path.insert(0, str(Path(__file__).parent))

from notebook_config import set_last_notebook, find_notebook_url
from browser_utils import browser_session, StealthUtils
from config import SOURCES_TAB_SELECTORS


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
    try:
        resolved_url = find_notebook_url(notebook_name, notebook_id, notebook_url)
    except Exception as e:
        return {"status": "error", "error": str(e)}

    print(f"🗑️ Removing source: {source_name}")
    print(f"  📚 Notebook: {resolved_url}")

    try:
        with browser_session(headless=headless) as page:
            print("  🌐 Opening notebook...")
            page.goto(resolved_url, wait_until="domcontentloaded")

            page.wait_for_url(re.compile(r"^https://notebooklm\.google\.com/"), timeout=15000)
            StealthUtils.random_delay(2000, 3000)

            # Click on Sources tab
            print("  🔍 Clicking Sources tab...")
            for selector in SOURCES_TAB_SELECTORS:
                try:
                    tab = page.wait_for_selector(selector, timeout=5000, state="visible")
                    if tab:
                        tab.click()
                        StealthUtils.random_delay(1500, 2500)
                        break
                except Exception:
                    continue

            # Find the source by name in the sources list (with retry for slow DOM rendering)
            print(f"  🔍 Looking for source: {source_name}...")

            found_source = None
            deadline = time.time() + 30
            while time.time() < deadline:
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

                if found_source and found_source.get("found"):
                    break
                time.sleep(2)

            if not found_source or not found_source.get("found"):
                print(f"  ❌ Source not found: {source_name}")
                return {"status": "error", "error": f"Source not found: {source_name}"}

            actual_source_name = found_source.get("name", source_name)
            print(f"  ✓ Found source: {actual_source_name[:60]}...")

            StealthUtils.random_delay(500, 1000)

            # Look for delete option - find the specific source row and its menu button
            print("  🔍 Looking for delete option...")

            delete_clicked = False

            # Use JavaScript to find the exact source row and click its menu button
            try:
                # Step 1: Find and hover over the specific source row to reveal the menu button
                row_info = page.evaluate('''(sourceName) => {
                    const sourceNameLower = sourceName.toLowerCase();

                    // Find all mat-checkbox elements (each source has one)
                    const checkboxes = document.querySelectorAll('mat-checkbox');

                    for (const checkbox of checkboxes) {
                        // Get the parent row element
                        const row = checkbox.closest('[class*="source-row"]') ||
                                   checkbox.closest('[class*="list-item"]') ||
                                   checkbox.parentElement?.parentElement ||
                                   checkbox.parentElement;

                        if (!row) continue;

                        // Check the text content of this row
                        const rowText = row.innerText || row.textContent || '';

                        // Match source name (but not "Select all sources")
                        if (rowText.toLowerCase().indexOf(sourceNameLower) >= 0 &&
                            rowText.toLowerCase().indexOf('select all') === -1) {

                            // Found the matching row - get its bounding box
                            const rect = row.getBoundingClientRect();

                            // Also try to find the more_vert button within this row
                            const moreBtn = row.querySelector('button[aria-label*="More"], button[aria-label*="more"], mat-icon');
                            let btnRect = null;
                            if (moreBtn) {
                                btnRect = moreBtn.getBoundingClientRect();
                            }

                            return {
                                found: true,
                                rowRect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
                                btnRect: btnRect ? { x: btnRect.x, y: btnRect.y, width: btnRect.width, height: btnRect.height } : null,
                                sourceName: rowText.split('\\n').filter(l => l.trim().length > 5 && l.toLowerCase().indexOf('select all') === -1)[0] || sourceName
                            };
                        }
                    }

                    return { found: false };
                }''', source_name)

                if not row_info.get("found"):
                    print(f"  ⚠️ Could not find source row for: {source_name}")
                else:
                    print(f"  ✓ Found source row: {row_info.get('sourceName', source_name)[:50]}...")

                    # Hover over the right side of the row to reveal the menu button
                    row_rect = row_info["rowRect"]
                    hover_x = row_rect["x"] + row_rect["width"] - 40
                    hover_y = row_rect["y"] + row_rect["height"] / 2

                    page.mouse.move(hover_x, hover_y)
                    StealthUtils.random_delay(800, 1200)
                    print("  ✓ Hovering over source row...")

                    # Now click the more_vert button that should be visible
                    # Use JavaScript to click the button within this specific row
                    click_result = page.evaluate('''(sourceName) => {
                        const sourceNameLower = sourceName.toLowerCase();
                        const checkboxes = document.querySelectorAll('mat-checkbox');

                        for (const checkbox of checkboxes) {
                            const row = checkbox.closest('[class*="source-row"]') ||
                                       checkbox.closest('[class*="list-item"]') ||
                                       checkbox.parentElement?.parentElement ||
                                       checkbox.parentElement;

                            if (!row) continue;

                            const rowText = row.innerText || row.textContent || '';

                            if (rowText.toLowerCase().indexOf(sourceNameLower) >= 0 &&
                                rowText.toLowerCase().indexOf('select all') === -1) {

                                // Find and click the more button within THIS row
                                const moreBtn = row.querySelector('button[aria-label*="More"], button[aria-label*="more"]') ||
                                               row.querySelector('button:has(mat-icon)') ||
                                               row.querySelector('mat-icon[fonticon="more_vert"]')?.closest('button') ||
                                               row.querySelector('mat-icon')?.closest('button');

                                if (moreBtn) {
                                    moreBtn.click();
                                    return { clicked: true, method: 'direct' };
                                }

                                // Fallback: try to find any clickable icon in the row
                                const icons = row.querySelectorAll('mat-icon, button');
                                for (const icon of icons) {
                                    const iconText = icon.textContent || '';
                                    if (iconText.indexOf('more') >= 0 || icon.getAttribute('aria-label')?.toLowerCase().indexOf('more') >= 0) {
                                        icon.click();
                                        return { clicked: true, method: 'icon' };
                                    }
                                }
                            }
                        }

                        return { clicked: false };
                    }''', source_name)

                    if click_result.get("clicked"):
                        print(f"  ✓ Clicked more options menu (method: {click_result.get('method')})")
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

                        if not delete_clicked:
                            page.keyboard.press("Escape")
                            StealthUtils.random_delay(300, 500)

            except Exception as e:
                print(f"  ⚠️ Error finding source row: {e}")

            # Fallback: Try right-click context menu on the source name
            if not delete_clicked:
                print("  🔍 Trying right-click context menu...")
                try:
                    # Use a more specific locator
                    source_el = page.locator(f'text="{actual_source_name[:40]}"').first
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
