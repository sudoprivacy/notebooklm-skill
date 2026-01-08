#!/usr/bin/env python3
"""
List all sources in a NotebookLM notebook via browser automation
"""

import argparse
import json
import sys
import re
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
        # Fetch notebooks and find by name (fuzzy match)
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
    last_notebook = get_last_notebook()
    if last_notebook:
        return last_notebook

    raise Exception("No notebook specified. Use --notebook-name, --notebook-id, or --notebook-url")


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

    Args:
        notebook_url: Direct notebook URL
        notebook_name: Notebook name (fuzzy match)
        notebook_id: Notebook UUID
        headless: Run browser in headless mode
        output_format: Output format (table, json)
        debug: Save screenshot for debugging

    Returns:
        Dict with status and sources list
    """
    auth = AuthManager()

    if not auth.is_authenticated():
        return {"status": "error", "error": "Not authenticated. Run: python auth_manager.py setup"}

    # Resolve notebook URL
    try:
        resolved_url = find_notebook_url(notebook_name, notebook_id, notebook_url)
    except Exception as e:
        return {"status": "error", "error": str(e)}

    print(f"📚 Listing sources for notebook: {resolved_url}")

    playwright = None
    context = None

    try:
        playwright = sync_playwright().start()
        context = BrowserFactory.launch_persistent_context(playwright, headless=headless)

        page = context.new_page()
        print("  🌐 Opening notebook...")
        page.goto(resolved_url, wait_until="domcontentloaded")

        # Wait for NotebookLM to load
        page.wait_for_url(re.compile(r"^https://notebooklm\.google\.com/"), timeout=15000)
        StealthUtils.random_delay(2000, 3000)

        # Click on Sources tab
        print("  🔍 Clicking Sources tab...")
        sources_tab_selectors = [
            'button:has-text("Sources")',
            '[role="tab"]:has-text("Sources")',
            'div:has-text("Sources"):not(:has(*))',
            '.tab:has-text("Sources")',
        ]
        for selector in sources_tab_selectors:
            try:
                tab = page.wait_for_selector(selector, timeout=5000, state="visible")
                if tab:
                    tab.click()
                    print("  ✓ Clicked Sources tab")
                    StealthUtils.random_delay(1500, 2500)
                    break
            except Exception:
                continue

        print("  🔍 Looking for sources...")

        # Find the scrollable sources container
        scroll_container_selectors = [
            'source-selector',
            '.sources-panel',
            '[class*="source-list"]',
            '[class*="sources-container"]',
        ]

        scroll_container = None
        for selector in scroll_container_selectors:
            try:
                container = page.query_selector(selector)
                if container:
                    scroll_container = container
                    break
            except Exception:
                continue

        # Scroll-and-collect: keep scrolling until no new sources found
        all_sources = []
        seen_names = set()
        max_scroll_attempts = 30  # Safety limit for large notebooks
        scroll_attempt = 0
        last_count = 0
        no_new_sources_count = 0

        print("  📜 Scrolling to load all sources...")

        while scroll_attempt < max_scroll_attempts:
            scroll_attempt += 1

            # Extract sources by parsing body text (more reliable than DOM queries)
            # NotebookLM uses Angular which makes textContent empty for mat-checkbox
            try:
                sources_data = page.evaluate('''() => {
                    const bodyText = document.body.innerText;
                    const lines = bodyText.split(String.fromCharCode(10));

                    // Find index of 'Select all sources'
                    let startIdx = -1;
                    for (let i = 0; i < lines.length; i++) {
                        if (lines[i].toLowerCase().indexOf('select all') >= 0) {
                            startIdx = i + 1;
                            break;
                        }
                    }

                    if (startIdx === -1) return [];

                    // Icon prefixes to skip (appear before source names)
                    const iconPrefixes = ['markdown', 'web', 'drive_pdf', 'youtube', 'video_youtube', 'check_box', 'check_box_outline_blank'];
                    const sources = [];

                    for (let i = startIdx; i < lines.length; i++) {
                        const line = lines[i].trim();
                        if (!line) continue;

                        // Stop at navigation elements
                        const lowerLine = line.toLowerCase();
                        if (lowerLine === 'chat' || lowerLine === 'studio' ||
                            lowerLine === 'add sources' || lowerLine.indexOf('notebook guide') >= 0) {
                            break;
                        }

                        // Skip icon prefix lines
                        if (iconPrefixes.indexOf(lowerLine) >= 0) continue;
                        // Skip lines that look like icon identifiers (video_*, drive_*, etc.)
                        if (lowerLine.indexOf('video_') === 0 || lowerLine.indexOf('drive_') === 0) continue;

                        // Source names are typically longer than 10 chars
                        if (line.length > 10) {
                            // Determine type based on the previous line (icon prefix)
                            let sourceType = 'Document';
                            if (i > 0) {
                                const prevLine = lines[i - 1].trim().toLowerCase();
                                if (prevLine === 'youtube') sourceType = 'YouTube';
                                else if (prevLine === 'web') sourceType = 'Website';
                                else if (prevLine === 'drive_pdf') sourceType = 'PDF';
                                else if (prevLine === 'markdown') sourceType = 'Document';
                            }
                            sources.push({ name: line, type: sourceType });
                        }
                    }

                    return sources;
                }''')

                # Add newly found sources
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

            # Check if we found new sources
            if current_count == last_count:
                no_new_sources_count += 1
                if no_new_sources_count >= 3:
                    # No new sources after 3 scroll attempts, we're done
                    break
            else:
                no_new_sources_count = 0
                if scroll_attempt == 1 or current_count % 10 == 0:
                    print(f"  ✓ Found {current_count} sources so far...")

            last_count = current_count

            # Scroll down to load more sources
            try:
                page.evaluate('''() => {
                    // Try to find and scroll the sources container
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

                    // Fallback: scroll the page
                    window.scrollBy(0, 500);
                    return false;
                }''')
                StealthUtils.random_delay(600, 1000)
            except Exception:
                break

        unique_sources = all_sources

        if debug:
            # Save screenshot for debugging
            debug_dir = Path(__file__).parent.parent / "data" / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            try:
                page.screenshot(path=str(debug_dir / "list_sources.png"))
                print(f"  📸 Screenshot saved to: {debug_dir / 'list_sources.png'}")
            except Exception as e:
                print(f"  ⚠️ Could not save screenshot: {e}")

        print(f"  ✅ Found {len(unique_sources)} sources")

        # Save as last used notebook
        set_last_notebook(resolved_url)

        return {
            "status": "success",
            "sources": unique_sources,
            "count": len(unique_sources),
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
    parser = argparse.ArgumentParser(description='List sources in a NotebookLM notebook')

    # Notebook selection (mutually exclusive priority: url > id > name > last used)
    parser.add_argument('--notebook-url', help='Direct notebook URL')
    parser.add_argument('--notebook-id', help='Notebook UUID')
    parser.add_argument('--notebook-name', help='Notebook name (fuzzy match)')

    # Output options
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
                    if src.get('id'):
                        print(f"     ID: {src['id']}")
                    print()
            else:
                print("\n📄 No sources found in this notebook.")
        return 0
    else:
        print(f"\n❌ Failed: {result.get('error', 'Unknown error')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
