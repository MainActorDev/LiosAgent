import os
import typer
from rich.console import Console
from rich.panel import Panel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = typer.Typer(
    help="Lios-Agent: The Autonomous iOS Engineer CLI",
    add_completion=False,
)
console = Console()

@app.command()
def epic(
    name: str = typer.Argument(..., help="The name of the Epic to generate (e.g., habit-tracker)"),
    context: list[str] = typer.Option(None, "--context", "-c", help="Paths to context files (e.g., prd.md)")
):
    """
    Initialize a full Epic Vault and begin the Interactive Architecture Planning phase.
    """
    console.print(Panel.fit(f"[bold blue]Initializing Epic Vault:[/bold blue] [green]{name}[/green]", border_style="blue"))
    console.print("[dim]This command will eventually drop you into the interactive REPL...[/dim]")
    # TODO: Implement interactive REPL and global blueprint generation

@app.command()
def story(
    name: str = typer.Argument(..., help="The name of the Story/Feature to generate (e.g., login-bug)"),
    context: list[str] = typer.Option(None, "--context", "-c", help="Paths to context files")
):
    """
    Initialize a standalone Story Vault and begin the Interactive Planning phase.
    """
    console.print(Panel.fit(f"[bold blue]Initializing Story Vault:[/bold blue] [green]{name}[/green]", border_style="blue"))
    console.print("[dim]This command will eventually drop you into the interactive REPL...[/dim]")
    # TODO: Implement interactive REPL and story plan generation

@app.command()
def execute(
    vault_path: str = typer.Argument(..., help="Path to the Epic or Story vault to execute")
):
    """
    Execute an approved Architectural Blueprint from a specific Vault.
    """
    if not os.path.exists(vault_path):
        console.print(f"[bold red]Error:[/bold red] Vault path '{vault_path}' does not exist.")
        raise typer.Exit(code=1)
        
    console.print(Panel.fit(f"[bold green]Executing Vault:[/bold green] [yellow]{vault_path}[/yellow]", border_style="green"))
    console.print("[dim]This command will eventually trigger the LangGraph Coder/Validator loop...[/dim]")
    # TODO: Load VaultSaver, load state, and invoke LangGraph

if __name__ == "__main__":
    app()
