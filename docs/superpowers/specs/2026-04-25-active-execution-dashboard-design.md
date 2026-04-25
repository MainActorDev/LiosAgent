# Lios-Agent Active Execution Dashboard Design

## Overview
Lios-Agent requires a more sophisticated, agentic terminal UI when executing tasks. Rather than relying on simple scrolling text outputs, the system will feature a "Live Dashboard" built using the `rich` library (`rich.layout`, `rich.live`, `rich.panel`). This dashboard will provide spatial awareness of the agent's current state, its recent history, and its overall execution plan.

## Architecture
- **Rendering Engine**: `rich.layout.Layout` combined with `rich.live.Live` to create a persistent, updating terminal window.
- **Decoupling**: The UI logic will be abstracted into a `UIManager` (or `DashboardManager`) class to separate display logic from core graph execution logic.
- **Integration**: The `rich.live.Live` context manager will wrap the `while True` async execution loop in `cli.py` (`run_graph()`).
- **Human-in-the-Loop**: When standard prompts are required (e.g., `blueprint_approval_gate`, `await_clarification`), the dashboard will temporarily suspend using `live.stop()`. Standard `rich.prompt.Prompt` will handle input, and the dashboard will resume with `live.start()` afterward.

## Components
The terminal will be split into three main vertical sections:
1. **Header (Fixed)**: Displays "Lios-Agent Active Execution Dashboard" and the active Epic/Story identifier.
2. **Main Body (Dynamic)**: Split horizontally into two main panels:
   - **Left Panel (Action Area)**:
     - **Current Action**: A prominent panel showing the immediate node/task currently executing (e.g., "Generating Architectural Blueprint...").
     - **Recent Events**: A panel showing a scrolling list (using a `collections.deque`) of the last N events or state transitions.
   - **Right Panel (Plan Sidebar)**:
     - A checklist of the high-level workflow steps (e.g., Intake -> Blueprint -> Code -> Test -> Push).
     - Checkboxes will visually update (e.g., `[ ]`, `[~]`, `[x]`) as the LangGraph transitions through nodes.
3. **Footer (Fixed)**: Displays helpful shortcuts (e.g., "Press Ctrl+C to abort").

## State Tracking
For V1, state tracking will occur at the LangGraph *Node* level, rather than at the individual LLM token/tool level.
- **Action Updates**: The `Current Action` panel will be updated based on the `next_node` identified by LangGraph before calling `await graph_app.ainvoke()`.
- **Event Logging**: As nodes complete, summary strings will be pushed to the `Recent Events` deque.
- **Plan Progress**: The `Plan Sidebar` will map specific graph nodes to high-level workflow stages and update their checkbox states accordingly.

## Extensibility
- The design allows for future enhancements, such as injecting LangChain callback handlers to stream specific tool usage or token generation directly into the "Current Action" panel.
