# Graph Execution Dashboard (Phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add real-time visibility into LangGraph pipeline execution through `graph.*` events, a Pipeline panel in the UI, and an execution timeline.

**Architecture:** A thin `GraphEventEmitter` wrapper emits `graph.start`, `graph.node_enter`, `graph.node_exit`, `graph.end`, and `graph.error` events through the existing `EventBus`. The `build_graph()` function accepts an optional `EventBus` instance and wraps each node function to emit enter/exit events automatically. A `PipelineRunner` in `agent/repl/pipeline_runner.py` handles `pipeline.start`/`pipeline.cancel` commands from the WSManager, runs the graph, and manages cancellation. The frontend Pipeline panel subscribes to `graph.*` events and renders a real-time execution timeline with node status indicators.

**Tech Stack:** Python 3.11, LangGraph, FastAPI, Vue 3 (CDN), WebSocket, existing EventBus

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `agent/graph_events.py` | Create | `GraphEventEmitter` class — wraps EventBus to emit typed `graph.*` events |
| `agent/graph.py` | Modify | Accept optional `event_emitter` in `build_graph()`, wrap nodes to emit enter/exit |
| `agent/repl/pipeline_runner.py` | Create | `PipelineRunner` — handles `pipeline.start`/`pipeline.cancel`, runs graph, manages state |
| `agent/repl/server.py` | Modify | Create `PipelineRunner` instance, wire to bus |
| `agent/repl/ws_manager.py` | Modify | Minor — remove direct bus emit for pipeline commands (runner handles them now) |
| `ui/js/pipeline.js` | Create | Vue composable for pipeline state management — subscribes to `graph.*` events |
| `ui/index.html` | Modify | Replace pipeline placeholder with actual dashboard markup, import pipeline.js and pipeline.css |
| `ui/js/app.js` | Modify | Integrate pipeline composable, add pipeline reactive state |
| `ui/css/pipeline.css` | Create | Pipeline dashboard styles — timeline, node cards, status indicators |
| `tests/agent/test_graph_events.py` | Create | Tests for `GraphEventEmitter` |
| `tests/agent/repl/test_pipeline_runner.py` | Create | Tests for `PipelineRunner` |

---

### Task 1: GraphEventEmitter

**Files:**
- Create: `agent/graph_events.py`
- Create: `tests/agent/test_graph_events.py`

- [ ] **Step 1: Write failing tests for GraphEventEmitter**

Create `tests/agent/test_graph_events.py`:

```python
"""Tests for GraphEventEmitter — typed graph.* event emission."""
import time
import pytest
from agent.event_bus import EventBus
from agent.graph_events import GraphEventEmitter


class TestGraphEventEmitterStart:
    """graph.start event emission."""

    def test_start_emits_event(self):
        bus = EventBus()
        emitter = GraphEventEmitter(bus)
        received = []
        bus.on("graph.start", lambda e: received.append(e))

        emitter.start(run_id="run-1", task="Build login")

        assert len(received) == 1
        assert received[0].type == "graph.start"
        assert received[0].payload["run_id"] == "run-1"
        assert received[0].payload["task"] == "Build login"
        assert received[0].correlation_id == "run-1"

    def test_start_includes_timestamp(self):
        bus = EventBus()
        emitter = GraphEventEmitter(bus)
        received = []
        bus.on("graph.start", lambda e: received.append(e))

        before = time.time()
        emitter.start(run_id="run-2", task="Test")
        after = time.time()

        assert before <= received[0].timestamp <= after


class TestGraphEventEmitterNodeEnterExit:
    """graph.node_enter and graph.node_exit events."""

    def test_node_enter_emits_event(self):
        bus = EventBus()
        emitter = GraphEventEmitter(bus)
        received = []
        bus.on("graph.node_enter", lambda e: received.append(e))

        emitter.node_enter(run_id="run-1", node="planner")

        assert len(received) == 1
        assert received[0].payload["node"] == "planner"
        assert received[0].payload["run_id"] == "run-1"
        assert received[0].correlation_id == "run-1"

    def test_node_exit_emits_event(self):
        bus = EventBus()
        emitter = GraphEventEmitter(bus)
        received = []
        bus.on("graph.node_exit", lambda e: received.append(e))

        emitter.node_exit(run_id="run-1", node="planner", duration_ms=1234.5)

        assert len(received) == 1
        assert received[0].payload["node"] == "planner"
        assert received[0].payload["duration_ms"] == 1234.5
        assert received[0].correlation_id == "run-1"

    def test_node_exit_includes_status(self):
        bus = EventBus()
        emitter = GraphEventEmitter(bus)
        received = []
        bus.on("graph.node_exit", lambda e: received.append(e))

        emitter.node_exit(run_id="run-1", node="validator", duration_ms=500, status="completed")

        assert received[0].payload["status"] == "completed"


class TestGraphEventEmitterEnd:
    """graph.end event emission."""

    def test_end_emits_event(self):
        bus = EventBus()
        emitter = GraphEventEmitter(bus)
        received = []
        bus.on("graph.end", lambda e: received.append(e))

        emitter.end(run_id="run-1", total_duration_ms=5000.0)

        assert len(received) == 1
        assert received[0].payload["run_id"] == "run-1"
        assert received[0].payload["total_duration_ms"] == 5000.0
        assert received[0].correlation_id == "run-1"


class TestGraphEventEmitterError:
    """graph.error event emission."""

    def test_error_emits_event(self):
        bus = EventBus()
        emitter = GraphEventEmitter(bus)
        received = []
        bus.on("graph.error", lambda e: received.append(e))

        emitter.error(run_id="run-1", node="architect_coder", error="LLM timeout")

        assert len(received) == 1
        assert received[0].payload["node"] == "architect_coder"
        assert received[0].payload["error"] == "LLM timeout"
        assert received[0].correlation_id == "run-1"

    def test_error_without_node(self):
        bus = EventBus()
        emitter = GraphEventEmitter(bus)
        received = []
        bus.on("graph.error", lambda e: received.append(e))

        emitter.error(run_id="run-1", error="Graph compilation failed")

        assert received[0].payload["node"] is None
        assert received[0].payload["error"] == "Graph compilation failed"


class TestGraphEventEmitterNoBus:
    """GraphEventEmitter with no bus (no-op mode)."""

    def test_no_bus_does_not_raise(self):
        emitter = GraphEventEmitter(bus=None)
        # All methods should be no-ops, no exceptions
        emitter.start(run_id="run-1", task="Test")
        emitter.node_enter(run_id="run-1", node="planner")
        emitter.node_exit(run_id="run-1", node="planner", duration_ms=100)
        emitter.end(run_id="run-1", total_duration_ms=500)
        emitter.error(run_id="run-1", error="fail")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/agent/test_graph_events.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent.graph_events'`

- [ ] **Step 3: Implement GraphEventEmitter**

Create `agent/graph_events.py`:

```python
"""Typed event emitter for graph.* pipeline events.

Wraps EventBus to provide a clean API for emitting graph lifecycle events.
Accepts bus=None for no-op mode (when running without the REPL server).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from agent.event_bus import EventBus


class GraphEventEmitter:
    """Emits graph.* events through an EventBus instance.

    All methods are safe to call even when bus is None (no-op mode).
    This allows graph code to always use the emitter without checking
    whether the REPL server is running.
    """

    def __init__(self, bus: Optional["EventBus"] = None) -> None:
        self._bus = bus

    def start(self, *, run_id: str, task: str) -> None:
        """Emit graph.start — pipeline execution begins."""
        if self._bus is None:
            return
        self._bus.emit(
            "graph.start",
            {"run_id": run_id, "task": task},
            correlation_id=run_id,
        )

    def node_enter(self, *, run_id: str, node: str) -> None:
        """Emit graph.node_enter — entering a graph node."""
        if self._bus is None:
            return
        self._bus.emit(
            "graph.node_enter",
            {"run_id": run_id, "node": node},
            correlation_id=run_id,
        )

    def node_exit(
        self,
        *,
        run_id: str,
        node: str,
        duration_ms: float,
        status: str = "completed",
    ) -> None:
        """Emit graph.node_exit — leaving a graph node."""
        if self._bus is None:
            return
        self._bus.emit(
            "graph.node_exit",
            {
                "run_id": run_id,
                "node": node,
                "duration_ms": duration_ms,
                "status": status,
            },
            correlation_id=run_id,
        )

    def end(self, *, run_id: str, total_duration_ms: float) -> None:
        """Emit graph.end — pipeline execution complete."""
        if self._bus is None:
            return
        self._bus.emit(
            "graph.end",
            {"run_id": run_id, "total_duration_ms": total_duration_ms},
            correlation_id=run_id,
        )

    def error(
        self, *, run_id: str, error: str, node: Optional[str] = None
    ) -> None:
        """Emit graph.error — pipeline error."""
        if self._bus is None:
            return
        self._bus.emit(
            "graph.error",
            {"run_id": run_id, "node": node, "error": error},
            correlation_id=run_id,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/agent/test_graph_events.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add agent/graph_events.py tests/agent/test_graph_events.py
git commit -m "feat: add GraphEventEmitter for typed graph.* events"
```

---

### Task 2: Instrument graph nodes with event emission

**Files:**
- Modify: `agent/graph.py` (lines 980, 984-1089, 1167)
- Create: `tests/agent/test_graph_instrumentation.py`

- [ ] **Step 1: Write failing tests for node wrapping**

Create `tests/agent/test_graph_instrumentation.py`:

```python
"""Tests for graph node instrumentation with event emission."""
import pytest
from unittest.mock import MagicMock, patch
from agent.event_bus import EventBus
from agent.graph_events import GraphEventEmitter


class TestWrapNodeWithEvents:
    """Test the _wrap_node_with_events helper."""

    def test_sync_node_emits_enter_and_exit(self):
        from agent.graph import _wrap_node_with_events

        bus = EventBus()
        emitter = GraphEventEmitter(bus)
        events = []
        bus.on("graph.*", lambda e: events.append(e))

        def fake_node(state):
            return {"history": ["did something"]}

        wrapped = _wrap_node_with_events(fake_node, "planner", emitter, "run-1")
        result = wrapped({"history": []})

        assert result == {"history": ["did something"]}
        assert len(events) == 2
        assert events[0].type == "graph.node_enter"
        assert events[0].payload["node"] == "planner"
        assert events[1].type == "graph.node_exit"
        assert events[1].payload["node"] == "planner"
        assert events[1].payload["status"] == "completed"
        assert events[1].payload["duration_ms"] >= 0

    def test_async_node_emits_enter_and_exit(self):
        import asyncio
        from agent.graph import _wrap_node_with_events

        bus = EventBus()
        emitter = GraphEventEmitter(bus)
        events = []
        bus.on("graph.*", lambda e: events.append(e))

        async def fake_async_node(state):
            return {"history": ["async result"]}

        wrapped = _wrap_node_with_events(fake_async_node, "context_aggregator", emitter, "run-2")
        result = asyncio.run(wrapped({"history": []}))

        assert result == {"history": ["async result"]}
        assert len(events) == 2
        assert events[0].type == "graph.node_enter"
        assert events[1].type == "graph.node_exit"

    def test_node_error_emits_error_event(self):
        from agent.graph import _wrap_node_with_events

        bus = EventBus()
        emitter = GraphEventEmitter(bus)
        events = []
        bus.on("graph.*", lambda e: events.append(e))

        def failing_node(state):
            raise ValueError("something broke")

        wrapped = _wrap_node_with_events(failing_node, "validator", emitter, "run-3")

        with pytest.raises(ValueError, match="something broke"):
            wrapped({"history": []})

        assert len(events) == 2
        assert events[0].type == "graph.node_enter"
        assert events[1].type == "graph.node_exit"
        assert events[1].payload["status"] == "error"

    def test_no_emitter_passthrough(self):
        from agent.graph import _wrap_node_with_events

        def fake_node(state):
            return {"history": ["ok"]}

        wrapped = _wrap_node_with_events(fake_node, "planner", None, "run-4")
        result = wrapped({"history": []})
        assert result == {"history": ["ok"]}


class TestBuildGraphWithEmitter:
    """Test that build_graph accepts event_emitter parameter."""

    @patch("agent.graph.create_llm")
    @patch("agent.graph.create_tools")
    def test_build_graph_accepts_emitter(self, mock_tools, mock_llm):
        mock_tools.return_value = []
        mock_llm.return_value = MagicMock()

        from agent.graph import build_graph

        bus = EventBus()
        emitter = GraphEventEmitter(bus)
        # Should not raise
        graph = build_graph(checkpointer=None, event_emitter=emitter)
        assert graph is not None

    def test_build_graph_works_without_emitter(self):
        """Backward compatibility — no emitter means no instrumentation."""
        from agent.graph import build_graph

        # Should not raise (existing behavior)
        graph = build_graph(checkpointer=None)
        assert graph is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/agent/test_graph_instrumentation.py -v`
Expected: FAIL — `ImportError: cannot import name '_wrap_node_with_events'`

- [ ] **Step 3: Add `_wrap_node_with_events` helper to `agent/graph.py`**

Add this function near the top of `agent/graph.py`, after the existing imports (around line 30):

```python
import asyncio
import time
import functools
from typing import Optional
from agent.graph_events import GraphEventEmitter


def _wrap_node_with_events(
    node_fn,
    node_name: str,
    emitter: Optional[GraphEventEmitter],
    run_id: str,
):
    """Wrap a graph node function to emit enter/exit events.

    Works with both sync and async node functions.
    If emitter is None, returns the original function unchanged.
    """
    if emitter is None:
        return node_fn

    if asyncio.iscoroutinefunction(node_fn):
        @functools.wraps(node_fn)
        async def async_wrapper(state):
            emitter.node_enter(run_id=run_id, node=node_name)
            t0 = time.monotonic()
            try:
                result = await node_fn(state)
                duration_ms = (time.monotonic() - t0) * 1000
                emitter.node_exit(
                    run_id=run_id, node=node_name,
                    duration_ms=duration_ms, status="completed",
                )
                return result
            except Exception:
                duration_ms = (time.monotonic() - t0) * 1000
                emitter.node_exit(
                    run_id=run_id, node=node_name,
                    duration_ms=duration_ms, status="error",
                )
                raise
        return async_wrapper
    else:
        @functools.wraps(node_fn)
        def sync_wrapper(state):
            emitter.node_enter(run_id=run_id, node=node_name)
            t0 = time.monotonic()
            try:
                result = node_fn(state)
                duration_ms = (time.monotonic() - t0) * 1000
                emitter.node_exit(
                    run_id=run_id, node=node_name,
                    duration_ms=duration_ms, status="completed",
                )
                return result
            except Exception:
                duration_ms = (time.monotonic() - t0) * 1000
                emitter.node_exit(
                    run_id=run_id, node=node_name,
                    duration_ms=duration_ms, status="error",
                )
                raise
        return sync_wrapper
```

- [ ] **Step 4: Modify `build_graph()` to accept `event_emitter` and wrap nodes**

In `agent/graph.py`, change the `build_graph` signature (line ~980) from:

```python
def build_graph(checkpointer=None):
```

to:

```python
def build_graph(checkpointer=None, event_emitter: Optional[GraphEventEmitter] = None, run_id: str = ""):
```

Then, after each `graph.add_node(name, fn)` call, the node function should be wrapped. The simplest approach: create a helper that adds the node with wrapping. Insert this inside `build_graph()`, before the `graph.add_node` calls:

```python
    def add_instrumented_node(name, fn):
        """Add a node to the graph, wrapping it with event emission if emitter is present."""
        wrapped = _wrap_node_with_events(fn, name, event_emitter, run_id)
        graph.add_node(name, wrapped)
```

Then replace all `graph.add_node("name", fn)` calls with `add_instrumented_node("name", fn)`. For example:

```python
    # Before:
    graph.add_node("vetting", vetting_node)
    # After:
    add_instrumented_node("vetting", vetting_node)
```

Apply this to all 18 node registrations (lines 984-999 and line 1088-1089). The `push_node` defined inline at line 1002 should also use `add_instrumented_node`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/agent/test_graph_instrumentation.py -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Run full test suite to verify no regressions**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All 68 existing tests + 5 new tests PASS (73 total)

- [ ] **Step 7: Commit**

```bash
git add agent/graph.py tests/agent/test_graph_instrumentation.py
git commit -m "feat: instrument graph nodes with event emission via _wrap_node_with_events"
```

---

### Task 3: PipelineRunner — handles pipeline.start/cancel commands

**Files:**
- Create: `agent/repl/pipeline_runner.py`
- Create: `tests/agent/repl/test_pipeline_runner.py`

- [ ] **Step 1: Write failing tests for PipelineRunner**

Create `tests/agent/repl/test_pipeline_runner.py`:

```python
"""Tests for PipelineRunner — handles pipeline.start/cancel commands."""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from agent.event_bus import EventBus
from agent.repl.pipeline_runner import PipelineRunner


class TestPipelineRunnerInit:
    """PipelineRunner initialization."""

    def test_init_subscribes_to_pipeline_commands(self):
        bus = EventBus()
        runner = PipelineRunner(bus)
        assert runner._bus is bus
        assert runner._running is False
        assert runner._current_run_id is None

    def test_start_subscribes_to_bus(self):
        bus = EventBus()
        runner = PipelineRunner(bus)
        runner.start()
        # Verify subscriptions exist by emitting events
        # (they won't crash even if handler is no-op)
        bus.emit("pipeline.start", {"text": "test"})
        bus.emit("pipeline.cancel", {})


class TestPipelineRunnerStart:
    """pipeline.start command handling."""

    def test_start_emits_graph_start(self):
        bus = EventBus()
        runner = PipelineRunner(bus)
        runner.start()
        received = []
        bus.on("graph.start", lambda e: received.append(e))

        bus.emit("pipeline.start", {"text": "Build a login screen"})

        assert len(received) == 1
        assert received[0].payload["task"] == "Build a login screen"
        assert received[0].payload["run_id"] is not None

    def test_start_sets_running_state(self):
        bus = EventBus()
        runner = PipelineRunner(bus)
        runner.start()

        bus.emit("pipeline.start", {"text": "Test task"})

        assert runner._running is True
        assert runner._current_run_id is not None

    def test_start_while_running_emits_error(self):
        bus = EventBus()
        runner = PipelineRunner(bus)
        runner.start()
        errors = []
        bus.on("pipeline.error", lambda e: errors.append(e))

        bus.emit("pipeline.start", {"text": "First"})
        bus.emit("pipeline.start", {"text": "Second"})

        assert len(errors) == 1
        assert "already running" in errors[0].payload["error"].lower()


class TestPipelineRunnerCancel:
    """pipeline.cancel command handling."""

    def test_cancel_when_running(self):
        bus = EventBus()
        runner = PipelineRunner(bus)
        runner.start()
        cancelled = []
        bus.on("graph.end", lambda e: cancelled.append(e))

        bus.emit("pipeline.start", {"text": "Task"})
        bus.emit("pipeline.cancel", {})

        assert runner._running is False
        assert len(cancelled) == 1
        assert cancelled[0].payload.get("cancelled") is True

    def test_cancel_when_not_running(self):
        bus = EventBus()
        runner = PipelineRunner(bus)
        runner.start()
        errors = []
        bus.on("pipeline.error", lambda e: errors.append(e))

        bus.emit("pipeline.cancel", {})

        assert len(errors) == 1
        assert "not running" in errors[0].payload["error"].lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/agent/repl/test_pipeline_runner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent.repl.pipeline_runner'`

- [ ] **Step 3: Implement PipelineRunner**

Create `agent/repl/pipeline_runner.py`:

```python
"""PipelineRunner — handles pipeline.start/cancel commands.

Bridges the WebSocket command protocol with graph execution.
Subscribes to pipeline.* events on the EventBus and manages
graph execution lifecycle.
"""
from __future__ import annotations

import uuid
import time
from typing import TYPE_CHECKING, Optional

from agent.graph_events import GraphEventEmitter

if TYPE_CHECKING:
    from agent.event_bus import EventBus, Event


class PipelineRunner:
    """Manages pipeline execution lifecycle.

    Subscribes to:
      - pipeline.start — begins a new graph run
      - pipeline.cancel — cancels the current run

    Emits graph.* events through GraphEventEmitter.
    Actual graph execution is delegated to _execute_graph() which
    can be overridden or will be wired to build_graph() in production.
    """

    def __init__(self, bus: "EventBus") -> None:
        self._bus = bus
        self._emitter = GraphEventEmitter(bus)
        self._running: bool = False
        self._current_run_id: Optional[str] = None
        self._start_time: Optional[float] = None
        self._sub_ids: list[str] = []

    def start(self) -> None:
        """Subscribe to pipeline commands on the bus."""
        self._sub_ids.append(
            self._bus.on("pipeline.start", self._on_pipeline_start)
        )
        self._sub_ids.append(
            self._bus.on("pipeline.cancel", self._on_pipeline_cancel)
        )

    def stop(self) -> None:
        """Unsubscribe from pipeline commands."""
        for sub_id in self._sub_ids:
            self._bus.off(sub_id)
        self._sub_ids.clear()

    def _on_pipeline_start(self, event: "Event") -> None:
        """Handle pipeline.start command."""
        if self._running:
            self._bus.emit(
                "pipeline.error",
                {"error": "Pipeline already running", "run_id": self._current_run_id},
            )
            return

        run_id = str(uuid.uuid4())
        task = event.payload.get("text", "")

        self._running = True
        self._current_run_id = run_id
        self._start_time = time.monotonic()

        self._emitter.start(run_id=run_id, task=task)

    def _on_pipeline_cancel(self, event: "Event") -> None:
        """Handle pipeline.cancel command."""
        if not self._running:
            self._bus.emit(
                "pipeline.error",
                {"error": "Pipeline not running"},
            )
            return

        run_id = self._current_run_id
        duration_ms = (time.monotonic() - self._start_time) * 1000 if self._start_time else 0

        self._running = False
        self._current_run_id = None
        self._start_time = None

        self._emitter.end(run_id=run_id, total_duration_ms=duration_ms)
        # Also emit with cancelled flag so UI can distinguish
        self._bus.emit(
            "graph.end",
            {"run_id": run_id, "total_duration_ms": duration_ms, "cancelled": True},
            correlation_id=run_id,
        )
```

Wait — the `end` method already emits `graph.end`, and then we emit another one. Let me fix that. The `_on_pipeline_cancel` should emit a single `graph.end` with the `cancelled` flag. We should use `_bus.emit` directly instead of `_emitter.end()`:

```python
    def _on_pipeline_cancel(self, event: "Event") -> None:
        """Handle pipeline.cancel command."""
        if not self._running:
            self._bus.emit(
                "pipeline.error",
                {"error": "Pipeline not running"},
            )
            return

        run_id = self._current_run_id
        duration_ms = (time.monotonic() - self._start_time) * 1000 if self._start_time else 0

        self._running = False
        self._current_run_id = None
        self._start_time = None

        self._bus.emit(
            "graph.end",
            {"run_id": run_id, "total_duration_ms": duration_ms, "cancelled": True},
            correlation_id=run_id,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/agent/repl/test_pipeline_runner.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add agent/repl/pipeline_runner.py tests/agent/repl/test_pipeline_runner.py
git commit -m "feat: add PipelineRunner for pipeline.start/cancel command handling"
```

---

### Task 4: Wire PipelineRunner into server.py

**Files:**
- Modify: `agent/repl/server.py` (lines 21-23)

- [ ] **Step 1: Update server.py to create and start PipelineRunner**

In `agent/repl/server.py`, add the import and create the runner after the bus and ws_manager:

```python
from agent.event_bus import EventBus
from agent.repl.ws_manager import WSManager
from agent.repl.pipeline_runner import PipelineRunner

bus = EventBus()
ws_manager = WSManager(bus)
ws_manager.start()
pipeline_runner = PipelineRunner(bus)
pipeline_runner.start()
```

- [ ] **Step 2: Run full test suite**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All tests PASS (no regressions — PipelineRunner subscribes to pipeline.* which doesn't conflict with existing WSManager routing)

- [ ] **Step 3: Commit**

```bash
git add agent/repl/server.py
git commit -m "feat: wire PipelineRunner into REPL server"
```

---

### Task 5: Pipeline CSS styles

**Files:**
- Create: `ui/css/pipeline.css`

- [ ] **Step 1: Create pipeline.css**

Create `ui/css/pipeline.css`:

```css
/* ============================================================
   Pipeline Dashboard — Graph Execution Timeline
   ============================================================ */

/* --- Dashboard Layout --- */
.pipeline-dashboard {
    display: flex;
    flex-direction: column;
    height: 100%;
    padding: var(--space-4, 16px);
    gap: var(--space-4, 16px);
    overflow-y: auto;
}

.pipeline-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: var(--space-3, 12px);
    border-bottom: 1px solid var(--border-subtle, rgba(148, 163, 184, 0.1));
}

.pipeline-header h2 {
    font-family: var(--font-mono, 'JetBrains Mono', monospace);
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary, #E2E8F0);
    margin: 0;
}

.pipeline-status-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: var(--radius-full, 9999px);
    font-family: var(--font-mono, 'JetBrains Mono', monospace);
    font-size: 11px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.pipeline-status-badge.idle {
    background: rgba(148, 163, 184, 0.1);
    color: var(--text-secondary, #94A3B8);
}

.pipeline-status-badge.running {
    background: rgba(59, 130, 246, 0.15);
    color: var(--accent-blue, #3B82F6);
}

.pipeline-status-badge.completed {
    background: rgba(34, 197, 94, 0.15);
    color: var(--accent-green, #22C55E);
}

.pipeline-status-badge.error {
    background: rgba(239, 68, 68, 0.15);
    color: var(--accent-red, #EF4444);
}

.pipeline-status-badge.cancelled {
    background: rgba(234, 179, 8, 0.15);
    color: var(--accent-yellow, #EAB308);
}

/* Status dot animation */
.status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
}

.pipeline-status-badge.running .status-dot {
    animation: pulse-dot 1.5s ease-in-out infinite;
}

@keyframes pulse-dot {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
}

/* --- Run Info Bar --- */
.pipeline-run-info {
    display: flex;
    align-items: center;
    gap: var(--space-4, 16px);
    padding: var(--space-3, 12px);
    background: var(--bg-secondary, rgba(15, 23, 42, 0.6));
    border-radius: var(--radius-md, 8px);
    border: 1px solid var(--border-subtle, rgba(148, 163, 184, 0.1));
    font-family: var(--font-mono, 'JetBrains Mono', monospace);
    font-size: 12px;
    color: var(--text-secondary, #94A3B8);
}

.pipeline-run-info .run-task {
    flex: 1;
    color: var(--text-primary, #E2E8F0);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.pipeline-run-info .run-duration {
    font-variant-numeric: tabular-nums;
}

/* --- Timeline --- */
.pipeline-timeline {
    display: flex;
    flex-direction: column;
    gap: 2px;
    flex: 1;
}

.pipeline-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    flex: 1;
    gap: var(--space-3, 12px);
    color: var(--text-muted, #475569);
    font-family: var(--font-sans, 'IBM Plex Sans', sans-serif);
}

.pipeline-empty svg {
    opacity: 0.3;
}

.pipeline-empty p {
    font-size: 13px;
    margin: 0;
}

/* --- Node Card --- */
.node-card {
    display: flex;
    align-items: center;
    gap: var(--space-3, 12px);
    padding: 10px var(--space-3, 12px);
    background: var(--bg-secondary, rgba(15, 23, 42, 0.6));
    border-radius: var(--radius-sm, 6px);
    border: 1px solid var(--border-subtle, rgba(148, 163, 184, 0.1));
    transition: border-color var(--transition-fast, 150ms ease),
                background var(--transition-fast, 150ms ease);
}

.node-card.pending {
    opacity: 0.5;
}

.node-card.running {
    border-color: var(--accent-blue, #3B82F6);
    background: rgba(59, 130, 246, 0.05);
}

.node-card.completed {
    border-color: var(--accent-green, #22C55E);
}

.node-card.error {
    border-color: var(--accent-red, #EF4444);
    background: rgba(239, 68, 68, 0.05);
}

/* Node status icon */
.node-status-icon {
    width: 20px;
    height: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}

.node-status-icon .spinner {
    width: 14px;
    height: 14px;
    border: 2px solid rgba(59, 130, 246, 0.2);
    border-top-color: var(--accent-blue, #3B82F6);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

.node-status-icon .check {
    color: var(--accent-green, #22C55E);
    font-size: 14px;
}

.node-status-icon .error-x {
    color: var(--accent-red, #EF4444);
    font-size: 14px;
}

.node-status-icon .pending-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--text-muted, #475569);
}

/* Node info */
.node-info {
    flex: 1;
    min-width: 0;
}

.node-name {
    font-family: var(--font-mono, 'JetBrains Mono', monospace);
    font-size: 13px;
    font-weight: 500;
    color: var(--text-primary, #E2E8F0);
}

.node-meta {
    font-family: var(--font-mono, 'JetBrains Mono', monospace);
    font-size: 11px;
    color: var(--text-muted, #475569);
    margin-top: 2px;
}

/* Node duration bar */
.node-duration {
    font-family: var(--font-mono, 'JetBrains Mono', monospace);
    font-size: 11px;
    color: var(--text-secondary, #94A3B8);
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
}

/* --- Duration Bar (visual timeline) --- */
.node-duration-bar {
    height: 3px;
    border-radius: 2px;
    background: var(--accent-green, #22C55E);
    opacity: 0.4;
    margin-top: 4px;
    transition: width 0.3s ease;
}

.node-card.running .node-duration-bar {
    background: var(--accent-blue, #3B82F6);
    animation: progress-pulse 1.5s ease-in-out infinite;
}

.node-card.error .node-duration-bar {
    background: var(--accent-red, #EF4444);
}

@keyframes progress-pulse {
    0%, 100% { opacity: 0.4; }
    50% { opacity: 0.8; }
}

/* --- Controls --- */
.pipeline-controls {
    display: flex;
    gap: var(--space-2, 8px);
    padding-top: var(--space-3, 12px);
    border-top: 1px solid var(--border-subtle, rgba(148, 163, 184, 0.1));
}

.pipeline-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    border: 1px solid var(--border-subtle, rgba(148, 163, 184, 0.1));
    border-radius: var(--radius-sm, 6px);
    background: var(--bg-secondary, rgba(15, 23, 42, 0.6));
    color: var(--text-primary, #E2E8F0);
    font-family: var(--font-mono, 'JetBrains Mono', monospace);
    font-size: 12px;
    cursor: pointer;
    transition: all var(--transition-fast, 150ms ease);
}

.pipeline-btn:hover {
    background: rgba(59, 130, 246, 0.1);
    border-color: var(--accent-blue, #3B82F6);
}

.pipeline-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
}

.pipeline-btn.cancel {
    border-color: rgba(239, 68, 68, 0.3);
    color: var(--accent-red, #EF4444);
}

.pipeline-btn.cancel:hover {
    background: rgba(239, 68, 68, 0.1);
}

/* --- Summary Stats --- */
.pipeline-summary {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: var(--space-2, 8px);
}

.summary-stat {
    padding: var(--space-3, 12px);
    background: var(--bg-secondary, rgba(15, 23, 42, 0.6));
    border-radius: var(--radius-sm, 6px);
    border: 1px solid var(--border-subtle, rgba(148, 163, 184, 0.1));
    text-align: center;
}

.summary-stat .stat-value {
    font-family: var(--font-mono, 'JetBrains Mono', monospace);
    font-size: 20px;
    font-weight: 600;
    color: var(--text-primary, #E2E8F0);
}

.summary-stat .stat-label {
    font-family: var(--font-sans, 'IBM Plex Sans', sans-serif);
    font-size: 11px;
    color: var(--text-muted, #475569);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 4px;
}
```

- [ ] **Step 2: Add CSS import to index.html**

In `ui/index.html`, add after the existing CSS imports (after the `chat.css` link):

```html
<link rel="stylesheet" href="css/pipeline.css">
```

- [ ] **Step 3: Commit**

```bash
git add ui/css/pipeline.css ui/index.html
git commit -m "feat: add pipeline dashboard CSS styles"
```

---

### Task 6: Pipeline Vue composable (ui/js/pipeline.js)

**Files:**
- Create: `ui/js/pipeline.js`

- [ ] **Step 1: Create pipeline.js composable**

Create `ui/js/pipeline.js`:

```javascript
/**
 * Pipeline Dashboard composable — manages pipeline execution state.
 *
 * Subscribes to graph.* events from the WebSocket EventBus and maintains
 * reactive state for the Pipeline panel UI.
 *
 * Usage in Vue app:
 *   const pipeline = usePipeline(bus)
 *   // pipeline.status — 'idle' | 'running' | 'completed' | 'error' | 'cancelled'
 *   // pipeline.nodes — [{name, status, duration_ms, entered_at}]
 *   // pipeline.runId — current run ID
 *   // pipeline.task — current task description
 *   // pipeline.totalDuration — total run duration in ms
 *   // pipeline.startPipeline(text) — send pipeline.start command
 *   // pipeline.cancelPipeline() — send pipeline.cancel command
 */

const { ref, reactive, computed } = Vue;

/**
 * @param {EventBus} bus - Client-side EventBus instance
 * @param {function} sendCommand - Function to send WS commands: (command, payload) => void
 * @returns {object} Reactive pipeline state and actions
 */
function usePipeline(bus, sendCommand) {
    // --- Reactive State ---
    const status = ref('idle');       // 'idle' | 'running' | 'completed' | 'error' | 'cancelled'
    const runId = ref(null);
    const task = ref('');
    const nodes = ref([]);            // [{name, status, duration_ms, entered_at}]
    const totalDuration = ref(0);
    const error = ref(null);
    const history = ref([]);          // Past runs: [{runId, task, status, totalDuration, nodes, timestamp}]

    // --- Computed ---
    const completedCount = computed(() =>
        nodes.value.filter(n => n.status === 'completed').length
    );
    const totalNodes = computed(() => nodes.value.length);
    const currentNode = computed(() =>
        nodes.value.find(n => n.status === 'running') || null
    );

    // --- Known graph nodes in execution order ---
    const GRAPH_NODES = [
        'vetting', 'await_clarification', 'initialize',
        'context_aggregator', 'planner', 'blueprint_presentation',
        'blueprint_approval_gate', 'prd_decomposer', 'story_selector',
        'story_commit', 'story_progress', 'story_skip',
        'architect_coder', 'validator', 'ui_vision_check',
        'maestro_navigation_generator', 'vision_validation', 'push'
    ];

    // --- Event Handlers ---

    function onGraphStart(event) {
        const p = event.payload || event;
        status.value = 'running';
        runId.value = p.run_id;
        task.value = p.task || '';
        error.value = null;
        totalDuration.value = 0;

        // Initialize all known nodes as pending
        nodes.value = GRAPH_NODES.map(name => ({
            name,
            status: 'pending',
            duration_ms: 0,
            entered_at: null,
        }));
    }

    function onNodeEnter(event) {
        const p = event.payload || event;
        const node = nodes.value.find(n => n.name === p.node);
        if (node) {
            node.status = 'running';
            node.entered_at = Date.now();
        } else {
            // Unknown node — add dynamically
            nodes.value.push({
                name: p.node,
                status: 'running',
                duration_ms: 0,
                entered_at: Date.now(),
            });
        }
    }

    function onNodeExit(event) {
        const p = event.payload || event;
        const node = nodes.value.find(n => n.name === p.node);
        if (node) {
            node.status = p.status || 'completed';
            node.duration_ms = p.duration_ms || 0;
        }
    }

    function onGraphEnd(event) {
        const p = event.payload || event;
        if (p.cancelled) {
            status.value = 'cancelled';
        } else {
            status.value = 'completed';
        }
        totalDuration.value = p.total_duration_ms || 0;

        // Save to history
        history.value.unshift({
            runId: runId.value,
            task: task.value,
            status: status.value,
            totalDuration: totalDuration.value,
            nodeCount: completedCount.value,
            timestamp: Date.now(),
        });

        // Keep last 10 runs
        if (history.value.length > 10) {
            history.value = history.value.slice(0, 10);
        }
    }

    function onGraphError(event) {
        const p = event.payload || event;
        status.value = 'error';
        error.value = p.error;

        // Mark the errored node if specified
        if (p.node) {
            const node = nodes.value.find(n => n.name === p.node);
            if (node) {
                node.status = 'error';
            }
        }
    }

    // --- Subscribe to events ---
    bus.on('graph.start', onGraphStart);
    bus.on('graph.node_enter', onNodeEnter);
    bus.on('graph.node_exit', onNodeExit);
    bus.on('graph.end', onGraphEnd);
    bus.on('graph.error', onGraphError);

    // --- Actions ---

    function startPipeline(text) {
        if (status.value === 'running') return;
        sendCommand('pipeline.start', { text });
    }

    function cancelPipeline() {
        if (status.value !== 'running') return;
        sendCommand('pipeline.cancel', {});
    }

    function reset() {
        status.value = 'idle';
        runId.value = null;
        task.value = '';
        nodes.value = [];
        totalDuration.value = 0;
        error.value = null;
    }

    return {
        // State
        status,
        runId,
        task,
        nodes,
        totalDuration,
        error,
        history,
        // Computed
        completedCount,
        totalNodes,
        currentNode,
        // Actions
        startPipeline,
        cancelPipeline,
        reset,
    };
}

// Export for use in app.js
window.usePipeline = usePipeline;
```

- [ ] **Step 2: Add script import to index.html**

In `ui/index.html`, add after the `event-bus.js` script tag and before `app.js`:

```html
<script src="js/pipeline.js"></script>
```

- [ ] **Step 3: Commit**

```bash
git add ui/js/pipeline.js ui/index.html
git commit -m "feat: add pipeline Vue composable for graph.* event state management"
```

---

### Task 7: Pipeline panel HTML in index.html

**Files:**
- Modify: `ui/index.html` (lines 327-335 — replace pipeline placeholder)

- [ ] **Step 1: Replace pipeline placeholder with dashboard markup**

In `ui/index.html`, replace the pipeline placeholder block (the `<div class="terminal-body" v-show="activePanel === 'pipeline'" ...>` and its contents) with:

```html
                <!-- ===== Pipeline Dashboard ===== -->
                <div class="terminal-body" v-show="activePanel === 'pipeline'">
                    <div class="pipeline-dashboard">
                        <!-- Header -->
                        <div class="pipeline-header">
                            <h2>Pipeline Execution</h2>
                            <span :class="['pipeline-status-badge', pipeline.status.value]">
                                <span class="status-dot"></span>
                                {{ pipeline.status.value }}
                            </span>
                        </div>

                        <!-- Run Info (visible when running or completed) -->
                        <div class="pipeline-run-info" v-if="pipeline.status.value !== 'idle'">
                            <span class="run-task" :title="pipeline.task.value">
                                {{ pipeline.task.value || 'Untitled run' }}
                            </span>
                            <span class="run-duration">
                                {{ formatDuration(pipeline.totalDuration.value) }}
                            </span>
                        </div>

                        <!-- Summary Stats (visible when running or completed) -->
                        <div class="pipeline-summary" v-if="pipeline.status.value !== 'idle'">
                            <div class="summary-stat">
                                <div class="stat-value">{{ pipeline.completedCount.value }}</div>
                                <div class="stat-label">Completed</div>
                            </div>
                            <div class="summary-stat">
                                <div class="stat-value">{{ pipeline.totalNodes.value }}</div>
                                <div class="stat-label">Total Nodes</div>
                            </div>
                            <div class="summary-stat">
                                <div class="stat-value">{{ formatDuration(pipeline.totalDuration.value) }}</div>
                                <div class="stat-label">Duration</div>
                            </div>
                        </div>

                        <!-- Empty State -->
                        <div class="pipeline-empty" v-if="pipeline.status.value === 'idle' && pipeline.nodes.value.length === 0">
                            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                                <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
                            </svg>
                            <p>No pipeline running. Start one from the chat or use the button below.</p>
                        </div>

                        <!-- Node Timeline -->
                        <div class="pipeline-timeline" v-if="pipeline.nodes.value.length > 0">
                            <div
                                v-for="node in pipeline.nodes.value"
                                :key="node.name"
                                :class="['node-card', node.status]"
                            >
                                <div class="node-status-icon">
                                    <div v-if="node.status === 'running'" class="spinner"></div>
                                    <span v-else-if="node.status === 'completed'" class="check">&#10003;</span>
                                    <span v-else-if="node.status === 'error'" class="error-x">&#10007;</span>
                                    <div v-else class="pending-dot"></div>
                                </div>
                                <div class="node-info">
                                    <div class="node-name">{{ node.name }}</div>
                                    <div class="node-meta" v-if="node.status === 'completed' || node.status === 'error'">
                                        {{ formatDuration(node.duration_ms) }}
                                    </div>
                                    <div class="node-meta" v-else-if="node.status === 'running'">
                                        Running...
                                    </div>
                                    <div class="node-duration-bar"
                                         v-if="node.status !== 'pending'"
                                         :style="{ width: getNodeBarWidth(node) }">
                                    </div>
                                </div>
                                <div class="node-duration" v-if="node.duration_ms > 0">
                                    {{ formatDuration(node.duration_ms) }}
                                </div>
                            </div>
                        </div>

                        <!-- Controls -->
                        <div class="pipeline-controls">
                            <button
                                class="pipeline-btn"
                                @click="pipeline.startPipeline(pipelineInput)"
                                :disabled="pipeline.status.value === 'running'"
                            >
                                &#9654; Start Pipeline
                            </button>
                            <button
                                class="pipeline-btn cancel"
                                @click="pipeline.cancelPipeline()"
                                :disabled="pipeline.status.value !== 'running'"
                            >
                                &#9632; Cancel
                            </button>
                            <button
                                class="pipeline-btn"
                                @click="pipeline.reset()"
                                :disabled="pipeline.status.value === 'running'"
                                v-if="pipeline.status.value !== 'idle'"
                            >
                                &#8634; Reset
                            </button>
                        </div>

                        <!-- Run History -->
                        <div v-if="pipeline.history.value.length > 0" style="margin-top: var(--space-4, 16px);">
                            <h3 style="font-family: var(--font-mono); font-size: 12px; color: var(--text-secondary, #94A3B8); margin: 0 0 8px 0; text-transform: uppercase; letter-spacing: 0.05em;">
                                Recent Runs
                            </h3>
                            <div v-for="run in pipeline.history.value" :key="run.runId"
                                 style="display: flex; align-items: center; gap: 12px; padding: 8px 12px; font-family: var(--font-mono); font-size: 11px; color: var(--text-muted, #475569); border-bottom: 1px solid var(--border-subtle, rgba(148,163,184,0.1));">
                                <span :class="['pipeline-status-badge', run.status]" style="font-size: 10px; padding: 2px 6px;">
                                    {{ run.status }}
                                </span>
                                <span style="flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                                    {{ run.task || 'Untitled' }}
                                </span>
                                <span>{{ run.nodeCount }} nodes</span>
                                <span>{{ formatDuration(run.totalDuration) }}</span>
                            </div>
                        </div>
                    </div>
                </div>
```

- [ ] **Step 2: Commit**

```bash
git add ui/index.html
git commit -m "feat: add pipeline dashboard HTML markup replacing Phase 2 placeholder"
```

---

### Task 8: Integrate pipeline composable into app.js

**Files:**
- Modify: `ui/js/app.js`

- [ ] **Step 1: Add pipeline composable integration to app.js**

In `ui/js/app.js`, inside the `setup()` function, after the existing EventBus subscriptions and before the `return` statement, add:

```javascript
        // --- Pipeline Dashboard ---
        const pipelineInput = ref('');

        // sendCommand helper for pipeline composable
        function sendCommand(command, payload) {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'command', command, payload }));
            }
        }

        const pipeline = usePipeline(bus, sendCommand);

        // Format duration helper
        function formatDuration(ms) {
            if (!ms || ms <= 0) return '0s';
            if (ms < 1000) return Math.round(ms) + 'ms';
            if (ms < 60000) return (ms / 1000).toFixed(1) + 's';
            const mins = Math.floor(ms / 60000);
            const secs = ((ms % 60000) / 1000).toFixed(0);
            return mins + 'm ' + secs + 's';
        }

        // Get node bar width relative to longest node
        function getNodeBarWidth(node) {
            if (node.status === 'running') return '60%';
            const maxDuration = Math.max(...pipeline.nodes.value.map(n => n.duration_ms || 0), 1);
            const pct = Math.max(5, (node.duration_ms / maxDuration) * 100);
            return pct + '%';
        }
```

Then add these to the `return` statement:

```javascript
        return {
            // ... existing returns ...
            pipeline,
            pipelineInput,
            formatDuration,
            getNodeBarWidth,
        };
```

- [ ] **Step 2: Run full test suite to verify no regressions**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add ui/js/app.js
git commit -m "feat: integrate pipeline composable into Vue app"
```

---

### Task 9: End-to-end verification and final test pass

**Files:**
- All modified files

- [ ] **Step 1: Run full test suite**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All tests PASS (68 original + new tests)

- [ ] **Step 2: Verify server starts without errors**

Run: `.venv/bin/python -c "from agent.repl.server import app, bus, ws_manager, pipeline_runner; print('Server imports OK')"` 
Expected: `Server imports OK`

- [ ] **Step 3: Verify graph event emitter imports**

Run: `.venv/bin/python -c "from agent.graph_events import GraphEventEmitter; from agent.event_bus import EventBus; e = GraphEventEmitter(EventBus()); e.start(run_id='test', task='test'); print('GraphEventEmitter OK')"`
Expected: `GraphEventEmitter OK`

- [ ] **Step 4: Verify build_graph accepts emitter**

Run: `.venv/bin/python -c "from agent.graph import build_graph, _wrap_node_with_events; print('Graph imports OK')"`
Expected: `Graph imports OK`

- [ ] **Step 5: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: address any issues found during e2e verification"
```

(Only if changes were needed)
