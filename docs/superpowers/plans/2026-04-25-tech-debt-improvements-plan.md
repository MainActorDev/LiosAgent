# Tech Debt Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve Lios-Agent stability via strict subprocess timeouts/retries, and significantly decrease execution time by parallelizing LangGraph execution via file-level locking.

**Architecture:** We will modify `subprocess.run` calls in `agent/tools.py` for stability, update the Pydantic models in `agent/ralph.py` to support explicit file targeting, and refactor `story_selector_node` in `agent/graph.py` to leverage LangGraph's `Send` API to map isolated tasks concurrently.

**Tech Stack:** Python 3.10+, LangGraph, Typer, pytest

---

### Task 1: Subprocess Resilience (Timeouts & Retries)

**Files:**
- Modify: `agent/state.py`
- Modify: `agent/tools.py`
- Modify: `agent/graph.py`

- [ ] **Step 1: Add retry tracking to state**

Update `agent/state.py` to include `compile_retry_count` in the `AgentState` TypedDict.

```python
from typing import TypedDict, Optional, List

class AgentState(TypedDict):
    # ... existing fields ...
    compile_retry_count: int
```

- [ ] **Step 2: Add strict timeouts to tool executions**

Update `agent/tools.py` to add `timeout=600` (10 minutes) for OpenCode and `timeout=300` (5 minutes) for Xcodebuild and Maestro. Import `subprocess.TimeoutExpired`.

```python
import subprocess
import logging

def execute_xcodebuild(path: str) -> str:
    try:
        # Example modification, ensure to preserve original args
        result = subprocess.run(["xcodebuild", "build"], cwd=path, capture_output=True, text=True, timeout=300)
        return result.stdout
    except subprocess.TimeoutExpired:
        logging.error("xcodebuild timed out after 5 minutes")
        return "ERROR: xcodebuild timed out."
# Apply similar timeout=600 blocks to the opencode-ai invocation in architect_coder logic if it lives here.
```

- [ ] **Step 3: Update `should_retry` conditional edge in graph**

Update `agent/graph.py` to check the `compile_retry_count`.

```python
def should_retry(state: AgentState) -> str:
    retry_count = state.get("compile_retry_count", 0)
    if retry_count >= 3:
        return "end" # Or a specific error handling node
    if state.get("compiler_errors"):
        return "architect_coder"
    return "validator"
```

- [ ] **Step 4: Commit**

```bash
git add agent/state.py agent/tools.py agent/graph.py
git commit -m "feat: add timeouts and retry bounds to subprocesses"
```

---

### Task 2: Parallel Execution Foundation (AgentState & Decomposer)

**Files:**
- Modify: `agent/state.py`
- Modify: `agent/ralph.py`

- [ ] **Step 1: Track active parallel stories**

Update `agent/state.py` to allow multiple active stories.

```python
class AgentState(TypedDict):
    # ... existing fields ...
    active_story_ids: List[str] # replaces current_story_id string
```

- [ ] **Step 2: Update PRD Decomposer for file targeting**

Update the `UserStory` Pydantic model in `agent/ralph.py` to require `target_files`. Update the LLM prompt to populate this array.

```python
from pydantic import BaseModel, Field
from typing import List

class UserStory(BaseModel):
    id: str = Field(description="Unique story ID")
    title: str = Field(description="Story title")
    description: str = Field(description="Detailed requirements")
    target_files: List[str] = Field(description="Exact file paths this story will modify or create")
    # ... existing fields ...
```

- [ ] **Step 3: Commit**

```bash
git add agent/state.py agent/ralph.py
git commit -m "feat: prep state and models for file-locked parallel stories"
```

---

### Task 3: Parallel Execution Router (Send API)

**Files:**
- Modify: `agent/graph.py`

- [ ] **Step 1: Import Send API**

```python
from langgraph.types import Send
```

- [ ] **Step 2: Refactor `story_selector_node` to act as a lock manager**

Update `agent/graph.py` to yield `Send` objects for independent stories.

```python
def story_selector_node(state: AgentState):
    stories = state.get("prd_stories", [])
    active_ids = state.get("active_story_ids", [])
    
    # Calculate locked files from currently active stories
    locked_files = set()
    for s in stories:
        if s["id"] in active_ids:
            locked_files.update(s.get("target_files", []))
            
    # Find pending stories that don't intersect with locked files
    sends = []
    new_active_ids = list(active_ids)
    
    for story in stories:
        # Assuming you add a 'status' field to track completion, or similar logic
        if story.get("status") == "pending" and story["id"] not in active_ids:
            story_files = set(story.get("target_files", []))
            if not story_files.intersection(locked_files):
                # No conflict! We can run this in parallel
                sends.append(Send("architect_coder", {"active_story_ids": [story["id"]]}))
                new_active_ids.append(story["id"])
                locked_files.update(story_files)
                
                # Enforce concurrency limit (e.g. max 3)
                if len(new_active_ids) >= 3:
                    break
                    
    # Return updated state tracking all running stories, plus the parallel Send routes
    return {"active_story_ids": new_active_ids}, sends
```

- [ ] **Step 3: Commit**

```bash
git add agent/graph.py
git commit -m "feat: implement LangGraph Send API for parallel story routing"
```

---

### Task 4: Testing Infrastructure & Graph Mocks

**Files:**
- Modify: `requirements.txt`
- Create: `tests/__init__.py`
- Create: `tests/test_graph.py`

- [ ] **Step 1: Install test dependencies**

```bash
echo "pytest>=8.0.0" >> requirements.txt
echo "pytest-mock>=3.12.0" >> requirements.txt
```

- [ ] **Step 2: Write graph routing tests**

Create `tests/test_graph.py` to verify the retry logic works without calling subprocesses.

```python
import pytest
from agent.graph import should_retry

def test_should_retry_aborts_after_max_attempts():
    # Arrange
    state = {"compile_retry_count": 3, "compiler_errors": "Failed"}
    
    # Act
    result = should_retry(state)
    
    # Assert
    assert result == "end"

def test_should_retry_loops_on_error():
    # Arrange
    state = {"compile_retry_count": 1, "compiler_errors": "Failed"}
    
    # Act
    result = should_retry(state)
    
    # Assert
    assert result == "architect_coder"
```

- [ ] **Step 3: Run tests to verify**

```bash
pytest tests/test_graph.py -v
```

- [ ] **Step 4: Commit**

```bash
git add requirements.txt tests/
git commit -m "test: add pytest suite for graph state machine logic"
```
