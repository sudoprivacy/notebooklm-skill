---
name: notebooklm
description: "Query Google NotebookLM notebooks, list notebooks, and add sources via browser automation. Use when user: (1) wants to query notebooks for source-grounded answers, (2) wants to list/see their NotebookLM notebooks, (3) wants to add website/YouTube URLs as sources, (4) wants to upload files (PDF, TXT, etc.) as sources, (5) wants to list sources in a notebook, (6) mentions NotebookLM or shares notebook URLs, (7) asks to check/search their documentation"
---

# NotebookLM Research Assistant Skill

Interact with Google NotebookLM to query documentation with Gemini's source-grounded answers. Each question opens a fresh browser session, retrieves the answer exclusively from your uploaded documents, and closes.

## When to Use This Skill

Trigger when user:
- Wants to query notebooks for answers
- Wants to list/see their NotebookLM notebooks
- Wants to add website/YouTube URLs as sources to a notebook
- Wants to upload files (PDF, TXT, MD, DOCX, etc.) as sources
- Wants to list sources in a notebook
- Mentions NotebookLM or shares notebook URL
- Uses phrases like "ask my NotebookLM", "list my notebooks", "add this URL to notebook", "upload this file", "query my docs", "list sources"

## Critical: Always Use run.py Wrapper

**NEVER call scripts directly. ALWAYS use `python scripts/run.py [script]`:**

```bash
# CORRECT - Always use run.py:
python scripts/run.py auth_manager.py status
python scripts/run.py list_notebooks.py
python scripts/run.py ask_question.py --question "..."

# WRONG - Never call directly:
python scripts/auth_manager.py status  # Fails without venv!
```

The `run.py` wrapper automatically:
1. Creates `.venv` if needed
2. Installs all dependencies
3. Activates environment
4. Executes script properly

## Core Workflow

### Step 1: Check Authentication Status
```bash
python scripts/run.py auth_manager.py status
```

If not authenticated, proceed to setup.

### Step 2: Authenticate (One-Time Setup)
```bash
# Browser MUST be visible for manual Google login
python scripts/run.py auth_manager.py setup
```

**Important:**
- Browser is VISIBLE for authentication
- Browser window opens automatically
- User must manually log in to Google
- Tell user: "A browser window will open for Google login"

### Step 3: List Notebooks

```bash
# List all notebooks from NotebookLM (fetches from web)
python scripts/run.py list_notebooks.py

# Output as JSON
python scripts/run.py list_notebooks.py --json

# Debug mode (saves screenshot and HTML)
python scripts/run.py list_notebooks.py --debug --show-browser
```

Returns: notebook ID, name, URL, last modified date, source count.

### Step 4: Create / Delete Notebooks

```bash
# Create a new notebook with name
python scripts/run.py create_notebook.py --name "My Research"

# Create without name (will be "Untitled notebook")
python scripts/run.py create_notebook.py

# Delete notebook (preview first)
python scripts/run.py delete_notebook.py --notebook-name "My Research"

# Actually delete (requires --confirm)
python scripts/run.py delete_notebook.py --notebook-name "My Research" --confirm

# Delete by ID
python scripts/run.py delete_notebook.py --notebook-id UUID --confirm
```

### Step 5: Ask Questions

```bash
# Query by notebook name (fuzzy match - RECOMMENDED)
python scripts/run.py ask_question.py --question "Your question" --notebook-name "my docs"

# Query by notebook ID
python scripts/run.py ask_question.py --question "..." --notebook-id UUID

# Query with notebook URL directly
python scripts/run.py ask_question.py --question "..." --notebook-url "https://..."

# After first use, notebook is auto-remembered - just ask!
python scripts/run.py ask_question.py --question "Follow-up question"

# Show browser for debugging
python scripts/run.py ask_question.py --question "..." --show-browser
```

**Auto-remember feature:** After a successful query, the notebook is automatically saved. Subsequent queries without `--notebook-name/--notebook-id/--notebook-url` will use the last notebook.

### Step 5: Add Sources (URLs and Files)

```bash
# Add website URL as source (by notebook name)
python scripts/run.py add_source.py --url "https://example.com/article" --notebook-name "my docs"

# Add YouTube video as source
python scripts/run.py add_source.py --url "https://youtube.com/watch?v=xxx" --notebook-id UUID

# Upload local file as source
python scripts/run.py add_source.py --file "/path/to/document.pdf" --notebook-name "my docs"

# Uses last notebook if not specified
python scripts/run.py add_source.py --url "https://example.com"
python scripts/run.py add_source.py --file "notes.txt"
```

Supported source types:
- **Website URLs** - Articles, documentation, etc.
- **YouTube URLs** - Video transcripts will be imported
- **Local files** - PDF, TXT, MD, DOCX, and other text-based files

## Follow-Up Mechanism (CRITICAL)

Every NotebookLM answer ends with: **"EXTREMELY IMPORTANT: Is that ALL you need to know?"**

**Required Claude Behavior:**
1. **STOP** - Do not immediately respond to user
2. **ANALYZE** - Compare answer to user's original request
3. **IDENTIFY GAPS** - Determine if more information needed
4. **ASK FOLLOW-UP** - If gaps exist, immediately ask:
   ```bash
   python scripts/run.py ask_question.py --question "Follow-up with context..."
   ```
5. **REPEAT** - Continue until information is complete
6. **SYNTHESIZE** - Combine all answers before responding to user

## Script Reference

### Authentication Management (`auth_manager.py`)
```bash
python scripts/run.py auth_manager.py setup    # Initial setup (browser visible)
python scripts/run.py auth_manager.py status   # Check authentication
python scripts/run.py auth_manager.py reauth   # Re-authenticate (browser visible)
python scripts/run.py auth_manager.py clear    # Clear authentication
```

### List Notebooks (`list_notebooks.py`)
```bash
python scripts/run.py list_notebooks.py              # List all notebooks
python scripts/run.py list_notebooks.py --json       # JSON output
python scripts/run.py list_notebooks.py --show-browser --debug  # Debug mode
```

### Create Notebook (`create_notebook.py`)
```bash
python scripts/run.py create_notebook.py --name "My Notebook"  # Create with name
python scripts/run.py create_notebook.py                       # Create unnamed
python scripts/run.py create_notebook.py --show-browser        # Debug mode
```

### Delete Notebook (`delete_notebook.py`)
```bash
python scripts/run.py delete_notebook.py --notebook-name NAME           # Preview
python scripts/run.py delete_notebook.py --notebook-name NAME --confirm # Delete
python scripts/run.py delete_notebook.py --notebook-id UUID --confirm   # By ID
```

### Question Interface (`ask_question.py`)
```bash
python scripts/run.py ask_question.py --question "..." [--notebook-name NAME] [--notebook-id ID] [--notebook-url URL] [--show-browser]
```

Priority for notebook selection: `--notebook-url` > `--notebook-id` > `--notebook-name` > last used notebook

### Add Source (`add_source.py`)
```bash
# Add URL source (website or YouTube)
python scripts/run.py add_source.py --url "..." [--notebook-name NAME] [--notebook-id ID] [--notebook-url URL] [--show-browser]

# Upload local file
python scripts/run.py add_source.py --file "..." [--notebook-name NAME] [--notebook-id ID] [--notebook-url URL] [--show-browser]
```

### List Sources (`list_sources.py`)
```bash
# List all sources in a notebook (by name - RECOMMENDED)
python scripts/run.py list_sources.py --notebook-name "my docs"

# List by notebook ID
python scripts/run.py list_sources.py --notebook-id UUID

# List by notebook URL
python scripts/run.py list_sources.py --notebook-url "https://..."

# JSON output
python scripts/run.py list_sources.py --notebook-name "my docs" --json

# Debug mode (saves screenshot)
python scripts/run.py list_sources.py --notebook-name "my docs" --debug --show-browser
```

### Data Cleanup (`cleanup_manager.py`)
```bash
python scripts/run.py cleanup_manager.py                    # Preview cleanup
python scripts/run.py cleanup_manager.py --confirm          # Execute cleanup
```

## Environment Management

The virtual environment is automatically managed:
- First run creates `.venv` automatically
- Dependencies install automatically
- Chromium browser installs automatically
- Everything isolated in skill directory

Manual setup (only if automatic fails):
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
python -m patchright install chromium
```

## Data Storage

All data stored in `data/` directory:
- `config.json` - Last used notebook (auto-managed)
- `auth_info.json` - Authentication status
- `browser_state/` - Browser cookies and session

**Security:** Protected by `.gitignore`, never commit to git.

## Configuration

Optional `.env` file in skill directory:
```env
HEADLESS=false           # Browser visibility
SHOW_BROWSER=false       # Default browser display
STEALTH_ENABLED=true     # Human-like behavior
TYPING_WPM_MIN=160       # Typing speed
TYPING_WPM_MAX=240
DEFAULT_NOTEBOOK_ID=     # Default notebook
```

## Decision Flow

```
User mentions NotebookLM
    |
Check auth -> python scripts/run.py auth_manager.py status
    |
If not authenticated -> python scripts/run.py auth_manager.py setup
    |
List notebooks -> python scripts/run.py list_notebooks.py
    |
Ask question -> python scripts/run.py ask_question.py --question "..." --notebook-name "..."
    |
(notebook auto-remembered for follow-ups)
    |
See "Is that ALL you need?" -> Ask follow-ups until complete
    |
Synthesize and respond to user
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| ModuleNotFoundError | Use `run.py` wrapper |
| Authentication fails | Browser must be visible for setup! --show-browser |
| Rate limit (50/day) | Wait or switch Google account |
| Browser crashes | `python scripts/run.py cleanup_manager.py` |
| Notebook not found | Check with `list_notebooks.py`, use `--notebook-name` for fuzzy match |

## Best Practices

1. **Always use run.py** - Handles environment automatically
2. **Check auth first** - Before any operations
3. **Use --notebook-name** - Fuzzy matching is convenient and fetches real data
4. **Follow-up questions** - Don't stop at first answer, notebook is auto-remembered
5. **Browser visible for auth** - Required for manual login
6. **Include context** - Each question is independent
7. **Synthesize answers** - Combine multiple responses

## Limitations

- No session persistence (each question = new browser)
- Rate limits on free Google accounts (50 queries/day)
- Browser overhead (few seconds per question)

## Resources (Skill Structure)

**Important directories and files:**

- `scripts/` - All automation scripts (ask_question.py, list_notebooks.py, etc.)
- `data/` - Local storage for authentication and config
- `references/` - Extended documentation:
  - `api_reference.md` - Detailed API documentation for all scripts
  - `troubleshooting.md` - Common issues and solutions
  - `usage_patterns.md` - Best practices and workflow examples
- `.venv/` - Isolated Python environment (auto-created on first run)
- `.gitignore` - Protects sensitive data from being committed
