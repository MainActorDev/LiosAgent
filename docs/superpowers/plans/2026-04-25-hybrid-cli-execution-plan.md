# Lios-Agent Hybrid CLI & Kanban Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a polished, scrolling terminal UI for the agent execution lifecycle using `rich`, and scaffold a `/board` command for the future Kanban phase.

**Architecture:** Use `rich.status` and `rich.console` for transient spinners and beautiful scrolling logs throughout all LangGraph nodes in `cli.py`. Scaffold `/board` in `agent/repl.py`.

**Tech Stack:** Python, Typer, Rich, LangGraph.

---

### Task 1: Refactor `execute` Loop in `cli.py` for Smooth Scrolling

**Files:**
- Modify: `cli.py`

- [ ] **Step 1: Write a test/check for the `execute` loop**

Since `cli.py` runs an async loop over LangGraph, standard unit tests are tricky. We will manually test the CLI output after modification. (We will use an empty vault or dummy command if possible).

- [ ] **Step 2: Update imports in `cli.py`**

```python
from rich.console import Console
from rich.status import Status
from rich.markdown import Markdown
from rich.panel import Panel

console = Console()
```

- [ ] **Step 3: Modify `execute` to use `rich.status`**

Change the `while True` loop inside `execute` to wrap the `ainvoke` call with a transient status spinner that updates based on the current node.

```python
        while True:
            # Determine current node based on vault_manager state
            # If state not found, default to "Thinking"
            state = vault_manager.read_state()
            current_node = state.get("current_node", "Thinking") if state else "Thinking"
            
            # Use transient=True so the spinner disappears after the action completes
            with console.status(f"[bold cyan]Agent is {current_node}...[/bold cyan]", spinner="dots", transient=True) as status:
                try:
                    result = await graph_app.ainvoke(None, config)
                except Exception as e:
                    console.print(f"[bold red]Error during {current_node}:[/bold red] {e}")
                    raise typer.Exit(1)
            
            # After node completes, print a clean summary line
            console.print(f"[dim]✓ Completed {current_node}[/dim]")
            
            # Existing break condition check here
```

*Note: Ensure to adapt this precisely to the existing `ainvoke` and break logic in `cli.py`.*

- [ ] **Step 4: Run CLI command to verify**

Run: `poetry run lios execute`
Expected: The CLI should display a spinner with the node name, then print a checkmark and disappear before moving to the next node or pausing.

- [ ] **Step 5: Commit**

```bash
git add cli.py
git commit -m "feat: implement rich scrolling status in execute loop"
```

### Task 2: Scaffold `/board` Command in REPL

**Files:**
- Modify: `agent/repl.py`

- [ ] **Step 1: Identify REPL command handler**

Find the loop or function handling user input in `agent/repl.py` (usually a `Prompt.ask` loop).

- [ ] **Step 2: Add `/board` handler**

```python
        user_input = Prompt.ask("...")
        
        if user_input.strip() == "/board":
            from rich.console import Console
            from rich.panel import Panel
            console = Console()
            console.print(Panel("[yellow]Kanban Board feature is planned for a future phase.[/yellow]\nThis will eventually display Epic and Story progress across vaults.", title="Board Scaffold"))
            continue
```

- [ ] **Step 3: Run REPL to verify**

Run: `poetry run lios` (or whatever starts the repl)
Type: `/board`
Expected: The panel placeholder message appears, and the REPL continues.

- [ ] **Step 4: Commit**

```bash
git add agent/repl.py
git commit -m "feat: scaffold /board command in repl"
```
