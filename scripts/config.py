"""
Configuration for NotebookLM Skill
Centralizes constants, selectors, and paths
"""

from pathlib import Path

# Paths
SKILL_DIR = Path(__file__).parent.parent
DATA_DIR = SKILL_DIR / "data"
BROWSER_STATE_DIR = DATA_DIR / "browser_state"
BROWSER_PROFILE_DIR = BROWSER_STATE_DIR / "browser_profile"
STATE_FILE = BROWSER_STATE_DIR / "state.json"
AUTH_INFO_FILE = DATA_DIR / "auth_info.json"

# NotebookLM Selectors
QUERY_INPUT_SELECTORS = [
    "textarea.query-box-input",  # Primary
    'textarea[aria-label="Feld für Anfragen"]',  # Fallback German
    'textarea[aria-label="Input for queries"]',  # Fallback English
]

RESPONSE_SELECTORS = [
    ".to-user-container .message-text-content",  # Primary
    "[data-message-author='bot']",
    "[data-message-author='assistant']",
]

# Chat Tab Selectors
CHAT_TAB_SELECTORS = [
    'button:has-text("Chat")',
    '[role="tab"]:has-text("Chat")',
]

# Sources Tab Selectors
SOURCES_TAB_SELECTORS = [
    'button:has-text("Sources")',
    '[role="tab"]:has-text("Sources")',
    'div:has-text("Sources"):not(:has(*))',
    '.tab:has-text("Sources")',
]

ADD_SOURCE_BUTTON_SELECTORS = [
    'button[aria-label="Add source"]',
    'button[aria-label="Add sources"]',
    'button:has-text("Add source")',
    'button:has-text("Add")',
    '[data-test-id="add-source-button"]',
    'button:has(mat-icon:has-text("add"))',
]

# Browser Configuration
BROWSER_ARGS = [
    '--disable-blink-features=AutomationControlled',  # Patches navigator.webdriver
    '--disable-dev-shm-usage',
    '--no-sandbox',
    '--no-first-run',
    '--no-default-browser-check'
]

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

# Timeouts
LOGIN_TIMEOUT_MINUTES = 10
QUERY_TIMEOUT_SECONDS = 120
PAGE_LOAD_TIMEOUT = 30000
