# Project Overview: Lios-Agent

## Purpose
Lios-Agent is an autonomous, terminal-first agentic coding platform specifically engineered for iOS development. It leverages a Mixture-of-Experts ecosystem (via LangGraph) to brainstorm architectures, decompose work into atomic user stories, validate against compiler errors locally, and autonomously push pull requests.

## Architecture
The platform operates as a CLI (`lios`) on macOS and consists of three main phases:
1. **Planning Phase**: Gathers requirements via Universal REPL, processes them with a Context Aggregator, and generates a `FeatureBlueprint` using a Planner node. Requires human-in-the-loop (HITL) approval.
2. **Decomposition & Execution Phase**: Breaks down blueprints into atomic `UserStory` models (via "Ralph" PRD decomposer). Executes code generation headlessly using the `opencode-ai` CLI within isolated APFS copy-on-write workspaces.
3. **Multi-Story Review Phase**: Validates generated code by natively compiling the iOS project, atomically committing passing stories, running Maestro UI validation on iOS simulators, and pushing PRs via GitHub App integrations.

## Tech Stack
*   **Language**: Python 3.10+
*   **Orchestration**: LangGraph (State machine routing, SQLite checkpoints)
*   **CLI Interface**: Typer & Rich
*   **Agent Execution**: OpenCode-AI CLI (`opencode-ai`)
*   **iOS Testing/Validation**: Xcodebuild, Maestro (`xcrun simctl` + `maestro`)
*   **Authentication/SCM**: PyGithub (JWT)

## Key Concepts
*   **Feature Vaults**: Physical directories (`.lios/epics/{epic_name}/`) to track agent state and execution history.
*   **Isolated Workspaces**: APFS Copy-on-Write clones of the target iOS repository for sandboxed execution without polluting the main directory.
*   **Universal REPL**: Interactive chat for intake with support for injecting local files via `@path/to/file` syntax.