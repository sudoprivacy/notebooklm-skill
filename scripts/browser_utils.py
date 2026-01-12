"""
Browser Utilities for NotebookLM Skill
Handles browser launching, stealth features, and common interactions
"""

import json
import time
import random
from contextlib import contextmanager
from typing import Optional, List, Generator

from patchright.sync_api import Playwright, BrowserContext, Page, sync_playwright
from config import BROWSER_PROFILE_DIR, STATE_FILE, BROWSER_ARGS, USER_AGENT


@contextmanager
def browser_session(headless: bool = True) -> Generator[Page, None, None]:
    """
    Context manager for browser sessions with automatic cleanup.

    Usage:
        with browser_session(headless=True) as page:
            page.goto(url)
            # ... do stuff ...

    Raises:
        Exception if not authenticated
    """
    # Lazy import to avoid circular dependency
    from auth_manager import AuthManager

    auth = AuthManager()
    if not auth.is_authenticated():
        raise Exception("Not authenticated. Run: python scripts/run.py auth_manager.py setup")

    playwright = None
    context = None
    try:
        playwright = sync_playwright().start()
        context = BrowserFactory.launch_persistent_context(playwright, headless=headless)
        page = context.new_page()
        yield page
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


class BrowserFactory:
    """Factory for creating configured browser contexts"""

    @staticmethod
    def launch_persistent_context(
        playwright: Playwright,
        headless: bool = True,
        user_data_dir: str = str(BROWSER_PROFILE_DIR)
    ) -> BrowserContext:
        """
        Launch a persistent browser context with anti-detection features
        and cookie workaround.
        """
        # Launch persistent context
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            channel="chrome",  # Use real Chrome
            headless=headless,
            no_viewport=True,
            ignore_default_args=["--enable-automation"],
            user_agent=USER_AGENT,
            args=BROWSER_ARGS
        )

        # Cookie Workaround for Playwright bug #36139
        # Session cookies (expires=-1) don't persist in user_data_dir automatically
        BrowserFactory._inject_cookies(context)

        return context

    @staticmethod
    def _inject_cookies(context: BrowserContext):
        """Inject cookies from state.json if available"""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, 'r') as f:
                    state = json.load(f)
                    if 'cookies' in state and len(state['cookies']) > 0:
                        context.add_cookies(state['cookies'])
                        # print(f"  🔧 Injected {len(state['cookies'])} cookies from state.json")
            except Exception as e:
                print(f"  ⚠️  Could not load state.json: {e}")


class StealthUtils:
    """Human-like interaction utilities"""

    @staticmethod
    def random_delay(min_ms: int = 100, max_ms: int = 500):
        """Add random delay"""
        time.sleep(random.uniform(min_ms / 1000, max_ms / 1000))

    @staticmethod
    def human_type(page: Page, selector: str, text: str, wpm_min: int = 320, wpm_max: int = 480):
        """Type with human-like speed"""
        element = page.query_selector(selector)
        if not element:
            # Try waiting if not immediately found
            try:
                element = page.wait_for_selector(selector, timeout=2000)
            except:
                pass
        
        if not element:
            print(f"⚠️ Element not found for typing: {selector}")
            return

        # Click to focus
        element.click()
        
        # Type
        for char in text:
            element.type(char, delay=random.uniform(25, 75))
            if random.random() < 0.05:
                time.sleep(random.uniform(0.15, 0.4))

    @staticmethod
    def realistic_click(page: Page, selector: str):
        """Click with realistic movement"""
        element = page.query_selector(selector)
        if not element:
            return

        # Optional: Move mouse to element (simplified)
        box = element.bounding_box()
        if box:
            x = box['x'] + box['width'] / 2
            y = box['y'] + box['height'] / 2
            page.mouse.move(x, y, steps=5)

        StealthUtils.random_delay(100, 300)
        element.click()
        StealthUtils.random_delay(100, 300)


def find_and_click(page: Page, selectors: List[str], description: str, timeout: int = 10000) -> bool:
    """
    Try to find and click an element using multiple selectors.

    Args:
        page: Playwright page
        selectors: List of CSS selectors to try
        description: Human-readable description for logging
        timeout: Timeout in milliseconds

    Returns:
        True if clicked successfully, False otherwise
    """
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


def find_and_fill(page: Page, selectors: List[str], text: str, description: str, timeout: int = 10000) -> bool:
    """
    Try to find an input and fill it using multiple selectors.

    Args:
        page: Playwright page
        selectors: List of CSS selectors to try
        text: Text to type
        description: Human-readable description for logging
        timeout: Timeout in milliseconds

    Returns:
        True if filled successfully, False otherwise
    """
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
