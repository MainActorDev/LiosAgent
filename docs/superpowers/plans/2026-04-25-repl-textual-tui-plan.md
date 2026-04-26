# REPL Textual TUI Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `agent/repl.py` from Rich+prompt_toolkit to a Textual TUI application matching the prototype in `docs/cli_ui_prototype.html` at ~95% visual fidelity.

**Architecture:** Split the monolithic `agent/repl.py` (349 lines) into an `agent/repl/` package with dedicated modules for the Textual app, widgets, theme, LLM bridge, command routing, and a backward-compatible shim. The existing `agent/repl.py` becomes a thin re-export file so all external imports (`from agent.repl import X`) continue to work.

**Tech Stack:** Python 3.11+, Textual >=0.50.0, Rich (Textual dependency), LangChain (ChatOpenAI `.stream()`), Pygments (LiosLexer preserved)

**Spec:** `docs/superpowers/specs/2026-04-25-repl-textual-tui-design.md`

---

## File Structure

```
agent/
  repl.py                          # MODIFIED: becomes thin re-export shim (replaces 349-line file)
  repl/
    __init__.py                    # CREATE: re-exports UniversalREPL, FileMentionCompleter, LiosLexer
    app.py                         # CREATE: LiosChatApp(textual.App)
    widgets/
      __init__.py                  # CREATE: re-exports all widgets
      chat_log.py                  # CREATE: ChatLog(VerticalScroll)
      message_bubble.py            # CREATE: UserMessage, AgentMessage, ThinkingIndicator
      input_bar.py                 # CREATE: ChatInput(Input) with highlighter + suggester
      status_bar.py                # CREATE: StatusBar(Static)
      welcome.py                   # CREATE: WelcomeBanner(Static)
    theme.py                       # CREATE: design tokens + APP_CSS
    completer.py                   # CREATE: FileMentionCompleter (moved from repl.py, unchanged API)
    lexer.py                       # CREATE: LiosLexer (moved from repl.py, unchanged API)
    parse_input.py                 # CREATE: parse_input() pure function
    llm_bridge.py                  # CREATE: LLMBridge class with streaming + token tracking
    commands.py                    # CREATE: command routing handlers
    legacy.py                      # CREATE: UniversalREPL facade class
tests/
  test_repl_completer.py           # UNCHANGED (imports from agent.repl still work via shim)
  test_repl_lexer.py               # UNCHANGED
  test_repl_history.py             # REWRITE: test Textual app widget composition
  test_repl_parse_input.py         # CREATE: test parse_input() pure function
  test_repl_commands.py            # CREATE: test command routing
  test_repl_llm_bridge.py          # CREATE: test token/cost tracking
  test_repl_app.py                 # CREATE: Textual pilot integration tests
requirements.txt                   # MODIFY: add textual>=0.50.0
```

---

### Task 1: Add Textual Dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add textual to requirements.txt**

Add `textual>=0.50.0` after the existing `pygments>=2.15.0` line:

```
textual>=0.50.0
```

The full `requirements.txt` becomes:
```
PyGithub>=2.1.1
python-dotenv>=1.0.0
langchain>=0.2.0
langchain-core>=0.2.0
langchain-openai>=0.1.0
langgraph>=0.1.0
mcp>=1.0.0
langchain-mcp-adapters>=0.1.0
langgraph-checkpoint-sqlite
aiosqlite
typer>=0.9.0
rich>=13.0.0
pyyaml>=6.0.1
pytest>=8.0.0
pytest-mock>=3.12.0
prompt_toolkit
pygments>=2.15.0
textual>=0.50.0
```

- [ ] **Step 2: Install the new dependency**

Run: `pip install textual>=0.50.0`
Expected: Successfully installed textual and any sub-dependencies.

- [ ] **Step 3: Verify import works**

Run: `python -c "import textual; print(textual.__version__)"`
Expected: Prints version >= 0.50.0

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "deps: add textual>=0.50.0 for TUI refactor"
```

---

### Task 2: Create Package Structure + Theme Module

**Files:**
- Rename: `agent/repl.py` → `agent/repl_old.py` (temporary, to unblock package creation)
- Create: `agent/repl/__init__.py`
- Create: `agent/repl/theme.py`
- Create: `agent/repl/widgets/__init__.py`

**IMPORTANT:** Python cannot have both `agent/repl.py` (module) and `agent/repl/` (package). We must rename the old file first.

- [ ] **Step 1: Rename the old repl.py to unblock package creation**

Run: `git mv agent/repl.py agent/repl_old.py`

This preserves git history and allows the `agent/repl/` directory to be created. The old file remains available as `agent/repl_old.py` for reference and is used by existing tests until Task 12.

**Update test imports temporarily:** The existing tests import from `agent.repl`. After renaming, they'll break. We need to create the `__init__.py` that re-exports from the old file first, then progressively switch to the new modules.

- [ ] **Step 2: Create the agent/repl/ directory and __init__.py**

Create `agent/repl/__init__.py` that initially re-exports from the OLD file (will be updated in Task 12):

```python
"""
agent.repl package — Textual TUI for Lios-Agent REPL.

Re-exports public API for backward compatibility with `from agent.repl import X`.
Initially re-exports from the renamed old module; updated to use new modules in Task 12.
"""

from agent.repl_old import FileMentionCompleter, LiosLexer, UniversalREPL

__all__ = ["UniversalREPL", "FileMentionCompleter", "LiosLexer"]
```

- [ ] **Step 2: Create agent/repl/widgets/__init__.py**

Create `agent/repl/widgets/__init__.py`:

```python
"""Widget re-exports for the Lios TUI."""

from agent.repl.widgets.welcome import WelcomeBanner
from agent.repl.widgets.chat_log import ChatLog
from agent.repl.widgets.message_bubble import UserMessage, AgentMessage, ThinkingIndicator
from agent.repl.widgets.input_bar import ChatInput
from agent.repl.widgets.status_bar import StatusBar

__all__ = [
    "WelcomeBanner",
    "ChatLog",
    "UserMessage",
    "AgentMessage",
    "ThinkingIndicator",
    "ChatInput",
    "StatusBar",
]
```

- [ ] **Step 3: Create agent/repl/theme.py**

Create `agent/repl/theme.py` with design tokens from the prototype and the Textual CSS string:

```python
"""Design tokens and Textual CSS for the Lios TUI."""

# ── Color Tokens ──────────────────────────────────────────────
BG_DEEP = "#0B1120"
BG_PRIMARY = "#0F172A"
BG_SURFACE = "#1E293B"
BG_ELEVATED = "#334155"

GREEN = "#22C55E"
CYAN = "#06B6D4"
PURPLE = "#A78BFA"
AMBER = "#F59E0B"
RED = "#EF4444"

TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#94A3B8"
TEXT_MUTED = "#64748B"

# ── Textual Application CSS ──────────────────────────────────
APP_CSS = """
Screen {
    background: """ + BG_PRIMARY + """;
}

/* ── Welcome Banner ─────────────────────────────────────── */
WelcomeBanner {
    padding: 1 2;
    margin-bottom: 1;
}

/* ── Chat Log ───────────────────────────────────────────── */
ChatLog {
    height: 1fr;
    overflow-y: auto;
    padding: 0 1;
}

/* ── User Message ───────────────────────────────────────── */
UserMessage {
    padding: 0 2;
    margin: 0 0;
}

/* ── Agent Message ──────────────────────────────────────── */
AgentMessage {
    border-left: solid """ + BG_ELEVATED + """;
    padding: 0 0 0 2;
    margin: 1 0;
}

AgentMessage Markdown {
    color: """ + TEXT_SECONDARY + """;
}

/* ── Thinking Indicator ─────────────────────────────────── */
ThinkingIndicator {
    padding: 0 0 0 2;
    height: auto;
    color: """ + TEXT_MUTED + """;
}

ThinkingIndicator LoadingIndicator {
    color: """ + PURPLE + """;
    width: 4;
    height: 1;
}

/* ── Chat Input ─────────────────────────────────────────── */
ChatInput {
    dock: bottom;
    height: auto;
    max-height: 3;
    background: """ + BG_DEEP + """;
    padding: 0 1;
    margin: 0;
}

ChatInput:focus {
    border: solid """ + GREEN + """;
}

/* ── Status Bar ─────────────────────────────────────────── */
StatusBar {
    dock: bottom;
    height: 1;
    background: """ + BG_DEEP + """;
    color: """ + TEXT_MUTED + """;
    padding: 0 2;
}
"""
```

- [ ] **Step 4: Verify the theme module imports cleanly**

Run: `python -c "from agent.repl.theme import APP_CSS, BG_PRIMARY, GREEN; print('OK')"`
Expected: `OK` (no import errors)

- [ ] **Step 5: Verify existing tests still pass via the shim**

Run: `pytest tests/test_repl_completer.py tests/test_repl_lexer.py -v`
Expected: All tests PASS (the `__init__.py` re-exports from `agent.repl_old` which has the original classes).

Note: The `widgets/__init__.py` will fail to import until widget modules are created in later tasks. That's expected — it's not imported by anything yet.

- [ ] **Step 6: Commit**

```bash
git add agent/repl/__init__.py agent/repl/theme.py agent/repl/widgets/__init__.py agent/repl_old.py
git commit -m "scaffold: rename repl.py, create agent/repl/ package structure and theme module"
```

---

**Note on test_repl_history.py:** After Task 2, `tests/test_repl_history.py` will break because it patches `agent.repl.PromptSession` and `agent.repl.os.makedirs`, which no longer exist in the package `__init__.py`. This is expected — these tests are rewritten in Task 13. During Tasks 3-12, only run the completer, lexer, and cli_default tests to verify backward compatibility.

---

### Task 3: Extract FileMentionCompleter and LiosLexer

**Files:**
- Create: `agent/repl/completer.py`
- Create: `agent/repl/lexer.py`

These are direct copies from the current `agent/repl.py` with no logic changes.

- [ ] **Step 1: Create agent/repl/completer.py**

```python
"""File mention autocomplete for the Lios REPL input."""

import os
from prompt_toolkit.completion import Completer, Completion


class FileMentionCompleter(Completer):
    """Triggers on '@', suggests file paths from the working directory."""

    def get_completions(self, document, complete_event):
        word_before_cursor = document.get_word_before_cursor(WORD=True)

        if not word_before_cursor.startswith("@"):
            return

        path_prefix = word_before_cursor[1:]

        # Block traversal outside current directory
        if ".." in path_prefix.split(os.sep):
            return

        dirname = os.path.dirname(path_prefix)
        basename = os.path.basename(path_prefix)

        search_dir = dirname if dirname else "."

        try:
            entries = os.listdir(search_dir)
        except OSError:
            return

        for entry in entries:
            if entry.startswith("."):
                continue

            if entry.startswith(basename):
                full_path = os.path.join(search_dir, entry)
                completion_text = entry
                if os.path.isdir(full_path):
                    completion_text += "/"

                yield Completion(completion_text, start_position=-len(basename))
```

- [ ] **Step 2: Create agent/repl/lexer.py**

```python
"""Pygments lexer for Lios REPL input highlighting."""

from pygments.lexer import RegexLexer
from pygments.token import Token


class LiosLexer(RegexLexer):
    name = "Lios"
    aliases = ["lios"]
    filenames = []

    tokens = {
        "root": [
            (r"^/\w+", Token.Keyword),         # Slash commands
            (r"@[\w./-]+", Token.Name.Class),   # File paths
            (r"[^/@\n]+", Token.Text),          # Standard text
            (r".", Token.Text),                  # Fallback
        ]
    }
```

- [ ] **Step 3: Run existing completer tests**

Run: `pytest tests/test_repl_completer.py -v`
Expected: All 5 tests PASS (they still import from `agent.repl` which hasn't been replaced yet — this verifies the extracted code is identical).

Actually, the tests import from `agent.repl` (the old file), so they'll still pass. We need to also verify the new module directly:

Run: `python -c "from agent.repl.completer import FileMentionCompleter; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Run existing lexer test**

Run: `pytest tests/test_repl_lexer.py -v`
Expected: 1 test PASSES.

Also verify the new module:
Run: `python -c "from agent.repl.lexer import LiosLexer; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add agent/repl/completer.py agent/repl/lexer.py
git commit -m "extract: move FileMentionCompleter and LiosLexer to agent/repl/ package"
```

---

### Task 4: Extract parse_input() as Pure Function

**Files:**
- Create: `agent/repl/parse_input.py`
- Create: `tests/test_repl_parse_input.py`

The spec changes the API: `parse_input()` now returns `(processed_text: str, attachments: list[dict])` instead of just a string. Each attachment dict has `{"path": str, "lines": int}`.

- [ ] **Step 1: Write failing tests for parse_input**

Create `tests/test_repl_parse_input.py`:

```python
"""Tests for the parse_input pure function."""

import os
import pytest
from agent.repl.parse_input import parse_input


def test_no_mentions_returns_unchanged(tmp_path):
    text, attachments = parse_input("hello world", str(tmp_path))
    assert text == "hello world"
    assert attachments == []


def test_single_file_mention(tmp_path):
    # Create a test file
    test_file = tmp_path / "readme.md"
    test_file.write_text("# Hello\nWorld\n")

    text, attachments = parse_input("check @readme.md please", str(tmp_path))

    assert "### Injected Context from @mentions:" in text
    assert "--- readme.md ---" in text
    assert "# Hello" in text
    assert len(attachments) == 1
    assert attachments[0]["path"] == "readme.md"
    assert attachments[0]["lines"] == 2


def test_multiple_file_mentions(tmp_path):
    (tmp_path / "a.py").write_text("line1\nline2\nline3\n")
    (tmp_path / "b.py").write_text("x\n")

    text, attachments = parse_input("compare @a.py and @b.py", str(tmp_path))

    assert len(attachments) == 2
    paths = {a["path"] for a in attachments}
    assert paths == {"a.py", "b.py"}


def test_duplicate_mentions_deduplicated(tmp_path):
    (tmp_path / "file.txt").write_text("content\n")

    text, attachments = parse_input("@file.txt and @file.txt again", str(tmp_path))

    # Should only attach once
    assert len(attachments) == 1


def test_missing_file_still_noted(tmp_path):
    text, attachments = parse_input("look at @nonexistent.py", str(tmp_path))

    assert "nonexistent.py (NOT FOUND)" in text
    assert attachments == []


def test_file_read_error(tmp_path):
    # Create a directory with the same name as the mention (can't read as file)
    (tmp_path / "adir").mkdir()

    text, attachments = parse_input("check @adir", str(tmp_path))

    # adir is not a file, so it should be NOT FOUND
    assert attachments == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_repl_parse_input.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent.repl.parse_input'`

- [ ] **Step 3: Implement parse_input**

Create `agent/repl/parse_input.py`:

```python
"""Pure function to parse @file mentions from user input."""

import os
import re


def parse_input(
    user_input: str, workspace_root: str = "."
) -> tuple[str, list[dict]]:
    """Parse user input for @file mentions.

    Returns:
        A tuple of (processed_text, attachments).
        - processed_text: the original input with file contents appended.
        - attachments: list of {"path": str, "lines": int} for each
          successfully read file.
    """
    pattern = r"@([a-zA-Z0-9_./-]+)"
    matches = re.findall(pattern, user_input)

    if not matches:
        return user_input, []

    compiled_input = user_input + "\n\n### Injected Context from @mentions:\n"
    attachments: list[dict] = []
    seen: set[str] = set()

    for filepath in matches:
        if filepath in seen:
            continue
        seen.add(filepath)

        full_path = os.path.join(workspace_root, filepath)
        if os.path.isfile(full_path):
            try:
                with open(full_path, "r") as f:
                    content = f.read()
                line_count = len(content.splitlines())
                compiled_input += f"\n--- {filepath} ---\n```\n{content}\n```\n"
                attachments.append({"path": filepath, "lines": line_count})
            except Exception:
                compiled_input += f"\n--- {filepath} (ERROR) ---\nCould not read file.\n"
        else:
            compiled_input += f"\n--- {filepath} (NOT FOUND) ---\n"

    return compiled_input, attachments
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_repl_parse_input.py -v`
Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/repl/parse_input.py tests/test_repl_parse_input.py
git commit -m "feat: extract parse_input() as pure function with attachment metadata"
```

---

### Task 5: Create Widgets — WelcomeBanner, StatusBar

**Files:**
- Create: `agent/repl/widgets/welcome.py`
- Create: `agent/repl/widgets/status_bar.py`

These are the simplest widgets — static content, no interactivity.

- [ ] **Step 1: Create WelcomeBanner widget**

Create `agent/repl/widgets/welcome.py`:

```python
"""Welcome banner shown at the top of the Lios TUI."""

from textual.widgets import Static
from rich.text import Text

from agent.repl.theme import GREEN, TEXT_PRIMARY, TEXT_MUTED


class WelcomeBanner(Static):
    """Displays the Lios welcome message at app startup."""

    def __init__(self, version: str = "0.4.2", **kwargs) -> None:
        super().__init__(**kwargs)
        self._version = version

    def render(self) -> Text:
        text = Text()
        text.append("  ⬢  ", style=f"bold {GREEN}")
        text.append(f"Lios Agent v{self._version}", style=f"bold {TEXT_PRIMARY}")
        text.append("\n")
        text.append(
            "  Type a message to chat, /help for commands, @ to mention files",
            style=TEXT_MUTED,
        )
        return text
```

- [ ] **Step 2: Create StatusBar widget**

Create `agent/repl/widgets/status_bar.py`:

```python
"""Persistent status bar at the bottom of the Lios TUI."""

from textual.widgets import Static
from rich.text import Text

from agent.repl.theme import GREEN, TEXT_MUTED


class StatusBar(Static):
    """Shows connection status, model name, token count, and cost."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._model_name: str = ""
        self._total_tokens: int = 0
        self._total_cost: float = 0.0
        self._connected: bool = False

    def set_connected(self, model_name: str) -> None:
        """Mark as connected with the given model name."""
        self._model_name = model_name
        self._connected = True
        self._refresh_display()

    def update_stats(self, total_tokens: int, total_cost: float) -> None:
        """Update cumulative token and cost counters."""
        self._total_tokens = total_tokens
        self._total_cost = total_cost
        self._refresh_display()

    def _refresh_display(self) -> None:
        """Re-render the status bar content."""
        self.update(self.render())

    def render(self) -> Text:
        width = self.size.width if self.size.width > 0 else 80

        left = Text()
        if self._connected:
            left.append("  ● ", style=f"bold {GREEN}")
            left.append("Connected", style=TEXT_MUTED)
            left.append(f" · {self._model_name}", style=TEXT_MUTED)
        else:
            left.append("  ○ ", style=TEXT_MUTED)
            left.append("Disconnected", style=TEXT_MUTED)

        right = Text()
        if self._total_tokens > 0:
            right.append(f"{self._total_tokens:,} tokens", style=TEXT_MUTED)
            right.append(f" · ${self._total_cost:.2f}", style=TEXT_MUTED)

        # Pad to fill the width
        gap = max(1, width - len(left.plain) - len(right.plain))
        combined = Text()
        combined.append_text(left)
        combined.append(" " * gap)
        combined.append_text(right)
        return combined
```

- [ ] **Step 3: Verify widgets import**

Run: `python -c "from agent.repl.widgets.welcome import WelcomeBanner; from agent.repl.widgets.status_bar import StatusBar; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add agent/repl/widgets/welcome.py agent/repl/widgets/status_bar.py
git commit -m "feat: add WelcomeBanner and StatusBar widgets"
```

---

### Task 6: Create Widgets — ChatLog, MessageBubbles, ThinkingIndicator

**Files:**
- Create: `agent/repl/widgets/chat_log.py`
- Create: `agent/repl/widgets/message_bubble.py`

- [ ] **Step 1: Create ChatLog widget**

Create `agent/repl/widgets/chat_log.py`:

```python
"""Scrollable chat log container."""

from textual.containers import VerticalScroll


class ChatLog(VerticalScroll):
    """Scrollable container that holds all chat messages.

    Call .anchor() to pin scroll to the bottom during streaming.
    """

    pass
```

- [ ] **Step 2: Create message bubble widgets**

Create `agent/repl/widgets/message_bubble.py`:

```python
"""Chat message widgets: user turns, agent turns, and thinking indicator."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static, Markdown, LoadingIndicator
from rich.text import Text

from agent.repl.theme import GREEN, CYAN, PURPLE, TEXT_PRIMARY, TEXT_MUTED


class UserMessage(Static):
    """Displays a user turn with green chevron and optional file attachments."""

    def __init__(self, content: str, attachments: list[dict] | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._content = content
        self._attachments = attachments or []

    def render(self) -> Text:
        text = Text()
        text.append("  ❯  ", style=f"bold {GREEN}")
        # Highlight @mentions in cyan within the user text
        self._render_with_mentions(text, self._content)

        for att in self._attachments:
            text.append("\n")
            text.append("     📎 ", style=TEXT_MUTED)
            text.append(
                f"Attached {att['path']} ({att['lines']} lines)",
                style=TEXT_MUTED,
            )
        return text

    @staticmethod
    def _render_with_mentions(text: Text, content: str) -> None:
        """Append content to text, highlighting @mentions in cyan."""
        import re

        parts = re.split(r"(@[a-zA-Z0-9_./-]+)", content)
        for part in parts:
            if part.startswith("@"):
                text.append(part, style=f"bold {CYAN}")
            else:
                text.append(part, style=TEXT_PRIMARY)


class AgentMessage(Vertical):
    """Displays an agent response with left border, label, and streaming markdown."""

    def __init__(self, model_name: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._model_name = model_name

    def compose(self) -> ComposeResult:
        label = Text()
        label.append("  ☀ LIOS", style=f"bold {PURPLE}")
        if self._model_name:
            label.append(f" · {self._model_name}", style=TEXT_MUTED)
        yield Static(label, classes="agent-label")
        yield Markdown("", classes="agent-content")

    def get_markdown_widget(self) -> Markdown:
        """Return the Markdown widget for streaming updates."""
        return self.query_one(".agent-content", Markdown)


class ThinkingIndicator(Horizontal):
    """Purple spinner + 'Thinking...' label, removed when first token arrives."""

    def compose(self) -> ComposeResult:
        yield LoadingIndicator()
        yield Static(
            Text("Thinking...", style=TEXT_MUTED),
            classes="thinking-label",
        )
```

- [ ] **Step 3: Verify widgets import**

Run: `python -c "from agent.repl.widgets.chat_log import ChatLog; from agent.repl.widgets.message_bubble import UserMessage, AgentMessage, ThinkingIndicator; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add agent/repl/widgets/chat_log.py agent/repl/widgets/message_bubble.py
git commit -m "feat: add ChatLog, UserMessage, AgentMessage, ThinkingIndicator widgets"
```

---

### Task 7: Create ChatInput Widget with Highlighter and Suggester

**Files:**
- Create: `agent/repl/widgets/input_bar.py`

- [ ] **Step 1: Create ChatInput with highlighter and suggester**

Create `agent/repl/widgets/input_bar.py`:

```python
"""Chat input widget with syntax highlighting and file path suggestions."""

import os
import re

from rich.highlighter import Highlighter
from rich.text import Text
from textual.suggester import Suggester
from textual.widgets import Input

from agent.repl.theme import AMBER, CYAN, GREEN


class ChatInputHighlighter(Highlighter):
    """Highlights /commands in amber and @file mentions in cyan."""

    def highlight(self, text: Text) -> None:
        plain = text.plain
        # Highlight /commands at start of input
        for match in re.finditer(r"^/\w+", plain):
            text.stylize(f"bold {AMBER}", match.start(), match.end())
        # Highlight @file mentions
        for match in re.finditer(r"@[\w./-]+", plain):
            text.stylize(f"bold {CYAN}", match.start(), match.end())


class FileMentionSuggester(Suggester):
    """Ghost-text file path suggestions triggered by @.

    Wraps the same directory-listing logic as FileMentionCompleter
    but returns a single suggestion string for the entire input value.
    """

    def __init__(self, workspace_root: str = ".") -> None:
        super().__init__(use_cache=False)
        self._workspace_root = workspace_root

    async def get_suggestion(self, value: str) -> str | None:
        at_idx = value.rfind("@")
        if at_idx == -1:
            return None

        partial = value[at_idx + 1 :]
        prefix = value[: at_idx + 1]

        dirname = os.path.dirname(partial)
        basename = os.path.basename(partial)
        search_dir = os.path.join(
            self._workspace_root, dirname if dirname else "."
        )

        try:
            entries = sorted(os.listdir(search_dir))
        except OSError:
            return None

        for entry in entries:
            if entry.startswith("."):
                continue
            if entry.lower().startswith(basename.lower()) and entry != basename:
                suggestion_path = os.path.join(dirname, entry) if dirname else entry
                if os.path.isdir(os.path.join(search_dir, entry)):
                    suggestion_path += "/"
                return prefix + suggestion_path

        return None


class ChatInput(Input):
    """Styled input widget for the Lios TUI chat."""

    def __init__(self, **kwargs) -> None:
        super().__init__(
            placeholder="Type a message...",
            highlighter=ChatInputHighlighter(),
            suggester=FileMentionSuggester(),
            **kwargs,
        )
```

- [ ] **Step 2: Verify import**

Run: `python -c "from agent.repl.widgets.input_bar import ChatInput; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add agent/repl/widgets/input_bar.py
git commit -m "feat: add ChatInput widget with highlighter and file path suggester"
```

---

### Task 8: Create LLM Bridge with Streaming and Token Tracking

**Files:**
- Create: `agent/repl/llm_bridge.py`
- Create: `tests/test_repl_llm_bridge.py`

- [ ] **Step 1: Write failing tests for LLMBridge**

Create `tests/test_repl_llm_bridge.py`:

```python
"""Tests for LLMBridge token/cost tracking."""

import pytest
from unittest.mock import MagicMock, patch
from agent.repl.llm_bridge import LLMBridge


@pytest.fixture
def bridge():
    """Create an LLMBridge with a mocked LLM."""
    with patch("agent.repl.llm_bridge.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.model_name = "gpt-4o"
        mock_get_llm.return_value = mock_llm
        b = LLMBridge()
        b._ensure_llm()
        return b


def test_initial_state(bridge):
    assert bridge.total_input_tokens == 0
    assert bridge.total_output_tokens == 0
    assert bridge.total_cost == 0.0
    assert bridge.model_name == "gpt-4o"


def test_accumulate_usage(bridge):
    bridge.accumulate_usage(input_tokens=100, output_tokens=50)
    assert bridge.total_input_tokens == 100
    assert bridge.total_output_tokens == 50
    assert bridge.total_tokens == 150

    bridge.accumulate_usage(input_tokens=200, output_tokens=100)
    assert bridge.total_input_tokens == 300
    assert bridge.total_output_tokens == 150
    assert bridge.total_tokens == 450


def test_cost_calculation_gpt4o(bridge):
    # gpt-4o: $2.50/1M input, $10.00/1M output
    bridge.accumulate_usage(input_tokens=1_000_000, output_tokens=1_000_000)
    assert abs(bridge.total_cost - 12.50) < 0.01


def test_cost_calculation_unknown_model():
    with patch("agent.repl.llm_bridge.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.model_name = "some-unknown-model"
        mock_get_llm.return_value = mock_llm
        b = LLMBridge()
        b._ensure_llm()
        b.accumulate_usage(input_tokens=1000, output_tokens=500)
        assert b.total_cost == 0.0
        assert b.total_tokens == 1500


def test_history_management(bridge):
    assert len(bridge.history) == 0
    bridge.add_system_prompt("You are helpful.")
    assert len(bridge.history) == 1
    bridge.add_user_message("Hello")
    assert len(bridge.history) == 2
    bridge.add_ai_message("Hi there!")
    assert len(bridge.history) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_repl_llm_bridge.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent.repl.llm_bridge'`

- [ ] **Step 3: Implement LLMBridge**

Create `agent/repl/llm_bridge.py`:

```python
"""Async-friendly LLM wrapper with streaming and token/cost tracking."""

from __future__ import annotations

from typing import Generator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


# Pricing per 1M tokens: (input_cost, output_cost)
PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-3.5-turbo": (0.50, 1.50),
    "glm-4": (1.00, 1.00),
    "glm-5.1": (1.00, 1.00),
}

SYSTEM_PROMPT = """You are Lios, an Autonomous iOS Engineer.
The user is talking to you via your interactive CLI mode.
You can help them brainstorm, explain how to use the CLI, or answer general questions.
The available CLI commands are: /epic <name>, /story <epic> <id>, /execute <vault>, /board.
Keep your answers concise, helpful, and formatted in markdown."""

INTAKE_SYSTEM_PROMPT = """You are an expert iOS Product Manager. The user wants to build a new feature.
They will provide an initial PRD or description. Ask clarifying questions until you have enough detail to write a comprehensive technical PRD.
Do not write the PRD yet. Just ask 1-2 focused questions at a time to clarify the user's intent.
Once you have enough detail to proceed with architecture, or if the user explicitly says they are done, output exactly 'READY_TO_ARCHITECT' on a new line. Do not output this prematurely."""


def _get_pricing(model_name: str) -> tuple[float, float]:
    """Look up pricing for a model name, matching by prefix."""
    for prefix, costs in PRICING.items():
        if model_name.startswith(prefix):
            return costs
    return (0.0, 0.0)


def get_llm():
    """Lazy import to avoid circular deps."""
    from agent.llm_factory import get_llm as factory_get_llm

    return factory_get_llm


class LLMBridge:
    """Wraps LangChain ChatOpenAI with streaming, history, and cost tracking."""

    def __init__(self) -> None:
        self._llm = None
        self._model_name: str = ""
        self.history: list = []
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.total_cost: float = 0.0

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    def _ensure_llm(self) -> None:
        """Initialize the LLM on first use."""
        if self._llm is None:
            factory = get_llm()
            self._llm = factory(role="planning")
            self._model_name = getattr(self._llm, "model_name", "unknown")

    def add_system_prompt(self, content: str) -> None:
        self.history.append(SystemMessage(content=content))

    def add_user_message(self, content: str) -> None:
        self.history.append(HumanMessage(content=content))

    def add_ai_message(self, content: str) -> None:
        self.history.append(AIMessage(content=content))

    def accumulate_usage(self, input_tokens: int, output_tokens: int) -> None:
        """Add token counts and compute incremental cost."""
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        input_price, output_price = _get_pricing(self._model_name)
        self.total_cost += (input_tokens * input_price / 1_000_000) + (
            output_tokens * output_price / 1_000_000
        )

    def stream(self, messages: list | None = None) -> Generator[str, None, dict]:
        """Stream LLM response, yielding content chunks.

        Args:
            messages: If provided, use these instead of self.history.

        Yields:
            String chunks of the response content.

        Returns:
            A dict with ``usage_metadata`` (if available) after the generator
            is exhausted. Access via generator's ``.value`` attribute is not
            standard — callers should use ``accumulate_usage`` after streaming.
        """
        self._ensure_llm()
        msgs = messages if messages is not None else self.history

        full_content = ""
        usage_metadata = {}

        for chunk in self._llm.stream(msgs):
            token = chunk.content
            if token:
                full_content += token
                yield token

            # LangChain populates usage_metadata on the final chunk
            meta = getattr(chunk, "usage_metadata", None)
            if meta:
                usage_metadata = meta

        # Accumulate usage if metadata was provided
        if usage_metadata:
            self.accumulate_usage(
                input_tokens=usage_metadata.get("input_tokens", 0),
                output_tokens=usage_metadata.get("output_tokens", 0),
            )

        return usage_metadata
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_repl_llm_bridge.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/repl/llm_bridge.py tests/test_repl_llm_bridge.py
git commit -m "feat: add LLMBridge with streaming, token tracking, and cost calculation"
```

---

### Task 9: Create Command Routing

**Files:**
- Create: `agent/repl/commands.py`
- Create: `tests/test_repl_commands.py`

- [ ] **Step 1: Write failing tests for command routing**

Create `tests/test_repl_commands.py`:

```python
"""Tests for command routing."""

import pytest
from unittest.mock import MagicMock, patch
from agent.repl.commands import route_command, is_command


def test_is_command_true():
    assert is_command("/help") is True
    assert is_command("/exit") is True
    assert is_command("/epic myapp") is True


def test_is_command_false():
    assert is_command("hello") is False
    assert is_command("") is False
    assert is_command("@file.py") is False


@patch("agent.repl.commands._post_system_message")
def test_route_help(mock_post):
    app = MagicMock()
    result = route_command("/help", app)
    assert result == "handled"
    mock_post.assert_called_once()


def test_route_exit():
    app = MagicMock()
    result = route_command("/exit", app)
    app.exit.assert_called_once()
    assert result == "handled"


def test_route_quit():
    app = MagicMock()
    result = route_command("/quit", app)
    app.exit.assert_called_once()
    assert result == "handled"


def test_route_unknown():
    app = MagicMock()
    result = route_command("/foobar", app)
    assert result == "unknown"


@patch("agent.repl.commands._handle_subflow")
def test_route_epic_with_args(mock_subflow):
    app = MagicMock()
    result = route_command("/epic myapp", app)
    assert result == "handled"
    mock_subflow.assert_called_once_with(app, "epic", ["myapp"])


def test_route_epic_no_args():
    app = MagicMock()
    result = route_command("/epic", app)
    assert result == "error"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_repl_commands.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement command routing**

Create `agent/repl/commands.py`:

```python
"""Command routing for the Lios TUI REPL."""

from __future__ import annotations

import shlex
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from textual.app import App

# Help text shown in the chat log
HELP_TEXT = """\
**Available Commands**

| Command | Description |
|---|---|
| `/help` | Show this help message |
| `/epic <name>` | Initialize a new Epic vault |
| `/story <epic> <id>` | Initialize a new Story vault |
| `/execute <vault>` | Execute an approved blueprint |
| `/board` | Show board status |
| `/exit`, `/quit` | Exit the REPL |

Type a message to chat with Lios, use `@path/to/file` to attach files.
"""

BOARD_TEXT = "**Trello integration coming soon!**\n\nFetching tasks from your remote board..."


def is_command(text: str) -> bool:
    """Return True if text starts with a slash command."""
    return text.startswith("/")


def route_command(text: str, app: "App") -> str:
    """Route a slash command and execute its handler.

    Returns:
        "handled" — command was executed successfully.
        "error"   — command recognized but bad arguments.
        "unknown" — command not recognized.
    """
    try:
        parts = shlex.split(text)
    except ValueError:
        parts = text.split()

    command = parts[0].lower()
    args = parts[1:]

    if command in ("/exit", "/quit"):
        app.exit()
        return "handled"

    if command == "/help":
        _post_system_message(app, HELP_TEXT)
        return "handled"

    if command == "/board":
        _post_system_message(app, BOARD_TEXT)
        return "handled"

    if command == "/epic":
        if not args:
            _post_system_message(app, "**Error:** Usage: `/epic <name>`")
            return "error"
        _handle_subflow(app, "epic", args)
        return "handled"

    if command == "/story":
        if len(args) < 2:
            _post_system_message(app, "**Error:** Usage: `/story <epic_name> <story_id>`")
            return "error"
        _handle_subflow(app, "story", args)
        return "handled"

    if command == "/execute":
        if not args:
            _post_system_message(app, "**Error:** Usage: `/execute <vault_path>`")
            return "error"
        _handle_subflow(app, "execute", args)
        return "handled"

    return "unknown"


def _post_system_message(app: "App", markdown_text: str) -> None:
    """Add a system/help message to the chat log."""
    from agent.repl.widgets.message_bubble import AgentMessage

    chat_log = app.query_one("#chat-log")
    msg = AgentMessage(model_name="system")
    chat_log.mount(msg)
    msg.get_markdown_widget().update(markdown_text)


def _handle_subflow(app: "App", flow_type: str, args: list[str]) -> None:
    """Suspend the TUI and run a CLI sub-flow, then resume.

    For the initial implementation, this suspends the Textual app,
    imports and calls the relevant CLI function, then resumes.
    """

    def _run_flow() -> None:
        if flow_type == "epic":
            from cli import epic

            epic(name=args[0])
        elif flow_type == "story":
            from cli import story

            story(epic_name=args[0], story_id=args[1])
        elif flow_type == "execute":
            from cli import execute

            execute(vault_path=args[0])

    # Suspend TUI, run the blocking flow, resume
    with app.suspend():
        _run_flow()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_repl_commands.py -v`
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/repl/commands.py tests/test_repl_commands.py
git commit -m "feat: add command routing with /help, /exit, /epic, /story, /execute, /board"
```

---

### Task 10: Create the Main Textual App

**Files:**
- Create: `agent/repl/app.py`

This is the core of the TUI — composes all widgets and handles the chat flow.

- [ ] **Step 1: Create LiosChatApp**

Create `agent/repl/app.py`:

```python
"""Main Textual application for the Lios TUI REPL."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.worker import Worker, get_current_worker

from agent.repl.theme import APP_CSS
from agent.repl.widgets.welcome import WelcomeBanner
from agent.repl.widgets.chat_log import ChatLog
from agent.repl.widgets.message_bubble import (
    AgentMessage,
    ThinkingIndicator,
    UserMessage,
)
from agent.repl.widgets.input_bar import ChatInput
from agent.repl.widgets.status_bar import StatusBar
from agent.repl.llm_bridge import LLMBridge, SYSTEM_PROMPT, INTAKE_SYSTEM_PROMPT
from agent.repl.parse_input import parse_input
from agent.repl.commands import is_command, route_command


class LiosChatApp(App):
    """Textual TUI for the Lios-Agent interactive REPL."""

    CSS = APP_CSS

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("ctrl+l", "clear_chat", "Clear", show=False),
    ]

    def __init__(
        self,
        mode: str = "chat",
        epic_name: str = "",
        workspace_root: str = ".",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.mode = mode
        self.epic_name = epic_name
        self.workspace_root = workspace_root
        self.llm_bridge = LLMBridge()
        self._intake_result: str = ""

    def compose(self) -> ComposeResult:
        yield WelcomeBanner()
        yield ChatLog(id="chat-log")
        yield ChatInput(id="input")
        yield StatusBar(id="status")

    def on_mount(self) -> None:
        """Initialize LLM bridge and set up the system prompt."""
        if self.mode == "chat":
            self.llm_bridge.add_system_prompt(SYSTEM_PROMPT)
        elif self.mode == "intake":
            self.llm_bridge.add_system_prompt(INTAKE_SYSTEM_PROMPT)

        # Focus the input
        self.query_one("#input").focus()

    async def on_input_submitted(self, event: ChatInput.Submitted) -> None:
        """Handle user input submission."""
        text = event.value.strip()
        if not text:
            return

        # Clear the input
        input_widget = self.query_one("#input", ChatInput)
        input_widget.value = ""

        # Handle commands
        if is_command(text):
            result = route_command(text, self)
            if result == "unknown":
                self._add_system_message(f"Unknown command: `{text.split()[0]}`")
            return

        # Handle intake /done
        if self.mode == "intake" and text.strip() in ("/exit", "/done"):
            self.exit(result=self._intake_result)
            return

        # Parse @file mentions
        processed_text, attachments = parse_input(text, self.workspace_root)

        # Add user message to chat log
        chat_log = self.query_one("#chat-log", ChatLog)
        user_msg = UserMessage(text, attachments=attachments)
        await chat_log.mount(user_msg)

        # Add thinking indicator
        thinking = ThinkingIndicator(id="thinking")
        await chat_log.mount(thinking)
        chat_log.scroll_end(animate=False)

        # Add to LLM history and start streaming
        self.llm_bridge.add_user_message(processed_text)
        self._stream_response()

    def _stream_response(self) -> None:
        """Start the streaming worker."""
        self.run_worker(self._do_stream, thread=True)

    def _do_stream(self) -> None:
        """Run LLM streaming in a background thread."""
        worker = get_current_worker()

        # Create agent message widget
        model_name = self.llm_bridge.model_name
        agent_msg = AgentMessage(model_name=model_name)

        # Mount agent message and connect status bar (from thread)
        self.call_from_thread(self._mount_agent_message, agent_msg)

        # Stream tokens
        full_response = ""
        first_token = True

        for chunk in self.llm_bridge.stream():
            if worker.is_cancelled:
                break

            full_response += chunk

            if first_token:
                # Remove thinking indicator
                self.call_from_thread(self._remove_thinking)
                first_token = False

            # Update the markdown widget
            self.call_from_thread(self._update_agent_markdown, agent_msg, full_response)

        # Add AI message to history
        self.llm_bridge.add_ai_message(full_response)

        # Update status bar
        self.call_from_thread(self._update_status_bar)

        # For intake mode, accumulate context
        if self.mode == "intake":
            self._intake_result += f"User: {self.llm_bridge.history[-2].content}\n\n"
            self._intake_result += f"Agent: {full_response}\n\n"

            if "READY_TO_ARCHITECT" in full_response:
                self.call_from_thread(self.exit, self._intake_result)

    def _mount_agent_message(self, agent_msg: AgentMessage) -> None:
        """Mount agent message widget (must be called from main thread)."""
        chat_log = self.query_one("#chat-log", ChatLog)
        chat_log.mount(agent_msg)
        chat_log.scroll_end(animate=False)

        # Update status bar connection
        status = self.query_one("#status", StatusBar)
        status.set_connected(self.llm_bridge.model_name)

    def _remove_thinking(self) -> None:
        """Remove the thinking indicator (must be called from main thread)."""
        try:
            thinking = self.query_one("#thinking", ThinkingIndicator)
            thinking.remove()
        except Exception:
            pass

    def _update_agent_markdown(self, agent_msg: AgentMessage, content: str) -> None:
        """Update the agent message markdown (must be called from main thread)."""
        try:
            md_widget = agent_msg.get_markdown_widget()
            md_widget.update(content)
            chat_log = self.query_one("#chat-log", ChatLog)
            chat_log.scroll_end(animate=False)
        except Exception:
            pass

    def _update_status_bar(self) -> None:
        """Update status bar with latest token/cost stats (main thread)."""
        status = self.query_one("#status", StatusBar)
        status.update_stats(
            self.llm_bridge.total_tokens,
            self.llm_bridge.total_cost,
        )

    def _add_system_message(self, text: str) -> None:
        """Add a system message to the chat log."""
        from agent.repl.widgets.message_bubble import AgentMessage

        chat_log = self.query_one("#chat-log", ChatLog)
        msg = AgentMessage(model_name="system")
        chat_log.mount(msg)
        msg.get_markdown_widget().update(text)

    def action_clear_chat(self) -> None:
        """Clear the chat log."""
        chat_log = self.query_one("#chat-log", ChatLog)
        chat_log.remove_children()

    def action_quit(self) -> None:
        """Quit the application."""
        self.exit()
```

- [ ] **Step 2: Verify import**

Run: `python -c "from agent.repl.app import LiosChatApp; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add agent/repl/app.py
git commit -m "feat: add LiosChatApp — main Textual TUI application"
```

---

### Task 11: Create Legacy Facade (UniversalREPL)

**Files:**
- Create: `agent/repl/legacy.py`

This preserves the existing static method API so all call sites in `cli.py` continue to work.

- [ ] **Step 1: Create UniversalREPL facade**

Create `agent/repl/legacy.py`:

```python
"""Legacy facade preserving the UniversalREPL static method API.

All call sites (cli.py, tests) that use ``from agent.repl import UniversalREPL``
continue to work unchanged. The facade delegates to the Textual TUI app
for interactive sessions and keeps Rich-only output for non-TUI contexts.
"""

from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from agent.repl.parse_input import parse_input as _parse_input

console = Console()


class UniversalREPL:
    """Backward-compatible facade over the Textual TUI."""

    @staticmethod
    def start_interactive_session() -> None:
        """Launch the Textual TUI for interactive chat."""
        from agent.repl.app import LiosChatApp

        app = LiosChatApp(mode="chat")
        app.run()

    @staticmethod
    def interactive_intake_session(
        epic_name: str, workspace_root: str = "."
    ) -> str:
        """Launch the Textual TUI in intake mode for requirement refinement.

        Returns the accumulated conversation context as a string.
        """
        from agent.repl.app import LiosChatApp

        app = LiosChatApp(
            mode="intake",
            epic_name=epic_name,
            workspace_root=workspace_root,
        )
        result = app.run()
        return result if isinstance(result, str) else ""

    @staticmethod
    def parse_input(user_input: str, workspace_root: str = ".") -> str:
        """Parse @file mentions — backward-compatible string return.

        The underlying ``parse_input`` now returns a tuple, but this
        facade returns only the processed text string to avoid breaking
        existing call sites in cli.py.
        """
        processed_text, _attachments = _parse_input(user_input, workspace_root)
        return processed_text

    @staticmethod
    def single_prompt(prompt_text: str = "You", workspace_root: str = ".") -> str:
        """Single-turn prompt using Rich console (no TUI).

        Kept as-is because single-turn prompts don't benefit from the
        full TUI experience.
        """
        from rich.prompt import Prompt

        while True:
            try:
                user_input = Prompt.ask(f"[bold cyan]{prompt_text}[/bold cyan]")

                if not user_input.strip():
                    continue

                if user_input.strip() == "/exit":
                    console.print("[yellow]Exiting session...[/yellow]")
                    exit(0)

                if user_input.strip() == "/rollback":
                    console.print("[bold red]Rollback not yet implemented.[/bold red]")
                    continue

                if user_input.strip() == "/board":
                    console.print(
                        Panel(
                            "[bold green]Trello integration coming soon![/bold green]\n\n"
                            "Fetching tasks from your remote board...",
                            title="[bold blue]/board[/bold blue]",
                        )
                    )
                    continue

                processed_text, _attachments = _parse_input(user_input, workspace_root)
                return processed_text

            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Session aborted by user.[/yellow]")
                exit(0)

    @staticmethod
    def print_agent_message(message: str, title: str = "Lios-Agent") -> None:
        """Print a styled agent message using Rich (non-TUI context)."""
        console.print(
            Panel(
                Markdown(message),
                title=f"[bold purple]{title}[/bold purple]",
                border_style="purple",
            )
        )
```

- [ ] **Step 2: Verify import**

Run: `python -c "from agent.repl.legacy import UniversalREPL; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add agent/repl/legacy.py
git commit -m "feat: add UniversalREPL legacy facade delegating to Textual TUI"
```

---

### Task 12: Switch __init__.py to New Modules and Remove Old File

**Files:**
- Modify: `agent/repl/__init__.py` (switch from repl_old to new modules)
- Delete: `agent/repl_old.py`

This is the critical backward-compatibility cutover. The `__init__.py` currently re-exports from `agent.repl_old`. Now that all new modules exist, switch it to re-export from the new package modules.

- [ ] **Step 1: Update agent/repl/__init__.py to use new modules**

Replace the contents of `agent/repl/__init__.py`:

```python
"""
agent.repl package — Textual TUI for Lios-Agent REPL.

Re-exports public API for backward compatibility with `from agent.repl import X`.
"""

from agent.repl.completer import FileMentionCompleter
from agent.repl.lexer import LiosLexer
from agent.repl.legacy import UniversalREPL

__all__ = ["UniversalREPL", "FileMentionCompleter", "LiosLexer"]
```

- [ ] **Step 2: Run ALL existing tests to verify backward compatibility**

Run: `pytest tests/test_repl_completer.py tests/test_repl_lexer.py tests/test_cli_default.py -v`
Expected: All tests PASS. The imports `from agent.repl import FileMentionCompleter`, `from agent.repl import LiosLexer`, and `cli.UniversalREPL.start_interactive_session` all resolve correctly through the new modules.

- [ ] **Step 3: Delete the old file**

Run: `git rm agent/repl_old.py`

- [ ] **Step 4: Commit**

```bash
git rm agent/repl_old.py
git add agent/repl/__init__.py
git commit -m "refactor: switch agent/repl to new package modules, remove old repl_old.py"
```

---

### Task 13: Rewrite History Tests for Textual App

**Files:**
- Modify: `tests/test_repl_history.py`

The old tests verified PromptSession initialization. The new tests verify that the Textual app composes the correct widgets.

- [ ] **Step 1: Rewrite test_repl_history.py**

Replace the entire contents of `tests/test_repl_history.py`:

```python
"""Tests for Textual app widget composition (replaces old PromptSession tests)."""

import pytest
from agent.repl import UniversalREPL, FileMentionCompleter, LiosLexer


def test_repl_imports_are_available():
    """Verify backward-compatible imports still work."""
    assert UniversalREPL is not None
    assert FileMentionCompleter is not None
    assert LiosLexer is not None


def test_universal_repl_has_expected_methods():
    """Verify the facade exposes all expected static methods."""
    assert callable(UniversalREPL.start_interactive_session)
    assert callable(UniversalREPL.interactive_intake_session)
    assert callable(UniversalREPL.single_prompt)
    assert callable(UniversalREPL.parse_input)
    assert callable(UniversalREPL.print_agent_message)


def test_app_composes_expected_widgets():
    """Verify LiosChatApp composes the required widget tree."""
    from agent.repl.app import LiosChatApp
    from agent.repl.widgets.welcome import WelcomeBanner
    from agent.repl.widgets.chat_log import ChatLog
    from agent.repl.widgets.input_bar import ChatInput
    from agent.repl.widgets.status_bar import StatusBar

    app = LiosChatApp(mode="chat")

    # Use Textual's pilot for headless testing
    async def check_widgets():
        async with app.run_test() as pilot:
            assert app.query_one(WelcomeBanner) is not None
            assert app.query_one("#chat-log", ChatLog) is not None
            assert app.query_one("#input", ChatInput) is not None
            assert app.query_one("#status", StatusBar) is not None

    import asyncio
    asyncio.run(check_widgets())
```

- [ ] **Step 2: Run the rewritten tests**

Run: `pytest tests/test_repl_history.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_repl_history.py
git commit -m "test: rewrite history tests for Textual app widget composition"
```

---

### Task 14: Create Textual App Integration Tests

**Files:**
- Create: `tests/test_repl_app.py`

Uses Textual's built-in pilot for headless testing.

- [ ] **Step 1: Create integration tests**

Create `tests/test_repl_app.py`:

```python
"""Integration tests for LiosChatApp using Textual's pilot."""

import pytest
from unittest.mock import patch, MagicMock

from agent.repl.app import LiosChatApp
from agent.repl.widgets.welcome import WelcomeBanner
from agent.repl.widgets.chat_log import ChatLog
from agent.repl.widgets.input_bar import ChatInput
from agent.repl.widgets.status_bar import StatusBar
from agent.repl.widgets.message_bubble import UserMessage, AgentMessage


@pytest.fixture
def mock_llm():
    """Mock the LLM factory to avoid real API calls."""
    with patch("agent.repl.llm_bridge.get_llm") as mock_factory:
        mock_llm_instance = MagicMock()
        mock_llm_instance.model_name = "gpt-4o-test"

        def fake_stream(messages):
            chunks = ["Hello", " from", " Lios!"]
            for text in chunks:
                chunk = MagicMock()
                chunk.content = text
                chunk.usage_metadata = None
                yield chunk
            # Final chunk with usage
            final = MagicMock()
            final.content = ""
            final.usage_metadata = {
                "input_tokens": 50,
                "output_tokens": 10,
            }
            yield final

        mock_llm_instance.stream = fake_stream
        mock_factory.return_value = mock_llm_instance
        yield mock_llm_instance


@pytest.mark.asyncio
async def test_app_renders_welcome():
    app = LiosChatApp(mode="chat")
    async with app.run_test() as pilot:
        banner = app.query_one(WelcomeBanner)
        assert banner is not None


@pytest.mark.asyncio
async def test_help_command(mock_llm):
    app = LiosChatApp(mode="chat")
    async with app.run_test() as pilot:
        input_widget = app.query_one("#input", ChatInput)
        input_widget.value = "/help"
        await input_widget.action_submit()
        await pilot.pause()

        # Should have an AgentMessage with help text in the chat log
        messages = app.query(AgentMessage)
        assert len(messages) >= 1


@pytest.mark.asyncio
async def test_exit_command(mock_llm):
    app = LiosChatApp(mode="chat")
    async with app.run_test() as pilot:
        input_widget = app.query_one("#input", ChatInput)
        input_widget.value = "/exit"
        await input_widget.action_submit()
        await pilot.pause()
        # App should have exited (or be in process of exiting)


@pytest.mark.asyncio
async def test_chat_message_creates_user_bubble(mock_llm):
    app = LiosChatApp(mode="chat")
    async with app.run_test() as pilot:
        input_widget = app.query_one("#input", ChatInput)
        input_widget.value = "Hello Lios"
        await input_widget.action_submit()
        await pilot.pause(delay=0.5)

        # Should have a UserMessage in the chat log
        user_messages = app.query(UserMessage)
        assert len(user_messages) >= 1
```

- [ ] **Step 2: Install pytest-asyncio if not present**

Run: `pip install pytest-asyncio`

- [ ] **Step 3: Run integration tests**

Run: `pytest tests/test_repl_app.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_repl_app.py
git commit -m "test: add Textual pilot integration tests for LiosChatApp"
```

---

### Task 15: Update widgets/__init__.py and Run Full Test Suite

**Files:**
- Verify: `agent/repl/widgets/__init__.py` (already created in Task 2)

- [ ] **Step 1: Verify the widgets __init__.py imports all widgets**

Run: `python -c "from agent.repl.widgets import WelcomeBanner, ChatLog, UserMessage, AgentMessage, ThinkingIndicator, ChatInput, StatusBar; print('OK')"`
Expected: `OK`

- [ ] **Step 2: Run the complete test suite**

Run: `pytest tests/test_repl_completer.py tests/test_repl_lexer.py tests/test_repl_history.py tests/test_repl_parse_input.py tests/test_repl_commands.py tests/test_repl_llm_bridge.py tests/test_repl_app.py tests/test_cli_default.py -v`

Expected: ALL tests PASS.

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "chore: verify full test suite passes, clean up backup"
```

---

### Task 16: Manual Smoke Test

This task is not automated — it requires running the app and visually verifying the TUI.

- [ ] **Step 1: Launch the TUI**

Run: `python cli.py`

Expected:
- Welcome banner with green icon and version
- Status bar at bottom showing "Disconnected"
- Input field at bottom with placeholder text
- Green focus border on input

- [ ] **Step 2: Test /help command**

Type `/help` and press Enter.

Expected: Help text appears in the chat log as an agent message with left border.

- [ ] **Step 3: Test chat message (requires LLM API key)**

Type `Hello, what can you do?` and press Enter.

Expected:
- User message appears with green chevron
- Thinking indicator appears (pulsating dots + "Thinking...")
- Agent response streams in with left border and purple "LIOS" label
- Status bar updates with token count and cost
- Thinking indicator disappears when first token arrives

- [ ] **Step 4: Test @file mention**

Type `Tell me about @requirements.txt` and press Enter.

Expected:
- User message shows with cyan-highlighted `@requirements.txt`
- File attachment line: "📎 Attached requirements.txt (17 lines)"
- Agent responds with context about the file

- [ ] **Step 5: Test /exit**

Type `/exit` and press Enter.

Expected: App exits cleanly.

- [ ] **Step 6: Commit any fixes from smoke testing**

```bash
git add -A
git commit -m "fix: address issues found during smoke testing"
```

(Only if fixes were needed.)
