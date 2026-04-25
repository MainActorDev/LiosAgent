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
