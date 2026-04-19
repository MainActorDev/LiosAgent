# Lios-Agent Orchestrator 🤖🍏

Lios-Agent is an autonomous, agentic coding platform specifically engineered for iOS development. It leverages a Mixture-of-Experts ecosystem (via LangGraph) to read GitHub issues, generate localized Apple architectures, validate against compiler errors locally, and autonomously push pull requests.

## 🏗 Architecture

The platform operates purely via Slack and GitHub Webhooks, ensuring developers never need to leave their standard communication channels to trigger autonomous operations. The pipeline is organized into **3 main phases**, each containing specialized sub-nodes:

```
┌─────────────────────────────────────────────────────────────────────┐
│  📐 PLANNING PHASE                                                  │
│    Vetting → Workspace Init → Context Aggregator → Planner → HITL  │
├─────────────────────────────────────────────────────────────────────┤
│  ⚡ EXECUTION PHASE                                                 │
│    Architect Coder → Headless OpenCode CLI (AST Editing Sandbox)   │
├─────────────────────────────────────────────────────────────────────┤
│  🔍 REVIEW PHASE                                                    │
│    Build Validator Bypass → Maestro UI Nav → Push PR               │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 📐 Phase 1: Planning

Gathers intelligence, understands the task, and produces an architectural blueprint before any code is written.

| Sub-Node | Purpose |
|----------|---------|
| **Vetting** | Filters vague/spam issues. Posts a GitHub clarification comment if the issue lacks context; otherwise marks it `ACTIONABLE`. |
| **Workspace Init** | Clones the target repo into an isolated APFS Copy-on-Write sandbox. Checks out the agent's working branch (`ios-agent-issue-{id}`). |
| **Context Aggregator** | Async ReAct agent that: 1. Discovers codebase patterns via **Serena MCP** and **XcodeBuildMCP**. 2. Parses `.lios-config.yml` rules. 3. Aggregates any `.agent/**/*.md` instructions. 4. Fetches external web links if referenced in the target issue. |
| **Planner** | Consumes MCP context and outputs a strict Pydantic `FeatureBlueprint` JSON with mandatory `files_to_test` (enforcing TDD). |
| **Blueprint Presentation** *(HITL)* | Posts the blueprint as Markdown to the GitHub Issue. **Halts** the pipeline until a human comments **"Approve"**. |

---

### ⚡ Phase 2: Execution

Writes code through a stateless integration with the headless `opencode-ai` CLI. LangGraph acts strictly as the **Manager**, while OpenCode acts as the **Executor**.

| Sub-Node | Purpose |
|----------|---------|
| **Architect Coder** | Translates the blueprint into a massive Prompt Payload and injects safety guardrails (`opencode.json` blocklisting `rm -rf`) into the isolated workspace. |
| **OpenCode CLI** | Spawned as a streaming subprocess via Python. Handles AST parsing, surgical line replacements (`apply_patch`), and native compilation validation without LangGraph intervention. |

**Key Advantage:** OpenCode intrinsically loops upon itself if it introduces typographical compilation errors (`verification-before-completion`). LangGraph only parses the final output state.

---

### 🔍 Phase 3: Review

Validates the generated code against the compiler, the design system, and human feedback.

| Sub-Node | Purpose |
|----------|---------|
| **Build Validator Bypass** | Native Compilation validation assumes stability safely via OpenCode's enclosed native compilation loop, bypassing legacy standalone Python execution. |
| **Maestro UI Validation** | Computes intelligent autonomous visual verification on simulator (`xcrun simctl` + `maestro`). Dynamically captures iOS structures, checks against design limitations using multimodality, synthesizes deterministic replays (`maestro_flow.yaml`), and loops visually. Allows human-developer yaml overrides. |
| **Push** | Safely commits execution to GitHub. Generates markdown converting video telemetry straight to natively rendered `<video>` URLs. If a pipeline fatally traps the developer's execution limit, freezes execution on a suspended PR block for immediate GitHub Redo intervention. |
| **PR Review Loop** | When a human developer leaves an **inline code review comment**, the orchestrator clones the PR branch, triggers Coder → Validator, and pushes the fix natively! |

## 🚀 Quick Start & Installation

### 1. Pre-requisites
The orchestrator relies on several external CLI modules. Please ensure these are installed globally on your Host Mac:
- **Python 3.10+**
- **Xcode** (with Command Line Tools)
- **NVM / Node** (For the `npx xcodebuildmcp` client connection)
- **NPM / OpenCode CLI** (For native Agentic Execution)
  ```bash
  npm i -g opencode-ai@latest
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

# Optional: Figma & Jira MCP
FIGMA_ACCESS_TOKEN="figd_..."
JIRA_EMAIL="hello@yourcompany.com"
JIRA_BASE_URL="https://yourcompany.atlassian.net"
JIRA_API_TOKEN="..."
```

*Note: For Figma, generate a Personal Access Token with the `Files: Read` scope in your settings. For Jira, generate a standard API token from [Atlassian Security](https://id.atlassian.com/manage-profile/security/api-tokens).*

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
| **Headless OpenCode Run** | Delegates extremely tricky AST patching algorithms to a specialized 1st-party CLI. |
| **Pydantic FeatureBlueprint** | Forces deterministic JSON, preventing freeform text hallucination in planning. |
| **Auto-Destructing Workspaces** | Aggressive garbage collection (`shutil.rmtree`) happens immediately after a successful PR to prevent SPM / DerivedData bloat. |
| **Vision UI Validation** | Catches pixel-perfect regressions that pass compilation but look visually broken. |
| **Async Context Aggregator** | MCP connections require `AsyncExitStack` for persistent stdio pipe lifecycle. |

## ⚠️ Known Limitations
When scaling to a production team, be aware of the following system bounds:
1. **macOS Only**: APFS Copy-on-Write and `xcrun simctl` require macOS. Linux deployment requires alternative workspace strategies.
2. **Vision Model Required**: The UI Vision Check requires a multimodal LLM (e.g., GPT-4o, Claude Sonnet). If your configured model doesn't support image input, the vision check will gracefully skip.
3. **Simulator Availability**: The UI Vision Check requires at least one iOS Simulator runtime installed. Run `xcrun simctl list devices` to verify.

## 🛠️ Tech Stacks Used

Lios-Agent is orchestrated entirely in **Python**, binding native MacOS processes dynamically via Unix subshells for optimal hardware execution:

- **LangGraph** & **LangChain**: State machine routing, dependency injection, multi-agent synchronization, memory persistence (`sqlite`), and graph checkpoint definitions.
- **FastAPI**: Receives Github Webhooks efficiently via standard ASGI web applications.
- **Slack SDK**: Triggers HITL block-kits and pipelines across distributed engineering channels.
- **Opencode-AI CLI**: Specialized open-source headless Javascript execution terminal powering the fundamental LLM architectural AST traversal, tree-sitter patching syntax, and native `xcodebuild` execution matrix loop.
- **Maestro**: Native `.yaml` dynamic functional iOS visual UI testing layer.
- **Serena MCP**, **XcodeBuildMCP**, & **Figma MCP**: Pluggable protocol layers feeding semantic symbol context, native workspace schemas, and pixel-perfect design constraints natively into orchestrator loops via standard IO pipes.
