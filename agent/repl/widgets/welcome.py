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
        text.append("  >_ ", style=f"bold {GREEN}")
        text.append(f"Lios Agent ", style=f"bold {TEXT_PRIMARY}")
        text.append(f"v{self._version}", style=TEXT_MUTED)
        text.append("\n")
        text.append(
            "  Type a message to chat, /help for commands, @ to mention files",
            style=TEXT_MUTED,
        )
        return text
