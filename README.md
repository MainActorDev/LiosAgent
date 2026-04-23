# Lios-Agent CLI 🤖🍏

Lios-Agent is an autonomous, terminal-first agentic coding platform specifically engineered for iOS development. It leverages a Mixture-of-Experts ecosystem (via LangGraph) to brainstorm architectures, decompose work into atomic user stories, validate against compiler errors locally, and autonomously push pull requests.

We have transitioned from an opaque webhook-driven server to a highly transparent, interactive **Feature Vault CLI Architecture**, allowing complete reproducibility, human-in-the-loop control, and git-trackable agent state.

## 🏗 Architecture

The platform operates purely from your macOS terminal using the `lios` executable wrapper. The pipeline is organized into **3 main phases**, each containing specialized sub-nodes:

```
┌─────────────────────────────────────────────────────────────────────┐
│  📐 PLANNING PHASE (CLI Interactive REPL)                           │
│    Vault Initialization → REPL Context Intake → Planner → HITL      │
├─────────────────────────────────────────────────────────────────────┤
│  ⚡ DECOMPOSITION & EXECUTION PHASE                                 │
│    PRD Decomposer → Story Vault Gen → Architect Coder (OpenCode)   │
├─────────────────────────────────────────────────────────────────────┤
│  🔍 MULTI-STORY REVIEW PHASE                                        │
│    Build Validator → Per-Story Commit → Maestro UI Nav → Push PR   │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 📐 Phase 1: Planning

Gathers intelligence, understands the task, and produces an architectural blueprint before any code is written.

| Sub-Node | Purpose |
|----------|---------|
| **Vault Init** | Dynamically scaffolds `.lios/epics/{epic_name}/` to isolate feature state entirely from global dependencies. |
| **Universal REPL** | Interactive terminal chat where you can provide requirements and use `@path/to/file` mentions to securely inject local file context into the prompt. |
| **Context Aggregator** | Async ReAct agent that discovers codebase patterns and fetches external web links. |
| **Planner** | Consumes the context and outputs a strict Pydantic `FeatureBlueprint` JSON with mandatory `files_to_test`. |
| **Blueprint Gate** *(HITL)* | Yields control back to the CLI terminal. **Halts** the pipeline until you type `Approve` or provide course-correction feedback. |

---

### ⚡ Phase 2: Decomposition & Execution

Writes code through a stateless integration with the headless `opencode-ai` CLI. Powered by **Ralph**, it breaks massive iOS blueprints into tiny, independently verifiable PRD stories.

| Sub-Node | Purpose |
|----------|---------|
| **PRD Decomposer** | Fragments the approved FeatureBlueprint into an array of `UserStory` models. Physically generates a nested `.lios/epics/{epic}/stories/{id}/story_plan.md` vault for each! |
| **Story Selector** | Pops the next uncompleted User Story from the queue. Ensures the pipeline focuses on one micro-task at a time. |
| **Architect Coder** | Translates the specific isolated story into a Prompt Payload and executes headless OpenCode editing inside the workspace sandbox. |

**Key Advantage:** By chunking work into strictly isolated vaults, the agent avoids massive context-exhaustion and creates a cleanly bisectable Git history.

---

### 🔍 Phase 3: Multi-Story Review Loop

Validates the generated code against the compiler per-story, and finally runs visual multimodal validation against the entire feature before pushing.

| Sub-Node | Purpose |
|----------|---------|
| **Build Validator** | Natively compiles the iOS project to verify the specific story. If it fails, loops back to the Coder. |
| **Story Commit** | Once a story passes compilation, atomically `git commit`s the changes. |
| **Maestro UI Validation** | Computes intelligent autonomous visual verification on simulator (`xcrun simctl` + `maestro`). Dynamically captures iOS structures, checks against design limitations using multimodality, and synthesizes deterministic replays (`maestro_flow.yaml`). |
| **Push via GitHub App** | Automatically exchanges your `GITHUB_APP_ID` for a dynamic JWT installation token, pushing the PR and posting validation telemetry securely under the **[Bot]** identity. |

## 🚀 Quick Start & Installation

### 1. Pre-requisites
The orchestrator relies on several external CLI modules. Please ensure these are installed globally on your Host Mac:
- **Python 3.10+**
- **Xcode** (with Command Line Tools)
- **NVM / Node** (For MCP client connections)
- **NPM / OpenCode CLI** (For native Agentic Execution)
  ```bash
  npm i -g opencode-ai@latest
  ```

### 2. Environment Variables
Copy `.env.example` to `.env`. For seamless PR posting, provide your GitHub App credentials:
```bash
# LLM Routing
LLM_PROVIDER="openai"        # Options: openai, glm, ollama
LLM_MODEL_NAME="gpt-4o"
OPENAI_API_KEY="sk-..."

# GitHub Bot Identity (Push-Based API)
GITHUB_APP_ID="123456"
GITHUB_PRIVATE_KEY_PATH="./lios-agent.private-key.pem"
GITHUB_REPO="yourcompany/your-ios-repo"
```

### 3. CLI Initialization
Set up your venv and use the convenient `lios` wrapper:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Verify the CLI is working
./lios --help
```

## ⚙️ Usage Guide (The Vault Lifecycle)

Lios-Agent uses physical directory vaults to track execution state.

### 1. Initialize an Epic
Start by defining a new high-level feature (an Epic).
```bash
./lios epic habit-tracker
```
This drops you into the **Universal REPL**. You can type your requirements and use `@` to attach local files:
```text
You: Please implement the core UI from @docs/prd.md.
```

### 2. Execute the Vault
Once intake is complete, execute the LangGraph pipeline against your generated vault:
```bash
./lios execute .lios/epics/habit-tracker
```
The agent will spin up, generate the architecture, and then **pause execution**, prompting you in the terminal to review `blueprint.md`!

### 3. Human-In-The-Loop Approval
Review the generated `.lios/epics/habit-tracker/blueprint.md`. 
If you like it, type `Approve` in the terminal. If it missed a file, simply chat: *"You forgot to include the Coordinator class, please regenerate."*

### 4. Direct GitHub Issue Telemetry
If you initialize an epic using a GitHub Issue number instead of a string name:
```bash
./lios epic 402
```
The CLI will automatically push execution updates, Maestro validation videos, and PR links directly to GitHub Issue #402!

## 📁 Project Structure

```text
Lios-Agent/
├── cli.py                   # Typer CLI entrypoint
├── lios                     # Executable wrapper (activates venv automatically)
├── requirements.txt         # Python dependencies
├── agent/
│   ├── vault_manager.py     # Scaffolds physical directories and isolated Checkpointers
│   ├── repl.py              # The Universal REPL and @file regex parser
│   ├── graph.py             # LangGraph nodes, edges, sub-agents, and HITL interrupts
│   ├── tools.py             # Sandbox git tools, xcodebuild, simctl, vision, github auth
│   ├── ralph.py             # PRD decomposition, Pydantic models, and story logic
│   └── llm_factory.py       # Provider-agnostic LLM factory (OpenAI/GLM/Ollama)
├── .workspaces/             # Auto-generated isolated sandbox clones (gitignored)
└── .lios/                   # Feature Vaults (git-trackable state and blueprints)
```

## 🔧 Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Vault State Manager** | Deprecated the global, opaque `.state.db` in favor of per-epic `.lios/` directories. This allows human operators to manually inspect `state.yml` and version-control agent execution across the team. |
| **Universal CLI REPL** | Stripped out complex Slack/Webhook setups. Native terminal intake allows for dynamic filesystem awareness (e.g. `@file` mentions). |
| **Ralph Autonomous Loop** | Decomposes massive features into tiny atomic user stories, physically generating a nested `stories/` vault for each. |
| **APFS Copy-on-Write** | Instant 0.1s workspace duplication on macOS. Allows seamless sandboxing. |

## 🛠️ Tech Stacks Used

Lios-Agent is orchestrated entirely in **Python**, binding native MacOS processes dynamically via Unix subshells for optimal hardware execution:

- **LangGraph**: State machine routing, dependency injection, and SQLite checkpoint interruptions.
- **Typer & Rich**: Beautiful, interactive terminal interfaces and CLI argument parsing.
- **Opencode-AI CLI**: Specialized open-source headless Javascript execution terminal powering the fundamental LLM architectural AST traversal.
- **Maestro**: Native `.yaml` dynamic functional iOS visual UI testing layer.
- **PyGithub JWT**: Programmatic GitHub App authentication to ensure code is pushed correctly under the `[Bot]` identity without requiring inbound webhooks.
