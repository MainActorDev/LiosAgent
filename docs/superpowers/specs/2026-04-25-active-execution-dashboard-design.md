# Lios-Agent Hybrid CLI & Kanban Design

## Overview
Lios-Agent requires a simple, elegant, highly-polished terminal interface during the entire agent lifecycle, heavily inspired by modern agentic tools like Claude Code. It will feature a fluid, scrolling log with beautiful formatting for active operations across *all* nodes (Planning, Execution, Review, etc.), rather than a rigid dashboard layout. In future phases, it will support a full-screen interactive Kanban board to track multi-epic/story progress across the workspace.

## Mode 1: Active Stream Mode (Default)
During the agent's operation (e.g., `lios execute`), the interface should:
- Print natural scrolling text.
- Use elegant typography, distinct coloring, and markdown rendering.
- Employ smooth, transient spinner animations (e.g., via `rich.status` or `rich.progress`) that disappear or collapse cleanly once an action completes.
- Display inline blocks for agent thoughts, read operations, file edits, tool executions, and node transitions (Intake, Blueprint, Code, Test, Push).

### Execution Hooks
- The `while True` loop executing LangGraph steps will emit granular text logs for *every* node transition (e.g., "[dim]> Entering Planning Phase...[/dim]").
- When the graph yields or awaits human input (e.g., `blueprint_approval_gate`), the spinner stops, and a status is printed inline before standard prompt rendering takes over.
- This applies uniformly across the entire graph, not just the "execute" node.

## Mode 2: Kanban Board (Future Phase)
The Kanban mode will be accessible via a `/board` slash command during REPL intake, or as a standalone CLI command (`lios board`).
- **Triggering**: Typing `/board` suspends the active REPL and clears the screen using an alternate buffer (like `less` or `vim`).
- **Data Model**: The board will read from all vaults located in `.lios/epics/` and `.lios/stories/`. It will scan `state.yml` to determine the current state (LangGraph node) of each vault.
- **Columns**: States map to standard Kanban columns: `Backlog`, `Planning` (e.g., `blueprint_approval_gate`), `In Progress` (code generation nodes), `Review` (`push` node), and `Done`.
- **Exit**: Pressing `q` or `Esc` restores the original terminal buffer and returns the user to the scrolling prompt.

## Implementation Plan for Current Phase
1. Refactor the graph execution loop in `cli.py` to use `rich.status` or `rich.console` for highly polished, scrolling output across all LangGraph nodes.
2. Scaffold the `/board` slash command in `agent/repl.py` to acknowledge the feature placeholder without fully implementing the TUI board rendering logic yet.
