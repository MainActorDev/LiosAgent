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
