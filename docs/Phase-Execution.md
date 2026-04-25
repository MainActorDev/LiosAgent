# ⚡ Phase 2: Execution — Deep Dive

This document details the complete flow of the Execution phase in the Lios-Agent orchestrator. The Execution phase is responsible for writing code through a stateless, robust integration with the headless `opencode-ai` CLI.

---

## Overview

```
Blueprint Approved (HITL gate passed)
       │
       ▼
┌────────────────────────┐
│   Architect Coder      │  ← Auto-writes workspace guardrails
│   (opencode-ai Node)   │  
└──────┬─────────────────┘
       │ delegates execution
       ▼
┌────────────────────────┐
│  OpenCode CLI Spawn    │  ← Streaming subprocess
│  (Isolated Sandbox)    │ 
└──────┬─────────────────┘
       │ native AST AST + verification
       ▼
┌────────────────────────┐
│   Build Validator      │  → Review Phase
└────────────────────────┘
```

---

## Step 1: Architect Coder Node

**Source:** `agent/graph.py` → `architect_coder_node()`

### Purpose
Translate the machine-generated `FeatureBlueprint` into an actionable CLI execution payload, establish safety guardrails inside the isolated `.workspaces/Task/` sandbox, and invoke the OpenCode CLI.

### Architectural Evolution
Previously, this phase utilized a complex LangChain `Router` driving multiple fragile sub-agents (UI, Network, General). This was deprecated in favor of leveraging the world-class AST parsing and looping capabilities of OpenCode natively. Lios-Agent shifted from a *Coding Agent* into an *Orchestration Framework*.

### Flow

#### 1a. Safety Guardrail Injection
Before spawning the agent, `architect_coder_node` forcefully injects an `opencode.json` configuration file directly into the root of the active workspace.
```json
{
  "tool_rules": {
    "run_command": {
      "mode": "allow",
      "blacklist": ["rm -rf", "rm"]
    }
  }
}
```
This enables the agent to safely run in `--dangerously-skip-permissions` fully-autonomous mode while preventing the LLM from accidentally executing catastrophic shell commands.

#### 1b. Payload Construction
The blueprint's architecture domains, files to modify, and context are concatenated into a massive "Prompt Payload".

#### 1c. Subprocess Invocation & Streaming
The agent is executed via Python's `subprocess.Popen` instead of `os.system` or `subprocess.run(capture_output)`. A strict 30-minute timeout is enforced at the process level to prevent infinite LLM hallucinations.
```python
process = subprocess.Popen(
    ["npx", "--yes", "opencode-ai@latest", "run", prompt_payload, "--dangerously-skip-permissions"],
    cwd=workspace_path,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT
)
```
This enables **real-time terminal streaming** out to the macOS console. The developer watching the CLI matrix can monitor every AST edit and tool call line-by-line as OpenCode executes, rather than waiting 3 minutes for a silent script to return.

#### 1d. Session Recovery
As standard output streams by, Python actively regex-scans for OpenCode Session IDs:
*(e.g., `Session ID: 41bbfb77-3eab-4720`)*
If found, this is saved to `state["opencode_session_id"]`. This enables rapid, contextual "continue" executions during the PR Review loop in Phase 3 without starting the agent from scratch.

---

## Step 2: OpenCode Native Loop

Once the stateless execution begins, OpenCode takes over full responsibility for the "Coding Phase".
To understand OpenCode's role, think of the system as a **Manager/Executor** relationship:
- **LangGraph (The Manager):** Pulls issues from GitHub, assigns them to workspaces, posts Slack updates, runs tests, and pushes PRs.
- **OpenCode (The Executor):** Checks out the codebase, reads the Manager's blueprint, and physically writes the Swift/Obj-C code.

Specifically, OpenCode handles the following natively:

1. **Semantic Symbol Search:** Instead of doing basic `grep` searches, OpenCode natively understands AST (Abstract Syntax Trees). It searches for class names, structs, and variables across the iOS codebase intelligently to understand the project structure.
2. **Surgical Patching:** When OpenCode generates code, it executes `apply_patch` natively. It does not rewrite the entire 500-line Swift file (which risks LLM hallucination). It surgically replaces specific line ranges.
3. **Self-Healing Verification:** OpenCode runs a `verification-before-completion` loop. If it writes a SwiftUI modifier that causes a syntax error, OpenCode natively triggers `xcodebuild` or diagnostic parsing internally.

If OpenCode natively fails to compile its changes, it will seamlessly loop back onto itself to fix its own typographical iOS errors without ever returning control to the Python LangGraph layer until the fix is secure or the run terminates. This is what allowed us to delete the brittle Python-based validation logic entirely.

---

## Failure & State Handling

If `opencode-ai` exits with a non-zero exit code, or if a downstream orchestrator natively triggers a retry condition, LangGraph automatically handles iterative corrections:
1. `compile_retry_count` is incremented in the `AgentState`.
2. The pipeline routes back to `architect_coder`.
3. Because `state["opencode_session_id"]` was captured contextually, the agent invokes `npx opencode-ai run --continue --session {ID}`, feeding the compiler error directly backward into the memory matrix of the exact existing session.
4. **Fatal Max Retries:** If the AI loops and fails **3 times** resolving the semantic compilation error, the orchestrator triggers a State Rollback (`git checkout -- .` and `git clean -fd`) destroying the workspace anomaly cleanly.
5. **Halt Trap:** To ensure developer visibility, the Orchestrator flips `state.halted` to `True` during the `Push` operation, skipping the final code pushes and dynamically freezing the thread state inside the GitHub PR. Developers can then instantly review the exact terminal abort log pushed to their GitHub issue, and reply `Redo: <feedback>` to resurrect the trapped LangGraph pipeline!
