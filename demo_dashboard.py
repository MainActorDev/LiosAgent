from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
import time

def run_demo():
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=3)
    )
    
    layout["body"].split_row(
        Layout(name="main"),
        Layout(name="sidebar", size=30)
    )

    layout["header"].update(Panel("Lios-Agent - Active Execution Dashboard", style="bold blue"))
    layout["footer"].update(Panel("Press Ctrl+C to exit | Status: Executing", style="dim"))
    layout["sidebar"].update(Panel("Steps:\n[ ] 1. Analysis\n[ ] 2. Edit code\n[ ] 3. Run tests", title="Plan"))
    
    with Live(layout, refresh_per_second=4) as live:
        time.sleep(1)
        layout["main"].update(Panel("Agent is reading files to understand context...\n- `cli.py`\n- `agent/repl.py`", title="Current Action", border_style="yellow"))
        layout["sidebar"].update(Panel("Steps:\n[x] 1. Analysis\n[ ] 2. Edit code\n[ ] 3. Run tests", title="Plan"))
        time.sleep(2)
        
        layout["main"].update(Panel("Applying changes to `cli.py` to add new command...", title="Current Action", border_style="green"))
        layout["sidebar"].update(Panel("Steps:\n[x] 1. Analysis\n[~] 2. Edit code\n[ ] 3. Run tests", title="Plan"))
        time.sleep(2)

if __name__ == "__main__":
    run_demo()
