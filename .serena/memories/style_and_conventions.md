# Code Style and Conventions: Lios-Agent

## General
*   **Language**: Python 3.10+
*   **Paradigm**: Object-Oriented and Functional (via LangGraph nodes and State objects). Agentic state management with explicit serialization to disk (`.lios/epics/...`).
*   **Frameworks**: Heavy usage of Typer for the CLI (`cli.py`), Rich for console formatting (`agent/repl.py`), and LangChain/LangGraph for LLM workflows (`agent/graph.py`, `agent/llm_factory.py`).
*   **Typing**: Type hints are heavily encouraged and used, particularly leveraging Pydantic models for structured output (e.g. `FeatureBlueprint`, `UserStory`, `PRDDocument`).
*   **OS Dependency**: Code relies heavily on macOS-specific tools and system calls via `subprocess` (e.g. `xcodebuild`, `xcrun simctl`, `maestro`, APFS Copy-on-Write).

## Naming Conventions
*   **Variables/Functions**: `snake_case` (e.g. `initialize_workspace_node`, `clone_isolated_workspace`)
*   **Classes**: `PascalCase` (e.g. `VaultManager`, `UniversalREPL`, `FeatureBlueprint`)
*   **Constants**: `UPPER_SNAKE_CASE` (e.g. `BASE_WORKSPACE_DIR`, `VAULTS_ROOT`)
*   **Private Methods**: Prefix with an underscore `_` (e.g. `_ensure_workspaces_dir`, `_analyze_navigation_from_source`)

## Documentation
*   Markdown files in `docs/` for project documentation.
*   Docstrings in functions and classes are expected for complex logic, particularly inside LangGraph nodes (`agent/graph.py`) and agent tools (`agent/tools.py`).

## Error Handling
*   Relies on returning state dictionary updates (e.g. `{"error": "message"}`) in LangGraph nodes for the routing functions (`should_retry`, `should_proceed_from_blueprint`) to decide the next step in the pipeline.

## System Tools
*   `git`: For version control and pushing PRs via GitHub App integrations (`PyGithub`).
*   `npm` / `opencode-ai`: External CLI executed via subprocess to act as the internal agentic coder.
*   `xcrun simctl`, `xcodebuild`, `maestro`: For compiling and visually validating the generated iOS code.