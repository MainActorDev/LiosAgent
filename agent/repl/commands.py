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

BOARD_TEXT = "**Trello integration coming soon!**\\n\\nFetching tasks from your remote board..."


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
    """Suspend the TUI and run a CLI sub-flow, then resume."""

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
