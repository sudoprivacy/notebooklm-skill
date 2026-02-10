#!/usr/bin/env python3
"""
List all sources in a NotebookLM notebook via browser automation
"""

import argparse
import json
import sys
import re
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from notebook_config import set_last_notebook, find_notebook_url
from browser_utils import browser_session, StealthUtils, find_and_click
from config import SOURCES_TAB_SELECTORS


def list_sources(
    notebook_url: str = None,
    notebook_name: str = None,
    notebook_id: str = None,
    headless: bool = True,
    output_format: str = "table",
    debug: bool = False
) -> dict:
    """
    List all sources in a NotebookLM notebook
    """
    # Resolve notebook URL first (before browser)
    try:
        resolved_url = find_notebook_url(notebook_name, notebook_id, notebook_url)
    except Exception as e:
        return {"status": "error", "error": str(e)}

    print(f"📚 Listing sources for notebook: {resolved_url}")

    try:
        with browser_session(headless=headless) as page:
            print("  🌐 Opening notebook...")
            page.goto(resolved_url, wait_until="domcontentloaded")

            # Wait for NotebookLM to load
            page.wait_for_url(re.compile(r"^https://notebooklm\.google\.com/"), timeout=15000)
            StealthUtils.random_delay(2000, 3000)

            # Click on Sources tab
            print("  🔍 Clicking Sources tab...")
            find_and_click(page, SOURCES_TAB_SELECTORS, "Sources tab", timeout=5000)
            StealthUtils.random_delay(1500, 2500)

            # Poll for at least 1 mat-checkbox to render (sources may be slow to load)
            print("  ⏳ Waiting for sources to render...")
            deadline = time.time() + 30
            while time.time() < deadline:
                count = page.evaluate('''() => {
                    const checkboxes = document.querySelectorAll('mat-checkbox');
                    let sourceCount = 0;
                    for (const cb of checkboxes) {
                        const row = cb.closest('[class*="source"]') || cb.parentElement?.parentElement;
                        if (!row) continue;
                        const rowText = (row.innerText || '').toLowerCase();
                        if (rowText.indexOf('select all') < 0) sourceCount++;
                    }
                    return sourceCount;
                }''')
                if count > 0:
                    print(f"  ✓ Sources rendered ({count} found)")
                    break
                time.sleep(2)

            print("  🔍 Looking for sources...")

            # Scroll-and-collect: keep scrolling until no new sources found
            all_sources = []
            seen_names = set()
            max_scroll_attempts = 30
            scroll_attempt = 0
            last_count = 0
            no_new_sources_count = 0

            print("  📜 Scrolling to load all sources...")

            while scroll_attempt < max_scroll_attempts:
                scroll_attempt += 1

                # Extract sources using DOM query (more reliable than text parsing)
                try:
                    sources_data = page.evaluate('''() => {
                        const sources = [];

                        // Find all mat-checkbox elements (each source has one)
                        const checkboxes = document.querySelectorAll('mat-checkbox');

                        for (const checkbox of checkboxes) {
                            // Get the parent row to find the source name
                            const row = checkbox.closest('[class*="source"]') ||
                                       checkbox.parentElement?.parentElement ||
                                       checkbox.parentElement;
                            if (!row) continue;

                            const rowText = row.innerText || row.textContent || '';

                            // Skip "Select all sources" row
                            if (rowText.toLowerCase().indexOf('select all') >= 0) continue;

                            // Get checkbox state - check multiple ways
                            const input = checkbox.querySelector('input[type="checkbox"]');
                            const isChecked = input ? input.checked :
                                            checkbox.classList.contains('mat-mdc-checkbox-checked') ||
                                            checkbox.classList.contains('mat-checkbox-checked');

                            // Extract source name (first non-empty line with length > 10)
                            const lines = rowText.split('\\n').map(l => l.trim()).filter(l => l.length > 10);
                            // Filter out icon names and other noise
                            const nameLines = lines.filter(l => {
                                const lower = l.toLowerCase();
                                return lower !== 'markdown' &&
                                       lower !== 'web' &&
                                       lower !== 'youtube' &&
                                       !lower.startsWith('drive_') &&
                                       !lower.startsWith('video_');
                            });

                            if (nameLines.length === 0) continue;
                            const name = nameLines[0];

                            // Determine source type from icons in the row
                            let sourceType = 'Document';
                            const rowLower = rowText.toLowerCase();
                            if (rowLower.indexOf('youtube') >= 0) sourceType = 'YouTube';
                            else if (rowLower.indexOf('web') >= 0 && rowLower.indexOf('web ') < 0) sourceType = 'Website';
                            else if (rowLower.indexOf('drive_pdf') >= 0) sourceType = 'PDF';

                            sources.push({
                                name: name,
                                type: sourceType,
                                enabled: isChecked
                            });
                        }

                        return sources;
                    }''')

                    if sources_data:
                        for src in sources_data:
                            name = src.get('name', '')
                            name_lower = name.lower() if name else ''
                            if name and name_lower not in seen_names:
                                seen_names.add(name_lower)
                                all_sources.append(src)

                except Exception as e:
                    print(f"  ⚠️ Extraction error: {e}")

                current_count = len(all_sources)

                if current_count == last_count:
                    no_new_sources_count += 1
                    if no_new_sources_count >= 3:
                        break
                else:
                    no_new_sources_count = 0
                    if scroll_attempt == 1 or current_count % 10 == 0:
                        print(f"  ✓ Found {current_count} sources so far...")

                last_count = current_count

                # Scroll down
                try:
                    page.evaluate('''() => {
                        const containers = [
                            document.querySelector('mat-sidenav-content'),
                            document.querySelector('[class*="source-list"]'),
                            document.querySelector('[class*="sources-container"]'),
                        ];
                        for (const container of containers) {
                            if (container && container.scrollHeight > container.clientHeight) {
                                container.scrollTop += 500;
                                return true;
                            }
                        }
                        window.scrollBy(0, 500);
                        return false;
                    }''')
                    StealthUtils.random_delay(600, 1000)
                except Exception:
                    break

            if debug:
                debug_dir = Path(__file__).parent.parent / "data" / "debug"
                debug_dir.mkdir(parents=True, exist_ok=True)
                try:
                    page.screenshot(path=str(debug_dir / "list_sources.png"))
                    print(f"  📸 Screenshot saved to: {debug_dir / 'list_sources.png'}")
                except Exception as e:
                    print(f"  ⚠️ Could not save screenshot: {e}")

            print(f"  ✅ Found {len(all_sources)} sources")

            # Save as last used notebook
            set_last_notebook(resolved_url)

            return {
                "status": "success",
                "sources": all_sources,
                "count": len(all_sources),
                "notebook_url": resolved_url
            }

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return {"status": "error", "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description='List sources in a NotebookLM notebook')
    parser.add_argument('--notebook-url', help='Direct notebook URL')
    parser.add_argument('--notebook-id', help='Notebook UUID')
    parser.add_argument('--notebook-name', help='Notebook name (fuzzy match)')
    parser.add_argument('--show-browser', action='store_true', help='Show browser for debugging')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--debug', action='store_true', help='Save screenshot for debugging')

    args = parser.parse_args()

    result = list_sources(
        notebook_url=args.notebook_url,
        notebook_name=args.notebook_name,
        notebook_id=args.notebook_id,
        headless=not args.show_browser,
        output_format="json" if args.json else "table",
        debug=args.debug
    )

    if result["status"] == "success":
        sources = result["sources"]
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            if sources:
                enabled_count = sum(1 for s in sources if s.get('enabled', True))
                disabled_count = len(sources) - enabled_count
                print(f"\n📄 Sources ({len(sources)} total, {enabled_count} on, {disabled_count} off):\n")
                for i, src in enumerate(sources, 1):
                    status = "✅" if src.get('enabled', True) else "⬜"
                    print(f"  {i}. {status} {src.get('name', 'Unnamed')}")
                    if src.get('type') and src['type'] != 'Unknown':
                        print(f"        Type: {src['type']}")
                    print()
            else:
                print("\n📄 No sources found in this notebook.")
        return 0
    else:
        print(f"\n❌ Failed: {result.get('error', 'Unknown error')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
