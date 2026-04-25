# Lios-Agent Suggested Commands

## Setup and Initialization
*   `python3 -m venv venv`: Create a virtual environment.
*   `source venv/bin/activate`: Activate the virtual environment.
*   `pip install -r requirements.txt`: Install Python dependencies.
*   `npm i -g opencode-ai@latest`: Install required external dependency (OpenCode CLI).

## Running the CLI
The main entry point is the `lios` executable script, which wraps `cli.py` and handles virtual environment activation.

*   `./lios --help`: Verify the CLI is working and see available commands.
*   `./lios epic <epic-name-or-issue-id>`: Initialize a new Epic or work on a GitHub issue. This drops you into the Universal REPL for intake.
*   `./lios story <story-name> <epic-name>`: Generate a single UI story without the full workflow (useful for testing single components).
*   `./lios execute .lios/epics/<epic-name>`: Execute the LangGraph pipeline against a initialized feature vault.

## Formatting & Linting
*(Note: Explicit commands for linting/formatting are not explicitly defined in the README. Assuming standard Python tools if added later, like `ruff` or `black`, but none are currently configured in `requirements.txt` besides `pyyaml`, `typer`, `rich`, `langchain` stack. We will need to ask the user if they have specific ones. For now, rely on standard python conventions.)*

## Testing
*(Note: Similarly, standard python test frameworks like `pytest` are not in `requirements.txt`. The agent natively tests iOS apps via `xcodebuild` and `maestro`, but unit testing for the agent itself is undefined. Needs clarification from user.)*