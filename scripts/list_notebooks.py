#!/usr/bin/env python3
"""
List all notebooks from NotebookLM via browser automation
Fetches the actual notebooks from NotebookLM's UI
"""

import argparse
import json
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from browser_utils import browser_session, StealthUtils


NOTEBOOKLM_HOME = "https://notebooklm.google.com/"


def list_notebooks(headless: bool = True, output_format: str = "table", debug: bool = False) -> dict:
    """
    List all notebooks from NotebookLM

    Args:
        headless: Run browser in headless mode
        output_format: Output format (table, json)

    Returns:
        Dict with status and notebooks list
    """
    print("📚 Fetching notebooks from NotebookLM...")

    try:
        with browser_session(headless=headless) as page:
            print("  🌐 Opening NotebookLM...")
            page.goto(NOTEBOOKLM_HOME, wait_until="domcontentloaded")

            # Wait for page to load
            page.wait_for_url(re.compile(r"^https://notebooklm\.google\.com/"), timeout=15000)
            StealthUtils.random_delay(2000, 3000)

            # Click on "All" tab to see user's notebooks (not just featured)
            print("  🔍 Clicking 'All' tab...")
            all_tab_selectors = [
                'button:has-text("All")',
                '[role="tab"]:has-text("All")',
                'div[role="tab"]:has-text("All")',
                '.tab:has-text("All")',
            ]
            for selector in all_tab_selectors:
                try:
                    tab = page.wait_for_selector(selector, timeout=5000, state="visible")
                    if tab:
                        tab.click()
                        print("  ✓ Clicked 'All' tab")
                        StealthUtils.random_delay(1500, 2500)
                        break
                except Exception:
                    continue

            print("  🔍 Looking for notebooks...")

            notebooks = []

            # Try multiple selectors for notebook items
            notebook_selectors = [
                # NotebookLM Angular component patterns (from actual page structure)
                'project-button:not(.featured-project-card *) .project-button-card:not(.featured-project-card)',
                'project-button .project-button-card.blue-background',  # User notebooks have blue-background
                '.my-projects-container project-button',
                # Fallback patterns
                '[data-notebook-id]',
                '.notebook-card',
                '.notebook-item',
                'a[href*="/notebook/"]',
            ]

            notebook_elements = []

            for selector in notebook_selectors:
                try:
                    elements = page.query_selector_all(selector)
                    if elements:
                        notebook_elements = elements
                        print(f"  ✓ Found {len(elements)} notebooks using: {selector}")
                        break
                except Exception:
                    continue

            # If no specific selectors work, try finding all notebook links
            if not notebook_elements:
                try:
                    # Find all links to notebooks
                    all_links = page.query_selector_all('a[href*="/notebook/"]')
                    # Deduplicate by href
                    seen_urls = set()
                    for link in all_links:
                        href = link.get_attribute('href')
                        if href and href not in seen_urls:
                            seen_urls.add(href)
                            notebook_elements.append(link)
                    if notebook_elements:
                        print(f"  ✓ Found {len(notebook_elements)} notebook links")
                except Exception:
                    pass

            if not notebook_elements:
                print("  ⚠️ No notebooks found with selectors. Checking page content...")

                if debug:
                    # Save screenshot and HTML for debugging
                    debug_dir = Path(__file__).parent.parent / "data" / "debug"
                    debug_dir.mkdir(parents=True, exist_ok=True)
                    try:
                        page.screenshot(path=str(debug_dir / "notebooklm_home.png"))
                        print(f"  📸 Screenshot saved to: {debug_dir / 'notebooklm_home.png'}")
                    except Exception as e:
                        print(f"  ⚠️ Could not save screenshot: {e}")
                    try:
                        html = page.content()
                        with open(debug_dir / "notebooklm_home.html", "w") as f:
                            f.write(html)
                        print(f"  📄 HTML saved to: {debug_dir / 'notebooklm_home.html'}")
                    except Exception as e:
                        print(f"  ⚠️ Could not save HTML: {e}")

                # Try to get any visible text for debugging
                try:
                    page_text = page.inner_text('body')
                    if "Create new notebook" in page_text or "New notebook" in page_text:
                        print("  ℹ️ NotebookLM loaded but no notebooks exist yet")
                        return {"status": "success", "notebooks": [], "count": 0}
                except Exception:
                    pass
                return {"status": "error", "error": "Could not find notebooks on page"}

            # Extract notebook info
            for element in notebook_elements:
                try:
                    notebook_info = {}

                    # Extract ID from aria-labelledby attribute (e.g., "project-UUID-title")
                    # or from button's aria-labelledby
                    notebook_id = None
                    try:
                        button = element.query_selector('button[aria-labelledby]')
                        if button:
                            aria_labelledby = button.get_attribute('aria-labelledby')
                            if aria_labelledby:
                                # Extract UUID from "project-UUID-title project-UUID-emoji"
                                match = re.search(r'project-([a-f0-9-]+)-', aria_labelledby)
                                if match:
                                    notebook_id = match.group(1)
                    except Exception:
                        pass

                    # Also try from element IDs
                    if not notebook_id:
                        try:
                            title_el = element.query_selector('[id*="project-"][id*="-title"]')
                            if title_el:
                                el_id = title_el.get_attribute('id')
                                match = re.search(r'project-([a-f0-9-]+)-title', el_id)
                                if match:
                                    notebook_id = match.group(1)
                        except Exception:
                            pass

                    if notebook_id:
                        notebook_info['id'] = notebook_id
                        notebook_info['url'] = f"https://notebooklm.google.com/notebook/{notebook_id}"

                    # Get name from .project-button-title
                    name = None
                    try:
                        title_el = element.query_selector('.project-button-title')
                        if title_el:
                            name = title_el.inner_text().strip()
                    except Exception:
                        pass

                    # Fallback to inner text
                    if not name:
                        try:
                            text = element.inner_text().strip()
                            lines = [l.strip() for l in text.split('\n') if l.strip()]
                            # Skip emoji and get first real text
                            for line in lines:
                                if len(line) > 2 and not line.startswith('more'):  # Skip emoji and menu icon
                                    name = line
                                    break
                        except Exception:
                            pass

                    if name:
                        notebook_info['name'] = name
                    elif notebook_id:
                        notebook_info['name'] = f"Notebook {notebook_id[:8]}..."

                    # Get date and source count from subtitle
                    try:
                        subtitle_parts = element.query_selector_all('.project-button-subtitle-part')
                        for part in subtitle_parts:
                            text = part.inner_text().strip()
                            if 'source' in text.lower():
                                notebook_info['sources'] = text
                            elif text and not notebook_info.get('last_modified'):
                                notebook_info['last_modified'] = text
                    except Exception:
                        pass

                    if notebook_info.get('id'):
                        notebooks.append(notebook_info)

                except Exception as e:
                    print(f"  ⚠️ Error parsing notebook: {e}")
                    continue

            # Deduplicate by URL
            seen_urls = set()
            unique_notebooks = []
            for nb in notebooks:
                url = nb.get('url')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    unique_notebooks.append(nb)

            print(f"  ✅ Found {len(unique_notebooks)} notebooks")

            return {
                "status": "success",
                "notebooks": unique_notebooks,
                "count": len(unique_notebooks)
            }

    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description='List notebooks from NotebookLM')

    parser.add_argument('--show-browser', action='store_true', help='Show browser for debugging')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--debug', action='store_true', help='Save screenshot and HTML for debugging')

    args = parser.parse_args()

    result = list_notebooks(
        headless=not args.show_browser,
        output_format="json" if args.json else "table",
        debug=args.debug
    )

    if result["status"] == "success":
        notebooks = result["notebooks"]

        if args.json:
            print(json.dumps(notebooks, indent=2, ensure_ascii=False))
        else:
            if notebooks:
                print(f"\n📚 NotebookLM Notebooks ({len(notebooks)}):\n")
                for i, nb in enumerate(notebooks, 1):
                    print(f"  {i}. {nb.get('name', 'Unnamed')}")
                    if nb.get('id'):
                        print(f"     ID: {nb['id']}")
                    if nb.get('url'):
                        print(f"     URL: {nb['url']}")
                    if nb.get('last_modified'):
                        print(f"     Modified: {nb['last_modified']}")
                    if nb.get('sources'):
                        print(f"     Sources: {nb['sources']}")
                    print()
            else:
                print("\n📚 No notebooks found. Create one at https://notebooklm.google.com/")
        return 0
    else:
        print(f"\n❌ Failed: {result.get('error', 'Unknown error')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
