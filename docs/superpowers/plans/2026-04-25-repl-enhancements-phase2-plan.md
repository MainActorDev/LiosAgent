# REPL Enhancements Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement explicit file path auto-completion in the Universal REPL when the user types `@`.

**Architecture:** Create a `FileMentionCompleter` inheriting from `prompt_toolkit.completion.Completer`. It will trigger only on `@`, traverse the current directory, exclude hidden files/directories, and prevent navigation outside the project root.

**Tech Stack:** Python, `prompt_toolkit`, `pytest`

---

### Task 1: Implement FileMentionCompleter

**Files:**
- Create: `tests/test_repl_completer.py`
- Modify: `agent/repl.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_repl_completer.py
import os
import pytest
from unittest.mock import patch, MagicMock
from prompt_toolkit.document import Document
from prompt_toolkit.completion import Completion
from agent.repl import FileMentionCompleter

@pytest.fixture
def mock_fs(tmp_path):
    # Create a mock file system structure
    (tmp_path / "visible.txt").touch()
    (tmp_path / ".hidden.txt").touch()
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "visible_in_subdir.txt").touch()
    return tmp_path

def test_completer_triggers_on_at():
    completer = FileMentionCompleter()
    document = Document("Hello @")
    
    # We mock os.listdir to return our files instead of actual fs
    with patch('os.listdir', return_value=['visible.txt', '.hidden.txt', 'subdir']):
        with patch('os.path.isdir', side_effect=lambda p: p.endswith('subdir')):
            completions = list(completer.get_completions(document, MagicMock()))
    
    # Should only return visible items
    texts = [c.text for c in completions]
    assert "visible.txt" in texts
    assert "subdir/" in texts
    assert ".hidden.txt" not in texts
    
    # The start_position should replace everything after @
    assert all(c.start_position == 0 for c in completions)

def test_completer_filters_by_prefix():
    completer = FileMentionCompleter()
    document = Document("Read @vis")
    
    with patch('os.listdir', return_value=['visible.txt', 'other.txt']):
        with patch('os.path.isdir', return_value=False):
            completions = list(completer.get_completions(document, MagicMock()))
    
    texts = [c.text for c in completions]
    assert "visible.txt" in texts
    assert "other.txt" not in texts
    assert all(c.start_position == -3 for c in completions) # replacing "vis"

def test_completer_navigates_subdirs(mock_fs, monkeypatch):
    # Change working directory to our mock filesystem
    monkeypatch.chdir(mock_fs)
    
    completer = FileMentionCompleter()
    document = Document("Check @subdir/")
    
    completions = list(completer.get_completions(document, MagicMock()))
    texts = [c.text for c in completions]
    assert "visible_in_subdir.txt" in texts
    assert all(c.start_position == 0 for c in completions)

def test_completer_blocks_parent_traversal():
    completer = FileMentionCompleter()
    document = Document("Look @../")
    
    completions = list(completer.get_completions(document, MagicMock()))
    assert len(completions) == 0

def test_completer_ignores_non_at_text():
    completer = FileMentionCompleter()
    document = Document("Hello world")
    
    completions = list(completer.get_completions(document, MagicMock()))
    assert len(completions) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_repl_completer.py -v`
Expected: FAIL with "ImportError: cannot import name 'FileMentionCompleter'"

- [ ] **Step 3: Write minimal implementation**

Add the completer class to `agent/repl.py` (before `UniversalREPL`):

```python
import os
import re
from prompt_toolkit.completion import Completer, Completion

class FileMentionCompleter(Completer):
    def get_completions(self, document, complete_event):
        # We only care about the word right before the cursor
        word_before_cursor = document.get_word_before_cursor(WORD=True)
        
        # Does it start with '@'?
        if not word_before_cursor.startswith('@'):
            return

        # Extract the path part
        path_prefix = word_before_cursor[1:]
        
        # Block traversal outside current directory
        if '..' in path_prefix.split(os.sep):
            return

        # Determine the directory to search and the prefix to match
        dirname = os.path.dirname(path_prefix)
        basename = os.path.basename(path_prefix)
        
        search_dir = dirname if dirname else '.'
        
        try:
            # List contents of the directory
            entries = os.listdir(search_dir)
        except OSError:
            # Directory doesn't exist or no permission
            return

        for entry in entries:
            # Ignore hidden files/directories
            if entry.startswith('.'):
                continue
                
            # Filter by the typed prefix
            if entry.startswith(basename):
                # Construct the full relative path for display if needed, 
                # but we usually just yield the completion text.
                
                # Check if it's a directory to append a slash
                full_path = os.path.join(search_dir, entry)
                completion_text = entry
                if os.path.isdir(full_path):
                    completion_text += '/'
                    
                # Yield the completion. 
                # start_position is negative length of the matched prefix.
                yield Completion(completion_text, start_position=-len(basename))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_repl_completer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent/repl.py tests/test_repl_completer.py
git commit -m "feat: implement FileMentionCompleter for @ file auto-completion"
```

### Task 2: Integrate Completer into REPL

**Files:**
- Modify: `tests/test_repl_history.py`
- Modify: `agent/repl.py`

- [ ] **Step 1: Write the failing tests**

Modify `tests/test_repl_history.py` to also assert the completer is passed to `PromptSession`.

```python
# tests/test_repl_history.py
# (Add inside test_history_initialization and test_history_initialization_with_xdg)

    call_kwargs = mock_prompt_session.call_args[1]
    assert "history" in call_kwargs
    assert "lexer" in call_kwargs
    assert "style" in call_kwargs
    assert "completer" in call_kwargs # NEW ASSERTION
    from agent.repl import FileMentionCompleter
    assert isinstance(call_kwargs["completer"], FileMentionCompleter) # NEW ASSERTION
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_repl_history.py -v`
Expected: FAIL because `completer` is not passed to `PromptSession`.

- [ ] **Step 3: Write minimal implementation**

Modify `UniversalREPL.start_interactive_session` in `agent/repl.py`:

```python
    @staticmethod
    def start_interactive_session():
        from prompt_toolkit.history import FileHistory
        from prompt_toolkit.lexers import PygmentsLexer
        import os
        
        console.print(Panel.fit("[bold green]Welcome to the Lios-Agent REPL![/bold green]\nType [cyan]/help[/cyan] for commands or start chatting.", title="Lios", border_style="green"))

        # ... (history setup remains the same) ...

        style = PromptStyle.from_dict({
            'prompt': 'bold cyan',
            'pygments.keyword': 'cyan',
            'pygments.name.class': 'green',
        })
        
        session = PromptSession(
            history=history,
            lexer=PygmentsLexer(LiosLexer),
            completer=FileMentionCompleter(), # ADD THIS LINE
            style=style
        )
        # ... rest remains the same ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_repl_history.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent/repl.py tests/test_repl_history.py
git commit -m "feat: integrate FileMentionCompleter into UniversalREPL PromptSession"
```

