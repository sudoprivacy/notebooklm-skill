#!/usr/bin/env python3
"""
Download source content from a NotebookLM notebook
"""

import argparse
import json
import sys
import re
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from notebook_config import set_last_notebook, find_notebook_url
from browser_utils import browser_session, StealthUtils
from config import SOURCES_TAB_SELECTORS


def clean_source_content(raw_content: str, source_name: str) -> str:
    """
    Clean extracted content by removing NotebookLM UI elements.

    The NotebookLM page structure when viewing a source is:
    1. Header UI (settings, PRO, Create notebook, etc.)
    2. Source header: filename + "Source guide" + "arrow_drop_down"
    3. ACTUAL CONTENT (what we want)
    4. Source footer: "tune more_vert"
    5. Chat/Search UI (Search results, chat history, etc.)

    Args:
        raw_content: Raw extracted text
        source_name: Name of the source being downloaded

    Returns:
        Cleaned content
    """
    lines = raw_content.split('\n')

    # Find content boundaries
    # Start: after "Source guide" or "arrow_drop_down" line
    # End: before "tune more_vert" or chat UI elements

    start_idx = 0
    end_idx = len(lines)

    # Find start - look for Source guide marker
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped in ['Source guide', 'arrow_drop_down']:
            start_idx = i + 1
        # Also check for the source filename as fallback
        elif source_name.replace('.md', '') in stripped.lower():
            # Start after the filename line
            start_idx = i + 1

    # Find end - look for "tune more_vert" which ends the source viewer
    end_markers = [
        'tune more_vert',
        'Search results',
        'No emoji found',
        'Recently used',
        'sources The provided sources',
        'keep Save to note',
        'keyboard_arrow_down docs',
    ]

    for i, line in enumerate(lines):
        if i <= start_idx:
            continue
        stripped = line.strip()
        for marker in end_markers:
            if marker in stripped:
                end_idx = i
                break
        if end_idx < len(lines):
            break

    # Extract content between boundaries
    content_lines = lines[start_idx:end_idx]

    # Clean individual lines
    ui_line_markers = [
        'Project: Open Company - NotebookLM',
        'Create notebook',
        'trending_up',
        'Sources Chat Studio',
        'Source guide',
        'arrow_drop_down',
        'arrow_back',
        'button_magic',
        'Google apps',
        'Google Account',
        'elfenliedsp@gmail.com',
        'Loading',
    ]

    icon_words = {
        'settings', 'PRO', 'add', 'share', 'arrow_forward', 'keep', 'keep_pin',
        'docs', 'keyboard_arrow_down', 'tune', 'more_vert', '&nbsp;',
    }

    cleaned_lines = []
    for line in content_lines:
        stripped = line.strip()

        # Skip empty lines (but preserve one blank between paragraphs)
        if not stripped:
            if cleaned_lines and cleaned_lines[-1] != '':
                cleaned_lines.append('')
            continue

        # Skip UI marker lines
        skip = False
        for marker in ui_line_markers:
            if marker in stripped:
                skip = True
                break
        if skip:
            continue

        # Skip icon-only lines
        if stripped in icon_words:
            continue

        # Skip very short lines that are likely UI artifacts (but keep numbers)
        if len(stripped) < 3 and not stripped[0].isdigit():
            continue

        # Fix HTML entities
        stripped = stripped.replace('&nbsp;', ' ')
        stripped = stripped.replace('&amp;', '&')
        stripped = stripped.replace('&lt;', '<')
        stripped = stripped.replace('&gt;', '>')

        cleaned_lines.append(stripped)

    # Remove trailing empty lines
    while cleaned_lines and cleaned_lines[-1] == '':
        cleaned_lines.pop()

    return '\n'.join(cleaned_lines)


def download_source(
    source_name: str,
    notebook_url: str = None,
    notebook_name: str = None,
    notebook_id: str = None,
    output_path: str = None,
    headless: bool = True,
    debug: bool = False
) -> dict:
    """
    Download source content from a NotebookLM notebook

    Args:
        source_name: Name of the source to download (partial match supported)
        notebook_url: Direct notebook URL
        notebook_name: Notebook name (fuzzy match)
        notebook_id: Notebook UUID
        output_path: Output file path (auto-generated if not provided)
        headless: Run browser in headless mode
        debug: Save screenshot for debugging

    Returns:
        Dict with status and content/file path
    """
    try:
        resolved_url = find_notebook_url(notebook_name, notebook_id, notebook_url)
    except Exception as e:
        return {"status": "error", "error": str(e)}

    print(f"📥 Downloading source: {source_name}")
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

            # Find and click on the source to open it (with retry for slow DOM rendering)
            print(f"  🔍 Looking for source: {source_name}...")

            source_info = None
            deadline = time.time() + 30
            while time.time() < deadline:
                # First scroll to make sure source is visible
                page.evaluate('''(sourceName) => {
                    const sourceNameLower = sourceName.toLowerCase();
                    const checkboxes = document.querySelectorAll('mat-checkbox');
                    for (const cb of checkboxes) {
                        const row = cb.closest('[class*="source"]') || cb.parentElement?.parentElement;
                        if (!row) continue;
                        const rowText = row.innerText || '';
                        if (rowText.toLowerCase().indexOf(sourceNameLower) >= 0 &&
                            rowText.toLowerCase().indexOf('select all') < 0) {
                            row.scrollIntoView({ block: 'center' });
                            return true;
                        }
                    }
                    return false;
                }''', source_name)
                StealthUtils.random_delay(500, 800)

                source_info = page.evaluate('''(sourceName) => {
                const sourceNameLower = sourceName.toLowerCase();

                // Find source by looking at checkbox rows and getting the clickable name element
                const checkboxes = document.querySelectorAll('mat-checkbox');
                for (const cb of checkboxes) {
                    const row = cb.closest('[class*="source"]') || cb.parentElement?.parentElement;
                    if (!row) continue;
                    const rowText = row.innerText || '';

                    if (rowText.toLowerCase().indexOf(sourceNameLower) >= 0 &&
                        rowText.toLowerCase().indexOf('select all') < 0) {

                        // Extract the actual source name
                        const lines = rowText.split('\\n').map(l => l.trim()).filter(l => l.length > 10);
                        const nameLines = lines.filter(l => {
                            const lower = l.toLowerCase();
                            return lower !== 'markdown' && lower !== 'web' && lower !== 'youtube' &&
                                   !lower.startsWith('drive_') && !lower.startsWith('video_');
                        });
                        const actualName = nameLines[0] || sourceName;

                        // Find the source name text element (usually after the icon, before checkbox)
                        // Look for spans or divs containing the source name
                        const allElements = row.querySelectorAll('span, div, a');
                        for (const el of allElements) {
                            const text = (el.innerText || '').trim();
                            // Skip if it's checkbox label, icon text, or too short
                            if (text.length < 10) continue;
                            if (el.closest('mat-checkbox')) continue;
                            if (text === 'markdown' || text === 'web' || text === 'youtube') continue;

                            // This should be the source name - get its position
                            const rect = el.getBoundingClientRect();
                            if (rect.width > 50 && rect.height > 10) {
                                return {
                                    found: true,
                                    name: actualName,
                                    clickTarget: text.substring(0, 50),
                                    rect: { x: rect.x + rect.width/2, y: rect.y + rect.height/2, width: rect.width, height: rect.height }
                                };
                            }
                        }

                        // Fallback: click the row area but avoid the checkbox (left side)
                        const rowRect = row.getBoundingClientRect();
                        // Click in the middle-left area (after icon, before checkbox)
                        return {
                            found: true,
                            name: actualName,
                            clickTarget: 'row-fallback',
                            rect: { x: rowRect.x + 150, y: rowRect.y + rowRect.height/2, width: rowRect.width, height: rowRect.height }
                        };
                    }
                }

                return { found: false };
            }''', source_name)

                if source_info and source_info.get('found'):
                    break
                time.sleep(2)

            if not source_info or not source_info.get('found'):
                print(f"  ❌ Source not found: {source_name}")
                return {"status": "error", "error": f"Source not found: {source_name}"}

            actual_name = source_info.get('name', source_name)
            click_target = source_info.get('clickTarget', 'unknown')
            rect = source_info['rect']
            print(f"  ✓ Found source: {actual_name}")
            print(f"  📍 Click target: {click_target} at ({rect['x']:.0f}, {rect['y']:.0f})")

            # Click on the source to open it
            print("  🖱️ Opening source...")
            page.mouse.click(rect['x'], rect['y'])
            StealthUtils.random_delay(3000, 4000)

            # Wait for source panel to appear
            print("  ⏳ Waiting for source panel...")
            try:
                # Try to wait for a panel/drawer to appear
                page.wait_for_selector('[class*="source-viewer"], [class*="source-panel"], [class*="drawer"], [class*="detail"], mat-drawer', timeout=5000)
                StealthUtils.random_delay(1000, 1500)
            except Exception:
                print("  ⚠️ No specific panel selector found, continuing...")

            # Wait for source panel to open and extract content
            print("  📄 Extracting content...")

            # Scroll to load all content and collect it
            all_content = []
            scroll_attempts = 0
            max_scrolls = 30
            last_length = 0

            while scroll_attempts < max_scrolls:
                scroll_attempts += 1

                # Get current visible content
                content_result = page.evaluate('''() => {
                    // Look for source content panel/viewer - the main content area after clicking a source
                    const selectors = [
                        // Source detail view selectors
                        '[class*="source-viewer"]',
                        '[class*="source-detail"]',
                        '[class*="source-content"]',
                        '[class*="document-viewer"]',
                        // The main content area (not the sources list)
                        'main',
                        '[role="main"]',
                    ];

                    for (const sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el) {
                            const text = el.innerText || '';
                            // Filter out UI elements
                            if (text.length > 200 && text.indexOf('Select all sources') < 0) {
                                return {
                                    content: text,
                                    selector: sel,
                                    scrollHeight: el.scrollHeight,
                                    clientHeight: el.clientHeight,
                                    scrollTop: el.scrollTop
                                };
                            }
                        }
                    }

                    // Fallback: find the largest content div
                    const allDivs = document.querySelectorAll('div');
                    let bestMatch = null;
                    let maxLength = 200;

                    for (const div of allDivs) {
                        const text = div.innerText || '';
                        // Skip if it's the sources list
                        if (text.indexOf('Select all sources') >= 0) continue;
                        if (div.querySelector('mat-checkbox')) continue;

                        if (text.length > maxLength) {
                            maxLength = text.length;
                            bestMatch = {
                                content: text,
                                selector: div.className.substring(0, 50),
                                scrollHeight: div.scrollHeight,
                                clientHeight: div.clientHeight,
                                scrollTop: div.scrollTop
                            };
                        }
                    }

                    return bestMatch;
                }''')

                if content_result and content_result.get('content'):
                    current_length = len(content_result['content'])

                    if current_length == last_length:
                        # No new content, we're done
                        break

                    last_length = current_length

                    # Scroll down in the content panel
                    page.evaluate('''() => {
                        // Find scrollable container and scroll it
                        const containers = [
                            document.querySelector('[class*="source-viewer"]'),
                            document.querySelector('[class*="source-detail"]'),
                            document.querySelector('[class*="source-content"]'),
                            document.querySelector('main'),
                            document.querySelector('mat-sidenav-content'),
                        ];

                        for (const container of containers) {
                            if (container && container.scrollHeight > container.clientHeight) {
                                container.scrollTop += 1000;
                                return true;
                            }
                        }
                        // Fallback to window scroll
                        window.scrollBy(0, 1000);
                        return false;
                    }''')
                    StealthUtils.random_delay(300, 500)
                else:
                    break

            # Get final content from the source viewer
            print("  📋 Extracting source content...")

            # First, scroll to load all content
            for _ in range(20):
                page.evaluate('''() => {
                    // Find the scrollable source viewer container
                    const containers = document.querySelectorAll('[class*="source"], [class*="viewer"], mat-sidenav-content');
                    for (const container of containers) {
                        if (container.scrollHeight > container.clientHeight + 100) {
                            container.scrollTop += 800;
                            return true;
                        }
                    }
                    window.scrollBy(0, 800);
                    return false;
                }''')
                StealthUtils.random_delay(200, 300)

            # Now extract the content - try multiple approaches
            content_result = page.evaluate('''() => {
                const result = { debug: {} };

                // Approach 1: Try mat-sidenav-content
                const sidenavContent = document.querySelector('mat-sidenav-content');
                result.debug.hasSidenav = !!sidenavContent;

                if (sidenavContent) {
                    const text = sidenavContent.innerText || '';
                    result.debug.sidenavLength = text.length;

                    const lines = text.split('\\n');
                    result.debug.totalLines = lines.length;

                    // Find where content starts (after "Source guide")
                    let startIdx = 0;
                    let endIdx = lines.length;

                    for (let i = 0; i < lines.length; i++) {
                        const line = lines[i].trim();
                        if (line === 'Source guide' || line.indexOf('Source guide') >= 0) {
                            startIdx = i + 1;
                            result.debug.foundSourceGuideAt = i;
                        }
                    }

                    // Find end markers
                    const endMarkers = ['tune', 'more_vert'];
                    for (let i = startIdx; i < lines.length; i++) {
                        const line = lines[i].trim();
                        if (endMarkers.includes(line)) {
                            endIdx = i;
                            result.debug.foundEndMarkerAt = i;
                            break;
                        }
                    }

                    result.debug.startIdx = startIdx;
                    result.debug.endIdx = endIdx;

                    // Extract content lines
                    const contentLines = lines.slice(startIdx, endIdx)
                        .map(l => l.trim())
                        .filter(l => l.length > 0)
                        .filter(l => !['settings', 'PRO', 'add', 'share', 'arrow_forward',
                                       'arrow_back', 'arrow_drop_down', 'button_magic',
                                       'Create notebook', 'trending_up'].includes(l))
                        .filter(l => l.indexOf('Project:') !== 0 || l.length > 50);

                    result.debug.contentLinesCount = contentLines.length;

                    if (contentLines.length > 0) {
                        result.content = contentLines.join('\\n');
                        result.selector = 'sidenav-filtered';
                        result.lines = contentLines.length;
                        return result;
                    }

                    // Return raw if filtering removed everything
                    result.content = text;
                    result.selector = 'sidenav-raw';
                    return result;
                }

                // Approach 2: Try document.body
                const bodyText = document.body.innerText || '';
                result.debug.bodyLength = bodyText.length;

                if (bodyText.length > 500) {
                    const lines = bodyText.split('\\n');
                    let startIdx = 0;
                    for (let i = 0; i < lines.length; i++) {
                        if (lines[i].indexOf('Source guide') >= 0) {
                            startIdx = i + 1;
                            break;
                        }
                    }
                    const contentLines = lines.slice(startIdx)
                        .filter(l => l.trim().length > 0);
                    result.content = contentLines.join('\\n');
                    result.selector = 'body-fallback';
                    return result;
                }

                return result;
            }''')

            # Log debug info
            if content_result and content_result.get('debug'):
                debug_info = content_result['debug']
                print(f"  🔍 Debug: sidenav={debug_info.get('hasSidenav')}, "
                      f"length={debug_info.get('sidenavLength', debug_info.get('bodyLength', 0))}, "
                      f"lines={debug_info.get('totalLines', '?')}")

            content = None
            if content_result and content_result.get('content'):
                raw_content = content_result['content']
                selector = content_result.get('selector', 'unknown')
                print(f"  ✓ Got content via: {selector}")
                print(f"  📊 Content length: {len(raw_content)} chars")

                if selector == 'sidenav-filtered':
                    # Already filtered in JavaScript, use directly
                    content = raw_content
                    print(f"  ✓ Lines extracted: {content_result.get('lines', '?')}")
                else:
                    # Raw content needs cleaning
                    content = clean_source_content(raw_content, actual_name)
                    print(f"  📊 After cleaning: {len(content)} chars")

            if debug:
                debug_dir = Path(__file__).parent.parent / "data" / "debug"
                debug_dir.mkdir(parents=True, exist_ok=True)
                try:
                    page.screenshot(path=str(debug_dir / "download_source.png"))
                    print(f"  📸 Screenshot saved to: {debug_dir / 'download_source.png'}")
                except Exception as e:
                    print(f"  ⚠️ Could not save screenshot: {e}")

            if not content:
                # Last resort: get page content and try to parse
                print("  ⚠️ Could not extract via panel, trying page content...")
                html = page.content()

                # Simple extraction from HTML
                import re as regex
                # Remove script/style tags
                html = regex.sub(r'<script[^>]*>.*?</script>', '', html, flags=regex.DOTALL)
                html = regex.sub(r'<style[^>]*>.*?</style>', '', html, flags=regex.DOTALL)
                # Remove HTML tags
                text = regex.sub(r'<[^>]+>', ' ', html)
                # Clean up whitespace
                text = regex.sub(r'\s+', ' ', text).strip()

                if len(text) > 500:
                    print(f"  📊 Raw HTML text length: {len(text)} chars")
                    # Clean the content
                    content = clean_source_content(text, actual_name)
                    print(f"  📊 Cleaned length: {len(content)} chars")

            if not content:
                return {"status": "error", "error": "Could not extract source content"}

            # Save to file
            if not output_path:
                data_dir = Path(__file__).parent.parent / "data" / "downloads"
                data_dir.mkdir(parents=True, exist_ok=True)
                # Clean filename
                clean_name = re.sub(r'[^\w\-_.]', '_', actual_name)[:50]
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_path = str(data_dir / f"{clean_name}_{timestamp}.md")

            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)

            print(f"  ✅ Saved to: {output_path}")
            print(f"  📊 Content length: {len(content)} chars")

            set_last_notebook(resolved_url)

            return {
                "status": "success",
                "source_name": actual_name,
                "output_path": str(output_path),
                "content_length": len(content),
                "notebook_url": resolved_url
            }

    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description='Download source content from a NotebookLM notebook')

    # Source to download
    parser.add_argument('source_name', help='Name of the source to download (partial match)')

    # Notebook selection
    parser.add_argument('--notebook-url', help='Direct notebook URL')
    parser.add_argument('--notebook-id', help='Notebook UUID')
    parser.add_argument('--notebook-name', help='Notebook name (fuzzy match)')

    # Output
    parser.add_argument('--output', '-o', help='Output file path')

    # Options
    parser.add_argument('--show-browser', action='store_true', help='Show browser for debugging')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--debug', action='store_true', help='Save screenshot for debugging')

    args = parser.parse_args()

    result = download_source(
        source_name=args.source_name,
        notebook_url=args.notebook_url,
        notebook_name=args.notebook_name,
        notebook_id=args.notebook_id,
        output_path=args.output,
        headless=not args.show_browser,
        debug=args.debug
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
