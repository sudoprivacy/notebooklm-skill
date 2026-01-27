#!/usr/bin/env python3
"""
Generate NotebookLM Studio outputs
Supports: Audio Overview, Video Overview, Slide Deck, Infographic, Mind Map,
         Reports, Flashcards, Quiz, Data Table
"""

import argparse
import sys
import time
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from notebook_config import get_last_notebook, set_last_notebook
from browser_utils import browser_session, StealthUtils
from list_notebooks import list_notebooks


def click_studio_option(page, option_name: str) -> bool:
    """
    Generic function to click on any Studio option

    Args:
        page: Playwright page object
        option_name: Name of the option (e.g., 'audio overview', 'slide deck', 'infographic')

    Returns:
        True if successful, False otherwise
    """
    print(f"  🔍 Looking for {option_name.title()}...")
    result = page.evaluate(f'''() => {{
        const buttons = Array.from(document.querySelectorAll('button, [role="button"], div[role="button"]'));

        for (const button of buttons) {{
            const text = button.innerText?.toLowerCase() || '';
            if (text.includes('{option_name.lower()}')) {{
                button.click();
                return {{ success: true, found: button.innerText }};
            }}
        }}

        return {{ success: false, error: '{option_name.title()} button not found' }};
    }}''')

    if result.get('success'):
        print(f"  ✓ Clicked: {result.get('found')}")
        return True
    else:
        print(f"  ❌ {result.get('error')}")
        return False


def generate_studio_output(page, notebook_url: str, output_type: str, output_display_name: str) -> bool:
    """
    Generic function to generate any NotebookLM Studio output

    Args:
        page: Playwright page object
        notebook_url: URL of the notebook
        output_type: Type identifier (e.g., 'audio overview', 'slide deck')
        output_display_name: Display name for logging (e.g., '🎙️ Audio Overview', '📊 Slide Deck')

    Returns:
        True if successful, False otherwise
    """
    print(f"{output_display_name}")
    print(f"📚 Notebook: {notebook_url}")

    try:
        print("  🌐 Opening notebook...")
        page.goto(notebook_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_url(re.compile(r"^https://notebooklm\.google\.com/"), timeout=10000)
        StealthUtils.random_delay(2000, 3000)

        # Click Studio button
        print("  🔍 Looking for Studio button...")
        result = page.evaluate('''() => {
            const buttons = Array.from(document.querySelectorAll('button, [role="button"], [role="tab"]'));

            for (const button of buttons) {
                const text = button.innerText?.toLowerCase() || '';
                if (text.includes('studio')) {
                    button.click();
                    return { success: true };
                }
            }
            return { success: false };
        }''')

        if not result.get('success'):
            print("  ❌ Studio button not found")
            return False

        print("  ✓ Clicked: Studio")
        StealthUtils.random_delay(2000, 3000)

        # Click the specific output type
        if not click_studio_option(page, output_type):
            return False

        StealthUtils.random_delay(2000, 3000)

        # Look for Generate/Create button (some outputs may already exist)
        print("  🔍 Looking for Generate button...")
        result = page.evaluate('''() => {
            const buttons = Array.from(document.querySelectorAll('button'));

            // Look for Generate/Create button
            for (const button of buttons) {
                const text = button.innerText?.toLowerCase() || '';
                if (text.includes('generate') || text.includes('create')) {
                    button.click();
                    return { success: true, action: 'clicked generate', text: button.innerText };
                }
            }

            // Check if already exists
            const hasOutput = buttons.some(b => {
                const text = b.innerText?.toLowerCase() || '';
                return text.includes('view') || text.includes('download') ||
                       text.includes('play') || text.includes('open');
            });

            if (hasOutput) {
                return { success: true, action: 'already exists' };
            }

            // Some outputs might be generated automatically
            return { success: true, action: 'auto-generated' };
        }''')

        if result.get('success'):
            action = result.get('action')
            if action == 'already exists':
                print(f"  ✅ {output_type.title()} already exists!")
            elif action == 'auto-generated':
                print(f"  ✅ {output_type.title()} opened/generated!")
            else:
                print(f"  ✅ {output_type.title()} generation initiated!")
                print(f"  ⏳ Note: Generation may take a few minutes.")
            return True
        else:
            print(f"  ❌ Could not generate {output_type}")
            return False

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


# Specific generator functions for each output type
def generate_audio_overview(page, notebook_url: str) -> bool:
    """Generate Audio Overview (podcast)"""
    return generate_studio_output(page, notebook_url, "audio overview", "🎙️  Generating Audio Overview...")


def generate_video_overview(page, notebook_url: str) -> bool:
    """Generate Video Overview"""
    return generate_studio_output(page, notebook_url, "video overview", "🎥 Generating Video Overview...")


def generate_slide_deck(page, notebook_url: str) -> bool:
    """Generate Slide Deck (presentation)"""
    return generate_studio_output(page, notebook_url, "slide deck", "📊 Generating Slide Deck...")


def generate_infographic(page, notebook_url: str) -> bool:
    """Generate Infographic"""
    return generate_studio_output(page, notebook_url, "infographic", "📈 Generating Infographic...")


def generate_mind_map(page, notebook_url: str) -> bool:
    """Generate Mind Map"""
    return generate_studio_output(page, notebook_url, "mind map", "🧠 Generating Mind Map...")


def generate_reports(page, notebook_url: str) -> bool:
    """Generate Reports"""
    return generate_studio_output(page, notebook_url, "reports", "📄 Generating Reports...")


def generate_flashcards(page, notebook_url: str) -> bool:
    """Generate Flashcards"""
    return generate_studio_output(page, notebook_url, "flashcards", "🗂️  Generating Flashcards...")


def generate_quiz(page, notebook_url: str) -> bool:
    """Generate Quiz"""
    return generate_studio_output(page, notebook_url, "quiz", "❓ Generating Quiz...")


def generate_data_table(page, notebook_url: str) -> bool:
    """Generate Data Table"""
    return generate_studio_output(page, notebook_url, "data table", "📋 Generating Data Table...")


# Output type mapping
OUTPUT_GENERATORS = {
    'audio': generate_audio_overview,
    'video': generate_video_overview,
    'slides': generate_slide_deck,
    'slide-deck': generate_slide_deck,
    'infographic': generate_infographic,
    'mind-map': generate_mind_map,
    'reports': generate_reports,
    'flashcards': generate_flashcards,
    'quiz': generate_quiz,
    'data-table': generate_data_table,
}


def main():
    parser = argparse.ArgumentParser(
        description="Generate NotebookLM Studio outputs",
        epilog="""
Available output types:
  audio         - Audio Overview (podcast)
  video         - Video Overview
  slides        - Slide Deck (presentation)
  infographic   - Infographic
  mind-map      - Mind Map
  reports       - Reports
  flashcards    - Flashcards
  quiz          - Quiz
  data-table    - Data Table
  all           - Generate all available outputs
        """
    )
    parser.add_argument(
        "output_type",
        choices=list(OUTPUT_GENERATORS.keys()) + ['all'],
        help="Type of output to generate"
    )
    parser.add_argument("--notebook-url", help="Direct notebook URL")
    parser.add_argument("--notebook-id", help="Notebook ID")
    parser.add_argument("--notebook-name", help="Notebook name (fuzzy match)")
    parser.add_argument("--show-browser", action="store_true", help="Show browser window")

    args = parser.parse_args()

    # Resolve notebook URL
    notebook_url = args.notebook_url
    notebook_id = None
    notebook_name = None

    if notebook_url:
        match = re.search(r'/notebook/([a-f0-9-]+)', notebook_url)
        if match:
            notebook_id = match.group(1)

    if not notebook_url and args.notebook_id:
        notebook_id = args.notebook_id
        notebook_url = f"https://notebooklm.google.com/notebook/{notebook_id}"

    if not notebook_url and args.notebook_name:
        print(f"🔍 Looking for notebook: {args.notebook_name}")
        result = list_notebooks(headless=True, output_format="json")
        if result["status"] == "success":
            for nb in result["notebooks"]:
                if args.notebook_name.lower() in nb.get("name", "").lower():
                    notebook_url = nb["url"]
                    notebook_id = nb["id"]
                    notebook_name = nb.get("name", "")
                    print(f"📚 Found: {nb['name']}")
                    break

        if not notebook_url:
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
            print("❌ No notebook specified. Use --notebook-url, --notebook-id, or --notebook-name")
            return 1

    # Run generation
    try:
        with browser_session(headless=not args.show_browser) as page:
            success = False

            if args.output_type == "all":
                print("🎯 Generating all Studio outputs...\n")
                results = {}

                for output_type, generator_func in OUTPUT_GENERATORS.items():
                    try:
                        results[output_type] = generator_func(page, notebook_url)
                        print()
                        StealthUtils.random_delay(2000, 3000)
                    except Exception as e:
                        print(f"  ❌ Error generating {output_type}: {e}\n")
                        results[output_type] = False

                # Summary
                print("\n" + "="*60)
                print("Generation Summary:")
                print("="*60)
                for output_type, result in results.items():
                    status = "✅" if result else "❌"
                    print(f"{status} {output_type.replace('-', ' ').title()}")

                success = any(results.values())
            else:
                generator_func = OUTPUT_GENERATORS[args.output_type]
                success = generator_func(page, notebook_url)

            # Save last used notebook
            if success and notebook_id:
                set_last_notebook(notebook_id, notebook_name or "")

            if success:
                print("\n✅ Generation complete!")
                print(f"📖 View in NotebookLM: {notebook_url}")
                return 0
            else:
                print("\n❌ Generation failed")
                return 1

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
