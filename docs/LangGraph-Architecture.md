# Phase 2: LangGraph Orchestrator Architecture

This document serves as the super-detailed blueprint for the core reasoning engine ("The Brain") behind **Lios-Agent**. It describes how we use LangGraph to build a stateful, cyclical, and autonomous agent capable of resolving complex iOS issues.

---

## 1. The Core Philosophy
A standard webhook bot is linear: *Trigger -> Action -> Response*.  
**Lios-Agent** is cyclical: *Analyze -> Plan -> Write Code -> Build -> (If Error -> Re-Plan) -> Approve -> Push*. 

We achieve this multi-hop reasoning cycle using **LangGraph**. LangGraph allows us to define the process as a State Machine. The agent travels from node to node, passing a persistent "State" packet along the way.

---

## 2. The Agent State (`state.py`)
All nodes in the graph share a single dictionary structure called the State. As the graph executes, nodes append or modify this state.

```python
from typing import TypedDict, List, Annotated
import operator

class AgentState(TypedDict):
    # Metadata
    task_id: str                # Corresponds to GitHub issue number or slack timestamp
    instructions: str           # The raw request from the user
    
    # Execution Tracking
    workspace_path: str         # The local path where the isolated repo was cloned
    current_branch: str         # The random branch name generated for this task
    
    # LangGraph Memory
    history: Annotated[List[str], operator.add] # Log of all steps taken (for Slack status)
    compiler_errors: List[str]  # Accumulated xcodebuild errors
    retries_count: int          # Hard limit to prevent infinite loops (max 3)
```

---

## 3. The Graph Nodes (`graph.py`)

Each "Node" in the LangGraph is a discrete Python function. The LLM Factory pattern we implemented ensures we can use different models (e.g., GPT-4o for planning, GLM-5.1 for coding) on a per-node basis.

### Node 1: `InitializeWorkspaceNode`
This is a standard python function (no AI).
1. Receives the trigger.
2. Calls the `clone_isolated_workspace` tool.
3. Injects the `workspace_path` into the State.

### Node 2: `PlannerNode` (Mixture of Experts: Planner LLM)
1. Injects the `instructions` into the designated "Planner" model.
2. The Planner reads the project structure to find relevant files.
3. It emits a JSON plan: `["Files to edit", "Target Architecture Pattern"]`.

### Node 3: `CoderNode` (Mixture of Experts: Coder LLM)
1. Takes the Plan from Node 2.
2. Iterates over the target files using `read_workspace_file`.
3. Calls the `write_workspace_file` tool to apply modifications.

### Node 4: `ValidatorNode` (No AI)
1. Calls the `execute_xcodebuild` tool inside the sandbox.
2. If `returncode == 0`: Proceeds to `ApprovalNode`.
3. If `returncode != 0`: Appends the compiler stderr to `compiler_errors` and increments `retries_count`.

---

## 4. The Conditional Edges
LangGraph uses "Edges" to decide where to route the State next based on logic.

- **Edge from `ValidatorNode`**:
  - `If build was SUCCESS -> goto `ApprovalNode`.
  - `If build FAILED and retries < 3 -> goto `CoderNode` (Feeding the LLM the exact compiler error to fix itself).
  - `If build FAILED and retries >= 3 -> goto `ApprovalNode` (Giving up and asking the human for help).

---

## 5. The Approval Protocol
We never push broken or rogue code directly to the repository origin without a human eyeball.

### Node 5: `SlackApprovalNode`
1. The graph execution pauses.
2. The webhook server triggers a Slack `chat.postMessage` to `#agent-ops`.
3. The message is a Block Kit layout showing:
   - The git diff (what files changed).
   - The build status (Pass/Fail).
   - A button: **[Approve PR]** or **[Cancel Run]**.
4. The graph yields and stores its memory checkpoint.

### Node 6: `FinalizeNode`
When the user clicks **[Approve PR]** in Slack:
1. The orchestrator receives the `/interactions` webhook.
2. It resumes the LangGraph from the checkpoint.
3. Calls the `commit_and_push_branch` tool.
4. Uses PyGithub to automatically open a Pull Request linking to the target issue.
