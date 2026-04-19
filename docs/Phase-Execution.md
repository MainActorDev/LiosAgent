# ⚡ Phase 2: Execution — Deep Dive

This document details the complete flow of the Execution phase in the Lios-Agent orchestrator. The Execution phase is responsible for writing code through domain-specialized sub-agents using surgical line-range patching.

---

## Overview

```
Blueprint Approved (HITL gate passed)
       │
       ▼
┌──────────────┐
│    Router    │  ← classifies blueprint into domains
└──┬───┬───┬───┘
   │   │   │
   ▼   │   ▼
┌──────┐ │ ┌──────────────┐
│  UI  │ │ │   General    │
│ Agent│ │ │    Coder     │
└──┬───┘ │ └──────┬───────┘
   │     ▼        │
   │ ┌──────────┐ │
   │ │ Network  │ │
   │ │  Agent   │ │
   │ └────┬─────┘ │
   │      │       │
   ▼      ▼       ▼
┌──────────────────────┐
│      Validator       │  → Review Phase
└──────────────────────┘
```

---

## Step 1: Router Node

**Source:** `agent/graph.py` → `router_node()` / `_classify_blueprint_domains()`

### Purpose
Analyze the `FeatureBlueprint` to determine which specialized sub-agents should handle the code generation, then dispatch accordingly.

### Classification Logic

The router inspects two data sources from the blueprint:

1. **`architecture_components`** — e.g., `["SwiftUI", "MVVM", "Construkt.bgPrimary", "APIService"]`
2. **File paths** — merged from `files_to_create` + `files_to_modify` + `files_to_test`

| Domain | Keyword Triggers (architecture) | Keyword Triggers (file paths) |
|--------|-------------------------------|------------------------------|
| **UI** | `swiftui`, `uikit`, `view`, `construkt`, `screen`, `component`, `ui` | `view`, `screen`, `cell`, `component` |
| **Network** | `api`, `network`, `repository`, `service`, `endpoint`, `data`, `model` | `service`, `repository`, `api`, `model`, `dto` |
| **General** | *(fallback if neither UI nor Network matched)* | — |

### Routing Rules
- If **only UI** keywords match → dispatch to `ui_subagent`
- If **only Network** keywords match → dispatch to `network_subagent`
- If **both** match → dispatch to `ui_subagent` first, then chain to `network_subagent`
- If **neither** matches → dispatch to `general_coder`

### State Output
```python
{
    "active_subagents": ["ui", "network"],  # or ["ui"] or ["general"]
    "history": ["Router: Dispatching to sub-agents: ui, network"]
}
```

---

## Step 2: Specialized Sub-Agents

All sub-agents share the **same tool set** but receive **different system prompts** scoped to their domain.

### Shared Tool Binding
```python
tools = [read_workspace_file, read_workspace_file_lines, write_workspace_file, patch_workspace_file]
llm_with_tools = llm.bind_tools(tools)
```

| Tool | When to Use |
|------|-------------|
| `read_workspace_file` | Quick full-file read for small files (< 100 lines) |
| `read_workspace_file_lines(start, end)` | Numbered line-range read for large files (pre-patch recon) |
| `write_workspace_file` | Creating **new** files only |
| `patch_workspace_file(start, end, content)` | Surgically replacing a specific line range in existing files |

### UI Sub-Agent

**Source:** `agent/graph.py` → `ui_subagent_node()`

**System Prompt Scope:**
> "You are the Lios UI Sub-Agent, a specialist in iOS View layer code. You ONLY work on SwiftUI Views, UIKit ViewControllers, Construkt design tokens, and UI components."

**Focus Areas:**
- SwiftUI `View` structs and modifiers
- UIKit `UIViewController` / `UICollectionViewCell` subclasses
- Construkt design tokens (`bgPrimary`, `textPrimary`, spacing constants)
- Layout composition and navigation wiring

**Instructions:**
- Only touch files related to Views, Screens, Components, and Cells
- Use Construkt token references for all colors and spacing
- Create UI-related XCTest files from the blueprint's `files_to_test`

### Network Sub-Agent

**Source:** `agent/graph.py` → `network_subagent_node()`

**System Prompt Scope:**
> "You are the Lios Network Sub-Agent, a specialist in iOS data layer code. You ONLY work on API Services, Repositories, Data Models, DTOs, and Networking logic."

**Focus Areas:**
- Repository pattern implementations
- API Service classes
- DTO ↔ Domain Model mapping
- Codable conformances

**Instructions:**
- Only touch files related to Services, Repositories, Models, APIs, and DTOs
- Follow clean architecture patterns: Repository → Service → DTO → Domain Model
- Create data-layer XCTest files from the blueprint's `files_to_test`

### General Coder

**Source:** `agent/graph.py` → `general_coder_node()`

**System Prompt Scope:**
> "You are the Lios Coder Agent" *(no domain restriction)*

Used as a fallback for tasks that don't clearly fit into UI or Network categories — e.g., build configuration changes, utility functions, script modifications.

### Sequential Chaining
When both UI and Network domains are detected:
1. UI Sub-Agent runs first → writes all view-layer files
2. Network Sub-Agent runs second → writes all data-layer files
3. Both outputs converge at the Validator

This is governed by `should_chain_after_ui()`: after the UI sub-agent completes, if `"network"` is in `state["active_subagents"]`, it routes to the Network sub-agent. Otherwise it goes straight to the Validator.

---

## Surgical Patching Protocol

The patching workflow the sub-agents follow when modifying existing files:

### Step 1: Recon
```
AI calls: read_workspace_file_lines("Sources/App/AppCoordinator.swift", start_line=45, end_line=65)

Response:
[Sources/App/AppCoordinator.swift] Lines 45-65 of 312 total
45: class AppCoordinator: Coordinator {
46:     func start() {
47:         let homeVC = HomeViewController()
48:         navigationController.pushViewController(homeVC, animated: true)
49:     }
50: }
```

### Step 2: Patch
```
AI calls: patch_workspace_file(
    "Sources/App/AppCoordinator.swift",
    start_line=47,
    end_line=48,
    new_content="""        let homeVC = HomeViewController()
        let orderVC = OrderTrackingViewController()
        navigationController.pushViewController(homeVC, animated: true)
"""
)

Response:
Patched Sources/App/AppCoordinator.swift: replaced lines 47-48 (2 lines removed, new content injected). File now has 313 lines.
```

### Why This Matters
- A 3000-line Swift file only contributes ~20 lines to the LLM's context window instead of all 3000.
- The rest of the file is never seen or touched — eliminating hallucination risk on unrelated code.
- Compiler errors from the Validator can reference exact line numbers, making the feedback loop precise.

---

## Error Feedback Loop

When the Validator (Review Phase) detects build failures, the pipeline loops back to the Router:
1. The compiler error log is appended to `state["compiler_errors"]`.
2. `retries_count` is incremented.
3. The Router re-classifies and dispatches to the appropriate sub-agent.
4. The sub-agent receives the error in its prompt:
   > "🚨 PREVIOUS BUILD FAILED WITH ERRORS: {error_log}. Use read_workspace_file_lines to find the broken lines, then patch_workspace_file to fix them."
5. This cycles up to **3 times** before the review phase triggers a full rollback.
