import os
import re
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.markdown import Markdown

console = Console()

class UniversalREPL:
    """
    Handles interactive terminal sessions and parses special commands like @file.
    """
    
    @staticmethod
    def parse_input(user_input: str, workspace_root: str = ".") -> str:
        """
        Parses the user input for @file syntax.
        If a file is mentioned, it reads the file and appends its content to the prompt.
        """
        # Regex to find @filepath (allows alphanumeric, dots, slashes, dashes, underscores)
        # It stops at whitespace.
        pattern = r'@([a-zA-Z0-9_./-]+)'
        matches = re.findall(pattern, user_input)
        
        if not matches:
            return user_input
            
        compiled_input = user_input + "\n\n### Injected Context from @mentions:\n"
        
        for filepath in set(matches):
            full_path = os.path.join(workspace_root, filepath)
            if os.path.isfile(full_path):
                try:
                    with open(full_path, "r") as f:
                        content = f.read()
                    compiled_input += f"\n--- {filepath} ---\n```\n{content}\n```\n"
                    console.print(f"[dim]📎 Attached {filepath}[/dim]")
                except Exception as e:
                    console.print(f"[bold red]⚠️ Failed to read {filepath}:[/bold red] {e}")
                    compiled_input += f"\n--- {filepath} (ERROR) ---\nCould not read file.\n"
            else:
                console.print(f"[bold yellow]⚠️ File not found:[/bold yellow] {filepath}")
                compiled_input += f"\n--- {filepath} (NOT FOUND) ---\n"
                
        return compiled_input

    @staticmethod
    def chat_loop(prompt_text: str = "You", workspace_root: str = ".") -> str:
        """
        A single turn chat loop that handles slash commands.
        Returns the parsed instruction string.
        """
        while True:
            try:
                user_input = Prompt.ask(f"[bold cyan]{prompt_text}[/bold cyan]")
                
                if not user_input.strip():
                    continue
                    
                if user_input.strip() == "/exit":
                    console.print("[yellow]Exiting session...[/yellow]")
                    exit(0)
                    
                # You can add more slash commands here like /rollback
                if user_input.strip() == "/rollback":
                    console.print("[bold red]Rollback not yet implemented.[/bold red]")
                    continue
                
                parsed_input = UniversalREPL.parse_input(user_input, workspace_root)
                return parsed_input
                
            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Session aborted by user.[/yellow]")
                exit(0)

    @staticmethod
    def print_agent_message(message: str, title: str = "Lios-Agent"):
        """Prints a styled message from the agent."""
        console.print(Panel(Markdown(message), title=f"[bold purple]{title}[/bold purple]", border_style="purple"))
