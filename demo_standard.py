import time
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel

console = Console()

console.print(Panel("Lios-Agent - Active Mode", style="bold blue"))

with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    console=console,
) as progress:
    task1 = progress.add_task("[yellow]Agent is thinking...", total=None)
    time.sleep(1.5)
    progress.update(task1, description="[green]Plan ready!", completed=100)
    
    console.print("  [cyan]>[/cyan] Modify `app.py`")
    console.print("  [cyan]>[/cyan] Run tests")
    
    task2 = progress.add_task("[yellow]Executing step 1...", total=None)
    time.sleep(1.5)
    progress.update(task2, description="[green]Step 1 complete!", completed=100)
