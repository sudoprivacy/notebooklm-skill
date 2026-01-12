#!/usr/bin/env python3
"""
Add source to NotebookLM notebook
Supports: websites, YouTube videos, and local files (PDF, TXT, etc.)
"""

import argparse
import sys
import time
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from notebook_config import get_last_notebook, set_last_notebook
from browser_utils import browser_session, StealthUtils, find_and_click, find_and_fill
from config import SOURCES_TAB_SELECTORS, ADD_SOURCE_BUTTON_SELECTORS
from list_notebooks import list_notebooks

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
    is_youtube = is_youtube_url(source_url)
    source_type = "YouTube" if is_youtube else "Website"

    print(f"📎 Adding {source_type} source: {source_url}")
    print(f"📚 Notebook: {notebook_url}")

    try:
        with browser_session(headless=headless) as page:
            print("  🌐 Opening notebook...")
            page.goto(notebook_url, wait_until="domcontentloaded")

            # Wait for NotebookLM to load
            page.wait_for_url(re.compile(r"^https://notebooklm\.google\.com/"), timeout=15000)
            StealthUtils.random_delay(1000, 2000)

            # Step 0: Click on Sources tab first
            print("  🔍 Clicking Sources tab...")
            if not find_and_click(page, SOURCES_TAB_SELECTORS, "Sources tab", timeout=5000):
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


def add_file_source(notebook_url: str, file_path: str, headless: bool = True) -> dict:
    """
    Upload a local file as source to a NotebookLM notebook

    Args:
        notebook_url: NotebookLM notebook URL
        file_path: Path to local file (PDF, TXT, MD, etc.)
        headless: Run browser in headless mode

    Returns:
        Dict with status and details
    """
    # Validate file exists
    file_path = Path(file_path).resolve()
    if not file_path.exists():
        return {"status": "error", "error": f"File not found: {file_path}"}

    file_name = file_path.name
    print(f"📄 Uploading file: {file_name}")
    print(f"📚 Notebook: {notebook_url}")

    try:
        with browser_session(headless=headless) as page:
            print("  🌐 Opening notebook...")
            page.goto(notebook_url, wait_until="domcontentloaded")

            # Wait for NotebookLM to load
            page.wait_for_url(re.compile(r"^https://notebooklm\.google\.com/"), timeout=15000)
            StealthUtils.random_delay(2000, 3000)

            # Step 1: Click on Sources tab
            print("  🔍 Clicking Sources tab...")
            find_and_click(page, SOURCES_TAB_SELECTORS, "Sources tab", timeout=5000)
            StealthUtils.random_delay(1000, 1500)

            # Step 2: Click "Add source" or "Upload" button
            print("  🔍 Looking for upload option...")

            # First try to find and click Add source button
            add_clicked = find_and_click(page, ADD_SOURCE_BUTTON_SELECTORS, "Add source button", timeout=5000)
            if add_clicked:
                StealthUtils.random_delay(1000, 2000)

            # Now look for "Upload files" option or file input
            upload_selectors = [
                'button:has-text("Upload files")',
                'button:has-text("Upload")',
                ':has-text("Upload files"):not(:has(*))',
                '[aria-label*="upload" i]',
                'button:has(mat-icon:has-text("upload"))',
            ]

            upload_clicked = find_and_click(page, upload_selectors, "Upload files", timeout=5000)
            StealthUtils.random_delay(1000, 1500)

            # Step 3: Find file input and upload
            print("  📤 Uploading file...")

            # Look for file input element (might be hidden)
            file_input_selectors = [
                'input[type="file"]',
                'input[accept*="pdf"]',
                'input[accept*="text"]',
            ]

            file_input = None
            for selector in file_input_selectors:
                try:
                    file_input = page.query_selector(selector)
                    if file_input:
                        break
                except Exception:
                    continue

            if file_input:
                # Use set_input_files to upload
                file_input.set_input_files(str(file_path))
                print(f"  ✓ Selected file: {file_name}")
            else:
                # Try using page.set_input_files with a more general approach
                # Sometimes the input is dynamically created
                try:
                    # Wait for any file input to appear
                    file_input = page.wait_for_selector('input[type="file"]', timeout=5000)
                    if file_input:
                        file_input.set_input_files(str(file_path))
                        print(f"  ✓ Selected file: {file_name}")
                    else:
                        raise Exception("Could not find file input element")
                except Exception:
                    raise Exception("Could not find file input element for upload")

            # Step 4: Wait for upload to complete
            print("  ⏳ Waiting for upload to complete...")
            StealthUtils.random_delay(2000, 3000)

            # Check for processing/upload progress
            max_wait = 120  # 2 minutes max for file upload
            start_time = time.time()

            while time.time() - start_time < max_wait:
                # Check for error messages
                try:
                    error_element = page.query_selector('.error-message, [role="alert"]')
                    if error_element and error_element.is_visible():
                        error_text = error_element.inner_text()
                        if error_text and "error" in error_text.lower():
                            raise Exception(f"Upload error: {error_text}")
                except Exception as e:
                    if "Upload error" in str(e):
                        raise

                # Check for loading/progress indicators
                try:
                    loading = page.query_selector('.loading, .spinner, [aria-busy="true"], .progress')
                    if loading and loading.is_visible():
                        time.sleep(2)
                        continue
                except Exception:
                    pass

                # Check if upload dialog closed (success indicator)
                try:
                    # If the upload dialog is gone and we're back to the notebook view
                    sources_panel = page.query_selector('.sources-panel, [data-panel="sources"]')
                    if sources_panel:
                        # Look for the file in the sources list
                        source_items = page.query_selector_all('.source-item, .source-card, [class*="source"]')
                        for item in source_items:
                            try:
                                item_text = item.inner_text()
                                if file_name.split('.')[0].lower() in item_text.lower():
                                    print("  ✅ File uploaded successfully!")
                                    return {
                                        "status": "success",
                                        "file_path": str(file_path),
                                        "file_name": file_name,
                                        "source_type": "File",
                                        "notebook_url": notebook_url
                                    }
                            except Exception:
                                continue
                except Exception:
                    pass

                time.sleep(2)

            # Assume success if no error
            print("  ✅ Upload completed (verification timeout)")
            return {
                "status": "success",
                "file_path": str(file_path),
                "file_name": file_name,
                "source_type": "File",
                "notebook_url": notebook_url,
                "note": "Could not verify file was added, please check manually"
            }

    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}


def find_notebook_by_name(name: str) -> dict | None:
    """Find notebook by name (fuzzy match)"""
    result = list_notebooks(headless=True)
    if result["status"] != "success":
        return None
    for nb in result["notebooks"]:
        if name.lower() in nb.get("name", "").lower():
            return nb
    return None


def main():
    parser = argparse.ArgumentParser(description='Add source to NotebookLM (URL or local file)')

    # Source options (mutually exclusive)
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument('--url', help='URL to add as source (website or YouTube)')
    source_group.add_argument('--file', help='Local file to upload (PDF, TXT, MD, etc.)')

    parser.add_argument('--notebook-url', help='Full NotebookLM notebook URL')
    parser.add_argument('--notebook-id', help='Notebook UUID')
    parser.add_argument('--notebook-name', help='Notebook name (fuzzy match)')
    parser.add_argument('--show-browser', action='store_true', help='Show browser for debugging')

    args = parser.parse_args()

    # Resolve notebook URL (priority: url > id > name > last used)
    notebook_url = args.notebook_url
    notebook_id = None
    notebook_name = None

    if notebook_url:
        # Extract ID from URL
        match = re.search(r'/notebook/([a-f0-9-]+)', notebook_url)
        if match:
            notebook_id = match.group(1)

    if not notebook_url and args.notebook_id:
        notebook_id = args.notebook_id
        notebook_url = f"https://notebooklm.google.com/notebook/{notebook_id}"

    if not notebook_url and args.notebook_name:
        print(f"🔍 Looking for notebook: {args.notebook_name}")
        nb = find_notebook_by_name(args.notebook_name)
        if nb:
            notebook_url = nb["url"]
            notebook_id = nb["id"]
            notebook_name = nb.get("name", "")
            print(f"📚 Found: {nb['name']}")
        else:
            print(f"❌ No notebook found matching: {args.notebook_name}")
            return 1

    if not notebook_url:
        last = get_last_notebook()
        if last:
            notebook_url = last["url"]
            notebook_id = last["id"]
            notebook_name = last.get("name", "")
            print(f"📚 Using last notebook: {last.get('name') or last['id']}")
        else:
            print("❌ No notebook specified. Options:")
            print("  --notebook-url URL     Full NotebookLM URL")
            print("  --notebook-id UUID     Notebook UUID")
            print("  --notebook-name NAME   Fuzzy match by name")
            print("")
            print("List available notebooks:")
            print("  python scripts/run.py list_notebooks.py")
            return 1

    # Call appropriate function based on source type
    if args.file:
        result = add_file_source(
            notebook_url=notebook_url,
            file_path=args.file,
            headless=not args.show_browser
        )
    else:
        result = add_url_source(
            notebook_url=notebook_url,
            source_url=args.url,
            headless=not args.show_browser
        )

    if result["status"] == "success":
        # Auto-save last used notebook
        if notebook_id:
            set_last_notebook(notebook_id, notebook_name or "")

        if args.file:
            print(f"\n✅ Uploaded file: {result['file_name']}")
        else:
            print(f"\n✅ Added {result.get('source_type', 'URL')} source: {result['source_url']}")

        if result.get("note"):
            print(f"   Note: {result['note']}")
        return 0
    else:
        print(f"\n❌ Failed: {result.get('error', 'Unknown error')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
