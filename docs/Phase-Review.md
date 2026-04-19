# 🔍 Phase 3: Review — Deep Dive

This document details the complete flow of the Review phase in the Lios-Agent orchestrator. The Review phase validates generated code against the compiler, the visual design system, and human feedback.

---

## Overview

```
Code from Execution Phase
       │
       ▼
┌─────────────────┐    build failed     ┌─────────────────┐
│ Build Validator  │ ──────────────────► │ Router (retry)  │
│ (RTK + xcode)   │    (up to 3x)       └─────────────────┘
└───────┬─────────┘
        │ build passed
        ▼
┌─────────────────────┐    UI failed    ┌─────────────────┐
│  UI Vision Check    │ ──────────────► │ Router (retry)  │
│  (SimCtl + Vision)  │                 └─────────────────┘
└───────┬─────────────┘
        │ passed (or no UI)
        ▼
┌─────────────────┐
│      Push       │ → git commit + push → GitHub PR
└───────┬─────────┘
        │
        ▼
┌─────────────────────────┐
│    PR Review Loop       │  ← inline code review comments
│  (re-triggers pipeline) │     trigger a new fix cycle
└─────────────────────────┘
```

---

## Step 1: Build Validator

**Source:** `agent/graph.py` → `validator_node()` / `agent/tools.py` → `execute_xcodebuild()`

### Purpose
Compile the project and determine if the generated code actually works.

### Flow

#### 1a. Project Structure Generation
Before building, `prepare_project_structure()` auto-detects and runs the appropriate project generator:

| Detection | Command |
|-----------|---------|
| `project.yml` exists | `rtk xcodegen generate` |
| `Tuist/Project.swift` exists | `rtk tuist generate` |
| `Package.swift` exists | `rtk swift package resolve` |
| None of the above | Skip (assumes `.xcodeproj` already exists) |

#### 1b. Build Execution
```python
build_cmd = ["rtk", "xcodebuild", "build", "-scheme", "App", "-destination", "generic/platform=iOS Simulator"]
```
- If `scripts/xcodebuild_cached.sh` exists, it uses the cached build script instead.
- All output is piped through **RTK** (Rust Token Kit), which truncates verbose xcodebuild logs (~30,000 lines) into compact semantic summaries (~20 tokens).

#### 1c. RTK Safety Check
```python
if not shutil.which("rtk"):
    return "FATAL ERROR: The `rtk` CLI proxy is missing from the system PATH."
```
If RTK is not installed, the validator **halts immediately** rather than silently dumping 30K tokens into the LLM.

#### 1d. Result Routing

**Build Succeeded:**
- Posts a Slack Block Kit message with an **[Approve & Push]** button.
- Routes to `ui_vision_check` via `should_retry() → "ui_check"`.

**Build Failed (retries < 3):**
- Appends compiler output to `state["compiler_errors"]`.
- Increments `retries_count`.
- Routes back to the Router → Sub-Agents for targeted fixes.

**Build Failed (retries >= 3):**
- Triggers a **full state rollback**:
  ```bash
  rtk git clean -fd          # Remove untracked files
  rtk git checkout -- .      # Restore all modified files
  ```
- Routes to `ui_vision_check` (which will pass through to Push, giving up gracefully).

---

## Step 2: UI Vision Check

**Source:** `agent/graph.py` → `ui_vision_validator_node()` / `agent/tools.py` → `capture_simulator_screenshot()`, `validate_ui_with_vision()`

### Purpose
An app can compile perfectly but still look visually broken. This step catches pixel-level regressions that pass the compiler.

### Activation Condition
The node inspects `blueprint["architecture_components"]` for UI-related keywords:
```python
ui_keywords = ["SwiftUI", "UIKit", "View", "Construkt", "UI", "Screen", "Component"]
```
- **If no UI keywords found** → Skip entirely, proceed to Push.
- **If UI keywords found** → Run the visual verification pipeline.

### Flow

#### 2a. Simulator Screenshot Capture
1. `xcrun simctl list devices available -j` → Find an available iOS simulator.
2. `xcrun simctl boot {udid}` → Boot it if not already running.
3. `xcodebuild build -destination "platform=iOS Simulator,id={udid}"` → Build and install the app.
4. Wait 3 seconds for the simulator to settle.
5. `xcrun simctl io {udid} screenshot .lios_screenshot.png` → Capture the screen.

#### 2b. Vision LLM Validation
1. The screenshot PNG is base64-encoded.
2. A multimodal LLM (GPT-4o / Claude Sonnet) receives:
   - The screenshot image
   - Design constraints from the blueprint:
     ```
     Architecture components: SwiftUI, MVVM, Construkt.bgPrimary
     Feature: OrderTrackingScreen
     Ensure compliance with Construkt design tokens and MVVM layout patterns.
     ```
3. The LLM evaluates:
   - Color palette compliance
   - Layout structure (spacing, alignment, hierarchy)
   - Typography consistency
   - Component completeness
4. Response format: `"PASS: ..."` or `"FAIL: ..."`

#### 2c. Result Routing

**Vision Passed (or skipped)** → Proceed to Push.

**Vision Failed (retries < 3):**
- The visual feedback is appended to `state["compiler_errors"]` as `"UI VISION FAILURE: {feedback}"`.
- Routes back to Router → Sub-Agents, where the UI sub-agent receives the visual feedback in its error prompt.

**Screenshot capture failed** → Warning logged, proceed to Push anyway (non-blocking).

---

## Step 3: Push

**Source:** `agent/graph.py` → lambda node / `agent/tools.py` → `commit_and_push_branch()`

### Purpose
Commit the agent's changes and push them to GitHub as a pull request branch.

### Flow
1. `git checkout -B {branch_name}` — Ensure we're on the agent's branch.
2. `git add .` — Stage all modifications.
3. `git commit -m "{commit_message}"` — Commit with a descriptive message.
4. `git push -u origin {branch_name}` — Push to the remote.

### Note
The current implementation pushes the branch but does not yet auto-create a GitHub Pull Request via the API. The branch appears on GitHub and the developer can open the PR manually. Auto-PR creation is a future enhancement.

---

## Step 4: PR Review Loop

**Source:** `main.py` → `github_webhook()` handler for `pull_request_review_comment` events

### Purpose
When a human developer reviews the agent's PR and leaves inline code comments, the agent automatically picks up the feedback, fixes the code, and pushes the update — all without human intervention beyond the initial comment.

### Trigger
GitHub sends a `pull_request_review_comment` webhook when a developer comments on a specific line of code in the PR diff.

### Flow
1. **Extract Context:**
   ```python
   review_body = comment["body"]          # "Change this red to Construkt.bgPrimary"
   diff_hunk = comment["diff_hunk"]       # The surrounding diff context
   file_path = comment["path"]            # "Sources/Features/Order/OrderTrackingView.swift"
   pr_branch = pull_request["head"]["ref"] # "ios-agent-issue-42"
   ```

2. **Clone & Checkout PR Branch:**
   ```python
   task_id = f"pr-review-{pr_number}"
   clone_isolated_workspace(task_id, repo_url)
   git fetch origin {pr_branch}
   git checkout {pr_branch}
   ```

3. **Construct Targeted Instructions:**
   ```
   PR Review Fix Request:
   File: Sources/Features/Order/OrderTrackingView.swift
   Diff Context:
   @@ -45,7 +45,7 @@ struct OrderTrackingView: View {
   -    .foregroundColor(.red)
   +    .foregroundColor(Color("primary"))
   
   Reviewer Comment: Change this red to Construkt.bgPrimary
   
   Fix the code in the file mentioned above based on the reviewer's feedback.
   ```

4. **Re-trigger Pipeline:**
   The full Router → Sub-Agent → Validator pipeline runs with the review instructions.

5. **Push Fix:**
   The corrected code is committed and pushed directly to the existing PR branch.

### Key Behaviors
- Each review comment triggers an **independent** pipeline run.
- The `thread_id` is `"pr-review-{pr_number}"` so LangGraph checkpoints don't collide with the original issue thread.
- The workspace is a fresh sandbox (`pr-review-{pr_number}`) to avoid contaminating the original workspace.

---

## Retry Budget Summary

| Failure Type | Max Retries | On Exhaustion |
|-------------|-------------|---------------|
| **Build errors** | 3 | `git clean -fd && git checkout -- .` (full rollback), then proceed to push |
| **UI vision failures** | 3 (shared counter) | Skip visual check, proceed to push |
| **PR review fixes** | 3 (independent counter) | Pipeline ends; developer must fix manually |
