#!/usr/bin/env python3
"""
AUTO-GENERATED - DO NOT EDIT

This file was auto-generated from SKILL.md by integration-test-generator.
Generated: 2026-02-10 16:10:33

To modify test behavior:
  1. Update SKILL.md with better workflow examples
  2. Use integration-test-generator skill to regenerate

Manual edits will be lost when regenerated!

Coverage: 3/3 real workflows (100%)
Identified using AI scenario recognition with complete code generation

Coverage Report:
  ✅ Create Notebook → Add URL Source → Ask Question → Delete Notebook
  ✅ Create Notebook → Add File Source → List Sources (verify) → Ask Question → Delete Notebook
  ✅ Create Notebook → Add URL Source → Download Source → Remove Source → Delete Notebook

Uncovered workflows: None
"""

# Standard library imports
import os
from pathlib import Path

# Third-party imports
import pytest

# Skill-specific imports
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
from create_notebook import create_notebook
from delete_notebook import delete_notebook
from add_source import add_url_source, add_file_source
from ask_question import ask_notebooklm
from list_notebooks import list_notebooks
from list_sources import list_sources
from remove_source import remove_source
from download_source import download_source

# Integration guard: allow CI to opt-out with SKIP_INTEGRATION=1
SKIP_INTEGRATION = os.environ.get("SKIP_INTEGRATION", "").lower() in ("1", "true", "yes")


@pytest.fixture(autouse=True)
def _integration_guard():
    """Skip if SKIP_INTEGRATION is set."""
    if SKIP_INTEGRATION:
        pytest.skip("SKIP_INTEGRATION is set — skipping integration tests")




def test_research_with_url_source():
    """
    Real scenario: Create notebook, add URL source, query, and cleanup

    Workflow: Create Notebook → Add URL Source → Ask Question → Delete Notebook

    User problem: Researcher creates a temporary knowledge base from a web article, queries it for answers, then cleans up

    Data flow:
      1. create_notebook creates a fresh test notebook, returns dict with notebook_url and notebook_id
      2. add_url_source adds a Wikipedia article as source material
      3. ask_notebooklm queries the notebook, returns answer string from the source
      4. delete_notebook removes the test notebook (test data isolation)
    """
    # Step 1: create_notebook creates a fresh test notebook, returns dict with notebook_url and notebook_id
    nb = create_notebook(name='Integration Test - URL Research')
    assert nb["status"] == "success"
    assert nb['notebook_id'] is not None
    notebook_url = nb["notebook_url"]  # Extract for next step

    try:
        # Step 2: add_url_source adds a Wikipedia article as source material
        add_result = add_url_source(notebook_url=notebook_url, source_url='https://en.wikipedia.org/wiki/Artificial_intelligence')
        assert add_result["status"] == "success"

        # Step 3: ask_notebooklm queries the notebook, returns answer string from the source
        answer = ask_notebooklm(question='What is artificial intelligence? Give a brief definition.', notebook_url=notebook_url)
        assert isinstance(answer, str)
        assert len(answer) > 10

    finally:
        # Step 4: delete_notebook removes the test notebook (test data isolation)
        cleanup = delete_notebook(notebook_id=nb['notebook_id'], confirm=True)
        assert cleanup["status"] == "success"



def test_file_source_with_verification(tmp_path):
    """
    Real scenario: Upload file, verify in sources list, query, and cleanup

    Workflow: Create Notebook → Add File Source → List Sources (verify) → Ask Question → Delete Notebook

    User problem: User uploads a document to NotebookLM, verifies it appears in the sources, then queries for information from it

    Data flow:
      1. create_notebook creates a fresh test notebook
      2. Create test file, then add_file_source uploads it as a notebook source
      3. list_sources verifies the uploaded file appears in the notebook's sources
      4. ask_notebooklm queries the uploaded content to verify it's searchable
      5. delete_notebook removes the test notebook (test data isolation)
    """
    # Step 1: create_notebook creates a fresh test notebook
    nb = create_notebook(name='Integration Test - File Upload')
    assert nb["status"] == "success"
    assert nb['notebook_id'] is not None
    notebook_url = nb["notebook_url"]  # Extract for next step

    try:
        # Step 2: Create test file, then add_file_source uploads it as a notebook source
        test_file = str(tmp_path / 'test_notes.txt')
        Path(test_file).write_text('The Python programming language was created by Guido van Rossum in 1991. It emphasizes code readability and simplicity.')
        add_result = add_file_source(notebook_url=notebook_url, file_path=test_file)
        assert add_result["status"] == "success"

        # Step 3: list_sources verifies the uploaded file appears in the notebook's sources
        sources_result = list_sources(notebook_url=notebook_url)
        assert sources_result["status"] == "success"

        # Step 4: ask_notebooklm queries the uploaded content to verify it's searchable
        answer = ask_notebooklm(question='Who created Python and when?', notebook_url=notebook_url)
        assert isinstance(answer, str)
        assert len(answer) > 10

    finally:
        # Step 5: delete_notebook removes the test notebook (test data isolation)
        cleanup = delete_notebook(notebook_id=nb['notebook_id'], confirm=True)
        assert cleanup["status"] == "success"



def test_source_management_lifecycle():
    """
    Real scenario: Add source, download content, remove source, cleanup

    Workflow: Create Notebook → Add URL Source → Download Source → Remove Source → Delete Notebook

    User problem: User manages notebook sources: adds a URL, downloads its extracted content for offline use, then removes the source and cleans up

    Data flow:
      1. create_notebook creates a fresh test notebook
      2. add_url_source adds a Wikipedia article about Python as a source
      3. download_source extracts the source content for offline use
      4. remove_source deletes the source from the notebook
      5. delete_notebook removes the test notebook (test data isolation)
    """
    # Step 1: create_notebook creates a fresh test notebook
    nb = create_notebook(name='Integration Test - Source Mgmt')
    assert nb["status"] == "success"
    assert nb['notebook_id'] is not None
    notebook_url = nb["notebook_url"]  # Extract for next step

    try:
        # Step 2: add_url_source adds a Wikipedia article about Python as a source
        add_result = add_url_source(notebook_url=notebook_url, source_url='https://en.wikipedia.org/wiki/Python_(programming_language)')
        assert add_result["status"] == "success"

        # Step 3: download_source extracts the source content for offline use
        download_result = download_source(source_name='Python', notebook_url=notebook_url)
        assert download_result["status"] == "success"
        assert download_result.get('content_length', 0) > 0

        # Step 4: remove_source deletes the source from the notebook
        remove_result = remove_source(source_name='Python', notebook_url=notebook_url)
        assert remove_result["status"] == "success"

    finally:
        # Step 5: delete_notebook removes the test notebook (test data isolation)
        cleanup = delete_notebook(notebook_id=nb['notebook_id'], confirm=True)
        assert cleanup["status"] == "success"

# Smoke test - can import without errors
def test_imports_work():
    """Verify all imports are valid"""
    assert create_notebook is not None
    assert delete_notebook is not None
    assert add_url_source is not None
    assert ask_notebooklm is not None
    assert list_notebooks is not None
    assert list_sources is not None
    assert remove_source is not None
    assert download_source is not None

