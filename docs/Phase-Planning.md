# 📐 Phase 1: Planning — Deep Dive

This document details the complete flow of the Planning phase in the Lios-Agent orchestrator. The Planning phase is responsible for understanding the task, gathering codebase intelligence, producing a deterministic architectural blueprint, and gating execution behind human approval.

---

## Overview

```
GitHub Issue Opened
       │
       ▼
┌──────────────┐    vague    ┌──────────────────────────┐
│   Vetting    │ ──────────► │ Post Clarification & END │
└──────┬───────┘             └──────────────────────────┘
       │ actionable
       ▼
┌──────────────────┐
│  Workspace Init  │  (APFS Clone → sandbox)
└──────┬───────────┘
       ▼
┌──────────────────────────┐
│   Context Aggregator     │  (async MCP micro-agent)
│   ┌────────────────────┐ │
│   │ Serena MCP         │ │  → codebase symbols, protocols, patterns
│   │ XcodeBuildMCP      │ │  → build settings, schemes, targets
│   │ (Figma/Jira: TBD)  │ │
│   └────────────────────┘ │
└──────┬───────────────────┘
       ▼
┌──────────────────┐
│     Planner      │  (Pydantic structured output → FeatureBlueprint)
└──────┬───────────┘
       ▼
┌──────────────────────────────┐
│  Blueprint Presentation      │  → Posts Markdown to GitHub Issue
│  (HITL Gate — waits for      │  → Pipeline HALTS
│   "Approve" comment)         │
└──────────────────────────────┘
```

---

## Step 1: Issue Vetting

**Source:** `agent/graph.py` → `issue_vetting_node()`

### Purpose
Prevent the agent from wasting compute on vague, spam, or incomplete issues.

### Flow
1. The raw `issue.title` + `issue.body` text is passed to the Planning LLM.
2. The LLM is prompted:
   > "If the issue is clear enough to attempt finding/fixing code (it mentions a component, feature, or clear request), simply reply 'ACTIONABLE'. If the issue is vague, dummy testing text, or lacks context, write a short polite comment asking the developer for clarification."
3. Two outcomes:
   - **`"ACTIONABLE"`** → The graph proceeds to Workspace Init.
   - **Anything else** → The LLM's response is posted as a GitHub comment on the issue via `post_github_comment()`, and the pipeline terminates.

### What is gathered
Nothing. This is purely a quality gate.

### Example rejection
Issue: *"fix the app"*
Agent comment: *"Hi! Could you provide more details about what specifically needs to be fixed? For example: which screen, feature, or error are you experiencing?"*

---

## Step 2: Workspace Initialization

**Source:** `agent/graph.py` → `initialize_workspace_node()` / `agent/tools.py` → `clone_isolated_workspace()`

### Purpose
Create a fully isolated sandbox copy of the target repository so the agent can read, write, and build code without touching any developer's local state.

### Flow
1. **Seed Cache Strategy:**
   - First run: Full `git clone <repo_url>` into `.workspaces/seed_cache/`.
   - Subsequent runs: `git reset --hard` → `git checkout main` → `git pull` (fast refresh, no re-download).
2. **APFS Copy-on-Write:**
   - `cp -cR seed_cache/ .workspaces/{task_id}/` — This exploits macOS APFS cloning. The copy is near-instant (< 0.1s) and uses zero additional disk space until files diverge.
   - Fallback: Regular `cp -R` if APFS is unavailable (e.g., external HFS+ volumes).
3. **Branch Checkout:**
   - `git checkout -B ios-agent-issue-{task_id}` — The `-B` flag safely overwrites if the branch already exists from a previous run.

### What is stored in state
```python
{
    "workspace_path": "/path/to/.workspaces/{task_id}",
    "current_branch": "ios-agent-issue-{task_id}"
}
```

---

## Step 3: Context Aggregator (MCP Intelligence Gathering)

**Source:** `agent/graph.py` → `context_aggregator_node()` / `agent/mcp_clients.py` → `MCPManager`

This is the **most critical intelligence step** and the reason the agent can produce contextually accurate blueprints instead of hallucinated architectures.

### Why it's async
MCP servers communicate over persistent stdio pipes. Python's `AsyncExitStack` is required to properly manage the lifecycle of multiple concurrent pipe connections without leaking file descriptors.

### Flow

#### 3a. MCPManager Boot Sequence
1. **PATH Resolution:**
   - Runs `bash -l -c "echo $PATH"` to capture the interactive shell's full PATH.
   - This resolves NVM-managed Node.js, Homebrew binaries, Cargo tools, etc.
   - Fallback paths: `/opt/homebrew/bin`, `/usr/local/bin`, `~/.local/bin`, `~/.cargo/bin`.

2. **MCP Server Connections:**

   | Server | Stdio Command | What It Provides |
   |--------|--------------|------------------|
   | **XcodeBuildMCP** | `npx -y xcodebuildmcp@latest mcp` | Xcode project structure, build settings, available schemes, targets, SDK versions, deployment targets |
   | **Serena MCP** | `serena mcp` | Codebase-wide symbol search, file tree navigation, class/struct/protocol definitions, method signatures, dependency graphs, import analysis |
   | *(Figma MCP)* | *Placeholder* | *Design tokens, component specs, color palettes — not yet wired* |
   | *(Jira MCP)* | *Placeholder* | *Ticket acceptance criteria, linked issues — not yet wired* |

3. **Tool Loading:**
   - Each MCP session's capabilities are auto-converted into LangChain `Tool` objects via `load_mcp_tools(session)`.
   - All tools from all servers are merged into a single flat list.
   - Example tools surfaced: `search_symbol`, `get_file_content`, `list_build_settings`, `get_available_schemes`, etc.

#### 3b. Autonomous Micro-Agent Loop
4. **ReAct Agent Spawn:**
   - A `create_react_agent(llm, tools=all_tools)` is created — this is a fully autonomous reasoning loop running *inside* this single graph node.
   - The agent receives this prompt:
     > "Use your tools to find deep context related to this issue: {instructions}. Search codebase symbols or legacy patterns. Return a thorough technical summary."

5. **Multi-step Tool Calling:**
   - The micro-agent autonomously decides which tools to call and in what order. A typical session might look like:
     1. `search_symbol("OrderTrackingView")` → finds existing view file
     2. `get_file_content("Sources/Features/Order/OrderTrackingView.swift")` → reads the implementation
     3. `search_symbol("OrderRepository")` → discovers the data layer
     4. `list_build_settings()` → confirms the deployment target is iOS 16+
   - The agent loops until it has enough context, then produces a summary.

6. **Output:** The final response is stored as a plain string in `state["mcp_context"]`.

#### 3c. Failure Handling
- If no MCP servers connect (e.g., Node not installed, Serena not available):
  - Returns `"No external MCP context available."` 
  - The pipeline **proceeds anyway** — the Planner works with just the issue text.
- If the micro-agent errors mid-execution:
  - Returns `"Failed to execute context gathering: {error}"`
  - The pipeline proceeds with degraded context.
- **Cleanup:** `manager.cleanup()` always runs (via `finally` block) to close all stdio pipes.

### What information is gathered

| Category | Examples |
|----------|---------|
| **Existing code structure** | File tree, module boundaries, feature folder locations |
| **Class hierarchies** | Protocol conformances, base class chains, generic constraints |
| **Design patterns in use** | MVVM, Coordinator, Repository, Factory patterns already present |
| **Design system tokens** | Construkt color tokens, spacing constants, typography styles |
| **Build configuration** | Deployment target, SDK version, active schemes, Swift version |
| **Dependencies** | SPM packages, framework imports, third-party library versions |
| **Similar features** | How existing similar screens/modules are structured (prior art) |

---

## Step 4: Planner (Structured Blueprint Generation)

**Source:** `agent/graph.py` → `planner_node()`

### Purpose
Transform the gathered intelligence + issue requirements into a **deterministic, machine-readable** execution plan.

### Flow
1. **Structured Output Binding:**
   ```python
   llm = get_llm(role="planning").with_structured_output(FeatureBlueprint)
   ```
   This forces the LLM to return **only valid JSON** matching the Pydantic schema. No freeform text, no markdown — pure structured data.

2. **Prompt Construction:**
   The prompt combines three inputs:
   - `instructions` — the raw GitHub issue text
   - `mcp_context` — everything the Context Aggregator discovered
   - A directive: *"Ensure you mandate TDD by defining the XCTest suites."*

3. **Output Schema (`FeatureBlueprint`):**
   ```python
   class FeatureBlueprint(BaseModel):
       feature_name: str                       # "OrderTrackingScreen"
       files_to_create: List[FileModification]  # New files to scaffold
       files_to_modify: List[FileModification]  # Existing files to surgically patch  
       files_to_test: List[FileModification]    # XCTest suites (REQUIRED — enforces TDD)
       architecture_components: List[str]       # ["SwiftUI", "MVVM", "Construkt.bgPrimary"]
   ```
   Each `FileModification` contains:
   ```python
   class FileModification(BaseModel):
       filepath: str   # "Sources/Features/Order/OrderTrackingView.swift"
       purpose: str    # "New SwiftUI view implementing the tracking timeline UI"
   ```

4. **TDD Enforcement:**
   `files_to_test` has a Pydantic Field description that says *"Must contain at least 1 test file."* The LLM is structurally compelled to populate this array.

5. **Blueprint stored in state:**
   ```python
   state["blueprint"] = blueprint.dict()
   ```
   This flows downstream to the Router (for domain classification) and the Sub-Agents (as their execution instructions).

### Key design decision
By using Pydantic structured output instead of free-text planning, we eliminate an entire class of failure modes: the LLM cannot produce ambiguous plans, skip files, or forget tests. If the JSON doesn't validate, LangChain will retry the LLM call automatically.

---

## Step 5: Blueprint Presentation (Human-in-the-Loop Gate)

**Source:** `agent/graph.py` → `blueprint_presentation_node()`

### Purpose
Post the plan for human review before any code is written. This is the safety net that prevents the agent from autonomously implementing a bad architecture.

### Flow
1. **Markdown Generation:**
   The blueprint dict is converted into a formatted GitHub Markdown comment:
   ```markdown
   ### 🏗️ Lios-Agent Architectural Blueprint: OrderTrackingScreen
   
   **Files to Create:**
   - `Sources/Features/Order/OrderTrackingView.swift`: New SwiftUI view...
   
   **Files to Modify:**
   - `Sources/App/AppCoordinator.swift`: Add navigation route...
   
   **Files to Test (TDD Enforcement):**
   - `Tests/OrderTrackingViewTests.swift`: Snapshot tests for...
   
   **Architecture Components:** `SwiftUI, MVVM, Construkt.bgPrimary`
   
   ---
   *Please reply with **Approve** to execute this graph.*
   ```

2. **GitHub Comment Post:**
   Uses `post_github_comment()` which authenticates via the GitHub App's private key and installation token.

3. **Pipeline Halt:**
   The LangGraph is compiled with `interrupt_before=["router"]`. The graph state is checkpointed to `MemorySaver`, and the Python thread returns.

### How it resumes
- A developer reads the blueprint on GitHub and comments **"Approve"**.
- GitHub sends an `issue_comment` webhook to `POST /webhooks/github`.
- The handler in `main.py` detects `body.lower() == "approve"` and calls:
  ```python
  graph_app.invoke(None, config={"configurable": {"thread_id": f"issue-{issue_num}"}})
  ```
- LangGraph rehydrates the state from the checkpoint and continues from the Router node.

---

## Known Gaps & Future Improvements

### 1. No Figma/Jira MCP Integration
The `server_configs` in `mcp_clients.py` has placeholders for Figma and Jira MCP servers, but they are not wired. This means:
- The agent has no access to the actual Figma design specs (colors, spacing, component hierarchy).
- The agent has no access to the Jira ticket's acceptance criteria or linked issues.

**Improvement:** Wire up `figma-mcp` and `jira-mcp` servers once they are available in the team's environment.
