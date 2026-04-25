"""Scrollable chat log container."""

from textual.containers import VerticalScroll


class ChatLog(VerticalScroll):
    """Scrollable container that holds all chat messages.

    Call .anchor() to pin scroll to the bottom during streaming.
    """

    pass
