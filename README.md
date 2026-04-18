# Lios-Agent Orchestrator 🤖🍏

Lios-Agent is an autonomous, agentic coding platform specifically engineered for iOS development. It leverages a Mixture-of-Experts ecosystem (via LangGraph) to read GitHub issues, generate localized Apple architectures, validate against compiler errors locally, and autonomously push pull requests.

## 🏗 Architecture

The platform operates purely via Slack and GitHub Webhooks, ensuring developers never need to leave their standard communication channels to trigger autonomous operations. 

It is divided into 5 core LangGraph Nodes:
1. **Context Aggregator Sub-Graph**: Injects external tools (Jira, Figma, local Xcode systems) via persistent Model Context Protocol (MCP) clients.
2. **Planner Node**: Utilizes Pydantic to strictly generate a deterministic JSON `FeatureBlueprint` encompassing created files, modified files, and **enforced XCTest suites** (TDD constraint).
3. **Human-in-the-Loop Node**: Halts the execution thread and posts the blueprint to GitHub. Resumes natively when a developer comments **"Approve"**.
4. **Coder Node**: Uses LangChain tool-binding to safely read from and overwrite code files within an isolated APFS sandbox cache.
5. **Execution Validator**: Natively compiles `xcodegen`, `tuist`, or `SPM`, and executes an internal `xcodebuild`. All logs are piped through **RTK** (A Rust proxy token-saver) to truncate 30,000-line Swift compiler outputs into localized 20-token LLM-safe strings.

## 🚀 Quick Start & Installation

### 1. Pre-requisites
The orchestrator relies on several external CLI modules for performance rendering. Please ensure these are installed globally on your Host Mac:
- **Python 3.10+**
- **NVM / Node** (For the `npx xcodebuildmcp` client connection)
- **RTK Log Distiller** (Crucial for token savings!)
  ```bash
  brew install rtk
  ```

### 2. Environment Variables
Copy over the standard environments. You will need a registered GitHub App and a Slack Bot.
```bash
# LLM Routing
LLM_PROVIDER="openai" # Options: openai, glm, ollama
LLM_MODEL_NAME="gpt-4o"
OPENAI_API_KEY="sk-..."

# Integrations
SLACK_BOT_TOKEN="xoxb-..."
SLACK_SIGNING_SECRET="..."
SLACK_CHANNEL_ID="C0123456"

# Code Storage
GITHUB_APP_ID="123456"
GITHUB_PRIVATE_KEY_PATH="./lios-agent.private-key.pem"
```

### 3. Server Initialization
Set up your venv and boot the FastAPI orchestrator:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```
*Note: In local development, you should expose `port 8000` via ngrok so GitHub/Slack webhooks can accurately ping your machine.*

## ⚙️ Configuration & Slack Ops
You can control the orchestration dynamically mid-execution from Slack!

Use `/ios-agent config set <KEY> <VALUE>` to update specific routing behavior without restarting the underlying Python server. Available configuration keys include:
- `LLM_PROVIDER_PLANNING` (Assign an expensive reasoning model just to the Architecture Phase)
- `LLM_PROVIDER_CODING` (Assign a fast model specifically to sandbox coding)

Run `/agent-status` to test the Webhook stability.

## ⚠️ Known Limitations / Architectural Quality Notes
When scaling to a production team, be aware of the following system bounds:
1. **Branch Collisions**: The Agent automatically checks out `ios-agent-issue-{task_id}`. Concurrent runs on the exact same GitHub issue currently throw a git conflict upon `checkout -b`.
2. **PATH Resolution**: The MCP Stdio connections (`agent/mcp_clients.py`) currently assume Node and other binaries sit inside standard macOS root binaries (`/opt/homebrew/bin` or standard `.local/bin`). If deploying to a specialized Docker container or CI runner, ensure absolute paths match.
3. **RTK Enforcement**: If the `rtk` binary is uninstalled on the system, the Validator loop inside `execute_xcodebuild` will crash quietly underneath `subprocess.run(check=False)`.
4. **App Sandbox Sizes**: The `APFS` copy-on-write functionality is heavily reliant on macOS local environments. Native linux boxes do not support APFS, which will drastically increase the 0.1-second seed cache generation to full block duplicates (potentially hundreds of megabytes per task).
