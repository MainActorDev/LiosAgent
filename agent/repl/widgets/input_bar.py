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
