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

    def _format_tokens(self, count: int) -> str:
        """Format token count with k suffix for large numbers."""
        if count >= 1000:
            return f"{count / 1000:.1f}k tokens"
        return f"{count:,} tokens"

    def render(self) -> Text:
        width = self.size.width if self.size.width > 0 else 80

        left = Text()
        if self._connected:
            left.append("● ", style=f"bold {GREEN}")
            left.append("Connected", style=TEXT_MUTED)
            left.append(f"  {self._model_name}", style=TEXT_MUTED)
        else:
            left.append("○ ", style=TEXT_MUTED)
            left.append("Disconnected", style=TEXT_MUTED)

        right = Text()
        if self._total_tokens > 0:
            right.append(self._format_tokens(self._total_tokens), style=TEXT_MUTED)
            right.append(f"  ${self._total_cost:.3f}", style=TEXT_MUTED)

        # Pad to fill the width
        gap = max(1, width - len(left.plain) - len(right.plain))
        combined = Text()
        combined.append_text(left)
        combined.append(" " * gap)
        combined.append_text(right)
        return combined
