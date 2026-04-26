# Tech Debt & Architecture Improvements Design

## 1. Overview
This document outlines a series of technical debt and architectural improvements for the `Lios-Agent` codebase. The primary goals are to increase the reliability of agent execution (stability), reduce the time-to-completion for epics (speed) without risking git merge conflicts, and improve developer experience (DX). 

Cross-platform support (Linux/Docker) is explicitly deferred and should be tracked as a separate long-term backlog item.

## 2. Stability & Reliability (Subprocess Resilience)
The agent orchestrator relies heavily on native macOS subprocesses (`xcodebuild`, `xcrun simctl`, `maestro`, and the headless `opencode-ai` CLI). Currently, there are no strict guards against these processes hanging indefinitely.

### 2.1 Implementation Details
*   **Timeouts:** Update `subprocess.run` calls in `agent/tools.py` with explicit `timeout` arguments.
    *   `opencode-ai` execution: e.g., 10 minutes.
    *   `xcodebuild`: e.g., 5 minutes.
    *   `maestro` validation: e.g., 3 minutes.
*   **Retry Limits:** Update `AgentState` in `agent/state.py` to include an integer counter `compile_retry_count`.
*   **Graph Updates:** The LangGraph `should_retry` conditional edge will evaluate `compile_retry_count`. If it exceeds the maximum threshold (e.g., 3 retries), the graph will abort the epic or bubble up the error to the CLI rather than spinning in an infinite loop.

## 3. Parallel Execution (Speed via Strict File-Level Isolation)
To dramatically increase execution speed, the system will process independent user stories concurrently using LangGraph's `Send` API. To completely eliminate the risk of git merge conflicts, parallel execution will be gated by strict file-level isolation.

### 3.1 Implementation Details
*   **AgentState Update:** `AgentState` will track `active_story_ids: list[str]` instead of a single `current_story_id`.
*   **Decomposer Updates:** The `PRDDocument` Pydantic model in `agent/ralph.py` will be updated so that each `UserStory` includes a specific `target_files: list[str]` array detailing exactly which files it will modify.
*   **The Lock Manager:** `story_selector_node` will be refactored to act as a file lock manager. It will iterate through the queue of incomplete stories:
    1.  It maintains a list of `locked_files` currently being operated on by active stories.
    2.  If a pending story's `target_files` list does NOT intersect with `locked_files`, it is yielded concurrently via `Send("architect_coder", { "story_id": id })`.
    3.  If it does intersect, the story is deferred until the active lock is released.
*   **Concurrency limits:** A max concurrency limit (e.g. 3 parallel stories) should be introduced to prevent starving the host system's RAM/CPU during simultaneous compilations.

## 4. Testing & Maintenance (Developer Experience)
To ensure the complex state machine remains robust during iterations, a local test suite will be introduced.

### 4.1 Implementation Details
*   **Framework:** Introduce `pytest` to `requirements.txt`.
*   **Directory:** Create a standard `tests/` root directory.
*   **Graph Unit Tests:** Create `tests/test_graph.py` which will initialize the graph state and use `unittest.mock` to spoof LLM responses (the Planner and Decomposer) to verify conditional edge routing logic without calling OpenAI APIs.
*   **Tool Mocking:** Mock native subprocess calls in `agent/tools.py` (like `execute_xcodebuild`) so that the graph can be tested end-to-end on non-macOS hardware or CI pipelines instantly.
