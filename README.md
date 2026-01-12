<div align="center">

# NotebookLM Skill

**Programmatic access to Google NotebookLM for AI coding assistants**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![GitHub](https://img.shields.io/github/stars/sudoprivacy/notebooklm-skill?style=social)](https://github.com/sudoprivacy/notebooklm-skill)

</div>

---

## Important Notice

**This is an UNOFFICIAL tool, not affiliated with, endorsed by, or sponsored by Google.**

### Why This Project Exists

As of January 2025, there's a gap in NotebookLM's official offerings:
- **NotebookLM Plus (Enterprise)**: No mobile app
- **NotebookLM (Personal)**: No API access

This project provides a browser automation bridge for users who need programmatic access to their NotebookLM knowledge bases — whether through Claude Code, Gemini CLI, Codex, or other AI coding assistants that support skill/plugin systems.

**We will sunset this project** once Google provides official API access that meets these needs.

### Legal

- "NotebookLM" and "Google" are trademarks of Google LLC
- This tool uses browser automation to interact with NotebookLM's web interface
- Users are responsible for compliance with Google's Terms of Service
- This project is provided "as-is" for personal and educational purposes
- The authors assume no liability for any account restrictions or other consequences

**Prohibited Uses:**
- Mass bulk operations or scraping
- Commercial use (unless properly authorized)
- Circumventing official service limitations
- Infringing on copyrights or other legal rights

By using this tool, you acknowledge these terms and accept all associated risks.

---

## What It Does

- Query NotebookLM notebooks programmatically
- List, create, and delete notebooks
- Add sources (URLs, YouTube, local files)
- List, toggle, and remove sources
- Persistent authentication via browser automation

All answers are **source-grounded** — NotebookLM only responds based on your uploaded documents, significantly reducing hallucinations.

---

## Installation

```bash
# Clone this repository
git clone https://github.com/sudoprivacy/notebooklm-skill.git

# Symlink to your AI assistant's skill directory
# Example for Claude Code:
ln -s $(pwd)/notebooklm-skill ~/.claude/skills/notebooklm

# Example for other assistants - adapt the path as needed
```

That's it. The skill auto-installs dependencies (Python venv, browser) on first use.

---

## Usage

See **[SKILL.md](SKILL.md)** for complete documentation including:
- Authentication setup
- All available commands
- Script reference
- Troubleshooting

---

## Credits

Forked from [NotebookLM MCP Server](https://github.com/PleasePrompto/notebooklm-mcp) with deep customization: restructured as a skill (not MCP), added notebook listing/creation/deletion, source management (add/list/remove/download), exclude-sources for queries, and extensive workflow improvements.

---

<div align="center">

For source-grounded, document-based research via AI coding assistants

</div>
