# Unified CLI REPL Design

**Goal:** Create a default interactive session when the user types `lios` without arguments, combining natural language chat with slash commands (similar to Claude Code).

## Architecture
- **Entry Point:** Modify the Typer app in `cli.py` to use a callback with `invoke_without_command=True`. If `ctx.invoked_subcommand` is `None`, it launches the interactive session.
- **Session Loop:** `UniversalREPL.start_interactive_session()` in `agent/repl.py` uses `prompt_toolkit.PromptSession` to provide a robust terminal loop with history support.
- **Routing Logic:**
  - Input starting with `/` is parsed as a command (e.g., `/epic <name>`, `/story <epic> <id>`, `/execute <vault>`, `/board`, `/exit`).
  - Input without `/` is treated as conversational chat.
- **Manager Agent:** A lightweight conversational LLM invocation inside the REPL loop handles general user queries. It maintains an in-memory message history for the duration of the session.

## Components
1. **`cli.py` Updates:**
   - Add `@app.callback(invoke_without_command=True)` above a new `main` function.
   - Check `ctx.invoked_subcommand`. If None, call `UniversalREPL.start_interactive_session()`.
2. **`agent/repl.py` Updates:**
   - Implement `start_interactive_session()`.
   - Implement basic command parsing for slash commands to route to the existing Typer command functions (or their underlying logic).
   - Implement a simple `_chat_with_agent(prompt, history)` function using LangChain's `ChatOpenAI` to handle conversational input.

## Data Flow
1. User types `lios`.
2. Typer callback fires -> `start_interactive_session()`.
3. Loop waits for input at `lios> `.
4. User types `/epic my-epic`. REPL splits string, sees `/epic`, calls `epic("my-epic")` logic.
5. User types "What can you do?". REPL sends string to `_chat_with_agent`, streams response back to console.
6. User types `/exit`. Loop breaks, program ends.