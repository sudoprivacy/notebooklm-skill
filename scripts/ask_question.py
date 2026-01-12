#!/usr/bin/env python3
"""
Simple NotebookLM Question Interface
Based on MCP server implementation - simplified without sessions

Implements hybrid auth approach:
- Persistent browser profile (user_data_dir) for fingerprint consistency
- Manual cookie injection from state.json for session cookies (Playwright bug workaround)
See: https://github.com/microsoft/playwright/issues/36139
"""

import argparse
import sys
import time
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from notebook_config import get_last_notebook, set_last_notebook
from config import QUERY_INPUT_SELECTORS, RESPONSE_SELECTORS, SOURCES_TAB_SELECTORS
from browser_utils import browser_session, StealthUtils
from list_notebooks import list_notebooks


# Follow-up reminder (adapted from MCP server for stateless operation)
# Since we don't have persistent sessions, we encourage comprehensive questions
FOLLOW_UP_REMINDER = (
    "\n\nEXTREMELY IMPORTANT: Is that ALL you need to know? "
    "You can always ask another question! Think about it carefully: "
    "before you reply to the user, review their original request and this answer. "
    "If anything is still unclear or missing, ask me another comprehensive question "
    "that includes all necessary context (since each question opens a new browser session)."
)


def deactivate_sources(page, exclude_sources: list[str]) -> int:
    """
    Deactivate (uncheck) specified sources in the current notebook.

    Args:
        page: Playwright page object
        exclude_sources: List of source names to deactivate (partial match)

    Returns:
        Number of sources deactivated
    """
    if not exclude_sources:
        return 0

    print(f"  🔇 Excluding sources: {', '.join(exclude_sources)}")

    # Click Sources tab
    for selector in SOURCES_TAB_SELECTORS:
        try:
            tab = page.wait_for_selector(selector, timeout=5000, state="visible")
            if tab:
                tab.click()
                StealthUtils.random_delay(1000, 1500)
                break
        except:
            continue

    deactivated = 0

    for source_name in exclude_sources:
        # Find and click the checkbox for this source
        result = page.evaluate('''(sourceName) => {
            const sourceNameLower = sourceName.toLowerCase();
            const checkboxes = document.querySelectorAll('mat-checkbox');

            for (const cb of checkboxes) {
                const row = cb.closest('[class*="source"]') || cb.parentElement?.parentElement;
                if (!row) continue;
                const rowText = row.innerText || '';

                if (rowText.toLowerCase().indexOf(sourceNameLower) >= 0 &&
                    rowText.toLowerCase().indexOf('select all') < 0) {

                    // Check if currently checked
                    const input = cb.querySelector('input[type="checkbox"]');
                    const isChecked = input ? input.checked :
                                    cb.classList.contains('mat-mdc-checkbox-checked');

                    if (isChecked && input) {
                        input.click();
                        // Get actual source name (filter out icon labels)
                        const lines = rowText.split('\\n').map(l => l.trim()).filter(l => l.length > 10);
                        const nameLines = lines.filter(l => {
                            const lower = l.toLowerCase();
                            return lower !== 'markdown' && lower !== 'web' && lower !== 'youtube';
                        });
                        const name = nameLines[0] || sourceName;
                        return { found: true, clicked: true, name: name.substring(0, 60) };
                    } else if (!isChecked) {
                        return { found: true, clicked: false, reason: 'already deactivated' };
                    }
                }
            }
            return { found: false };
        }''', source_name)

        if result.get('clicked'):
            print(f"    ⬜ Deactivated: {result.get('name', source_name)}")
            deactivated += 1
            StealthUtils.random_delay(300, 500)
        elif result.get('found'):
            print(f"    ℹ️ Already deactivated: {source_name}")
        else:
            print(f"    ⚠️ Source not found: {source_name}")

    # Click Chat tab to go back
    try:
        chat_tab = page.wait_for_selector('button:has-text("Chat"), [role="tab"]:has-text("Chat")', timeout=3000)
        if chat_tab:
            chat_tab.click()
            StealthUtils.random_delay(500, 800)
    except:
        pass

    return deactivated


def ask_notebooklm(question: str, notebook_url: str, headless: bool = True, exclude_sources: list[str] = None) -> str:
    """
    Ask a question to NotebookLM

    Args:
        question: Question to ask
        notebook_url: NotebookLM notebook URL
        headless: Run browser in headless mode
        exclude_sources: List of source names to exclude from the query (partial match)

    Returns:
        Answer text from NotebookLM
    """
    print(f"💬 Asking: {question}")
    print(f"📚 Notebook: {notebook_url}")

    try:
        with browser_session(headless=headless) as page:
            print("  🌐 Opening notebook...")
            page.goto(notebook_url, wait_until="domcontentloaded")

            # Wait for NotebookLM
            page.wait_for_url(re.compile(r"^https://notebooklm\.google\.com/"), timeout=10000)
            StealthUtils.random_delay(1000, 1500)

            # Deactivate excluded sources before asking
            if exclude_sources:
                deactivate_sources(page, exclude_sources)

            # Wait for query input (MCP approach)
            print("  ⏳ Waiting for query input...")
            query_element = None

            for selector in QUERY_INPUT_SELECTORS:
                try:
                    query_element = page.wait_for_selector(
                        selector,
                        timeout=10000,
                        state="visible"  # Only check visibility, not disabled!
                    )
                    if query_element:
                        print(f"  ✓ Found input: {selector}")
                        break
                except:
                    continue

            if not query_element:
                print("  ❌ Could not find query input")
                return None

            # Type question (human-like, fast)
            print("  ⏳ Typing question...")

            # Use primary selector for typing
            input_selector = QUERY_INPUT_SELECTORS[0]
            StealthUtils.human_type(page, input_selector, question)

            # Submit
            print("  📤 Submitting...")
            page.keyboard.press("Enter")

            # Small pause
            StealthUtils.random_delay(500, 1500)

            # Wait for response (MCP approach: poll for stable text)
            print("  ⏳ Waiting for answer...")

            answer = None
            stable_count = 0
            last_text = None
            deadline = time.time() + 120  # 2 minutes timeout

            while time.time() < deadline:
                # Check if NotebookLM is still thinking (most reliable indicator)
                try:
                    thinking_element = page.query_selector('div.thinking-message')
                    if thinking_element and thinking_element.is_visible():
                        time.sleep(1)
                        continue
                except:
                    pass

                # Try to find response with MCP selectors
                for selector in RESPONSE_SELECTORS:
                    try:
                        elements = page.query_selector_all(selector)
                        if elements:
                            # Get last (newest) response
                            latest = elements[-1]
                            text = latest.inner_text().strip()

                            if text:
                                if text == last_text:
                                    stable_count += 1
                                    if stable_count >= 3:  # Stable for 3 polls
                                        answer = text
                                        break
                                else:
                                    stable_count = 0
                                    last_text = text
                    except:
                        continue

                if answer:
                    break

                time.sleep(1)

            if not answer:
                print("  ❌ Timeout waiting for answer")
                return None

            print("  ✅ Got answer!")
            # Add follow-up reminder to encourage Claude to ask more questions
            return answer + FOLLOW_UP_REMINDER

    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


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
    parser = argparse.ArgumentParser(description='Ask NotebookLM a question')

    parser.add_argument('--question', required=True, help='Question to ask')
    parser.add_argument('--notebook-url', help='Full NotebookLM notebook URL')
    parser.add_argument('--notebook-id', help='Notebook UUID (or partial)')
    parser.add_argument('--notebook-name', help='Notebook name (fuzzy match)')
    parser.add_argument('--exclude-sources', help='Comma-separated source names to exclude from query')
    parser.add_argument('--show-browser', action='store_true', help='Show browser')

    args = parser.parse_args()

    # Resolve notebook URL (priority: url > id > name > last used)
    notebook_url = args.notebook_url
    notebook_id = None
    notebook_name = None

    if notebook_url:
        # Extract ID from URL
        import re
        match = re.search(r'/notebook/([a-f0-9-]+)', notebook_url)
        if match:
            notebook_id = match.group(1)

    if not notebook_url and args.notebook_id:
        # Support both full UUID and partial
        notebook_id = args.notebook_id
        notebook_url = f"https://notebooklm.google.com/notebook/{notebook_id}"

    if not notebook_url and args.notebook_name:
        # Fuzzy match by name (requires fetching from web)
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
        # Check for last used notebook
        last = get_last_notebook()
        if last:
            notebook_url = last["url"]
            notebook_id = last["id"]
            notebook_name = last.get("name", "")
            print(f"📚 Using last notebook: {last.get('name') or last['id']}")
        else:
            # Show available notebooks
            print("❌ No notebook specified. Options:")
            print("  --notebook-url URL     Full NotebookLM URL")
            print("  --notebook-id UUID     Notebook UUID")
            print("  --notebook-name NAME   Fuzzy match by name")
            print("")
            print("List available notebooks:")
            print("  python scripts/run.py list_notebooks.py")
            return 1

    # Parse exclude sources
    exclude_sources = None
    if args.exclude_sources:
        exclude_sources = [s.strip() for s in args.exclude_sources.split(',') if s.strip()]

    # Ask the question
    answer = ask_notebooklm(
        question=args.question,
        notebook_url=notebook_url,
        headless=not args.show_browser,
        exclude_sources=exclude_sources
    )

    if answer:
        # Auto-save last used notebook
        if notebook_id:
            set_last_notebook(notebook_id, notebook_name or "")
        print("\n" + "=" * 60)
        print(f"Question: {args.question}")
        print("=" * 60)
        print()
        print(answer)
        print()
        print("=" * 60)
        return 0
    else:
        print("\n❌ Failed to get answer")
        return 1


if __name__ == "__main__":
    sys.exit(main())
