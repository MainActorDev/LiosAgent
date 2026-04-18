# Lios-Agent Orchestrator 🤖🍏

Lios-Agent is an autonomous, agentic coding platform specifically engineered for iOS development. It leverages a Mixture-of-Experts ecosystem (via LangGraph) to read GitHub issues, generate localized Apple architectures, validate against compiler errors locally, and autonomously push pull requests.

## 🏗 Architecture

The platform operates purely via Slack and GitHub Webhooks, ensuring developers never need to leave their standard communication channels to trigger autonomous operations.

### LangGraph Pipeline

```
Issue Opened → Vetting → Workspace Init → Context Aggregator (MCP)
    → Planner (Pydantic Blueprint) → Blueprint Presentation (HITL)
    → Router → [UI Sub-Agent | Network Sub-Agent | General Coder]
    → Validator (RTK Build) → UI Vision Check (SimCtl + Vision LLM)
    → Push PR
```

### Node Descriptions

| Node | Purpose |
|------|---------|
| **Vetting** | Filters vague/spam issues. Posts a clarification comment if the issue lacks context. |
| **Context Aggregator** | Async node that queries Serena MCP + XcodeBuildMCP for codebase symbols and patterns. |
| **Planner** | Outputs a strict Pydantic `FeatureBlueprint` JSON with mandatory `files_to_test` (TDD). |
| **Blueprint Presentation** | Posts the blueprint as Markdown to the GitHub Issue. Halts until a human comments **"Approve"**. |
| **Router** | Analyzes the blueprint and dispatches to specialized sub-agents based on domain classification. |
| **UI Sub-Agent** | Specialist for SwiftUI/UIKit Views, Construkt tokens, Screens, and Components. |
| **Network Sub-Agent** | Specialist for API Services, Repositories, DTOs, and Data Models. |
| **General Coder** | Fallback for tasks that don't fit UI or Network domains. |
| **Validator** | Runs `xcodebuild` through RTK for token-compressed logs. 3-strike rollback on failure. |
| **UI Vision Check** | Boots iOS Simulator, captures a screenshot, and validates it against design constraints via a Vision LLM. Only activates for UI-tagged blueprints. |
| **Push** | Commits and pushes the agent's branch to GitHub as a PR. |

### Surgical Code Patching

The agent uses **line-range patching** instead of full-file rewrites to prevent hallucination on large files:

1. `read_workspace_file_lines` — Reads a specific line range with line numbers prepended.
2. `patch_workspace_file` — Surgically replaces only the target line range, leaving the rest untouched.
3. `write_workspace_file` — Reserved exclusively for creating **new** files.

### PR Review Loop

When a human developer leaves an inline code review comment on the agent's PR, the orchestrator automatically:
1. Clones the existing PR branch into a fresh sandbox.
2. Re-triggers the Router → Sub-Agent → Validator pipeline with the review comment as instructions.
3. Pushes the fix directly to the open PR.

This is powered by the `pull_request_review_comment` GitHub webhook handler in `main.py`.

## 🚀 Quick Start & Installation

### 1. Pre-requisites
The orchestrator relies on several external CLI modules. Please ensure these are installed globally on your Host Mac:
- **Python 3.10+**
- **Xcode** (with Command Line Tools)
- **NVM / Node** (For the `npx xcodebuildmcp` client connection)
- **RTK Log Distiller** (Crucial for token savings!)
  ```bash
  brew install rtk
  ```

### 2. Environment Variables
Copy over the standard environments. You will need a registered GitHub App and a Slack Bot.
```bash
# LLM Routing
LLM_PROVIDER="openai"        # Options: openai, glm, ollama
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

### 4. GitHub Webhook Configuration
In your GitHub App settings, subscribe to the following events:
- `issues` — Triggers the main agent pipeline.
- `issue_comment` — Enables the "Approve" comment to resume the blueprint HITL gate.
- `pull_request_review_comment` — Enables the PR Review Loop for inline code feedback.

Set the webhook URL to `https://<your-ngrok-url>/webhooks/github`.

## ⚙️ Configuration & Slack Ops
You can control the orchestration dynamically mid-execution from Slack!

Use `/ios-agent config set <KEY> <VALUE>` to update specific routing behavior without restarting the underlying Python server. Available configuration keys include:
- `LLM_PROVIDER_PLANNING` — Assign an expensive reasoning model just to the Architecture Phase.
- `LLM_PROVIDER_CODING` — Assign a fast model specifically to sandbox coding.

Run `/agent-status` to test the Webhook stability.

## 📁 Project Structure

```
Lios-Agent/
├── main.py                  # FastAPI server, Slack handlers, GitHub webhooks
├── requirements.txt         # Python dependencies
├── agent/
│   ├── state.py             # AgentState TypedDict definition
│   ├── graph.py             # LangGraph nodes, edges, sub-agents, and build_graph()
│   ├── tools.py             # Workspace tools, patching, xcodebuild, simctl, vision
│   ├── mcp_clients.py       # MCPManager for stdio connections to MCP servers
│   └── llm_factory.py       # Provider-agnostic LLM factory (OpenAI/GLM/Ollama)
└── .workspaces/             # Auto-generated isolated sandbox clones (gitignored)
```

## 🔧 Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **APFS Copy-on-Write** | Instant 0.1s workspace duplication on macOS. Allows 10+ concurrent tasks. |
| **RTK for all CLI output** | Reduces 30,000-line xcodebuild output to ~20 tokens. Saves 60-90% on LLM billing. |
| **Pydantic FeatureBlueprint** | Forces deterministic JSON, preventing freeform text hallucination in planning. |
| **Sub-Agent Swarms** | Domain-specific system prompts (UI vs Network) reduce cognitive load per LLM call. |
| **Line-range patching** | Prevents the AI from rewriting entire 3000-line files and destroying unrelated code. |
| **Vision UI Validation** | Catches pixel-perfect regressions that pass compilation but look visually broken. |
| **Async Context Aggregator** | MCP connections require `AsyncExitStack` for persistent stdio pipe lifecycle. |

## ⚠️ Known Limitations
When scaling to a production team, be aware of the following system bounds:
1. **macOS Only**: APFS Copy-on-Write and `xcrun simctl` require macOS. Linux deployment requires alternative workspace strategies.
2. **RTK Dependency**: If `rtk` is not installed, the Validator will return a `FATAL ERROR` and halt execution (fail-safe, not fail-silent).
3. **Vision Model Required**: The UI Vision Check requires a multimodal LLM (e.g., GPT-4o, Claude Sonnet). If your configured model doesn't support image input, the vision check will gracefully skip.
4. **Simulator Availability**: The UI Vision Check requires at least one iOS Simulator runtime installed. Run `xcrun simctl list devices` to verify.
5. **Sequential Sub-Agents**: UI and Network sub-agents run sequentially (UI first, then Network). True parallel execution would require LangGraph's `parallel_execute` which is a future enhancement.
