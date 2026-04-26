from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.layout import Layout
from rich.live import Live
import time

console = Console()

def run_demo():
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main"),
        Layout(name="footer", size=3)
    )

    layout["header"].update(Panel("Lios-Agent - Active Mode", style="bold blue"))
    layout["main"].update(Panel(Markdown("Thinking...")))
    layout["footer"].update(Panel("Press Ctrl+C to exit", style="dim"))

    with Live(layout, refresh_per_second=4):
        time.sleep(1)
        layout["main"].update(Panel(Markdown("# Agent is analyzing\n- Scanning files...\n- Resolving dependencies...")))
        time.sleep(2)
        layout["main"].update(Panel(Markdown("# Plan ready\n1. Modify `app.py`\n2. Run tests")))
        time.sleep(1)

if __name__ == "__main__":
    run_demo()
