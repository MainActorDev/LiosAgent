"""Legacy facade preserving the UniversalREPL static method API."""

from __future__ import annotations
import threading
import time
import uvicorn
import webview

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from agent.repl.parse_input import parse_input as _parse_input

console = Console()

def start_server():
    from agent.repl.server import app
    # Run uvicorn on a specific port, log_level="warning" to keep terminal clean
    uvicorn.run(app, host="127.0.0.1", port=8123, log_level="warning")


class UniversalREPL:
    """Facade over the Web UI."""

    @staticmethod
    def start_interactive_session() -> None:
        """Launch the PyWebView Desktop App."""
        # Start FastAPI server in a background daemon thread
        server_thread = threading.Thread(target=start_server, daemon=True)
        server_thread.start()
        
        # Wait briefly to ensure server is up
        time.sleep(1)
        
        # Launch PyWebView window
        webview.create_window(
            'Lios-Agent', 
            'http://127.0.0.1:8123',
            width=1200, 
            height=800,
            background_color='#0a0a0c'
        )
        webview.start()

    @staticmethod
    def interactive_intake_session(
        epic_name: str, workspace_root: str = "."
    ) -> str:
        """Launch the UI in intake mode (Fallback for now)."""
        console.print("[yellow]Web UI intake mode not yet fully implemented, falling back to basic chat[/yellow]")
        UniversalREPL.start_interactive_session()
        return "Web UI Session Completed"

    @staticmethod
    def parse_input(user_input: str, workspace_root: str = ".") -> str:
        from agent.repl.parse_input import parse_input as _parse_input
        return _parse_input(user_input, workspace_root)

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
