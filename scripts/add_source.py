#!/usr/bin/env python3
"""
Add URL source to NotebookLM notebook
Supports websites and YouTube videos
"""

import argparse
import sys
import time
import re
from pathlib import Path

from patchright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))

from auth_manager import AuthManager
from notebook_manager import NotebookLibrary
from browser_utils import BrowserFactory, StealthUtils


# Selectors for adding sources
ADD_SOURCE_BUTTON_SELECTORS = [
    'button[aria-label="Add source"]',
    'button[aria-label="Add sources"]',
    'button:has-text("Add source")',
    'button:has-text("Add")',
    '[data-test-id="add-source-button"]',
    '.add-source-button',
    # Icons/buttons with + symbol
    'button:has(mat-icon:has-text("add"))',
    'button:has-text("+")',
    '[aria-label*="add" i]',
    '[aria-label*="Add" i]',
]

# Website/Link option in the add source dialog
WEBSITE_OPTION_SELECTORS = [
    'button:has-text("Websites")',  # Note: plural
    'button:has-text("Website")',
    ':has-text("Websites"):not(:has(*))',  # Text node with "Websites"
    '[data-source-type="website"]',
    '[data-source-type="link"]',
    'div:has-text("Websites")',
    'li:has-text("Websites")',
    # Try clicking on the link icon area
    ':has(mat-icon:has-text("link"))',
]

# YouTube option
YOUTUBE_OPTION_SELECTORS = [
    'button:has-text("YouTube")',
    '[data-source-type="youtube"]',
    'div[role="option"]:has-text("YouTube")',
    'li:has-text("YouTube")',
]

# URL input field
URL_INPUT_SELECTORS = [
    'textarea[placeholder*="Paste"]',  # "Paste any links"
    'textarea[placeholder*="links"]',
    'textarea[placeholder*="link"]',
    'textarea[placeholder*="URL"]',
    'input[type="url"]',
    'input[placeholder*="URL"]',
    'input[placeholder*="url"]',
    'input[placeholder*="link"]',
    'input[placeholder*="Link"]',
    'input[placeholder*="http"]',
    'input[aria-label*="URL"]',
    'input[name="url"]',
    # Generic
    'textarea:visible',
]

# Submit/Add button
SUBMIT_BUTTON_SELECTORS = [
    'button:has-text("Insert")',
    'button:has-text("Add")',
    'button:has-text("Submit")',
    'button[type="submit"]',
    '[data-test-id="submit-source"]',
]


def is_youtube_url(url: str) -> bool:
    """Check if URL is a YouTube video"""
    youtube_patterns = [
        r'youtube\.com/watch',
        r'youtu\.be/',
        r'youtube\.com/embed/',
    ]
    return any(re.search(pattern, url) for pattern in youtube_patterns)


def find_and_click(page, selectors: list, description: str, timeout: int = 10000) -> bool:
    """Try to find and click an element using multiple selectors"""
    for selector in selectors:
        try:
            element = page.wait_for_selector(selector, timeout=timeout, state="visible")
            if element:
                StealthUtils.random_delay(200, 500)
                StealthUtils.realistic_click(page, selector)
                print(f"  ✓ Clicked: {description}")
                return True
        except Exception:
            continue
    return False


def find_and_fill(page, selectors: list, text: str, description: str, timeout: int = 10000) -> bool:
    """Try to find an input and fill it using multiple selectors"""
    for selector in selectors:
        try:
            element = page.wait_for_selector(selector, timeout=timeout, state="visible")
            if element:
                StealthUtils.random_delay(200, 400)
                StealthUtils.human_type(page, selector, text)
                print(f"  ✓ Filled: {description}")
                return True
        except Exception:
            continue
    return False


def add_url_source(notebook_url: str, source_url: str, headless: bool = True) -> dict:
    """
    Add a URL source to a NotebookLM notebook

    Args:
        notebook_url: NotebookLM notebook URL
        source_url: URL to add as source (website or YouTube)
        headless: Run browser in headless mode

    Returns:
        Dict with status and details
    """
    auth = AuthManager()

    if not auth.is_authenticated():
        return {"status": "error", "error": "Not authenticated. Run: python auth_manager.py setup"}

    is_youtube = is_youtube_url(source_url)
    source_type = "YouTube" if is_youtube else "Website"

    print(f"📎 Adding {source_type} source: {source_url}")
    print(f"📚 Notebook: {notebook_url}")

    playwright = None
    context = None

    try:
        playwright = sync_playwright().start()
        context = BrowserFactory.launch_persistent_context(playwright, headless=headless)

        page = context.new_page()
        print("  🌐 Opening notebook...")
        page.goto(notebook_url, wait_until="domcontentloaded")

        # Wait for NotebookLM to load
        page.wait_for_url(re.compile(r"^https://notebooklm\.google\.com/"), timeout=15000)
        StealthUtils.random_delay(1000, 2000)


        # Step 0: Click on Sources tab first
        print("  🔍 Clicking Sources tab...")
        sources_tab_selectors = [
            'button:has-text("Sources")',
            '[role="tab"]:has-text("Sources")',
            'div:has-text("Sources"):not(:has(*))',  # Text-only div
            '.tab:has-text("Sources")',
        ]
        if not find_and_click(page, sources_tab_selectors, "Sources tab", timeout=5000):
            print("  ⚠️ Could not find Sources tab, continuing anyway...")

        StealthUtils.random_delay(1000, 1500)

        # Step 1: Click "Add source" button
        print("  🔍 Looking for Add source button...")
        if not find_and_click(page, ADD_SOURCE_BUTTON_SELECTORS, "Add source button"):
            # Try clicking on the sources panel first
            try:
                sources_panel = page.query_selector('[data-panel="sources"]')
                if sources_panel:
                    sources_panel.click()
                    StealthUtils.random_delay(500, 1000)
                    if not find_and_click(page, ADD_SOURCE_BUTTON_SELECTORS, "Add source button"):
                        raise Exception("Could not find Add source button")
            except Exception:
                raise Exception("Could not find Add source button")

        StealthUtils.random_delay(1500, 2500)  # Wait longer for dialog to appear

        # Step 2: Select source type (Website or YouTube)
        print(f"  🔍 Selecting {source_type}...")

        option_selectors = YOUTUBE_OPTION_SELECTORS if is_youtube else WEBSITE_OPTION_SELECTORS
        if not find_and_click(page, option_selectors, f"{source_type} option"):
            raise Exception(f"Could not find {source_type} option")

        StealthUtils.random_delay(1500, 2500)  # Wait for dialog to change

        # Step 3: Enter URL
        print("  📝 Entering URL...")
        if not find_and_fill(page, URL_INPUT_SELECTORS, source_url, "URL input"):
            raise Exception("Could not find URL input field")

        StealthUtils.random_delay(300, 600)

        # Step 4: Submit
        print("  📤 Submitting...")
        if not find_and_click(page, SUBMIT_BUTTON_SELECTORS, "Submit button"):
            # Try pressing Enter as fallback
            page.keyboard.press("Enter")
            print("  ✓ Pressed Enter to submit")

        # Step 5: Wait for processing
        print("  ⏳ Waiting for source to be added...")
        StealthUtils.random_delay(2000, 3000)

        # Check for success indicators or wait for the source to appear
        max_wait = 60  # 60 seconds max wait
        start_time = time.time()

        while time.time() - start_time < max_wait:
            # Check for error messages
            try:
                error_element = page.query_selector('.error-message, [role="alert"]')
                if error_element and error_element.is_visible():
                    error_text = error_element.inner_text()
                    if error_text:
                        raise Exception(f"Error adding source: {error_text}")
            except Exception as e:
                if "Error adding source" in str(e):
                    raise

            # Check for loading indicators
            try:
                loading = page.query_selector('.loading, .spinner, [aria-busy="true"]')
                if loading and loading.is_visible():
                    time.sleep(1)
                    continue
            except Exception:
                pass

            # Check if source was added (look for the URL in sources list)
            try:
                # Look for the source in the list
                sources = page.query_selector_all('.source-item, [data-source-url]')
                for source in sources:
                    if source_url in (source.get_attribute('data-source-url') or source.inner_text()):
                        print("  ✅ Source added successfully!")
                        return {
                            "status": "success",
                            "source_url": source_url,
                            "source_type": source_type,
                            "notebook_url": notebook_url
                        }
            except Exception:
                pass

            time.sleep(2)

        # If we get here, assume it worked (no error found)
        print("  ✅ Source submission completed (verification timeout)")
        return {
            "status": "success",
            "source_url": source_url,
            "source_type": source_type,
            "notebook_url": notebook_url,
            "note": "Could not verify source was added, please check manually"
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
    parser = argparse.ArgumentParser(description='Add URL source to NotebookLM')

    parser.add_argument('--url', required=True, help='URL to add as source (website or YouTube)')
    parser.add_argument('--notebook-url', help='NotebookLM notebook URL')
    parser.add_argument('--notebook-id', help='Notebook ID from library')
    parser.add_argument('--show-browser', action='store_true', help='Show browser for debugging')

    args = parser.parse_args()

    # Resolve notebook URL
    notebook_url = args.notebook_url

    if not notebook_url and args.notebook_id:
        library = NotebookLibrary()
        notebook = library.get_notebook(args.notebook_id)
        if notebook:
            notebook_url = notebook['url']
        else:
            print(f"❌ Notebook '{args.notebook_id}' not found")
            return 1

    if not notebook_url:
        library = NotebookLibrary()
        active = library.get_active_notebook()
        if active:
            notebook_url = active['url']
            print(f"📚 Using active notebook: {active['name']}")
        else:
            print("❌ No notebook specified. Use --notebook-url or --notebook-id")
            print("   Or set an active notebook: notebook_manager.py activate --id ID")
            return 1

    result = add_url_source(
        notebook_url=notebook_url,
        source_url=args.url,
        headless=not args.show_browser
    )

    if result["status"] == "success":
        print(f"\n✅ Added {result.get('source_type', 'URL')} source: {result['source_url']}")
        if result.get("note"):
            print(f"   Note: {result['note']}")
        return 0
    else:
        print(f"\n❌ Failed: {result.get('error', 'Unknown error')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
