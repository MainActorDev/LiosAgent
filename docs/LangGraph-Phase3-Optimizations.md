# Phase 3: Edge Case Resiliency & GitHub Two-Way Communication

This document outlines the Phase 3 enhancements to **Lios-Agent**, transforming it from a naive background executor into a communicative, highly concurrent AI team member.

---

## 1. APFS Copy-on-Write Concurrency (Implemented)

### The Problem
Traditional agent workflows run `git clone` or hold a single queue lock for local directories. For an iOS project using Swift Package Manager, a cold `xcodebuild` takes ~3-5 minutes to resolve dependencies and build DerivedData. If 5 developers open an issue concurrently, developer 5 waits 25 minutes.

### The Solution: Apple File System (APFS) Cloning
The `agent/tools.py` now maintains a single background repository: `.workspaces/seed_cache`.
- This `seed_cache` stays "warm", retaining all `.derived-data` and `.spm-cache`.
- When a task triggers `clone_isolated_workspace()`, the orchestrator uses `cp -cR` (macOS APFS Clone).
- **Result**: Instantaneous, zero-byte duplicate environments for concurrent agent workflows. Each developer's GitHub issue is processed immediately in parallel using pre-warmed Xcode caches.

---

## 2. Issue Vetting Node (The "Clarifier")

### The Problem
If a developer opens an issue with the description *"Fix the padding bug"*, the agent blindly launches Xcode, guesses the file, and runs a massive compiler loop, wasting LLM tokens and compute blindly.

### The Solution: Pre-Flight AI Vetting
We are introducing a new Node at the very start of the graph: `issue_vetting_node`.

1. **Trigger**: Executes immediately after `initialize_workspace_node`.
2. **Logic**: The LLM reads the GitHub Issue title and body. It evaluates:
   - Is it actionable iOS code work?
   - Is there enough context to locate the file, or is it too ambiguous (e.g. "dummy message")?
3. **Conditional Routing**:
   - `If Actionable`: Reroutes to standard `planner_node`.
   - `If Ambiguous`: Reroutes to standard `clarify_issue_node`.

---

## 3. GitHub Two-Way Pipeline

### The Problem
The agent currently communicates validation states via Slack (`#agent-ops`). However, the developer who opened the GitHub Issue has zero visibility into the agent's progress (e.g., if it failed to compile, or if it needs clarification).

### The Solution: The GitHub Comment Tool
We are building a `github_comment_tool` inside `agent/tools.py` using `PyGithub`.

1. **Auth Pivot**: Instead of just using webhooks to read, `main.py` will use the App ID (`GITHUB_APP_ID`) and the PEM Private Key (`lios-agent.private-key.pem`) to generate a temporary Installation Access Token.
2. **Implementation**:
   - The `Clarifier Node` will invoke the LLM to write a polite reply: *"Hi! Could you clarify which UI element has the padding bug?"*
   - The tool will post this directly into the Github Issue thread.
3. **Status Reporting**:
   - During long `xcodebuild` validation cycles, the agent will post GitHub comments (e.g. *"✅ Xcode validation finished. Push pending approval in Slack."*)

This unifies the developer experience, ensuring the human and the AI can converse asynchronously on GitHub exactly as two human developers would.
