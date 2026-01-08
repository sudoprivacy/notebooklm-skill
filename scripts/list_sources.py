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

        sources = []

        # Try multiple selectors to find source items
        source_selectors = [
            # NotebookLM source item patterns
            'source-item',
            '.source-item',
            '[data-source-id]',
            '.sources-list source-item',
            'source-selector source-item',
            # Source cards
            '.source-card',
            '.source-entry',
            # List items in sources panel
            '.sources-panel li',
            '[role="listitem"]',
        ]

        source_elements = []

        for selector in source_selectors:
            try:
                elements = page.query_selector_all(selector)
                if elements and len(elements) > 0:
                    source_elements = elements
                    print(f"  ✓ Found {len(elements)} sources using: {selector}")
                    break
            except Exception:
                continue

        # If no specific selectors work, try to extract from page content
        if not source_elements:
            print("  🔍 Trying alternative extraction method...")
            try:
                # Look for any clickable items in sources panel
                # NotebookLM uses Angular components
                source_elements = page.query_selector_all('source-selector [role="button"]')
                if source_elements:
                    print(f"  ✓ Found {len(source_elements)} sources via source-selector")
            except Exception:
                pass

        if not source_elements:
            # Try extracting from the page using JavaScript
            try:
                sources_data = page.evaluate('''() => {
                    const sources = [];
                    const seenNames = new Set();

                    // Helper to add unique source
                    const addSource = (name, type) => {
                        if (!name || name.length < 5) return;
                        // Filter out HTML/CSS artifacts
                        const lowerName = name.toLowerCase();
                        const skipPatterns = [
                            'select all', 'add source', 'search', 'web', 'fast research',
                            'markdown', 'ideo_', 'youtube', 'video_', 'icon', 'button',
                            'checkbox', 'mat-', 'ng-', 'class=', 'style=', 'aria-'
                        ];
                        if (skipPatterns.some(p => lowerName === p || (lowerName.length < 15 && lowerName.includes(p)))) {
                            return;
                        }
                        // Must have at least one letter and one space, or be a filename with extension
                        const hasSpace = name.includes(' ');
                        const isFilename = /\\.\\w{2,4}$/.test(name);
                        if (!hasSpace && !isFilename) return;

                        if (!seenNames.has(lowerName)) {
                            seenNames.add(lowerName);
                            sources.push({ name, type: type || 'Document' });
                        }
                    };

                    // Try to find source items
                    const sourceItems = document.querySelectorAll('source-item, .source-item, [data-source-id]');
                    sourceItems.forEach(item => {
                        const name = item.querySelector('.source-title, .title, h3, [class*="title"]')?.textContent?.trim();
                        const type = item.querySelector('.source-type, .type, [class*="type"]')?.textContent?.trim();
                        addSource(name, type);
                    });

                    // Look for checkbox items in sources panel (NotebookLM uses checkboxes for sources)
                    // Find the sources section first
                    const sourcesSection = document.querySelector('source-selector, [class*="source"]');
                    if (sourcesSection) {
                        // Find all list items or checkbox containers
                        const items = sourcesSection.querySelectorAll('mat-checkbox, [role="checkbox"], [role="listitem"]');
                        items.forEach(item => {
                            let label = item.textContent?.trim();
                            // Skip "Select all sources" and other UI elements
                            if (label &&
                                !label.toLowerCase().includes('select all') &&
                                !label.toLowerCase().includes('add source') &&
                                !label.toLowerCase().includes('search') &&
                                label.length > 3) {
                                // Clean up the label
                                label = label.replace(/^\\s*check_box.*?\\s*/i, '').trim();
                                // Determine type based on icon - YouTube has red icon, documents have blue
                                let type = 'Document';
                                const parentRow = item.closest('[class*="row"], [class*="item"], mat-checkbox')?.parentElement || item;
                                const hasYouTubeIcon = parentRow.innerHTML.includes('youtube') ||
                                                       parentRow.innerHTML.includes('YouTube') ||
                                                       parentRow.querySelector('img[src*="youtube"]') !== null ||
                                                       parentRow.querySelector('[style*="red"]') !== null;
                                if (hasYouTubeIcon) {
                                    type = 'YouTube';
                                }
                                addSource(label, type);
                            }
                        });
                    }

                    // Alternative: Look for source entries by their container structure
                    if (sources.length === 0) {
                        // NotebookLM source entries often have an icon + text structure
                        const allCheckboxes = document.querySelectorAll('mat-checkbox');
                        allCheckboxes.forEach(cb => {
                            const text = cb.textContent?.trim();
                            if (text &&
                                !text.toLowerCase().includes('select all') &&
                                text.length > 5) {
                                // Try to detect YouTube vs document
                                const parent = cb.closest('[class*="source"]') || cb;
                                const isYouTube = parent.innerHTML.toLowerCase().includes('youtube') ||
                                                  parent.querySelector('svg[class*="youtube"]') !== null;
                                addSource(text, isYouTube ? 'YouTube' : 'Document');
                            }
                        });
                    }

                    // Fallback: Look at page text for source names (between "Select all sources" and "Add sources")
                    if (sources.length === 0) {
                        const bodyText = document.body.innerText;
                        // Find text between source list markers
                        const selectAllIdx = bodyText.indexOf('Select all sources');
                        if (selectAllIdx !== -1) {
                            // Get text after "Select all sources"
                            const afterSelectAll = bodyText.substring(selectAllIdx + 20);
                            const lines = afterSelectAll.split('\\n')
                                .map(l => l.trim())
                                .filter(l => l.length > 5 &&
                                           !l.includes('Add source') &&
                                           !l.includes('Search') &&
                                           !l.includes('Web') &&
                                           !l.includes('Fast Research'));
                            // Take first few lines as sources
                            lines.slice(0, 10).forEach(line => {
                                addSource(line, 'Document');
                            });
                        }
                    }

                    return sources;
                }''')

                if sources_data:
                    sources = sources_data
                    print(f"  ✓ Extracted {len(sources)} sources via JavaScript")
            except Exception as e:
                print(f"  ⚠️ JavaScript extraction failed: {e}")

        # Extract from found elements if we have them
        if source_elements and not sources:
            for element in source_elements:
                try:
                    source_info = {}

                    # Get source name/title
                    name = None
                    try:
                        title_el = element.query_selector('.source-title, .title, h3, [class*="title"]')
                        if title_el:
                            name = title_el.inner_text().strip()
                    except Exception:
                        pass

                    if not name:
                        try:
                            name = element.inner_text().strip().split('\n')[0]
                        except Exception:
                            pass

                    if name:
                        source_info['name'] = name

                    # Get source type
                    try:
                        type_el = element.query_selector('.source-type, .type, [class*="type"]')
                        if type_el:
                            source_info['type'] = type_el.inner_text().strip()
                    except Exception:
                        pass

                    # Get source ID
                    try:
                        source_id = element.get_attribute('data-source-id')
                        if source_id:
                            source_info['id'] = source_id
                    except Exception:
                        pass

                    if source_info.get('name'):
                        sources.append(source_info)

                except Exception as e:
                    print(f"  ⚠️ Error parsing source: {e}")
                    continue

        # Deduplicate by name
        seen_names = set()
        unique_sources = []
        for src in sources:
            name = src.get('name', '')
            if name and name not in seen_names:
                seen_names.add(name)
                unique_sources.append(src)

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
