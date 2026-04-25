# 🔍 Phase 3: Review — Deep Dive

This document details the complete flow of the Review phase in the Lios-Agent orchestrator. The Review phase validates generated code against the compiler, autonomously navigates the UI via Maestro to assert pixel-perfect accuracy, and securely merges its workflow artifacts back to GitHub.

---

## Overview

```
Code from Execution Phase (Parallel Processing via Send API)
       │
       ▼
┌─────────────────┐    build failed     ┌─────────────────┐
│ Build Validator │ ──────────────────► │ Router (retry)  │
│ (Native Loop)   │    (up to 3x based  └─────────────────┘
└───────┬─────────┘    on compile_retry_count)
        │ build passed
        ▼
┌─────────────────────────────────┐   fails   ┌─────────────────┐
│ Maestro Flow & UI Vision Nav    │ ────────► │ Router (retry)  │
│ (simctl + glm-4v + maestro)     │           └─────────────────┘
└───────┬─────────────────────────┘
        │ passed (or no UI)
        ▼
┌──────────────────────────────────────────────┐
│  Push Node & GitHub Telemetry Rendering      │
│  (Commits flow, videos, or halts pipeline)   │
└───────┬──────────────────────────────────────┘
        │
        ▼
┌─────────────────────────┐
│    PR Review / Redo     │  ← Issue Comments or Redo override
│  (re-triggers pipeline) │     trigger a new fix cycle
└─────────────────────────┘
```

---

## Step 1: Build Validator Bypass

**Source:** `agent/graph.py` → `validator_node()`

### Purpose
Determine if the generated code actually compiles natively. A strict 5-minute timeout is enforced at the `xcodebuild` subprocess level to guarantee the orchestrator can never hang indefinitely.

### Flow
Lios-Agent entirely delegates `verification-before-completion` directly to the execution phase. If OpenCode exits cleanly, `validator_node` skips redundant Xcodebuild logic and inherently transitions the state forward by pushing the `Build SUCCESS` signal to the graph.

**Build Failed (via catastrophic LLM timeout):**
- LangGraph triggers a **full state rollback** after 3 failed compilation loops (managed by `compile_retry_count`).
- Routes to `push_node` with a halted status.

---

## Step 2: Maestro Flow Synthesis & UI Validation

**Source:** `agent/graph.py` → `maestro_navigation_generator`, `vision_validation` / `agent/tools.py`

### Purpose
An app can compile perfectly but still look visually incorrect. This phase performs dynamic, hierarchy-aware autonomous navigation using physical interaction (via Maestro) to reach modified views, capture telemetry, and pass vision evaluations.

### Flow

#### 2a. Human Override Detection Pipeline
Lios-Agent first regex scans the developer's GitHub Issue instructions for an explicit ````yaml appId: ... ```` markdown block.
- **Override Triggered:** The system completely bypasses the subjective LLM vision loop. It extracts the raw developer-provided Maestro flow, invisibly injects `- startRecording: lios_navigation` into it, and strictly follows the human's deterministic navigation logic.
- **No Override:** The system falls back to fully autonomous traversal.

#### 2b. Autonomous Vision Navigation Loop
1. **Source Code Hint Extraction:** A planning LLM parses the Git diffs of modified files (like `AppCoordinator.swift` and `ProfileView.swift`) to extrapolate semantic hints about how to reach the newly added view computationally.
2. **Interactive Simulation:**
   - Boot iOS Simulator.
   - The Orchestrator begins a finite loop state machine. At each frame, it uses `xcrun simctl` to capture a screenshot (`maestro_step_*.png`) and dumps the live semantic UI hierarchy using `maestro hierarchy --compact`.
   - A multimodal Vision LLM consumes the screen capture, the parsed UI elements array, and previous `action_history` context. It outputs an action command: `TAP: <label>`, `SCROLL: DOWN`, or `DONE` (Reached Target).
   - If `TAP` or `SCROLL` is outputted, the command translates into a temporary `maestro_step.yaml` (using `retryTapIfNoChange` capabilities) to physically move the simulator, validating interactions based on standard accessibility logic (IDs and Text properties).
   - The loop utilizes internal Loop Detection to prevent infinite tapping.

#### 2c. Replayable Flow Synthesis
Once the `DONE` flag is reached, `agent/tools.py` synthesizes the validated `action_history` sequence into a final, canonical `maestro_flow.yaml`. 
It natively wraps this artifact inside recording blocks. It then executes the sequence rapidly to create the high-definition `lios_navigation.mp4` output artifact and captures the final `lios_final_state.png`.

#### 2d. Quality Validation
A Multimodal LLM compares the final capture against Construkt design constraints inside the FeatureBlueprint to enforce pixel-perfect layout and token compliance. Returns `PASS` or `FAIL`.

---

## Step 3: Push Node & GitHub Formatting

**Source:** `agent/graph.py` → `push_node`

### Purpose
Commit the agent's workspace changes and pipe rich telemetry logs safely back into the developer's GitHub conversation.

### Flow
1. Evaluates overall workflow status.

**Status: SUCCESS**
- Code merges and pushes to feature branch remote.
- Generates a vibrant PR comment containing hydrated repository artifact `.mp4` URLs (automatically wrapping them natively via GitHub's Markdown video renderers).

**Status: FAILED (Halted)**
- If a pipeline fatally crashes (max SwiftUI compiler retries hit or Maestro navigation loop crashes), the system natively traps the LangGraph in the `await_clarification` state.
- `push_node` builds a `Push Halted` markdown block on the Issue comment and rigorously extracts the actual Xcode crash log OR the pipeline Python exception, mapping it cleanly so the developer doesn't need to read terminal outputs.

---

## Step 4: Redo Pipeline / Human-in-the-Loop Recovery

**Source:** `main.py` → `issue_comment` Webhook Handler

### Purpose
Gracefully recover aborted states without ever leaving GitHub via simple developer messaging.

### Flow
If the developer reads the `Push Halted` log and leaves a GitHub comment starting with **"Redo: <instruction>"**:
- `main.py` immediately resets `state.halted: False` and clears the error cache strings.
- Appends the developer's new instructions cleanly onto the agent workflow prompt context.
- Fires the exact same pre-configured LangGraph Config to intrinsically bypass the halt trap and seamlessly re-initialize the pipeline from the `vetting` node, inherently wiping the corrupt branch sandbox and trying again with fresh developer insight!
- If the thread was actually terminated historically and completely died natively, it bypasses graph logic and spins up a brand new `thread_id` to dynamically override the death.
