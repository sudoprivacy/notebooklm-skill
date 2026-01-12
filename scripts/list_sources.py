#!/usr/bin/env python3
"""
List all sources in a NotebookLM notebook via browser automation
"""

import argparse
import json
import sys
import re
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

                # Extract sources by parsing body text
                try:
                    sources_data = page.evaluate('''() => {
                        const bodyText = document.body.innerText;
                        const lines = bodyText.split(String.fromCharCode(10));

                        let startIdx = -1;
                        for (let i = 0; i < lines.length; i++) {
                            if (lines[i].toLowerCase().indexOf('select all') >= 0) {
                                startIdx = i + 1;
                                break;
                            }
                        }

                        if (startIdx === -1) return [];

                        const iconPrefixes = ['markdown', 'web', 'drive_pdf', 'youtube', 'video_youtube', 'check_box', 'check_box_outline_blank'];
                        const sources = [];

                        for (let i = startIdx; i < lines.length; i++) {
                            const line = lines[i].trim();
                            if (!line) continue;

                            const lowerLine = line.toLowerCase();
                            if (lowerLine === 'chat' || lowerLine === 'studio' ||
                                lowerLine === 'add sources' || lowerLine.indexOf('notebook guide') >= 0) {
                                break;
                            }

                            if (iconPrefixes.indexOf(lowerLine) >= 0) continue;
                            if (lowerLine.indexOf('video_') === 0 || lowerLine.indexOf('drive_') === 0) continue;

                            if (line.length > 10) {
                                let sourceType = 'Document';
                                if (i > 0) {
                                    const prevLine = lines[i - 1].trim().toLowerCase();
                                    if (prevLine === 'youtube') sourceType = 'YouTube';
                                    else if (prevLine === 'web') sourceType = 'Website';
                                    else if (prevLine === 'drive_pdf') sourceType = 'PDF';
                                }
                                sources.push({ name: line, type: sourceType });
                            }
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
                print(f"\n📄 Sources ({len(sources)}):\n")
                for i, src in enumerate(sources, 1):
                    print(f"  {i}. {src.get('name', 'Unnamed')}")
                    if src.get('type') and src['type'] != 'Unknown':
                        print(f"     Type: {src['type']}")
                    print()
            else:
                print("\n📄 No sources found in this notebook.")
        return 0
    else:
        print(f"\n❌ Failed: {result.get('error', 'Unknown error')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
