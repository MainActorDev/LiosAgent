# REPL Enhancements Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement persistent command history and live syntax highlighting in the Universal REPL.

**Architecture:** We will integrate `pygments` with `prompt_toolkit` to create a `LiosLexer` for coloring slash commands and file paths. We will also initialize `FileHistory` from `prompt_toolkit` to save history to `~/.config/lios/.lios_history`.

**Tech Stack:** Python, `prompt_toolkit`, `pygments`, `pytest`

---

### Task 1: Add Pygments Dependency

**Files:**
- Modify: `requirements.txt`
- Modify: `pyproject.toml` (if it exists, we will just use requirements.txt to be safe)

- [ ] **Step 1: Write the failing test**

There isn't a direct unit test for dependency addition, but we can write a test that attempts to import the required module and fails if it's missing.

```python
# tests/test_dependencies.py
def test_pygments_installed():
    try:
        import pygments
        assert True
    except ImportError:
        assert False, "Pygments is not installed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dependencies.py -v`
Expected: FAIL with "Pygments is not installed" (assuming it's not already installed)

- [ ] **Step 3: Write minimal implementation**

Add `pygments>=2.15.0` to `requirements.txt`.

```text
# requirements.txt (append)
pygments>=2.15.0
```
Then run `pip install -r requirements.txt`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_dependencies.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add requirements.txt tests/test_dependencies.py
git commit -m "build: add pygments dependency for syntax highlighting"
```

### Task 2: Implement LiosLexer

**Files:**
- Create: `tests/test_repl_lexer.py`
- Modify: `agent/repl.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_repl_lexer.py
from pygments.token import Token
from agent.repl import LiosLexer

def test_lios_lexer():
    lexer = LiosLexer()
    
    # Test slash command
    tokens = list(lexer.get_tokens_unprocessed("/help"))
    assert len(tokens) == 2
    assert tokens[0][1] == Token.Keyword
    assert tokens[0][2] == "/help"

    # Test file path
    tokens = list(lexer.get_tokens_unprocessed("@src/main.py"))
    assert len(tokens) == 2
    assert tokens[0][1] == Token.Name.Class
    assert tokens[0][2] == "@src/main.py"
    
    # Test standard text
    tokens = list(lexer.get_tokens_unprocessed("hello world"))
    assert len(tokens) == 2
    assert tokens[0][1] == Token.Text
    assert tokens[0][2] == "hello world"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_repl_lexer.py -v`
Expected: FAIL with "ImportError: cannot import name 'LiosLexer'"

- [ ] **Step 3: Write minimal implementation**

Modify `agent/repl.py` to include the lexer at the top of the file.

```python
import os
import shlex
import typer
from rich.console import Console
from rich.panel import Panel
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style as PromptStyle
from prompt_toolkit.lexers import PygmentsLexer
from pygments.lexer import RegexLexer
from pygments.token import Token

console = Console()

class LiosLexer(RegexLexer):
    name = 'Lios'
    aliases = ['lios']
    filenames = []

    tokens = {
        'root': [
            (r'^/\w+', Token.Keyword),        # Slash commands
            (r'@[\w./-]+', Token.Name.Class), # File paths
            (r'[^/@\n]+', Token.Text),        # Standard text
            (r'.', Token.Text),               # Fallback
        ]
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_repl_lexer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent/repl.py tests/test_repl_lexer.py
git commit -m "feat: implement LiosLexer for REPL syntax highlighting"
```

### Task 3: Integrate Lexer and History into REPL

**Files:**
- Create: `tests/test_repl_history.py`
- Modify: `agent/repl.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_repl_history.py
import os
from unittest.mock import patch, MagicMock
from agent.repl import UniversalREPL

@patch("agent.repl.PromptSession")
@patch("agent.repl.os.makedirs")
def test_history_initialization(mock_makedirs, mock_prompt_session):
    # Setup mock to immediately raise EOFError to exit the loop
    mock_instance = MagicMock()
    mock_instance.prompt.side_effect = EOFError()
    mock_prompt_session.return_value = mock_instance
    
    UniversalREPL.start_interactive_session()
    
    # Verify os.makedirs was called to ensure ~/.config/lios exists
    expected_path = os.path.expanduser("~/.config/lios")
    mock_makedirs.assert_called_with(expected_path, exist_ok=True)
    
    # Verify PromptSession was called with history and lexer args
    call_kwargs = mock_prompt_session.call_args[1]
    assert "history" in call_kwargs
    assert "lexer" in call_kwargs
    assert "style" in call_kwargs
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_repl_history.py -v`
Expected: FAIL because `os.makedirs` is not called and `PromptSession` isn't called with the new arguments.

- [ ] **Step 3: Write minimal implementation**

Modify `UniversalREPL.start_interactive_session` in `agent/repl.py`:

```python
    @staticmethod
    def start_interactive_session():
        from prompt_toolkit.history import FileHistory
        from prompt_toolkit.lexers import PygmentsLexer
        import os
        
        console.print(Panel.fit("[bold green]Welcome to the Lios-Agent REPL![/bold green]\nType [cyan]/help[/cyan] for commands or start chatting.", title="Lios", border_style="green"))
        
        # Setup history
        config_dir = os.path.expanduser("~/.config/lios")
        try:
            os.makedirs(config_dir, exist_ok=True)
            history_file = os.path.join(config_dir, ".lios_history")
            history = FileHistory(history_file)
        except Exception as e:
            console.print(f"[bold yellow]Warning: Could not initialize history file ({e})[/bold yellow]")
            history = None

        style = PromptStyle.from_dict({
            'prompt': 'bold cyan',
            'pygments.keyword': 'cyan',
            'pygments.name.class': 'green',
        })
        
        session = PromptSession(
            history=history,
            lexer=PygmentsLexer(LiosLexer),
            style=style
        )
        
        chat_history = []
        
        while True:
            try:
                # Use the session to prompt
                text = session.prompt("lios> ")
                # ... rest of the while loop remains exactly the same ...
```
*Note: Make sure to replace `text = session.prompt([('class:prompt', 'lios> ')], style=style)` or whatever the old prompt was with the correct arguments matching the old signature but using the session state.*

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_repl_history.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent/repl.py tests/test_repl_history.py
git commit -m "feat: integrate history and syntax highlighting into UniversalREPL"
```
````