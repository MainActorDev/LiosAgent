# HITL Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the `gate.*` event protocol so the Web UI can display approval dialogs for LangGraph interrupt nodes and resolve them via WebSocket commands.

**Architecture:** A `GateManager` backend component manages pending gates as asyncio Futures, emitting `gate.request` events and resolving them when `gate.response` arrives on the EventBus. A `GateEventEmitter` typed facade provides the event API. The frontend `useGates` composable tracks pending gates and renders an approval dialog overlay on the pipeline panel. Gate CSS lives in a dedicated `gates.css` file.

**Tech Stack:** Python 3.11+ (asyncio, dataclasses), FastAPI, EventBus (custom), Vue 3 (CDN), ES modules

---

## File Structure

| File | Responsibility |
|------|---------------|
| `agent/gate_events.py` (create) | Typed facade for `gate.request` / `gate.response` events |
| `agent/gate_manager.py` (create) | Manages pending gates — emits requests, resolves on response |
| `agent/repl/server.py` (modify) | Wire `GateManager` into shared bus |
| `ui/js/gates.js` (create) | `useGates(bus, sendCommand)` Vue composable |
| `ui/js/app.js` (modify) | Import and integrate `useGates` |
| `ui/index.html` (modify) | Gate approval dialog markup |
| `ui/css/gates.css` (create) | Gate dialog styles |
| `tests/agent/test_gate_events.py` (create) | Tests for GateEventEmitter |
| `tests/agent/test_gate_manager.py` (create) | Tests for GateManager |

---

### Task 1: GateEventEmitter — Typed Event Facade

**Files:**
- Create: `agent/gate_events.py`
- Create: `tests/agent/test_gate_events.py`

This mirrors the `GraphEventEmitter` pattern exactly — a typed facade that emits `gate.*` events on the bus.

- [ ] **Step 1: Write the failing tests**

Create `tests/agent/test_gate_events.py`:

```python
"""Tests for GateEventEmitter – typed facade for gate.* events."""

import pytest

from agent.event_bus import EventBus
from agent.gate_events import GateEventEmitter


class TestGateEventEmitterRequest:
    """gate.request event emission."""

    def test_emits_gate_request_with_payload(self):
        bus = EventBus()
        emitter = GateEventEmitter(bus=bus)
        received = []
        bus.on("gate.request", lambda e: received.append(e))

        emitter.request(
            gate_id="g-001",
            run_id="run-abc",
            node="blueprint_approval_gate",
            title="Approve Blueprint",
            description="Review the generated blueprint before proceeding.",
        )

        assert len(received) == 1
        evt = received[0]
        assert evt.type == "gate.request"
        assert evt.payload["gate_id"] == "g-001"
        assert evt.payload["run_id"] == "run-abc"
        assert evt.payload["node"] == "blueprint_approval_gate"
        assert evt.payload["title"] == "Approve Blueprint"
        assert evt.payload["description"] == "Review the generated blueprint before proceeding."
        assert evt.correlation_id == "run-abc"

    def test_emits_gate_request_with_optional_context(self):
        bus = EventBus()
        emitter = GateEventEmitter(bus=bus)
        received = []
        bus.on("gate.request", lambda e: received.append(e))

        emitter.request(
            gate_id="g-002",
            run_id="run-xyz",
            node="push",
            title="Approve Push",
            description="Push changes to remote?",
            context={"branch": "feat/login", "files_changed": 5},
        )

        assert received[0].payload["context"] == {"branch": "feat/login", "files_changed": 5}

    def test_emits_gate_request_without_context_defaults_to_empty(self):
        bus = EventBus()
        emitter = GateEventEmitter(bus=bus)
        received = []
        bus.on("gate.request", lambda e: received.append(e))

        emitter.request(
            gate_id="g-003",
            run_id="run-123",
            node="await_clarification",
            title="Clarification Needed",
            description="Waiting for developer input.",
        )

        assert received[0].payload["context"] == {}


class TestGateEventEmitterResponse:
    """gate.response event emission."""

    def test_emits_gate_response_approved(self):
        bus = EventBus()
        emitter = GateEventEmitter(bus=bus)
        received = []
        bus.on("gate.response", lambda e: received.append(e))

        emitter.response(
            gate_id="g-001",
            run_id="run-abc",
            approved=True,
        )

        assert len(received) == 1
        evt = received[0]
        assert evt.type == "gate.response"
        assert evt.payload["gate_id"] == "g-001"
        assert evt.payload["approved"] is True
        assert evt.payload["feedback"] == ""
        assert evt.correlation_id == "run-abc"

    def test_emits_gate_response_rejected_with_feedback(self):
        bus = EventBus()
        emitter = GateEventEmitter(bus=bus)
        received = []
        bus.on("gate.response", lambda e: received.append(e))

        emitter.response(
            gate_id="g-001",
            run_id="run-abc",
            approved=False,
            feedback="Needs more error handling in the auth module.",
        )

        evt = received[0]
        assert evt.payload["approved"] is False
        assert evt.payload["feedback"] == "Needs more error handling in the auth module."


class TestGateEventEmitterNoBus:
    """No-op when bus is None."""

    def test_request_noop_without_bus(self):
        emitter = GateEventEmitter(bus=None)
        # Should not raise
        emitter.request(
            gate_id="g-001",
            run_id="run-abc",
            node="push",
            title="Test",
            description="Test",
        )

    def test_response_noop_without_bus(self):
        emitter = GateEventEmitter(bus=None)
        # Should not raise
        emitter.response(
            gate_id="g-001",
            run_id="run-abc",
            approved=True,
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/agent/test_gate_events.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent.gate_events'`

- [ ] **Step 3: Write the implementation**

Create `agent/gate_events.py`:

```python
"""Typed facade for gate.* events.

Emits gate.request and gate.response events on the EventBus.
Mirrors the GraphEventEmitter pattern — all methods are no-ops when
bus is None, making the emitter safe to use in contexts where no
event bus is available.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from agent.event_bus import EventBus


class GateEventEmitter:
    """Typed facade for gate.* events."""

    def __init__(self, *, bus: Optional["EventBus"] = None) -> None:
        self._bus = bus

    def request(
        self,
        *,
        gate_id: str,
        run_id: str,
        node: str,
        title: str,
        description: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit a gate.request event — agent needs human approval."""
        if self._bus is None:
            return
        self._bus.emit(
            "gate.request",
            {
                "gate_id": gate_id,
                "run_id": run_id,
                "node": node,
                "title": title,
                "description": description,
                "context": context or {},
            },
            correlation_id=run_id,
        )

    def response(
        self,
        *,
        gate_id: str,
        run_id: str,
        approved: bool,
        feedback: str = "",
    ) -> None:
        """Emit a gate.response event — human provides approval/rejection."""
        if self._bus is None:
            return
        self._bus.emit(
            "gate.response",
            {
                "gate_id": gate_id,
                "approved": approved,
                "feedback": feedback,
            },
            correlation_id=run_id,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/agent/test_gate_events.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add agent/gate_events.py tests/agent/test_gate_events.py
git commit -m "feat: add GateEventEmitter typed facade for gate.* events"
```

---

### Task 2: GateManager — Pending Gate Lifecycle

**Files:**
- Create: `agent/gate_manager.py`
- Create: `tests/agent/test_gate_manager.py`

The GateManager is the core backend component. It:
- Listens for `gate.response` events on the bus
- Provides `request_gate()` which emits `gate.request` and returns an `asyncio.Future`
- Resolves the future when a matching `gate.response` arrives
- Tracks pending gates by `gate_id`
- Supports timeout and cancellation

- [ ] **Step 1: Write the failing tests**

Create `tests/agent/test_gate_manager.py`:

```python
"""Tests for GateManager – pending gate lifecycle."""

import asyncio

import pytest

from agent.event_bus import EventBus
from agent.gate_manager import GateManager


class TestGateManagerInit:
    """Initialization and wiring."""

    def test_creates_with_bus(self):
        bus = EventBus()
        manager = GateManager(bus=bus)
        assert manager._bus is bus

    def test_start_subscribes_to_gate_response(self):
        bus = EventBus()
        manager = GateManager(bus=bus)
        manager.start()
        assert len(manager._sub_ids) == 1

    def test_stop_unsubscribes(self):
        bus = EventBus()
        manager = GateManager(bus=bus)
        manager.start()
        manager.stop()
        assert len(manager._sub_ids) == 0

    def test_no_pending_gates_initially(self):
        bus = EventBus()
        manager = GateManager(bus=bus)
        assert manager.pending_gates == {}


class TestGateManagerRequestGate:
    """request_gate() emits gate.request and creates a pending future."""

    def test_emits_gate_request_event(self):
        bus = EventBus()
        manager = GateManager(bus=bus)
        manager.start()
        received = []
        bus.on("gate.request", lambda e: received.append(e))

        loop = asyncio.new_event_loop()
        try:
            future = loop.run_until_complete(
                self._request_gate(manager, loop)
            )
            assert len(received) == 1
            evt = received[0]
            assert evt.type == "gate.request"
            assert evt.payload["gate_id"] == "g-001"
            assert evt.payload["node"] == "blueprint_approval_gate"
            assert evt.payload["title"] == "Approve Blueprint"
        finally:
            loop.close()

    def test_creates_pending_gate(self):
        bus = EventBus()
        manager = GateManager(bus=bus)
        manager.start()

        loop = asyncio.new_event_loop()
        try:
            future = loop.run_until_complete(
                self._request_gate(manager, loop)
            )
            assert "g-001" in manager.pending_gates
            assert not future.done()
        finally:
            loop.close()

    def test_generates_gate_id_when_not_provided(self):
        bus = EventBus()
        manager = GateManager(bus=bus)
        manager.start()
        received = []
        bus.on("gate.request", lambda e: received.append(e))

        loop = asyncio.new_event_loop()
        try:
            future = loop.run_until_complete(
                self._request_gate_no_id(manager, loop)
            )
            gate_id = received[0].payload["gate_id"]
            assert gate_id  # non-empty
            assert gate_id in manager.pending_gates
        finally:
            loop.close()

    @staticmethod
    async def _request_gate(manager, loop):
        return manager.request_gate(
            gate_id="g-001",
            run_id="run-abc",
            node="blueprint_approval_gate",
            title="Approve Blueprint",
            description="Review the blueprint.",
            loop=loop,
        )

    @staticmethod
    async def _request_gate_no_id(manager, loop):
        return manager.request_gate(
            run_id="run-abc",
            node="push",
            title="Approve Push",
            description="Push to remote?",
            loop=loop,
        )


class TestGateManagerResolveGate:
    """gate.response resolves the pending future."""

    def test_approve_resolves_future(self):
        bus = EventBus()
        manager = GateManager(bus=bus)
        manager.start()

        loop = asyncio.new_event_loop()
        try:
            future = manager.request_gate(
                gate_id="g-001",
                run_id="run-abc",
                node="blueprint_approval_gate",
                title="Approve Blueprint",
                description="Review.",
                loop=loop,
            )

            # Simulate gate.response from WSManager
            bus.emit("gate.response", {
                "gate_id": "g-001",
                "approved": True,
                "feedback": "",
            })

            assert future.done()
            result = future.result()
            assert result["approved"] is True
            assert result["feedback"] == ""
            assert "g-001" not in manager.pending_gates
        finally:
            loop.close()

    def test_reject_resolves_future_with_feedback(self):
        bus = EventBus()
        manager = GateManager(bus=bus)
        manager.start()

        loop = asyncio.new_event_loop()
        try:
            future = manager.request_gate(
                gate_id="g-001",
                run_id="run-abc",
                node="blueprint_approval_gate",
                title="Approve Blueprint",
                description="Review.",
                loop=loop,
            )

            bus.emit("gate.response", {
                "gate_id": "g-001",
                "approved": False,
                "feedback": "Needs more detail on auth.",
            })

            assert future.done()
            result = future.result()
            assert result["approved"] is False
            assert result["feedback"] == "Needs more detail on auth."
        finally:
            loop.close()

    def test_ignores_response_for_unknown_gate(self):
        bus = EventBus()
        manager = GateManager(bus=bus)
        manager.start()

        # Should not raise
        bus.emit("gate.response", {
            "gate_id": "nonexistent",
            "approved": True,
            "feedback": "",
        })

    def test_multiple_gates_resolved_independently(self):
        bus = EventBus()
        manager = GateManager(bus=bus)
        manager.start()

        loop = asyncio.new_event_loop()
        try:
            future_1 = manager.request_gate(
                gate_id="g-001",
                run_id="run-abc",
                node="blueprint_approval_gate",
                title="Approve Blueprint",
                description="Review.",
                loop=loop,
            )
            future_2 = manager.request_gate(
                gate_id="g-002",
                run_id="run-abc",
                node="push",
                title="Approve Push",
                description="Push?",
                loop=loop,
            )

            bus.emit("gate.response", {
                "gate_id": "g-002",
                "approved": True,
                "feedback": "",
            })

            assert future_2.done()
            assert not future_1.done()
            assert "g-001" in manager.pending_gates
            assert "g-002" not in manager.pending_gates
        finally:
            loop.close()


class TestGateManagerCancelGate:
    """cancel_gate() cancels a pending future."""

    def test_cancel_gate_cancels_future(self):
        bus = EventBus()
        manager = GateManager(bus=bus)
        manager.start()

        loop = asyncio.new_event_loop()
        try:
            future = manager.request_gate(
                gate_id="g-001",
                run_id="run-abc",
                node="push",
                title="Approve Push",
                description="Push?",
                loop=loop,
            )

            manager.cancel_gate("g-001")

            assert future.cancelled()
            assert "g-001" not in manager.pending_gates
        finally:
            loop.close()

    def test_cancel_nonexistent_gate_is_noop(self):
        bus = EventBus()
        manager = GateManager(bus=bus)
        manager.start()
        # Should not raise
        manager.cancel_gate("nonexistent")

    def test_cancel_all_gates(self):
        bus = EventBus()
        manager = GateManager(bus=bus)
        manager.start()

        loop = asyncio.new_event_loop()
        try:
            f1 = manager.request_gate(
                gate_id="g-001", run_id="run-abc", node="push",
                title="T1", description="D1", loop=loop,
            )
            f2 = manager.request_gate(
                gate_id="g-002", run_id="run-abc", node="push",
                title="T2", description="D2", loop=loop,
            )

            manager.cancel_all_gates()

            assert f1.cancelled()
            assert f2.cancelled()
            assert manager.pending_gates == {}
        finally:
            loop.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/agent/test_gate_manager.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'agent.gate_manager'`

- [ ] **Step 3: Write the implementation**

Create `agent/gate_manager.py`:

```python
"""GateManager – manages pending HITL gates.

Bridges the gate.* event protocol:
1. request_gate() emits gate.request and returns an asyncio.Future
2. When gate.response arrives on the bus, resolves the matching future
3. Supports cancellation of individual or all pending gates

Usage:
    manager = GateManager(bus=bus)
    manager.start()

    # In an async context:
    future = manager.request_gate(
        gate_id="g-001",
        run_id="run-abc",
        node="blueprint_approval_gate",
        title="Approve Blueprint",
        description="Review the blueprint.",
        loop=loop,
    )
    result = await future  # {"approved": True/False, "feedback": "..."}
"""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional

from agent.gate_events import GateEventEmitter

if TYPE_CHECKING:
    from agent.event_bus import Event, EventBus


class GateManager:
    """Manages pending HITL gates via the EventBus."""

    def __init__(self, *, bus: "EventBus") -> None:
        self._bus = bus
        self._emitter = GateEventEmitter(bus=bus)
        self._pending: Dict[str, asyncio.Future] = {}
        self._sub_ids: list[str] = []

    @property
    def pending_gates(self) -> Dict[str, asyncio.Future]:
        """Read-only view of pending gates."""
        return dict(self._pending)

    def start(self) -> None:
        """Subscribe to gate.response events on the bus."""
        sub_id = self._bus.on("gate.response", self._on_gate_response)
        self._sub_ids.append(sub_id)

    def stop(self) -> None:
        """Unsubscribe from all bus events and cancel pending gates."""
        for sub_id in self._sub_ids:
            self._bus.off(sub_id)
        self._sub_ids.clear()

    def request_gate(
        self,
        *,
        run_id: str,
        node: str,
        title: str,
        description: str,
        gate_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> asyncio.Future:
        """Emit a gate.request and return a Future that resolves on response.

        Args:
            run_id: The pipeline run ID.
            node: The graph node requesting approval.
            title: Human-readable title for the gate.
            description: Detailed description of what needs approval.
            gate_id: Unique gate identifier. Auto-generated if not provided.
            context: Optional additional context for the gate.
            loop: Event loop for the Future. Uses running loop if not provided.

        Returns:
            asyncio.Future that resolves with {"approved": bool, "feedback": str}.
        """
        if gate_id is None:
            gate_id = f"gate-{uuid.uuid4().hex[:8]}"

        target_loop = loop or asyncio.get_event_loop()
        future: asyncio.Future = target_loop.create_future()
        self._pending[gate_id] = future

        self._emitter.request(
            gate_id=gate_id,
            run_id=run_id,
            node=node,
            title=title,
            description=description,
            context=context,
        )

        return future

    def cancel_gate(self, gate_id: str) -> None:
        """Cancel a pending gate by ID."""
        future = self._pending.pop(gate_id, None)
        if future is not None and not future.done():
            future.cancel()

    def cancel_all_gates(self) -> None:
        """Cancel all pending gates."""
        for gate_id in list(self._pending.keys()):
            self.cancel_gate(gate_id)

    def _on_gate_response(self, event: "Event") -> None:
        """Handle gate.response events from the bus."""
        gate_id = event.payload.get("gate_id")
        if gate_id is None:
            return

        future = self._pending.pop(gate_id, None)
        if future is None or future.done():
            return

        future.set_result({
            "approved": event.payload.get("approved", False),
            "feedback": event.payload.get("feedback", ""),
        })
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/agent/test_gate_manager.py -v`
Expected: All 12 tests PASS

- [ ] **Step 5: Commit**

```bash
git add agent/gate_manager.py tests/agent/test_gate_manager.py
git commit -m "feat: add GateManager for pending HITL gate lifecycle"
```

---

### Task 3: Wire GateManager into Server

**Files:**
- Modify: `agent/repl/server.py`
- Modify: `tests/agent/repl/test_server.py`

Add `GateManager` as a shared component in the server, alongside `WSManager` and `PipelineRunner`.

- [ ] **Step 1: Write the failing test**

Add to `tests/agent/repl/test_server.py`:

```python
class TestGateManagerIntegration:
    """GateManager is wired into the server."""

    def test_gate_manager_exists(self):
        from agent.repl.server import gate_manager
        from agent.gate_manager import GateManager
        assert isinstance(gate_manager, GateManager)

    def test_gate_manager_shares_bus(self):
        from agent.repl.server import bus, gate_manager
        assert gate_manager._bus is bus
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/agent/repl/test_server.py::TestGateManagerIntegration -v`
Expected: FAIL with `ImportError: cannot import name 'gate_manager' from 'agent.repl.server'`

- [ ] **Step 3: Modify server.py**

In `agent/repl/server.py`, add the import and instantiation. The file currently has:

```python
from agent.event_bus import EventBus
from agent.repl.ws_manager import WSManager
from agent.repl.pipeline_runner import PipelineRunner
```

Add after the `PipelineRunner` import:

```python
from agent.gate_manager import GateManager
```

The file currently has:

```python
bus = EventBus()

ws_manager = WSManager(bus)
ws_manager.start()

pipeline_runner = PipelineRunner(bus)
pipeline_runner.start()
```

Add after `pipeline_runner.start()`:

```python
gate_manager = GateManager(bus=bus)
gate_manager.start()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/agent/repl/test_server.py::TestGateManagerIntegration -v`
Expected: All 2 tests PASS

- [ ] **Step 5: Run all existing tests to verify no regressions**

Run: `python -m pytest tests/agent/ -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add agent/repl/server.py tests/agent/repl/test_server.py
git commit -m "feat: wire GateManager into server shared bus"
```

---

### Task 4: Gate End-to-End via WebSocket

**Files:**
- Modify: `tests/agent/repl/test_server.py`

Test the full round-trip: WS client sends `gate.response` command → WSManager emits on bus → GateManager resolves future.

- [ ] **Step 1: Write the failing test**

Add to `tests/agent/repl/test_server.py`:

```python
import asyncio


class TestGateWebSocketRoundTrip:
    """Full gate round-trip via WebSocket."""

    def test_gate_response_resolves_pending_gate(self):
        from agent.repl.server import bus, gate_manager

        loop = asyncio.new_event_loop()
        try:
            # Create a pending gate
            future = gate_manager.request_gate(
                gate_id="ws-gate-001",
                run_id="run-ws",
                node="blueprint_approval_gate",
                title="Approve Blueprint",
                description="Review.",
                loop=loop,
            )

            # Simulate what WSManager does when it receives gate.response command
            bus.emit("gate.response", {
                "gate_id": "ws-gate-001",
                "approved": True,
                "feedback": "",
            })

            assert future.done()
            result = future.result()
            assert result["approved"] is True
        finally:
            # Clean up any remaining pending gates
            gate_manager.cancel_all_gates()
            loop.close()

    def test_gate_request_broadcasts_to_bus(self):
        from agent.repl.server import bus, gate_manager

        received = []
        bus.on("gate.request", lambda e: received.append(e))

        loop = asyncio.new_event_loop()
        try:
            future = gate_manager.request_gate(
                gate_id="ws-gate-002",
                run_id="run-ws",
                node="push",
                title="Approve Push",
                description="Push to remote?",
                loop=loop,
            )

            assert len(received) == 1
            assert received[0].payload["gate_id"] == "ws-gate-002"
            assert received[0].payload["node"] == "push"
        finally:
            gate_manager.cancel_all_gates()
            loop.close()
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `python -m pytest tests/agent/repl/test_server.py::TestGateWebSocketRoundTrip -v`
Expected: All 2 tests PASS (these should pass immediately since the wiring is already done in Task 3)

- [ ] **Step 3: Commit**

```bash
git add tests/agent/repl/test_server.py
git commit -m "test: add gate end-to-end WebSocket round-trip tests"
```

---

### Task 5: Frontend useGates Composable

**Files:**
- Create: `ui/js/gates.js`

The `useGates` composable tracks pending gate requests and provides approve/reject actions. It mirrors the `usePipeline` pattern.

- [ ] **Step 1: Create the composable**

Create `ui/js/gates.js`:

```javascript
/**
 * useGates composable — tracks pending HITL gate requests.
 *
 * Listens for gate.request events from the backend and provides
 * approve/reject actions that send gate.response commands via WebSocket.
 *
 * @param {EventBus} bus - Client-side event bus
 * @param {Function} sendCommand - Function to send WS commands
 * @returns {Object} Reactive gate state and actions
 */
export function useGates(bus, sendCommand) {
  const { ref, computed } = Vue;

  // ── Reactive State ──────────────────────────────────────────────
  const pendingGates = ref([]);

  // ── Computed ────────────────────────────────────────────────────
  const hasActiveGate = computed(() => pendingGates.value.length > 0);
  const currentGate = computed(() => pendingGates.value[0] || null);

  // ── Event Handlers ──────────────────────────────────────────────
  function onGateRequest(event) {
    const payload = event.payload || event;
    pendingGates.value.push({
      gate_id: payload.gate_id,
      run_id: payload.run_id,
      node: payload.node,
      title: payload.title,
      description: payload.description,
      context: payload.context || {},
      timestamp: payload.timestamp || Date.now(),
    });
  }

  function onGateResponse(event) {
    const payload = event.payload || event;
    const gateId = payload.gate_id;
    pendingGates.value = pendingGates.value.filter(
      (g) => g.gate_id !== gateId
    );
  }

  // ── Actions ─────────────────────────────────────────────────────
  function approveGate(gateId, feedback = '') {
    sendCommand('gate.response', {
      gate_id: gateId,
      approved: true,
      feedback,
    });
  }

  function rejectGate(gateId, feedback = '') {
    sendCommand('gate.response', {
      gate_id: gateId,
      approved: false,
      feedback,
    });
  }

  // ── Subscriptions ───────────────────────────────────────────────
  bus.on('gate.request', onGateRequest);
  bus.on('gate.response', onGateResponse);

  return {
    // State
    pendingGates,
    // Computed
    hasActiveGate,
    currentGate,
    // Actions
    approveGate,
    rejectGate,
  };
}
```

- [ ] **Step 2: Verify file is syntactically valid**

Open `ui/js/gates.js` in the browser dev console or run a quick syntax check. The file should parse without errors.

- [ ] **Step 3: Commit**

```bash
git add ui/js/gates.js
git commit -m "feat: add useGates composable for frontend gate state"
```

---

### Task 6: Integrate useGates into App

**Files:**
- Modify: `ui/js/app.js`

Import `useGates` and wire it into the Vue app, following the same pattern as `usePipeline`.

- [ ] **Step 1: Add the import**

In `ui/js/app.js`, the imports section currently has:

```javascript
import { EventBus } from './event-bus.js';
import { usePipeline } from './pipeline.js';
```

Add after the `usePipeline` import:

```javascript
import { useGates } from './gates.js';
```

- [ ] **Step 2: Initialize the composable in setup()**

In the `setup()` function, after the line:

```javascript
      const pipeline = usePipeline(bus, sendCommand);
```

Add:

```javascript
      const gates = useGates(bus, sendCommand);
```

- [ ] **Step 3: Return gates to the template**

In the `return` statement of `setup()`, add `gates` alongside the existing returns. Find the return statement that includes `pipeline` and add `gates` next to it. The return currently includes:

```javascript
        pipeline,
```

Add after it:

```javascript
        gates,
```

- [ ] **Step 4: Verify the app loads without errors**

Start the server and open the browser. Check the console for any import or initialization errors.

Run: `cd /Volumes/berkakyo/Users/berkamain/Developer/w0rk/lionparcel/Lios-Agent && python -c "from agent.repl.server import app; print('Server imports OK')"`
Expected: `Server imports OK`

- [ ] **Step 5: Commit**

```bash
git add ui/js/app.js
git commit -m "feat: integrate useGates composable into Vue app"
```

---

### Task 7: Gate Approval Dialog — HTML Markup

**Files:**
- Modify: `ui/index.html`

Add the gate approval dialog as an overlay within the pipeline panel. It appears when `gates.hasActiveGate.value` is true, showing the current gate's title, description, and approve/reject buttons with an optional feedback textarea.

- [ ] **Step 1: Add the CSS import**

In `ui/index.html`, the CSS imports section currently has:

```html
    <link rel="stylesheet" href="/css/tokens.css">
    <link rel="stylesheet" href="/css/layout.css">
    <link rel="stylesheet" href="/css/chat.css">
    <link rel="stylesheet" href="/css/pipeline.css">
```

Add after `pipeline.css`:

```html
    <link rel="stylesheet" href="/css/gates.css">
```

- [ ] **Step 2: Add the gate dialog markup**

In `ui/index.html`, find the pipeline panel's closing `</div>` (the one that closes the `pipeline-dashboard` div). Insert the gate dialog overlay just before the pipeline controls section. Specifically, find this block:

```html
          <!-- Controls -->
          <div class="pipeline-controls">
```

Insert before it:

```html
          <!-- Gate Approval Dialog -->
          <div class="gate-overlay" v-if="gates.hasActiveGate.value">
            <div class="gate-dialog">
              <div class="gate-dialog-header">
                <div class="gate-dialog-icon">
                  <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                    <path d="M10 1.667A3.333 3.333 0 0 0 6.667 5v3.333H5A1.667 1.667 0 0 0 3.333 10v6.667A1.667 1.667 0 0 0 5 18.333h10a1.667 1.667 0 0 0 1.667-1.666V10A1.667 1.667 0 0 0 15 8.333h-1.667V5A3.333 3.333 0 0 0 10 1.667Zm0 1.666A1.667 1.667 0 0 1 11.667 5v3.333H8.333V5A1.667 1.667 0 0 1 10 3.333Z" fill="currentColor"/>
                  </svg>
                </div>
                <div class="gate-dialog-title">{{ gates.currentGate.value.title }}</div>
                <div class="gate-dialog-node">{{ gates.currentGate.value.node }}</div>
              </div>
              <div class="gate-dialog-body">
                <p class="gate-dialog-description">{{ gates.currentGate.value.description }}</p>
                <div class="gate-dialog-context" v-if="Object.keys(gates.currentGate.value.context).length > 0">
                  <div class="gate-context-item" v-for="(value, key) in gates.currentGate.value.context" :key="key">
                    <span class="gate-context-key">{{ key }}:</span>
                    <span class="gate-context-value">{{ value }}</span>
                  </div>
                </div>
                <textarea
                  class="gate-feedback-input"
                  v-model="gateFeedback"
                  placeholder="Optional feedback..."
                  rows="3"
                ></textarea>
              </div>
              <div class="gate-dialog-actions">
                <button
                  class="gate-btn gate-btn-reject"
                  @click="gates.rejectGate(gates.currentGate.value.gate_id, gateFeedback); gateFeedback = '';"
                >
                  Reject
                </button>
                <button
                  class="gate-btn gate-btn-approve"
                  @click="gates.approveGate(gates.currentGate.value.gate_id, gateFeedback); gateFeedback = '';"
                >
                  Approve
                </button>
              </div>
              <div class="gate-queue-indicator" v-if="gates.pendingGates.value.length > 1">
                {{ gates.pendingGates.value.length - 1 }} more gate{{ gates.pendingGates.value.length > 2 ? 's' : '' }} pending
              </div>
            </div>
          </div>

```

- [ ] **Step 3: Add gateFeedback reactive ref**

In `ui/js/app.js`, in the `setup()` function, after the `gates` initialization, add:

```javascript
      const gateFeedback = Vue.ref('');
```

And add `gateFeedback` to the return statement, after `gates`:

```javascript
        gateFeedback,
```

- [ ] **Step 4: Verify the markup renders correctly**

Start the server and verify the page loads without errors. The gate dialog should not be visible (no active gates).

- [ ] **Step 5: Commit**

```bash
git add ui/index.html ui/js/app.js
git commit -m "feat: add gate approval dialog HTML markup"
```

---

### Task 8: Gate Dialog CSS Styles

**Files:**
- Create: `ui/css/gates.css`

Style the gate approval dialog following the existing design token system and BEM-like naming from `pipeline.css`.

- [ ] **Step 1: Create the stylesheet**

Create `ui/css/gates.css`:

```css
/* ── Gate Approval Dialog ──────────────────────────────────────── */

.gate-overlay {
  position: absolute;
  inset: 0;
  background: rgba(11, 17, 32, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  backdrop-filter: blur(4px);
  animation: gate-fade-in var(--transition-normal) ease-out;
}

@keyframes gate-fade-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.gate-dialog {
  background: var(--bg-surface);
  border: 1px solid var(--border-active);
  border-radius: var(--radius-lg);
  width: 100%;
  max-width: 480px;
  margin: 0 24px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  animation: gate-slide-up var(--transition-normal) ease-out;
}

@keyframes gate-slide-up {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ── Header ────────────────────────────────────────────────────── */

.gate-dialog-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px 12px;
  border-bottom: 1px solid var(--border-subtle);
}

.gate-dialog-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  background: rgba(245, 158, 11, 0.12);
  color: var(--accent-amber);
  flex-shrink: 0;
}

.gate-dialog-title {
  font-family: var(--font-sans);
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
}

.gate-dialog-node {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-muted);
  background: var(--bg-elevated);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
}

/* ── Body ──────────────────────────────────────────────────────── */

.gate-dialog-body {
  padding: 16px 20px;
}

.gate-dialog-description {
  font-family: var(--font-sans);
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-secondary);
  margin: 0 0 12px;
}

.gate-dialog-context {
  background: var(--bg-primary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  margin-bottom: 12px;
}

.gate-context-item {
  display: flex;
  gap: 8px;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.6;
}

.gate-context-key {
  color: var(--text-muted);
  flex-shrink: 0;
}

.gate-context-value {
  color: var(--text-secondary);
}

.gate-feedback-input {
  width: 100%;
  background: var(--bg-primary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: 13px;
  padding: 10px 12px;
  resize: vertical;
  min-height: 60px;
  transition: border-color var(--transition-fast);
  box-sizing: border-box;
}

.gate-feedback-input::placeholder {
  color: var(--text-muted);
}

.gate-feedback-input:focus {
  outline: none;
  border-color: var(--accent-amber);
}

/* ── Actions ───────────────────────────────────────────────────── */

.gate-dialog-actions {
  display: flex;
  gap: 10px;
  padding: 12px 20px 16px;
  border-top: 1px solid var(--border-subtle);
  justify-content: flex-end;
}

.gate-btn {
  font-family: var(--font-sans);
  font-size: 13px;
  font-weight: 500;
  padding: 8px 20px;
  border-radius: var(--radius-sm);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.gate-btn-reject {
  background: transparent;
  border-color: var(--border-active);
  color: var(--text-secondary);
}

.gate-btn-reject:hover {
  background: rgba(239, 68, 68, 0.1);
  border-color: var(--accent-red);
  color: var(--accent-red);
}

.gate-btn-approve {
  background: var(--accent-green);
  color: var(--bg-deep);
}

.gate-btn-approve:hover {
  background: #16a34a;
}

/* ── Queue Indicator ───────────────────────────────────────────── */

.gate-queue-indicator {
  text-align: center;
  padding: 8px 20px 12px;
  font-family: var(--font-sans);
  font-size: 11px;
  color: var(--text-muted);
}
```

- [ ] **Step 2: Verify styles render correctly**

Start the server. To test the dialog visually, temporarily emit a fake gate.request event from the browser console:

```javascript
// In browser dev console:
document.querySelector('#app').__vue_app__
// Or dispatch via the WS event bus — the dialog should appear
```

- [ ] **Step 3: Commit**

```bash
git add ui/css/gates.css
git commit -m "feat: add gate approval dialog CSS styles"
```

---

### Task 9: Pipeline Node Gate Status Integration

**Files:**
- Modify: `ui/js/pipeline.js`
- Modify: `ui/index.html`
- Modify: `ui/css/pipeline.css`

When a gate node is active (has a pending gate.request), the node card in the pipeline timeline should show a distinct "gate" status with an amber indicator, making it visually clear which node is waiting for human approval.

- [ ] **Step 1: Update pipeline composable to track gate nodes**

In `ui/js/pipeline.js`, the composable needs to listen for `gate.request` and `gate.response` events to mark nodes as "gated". Find the event handler section (after `onGraphError`) and add:

```javascript
  function onGateRequest(event) {
    const payload = event.payload || event;
    const nodeName = payload.node;
    const node = nodes.value.find((n) => n.name === nodeName);
    if (node) {
      node.status = 'gated';
      node.gateId = payload.gate_id;
    }
  }

  function onGateResponse(event) {
    const payload = event.payload || event;
    const gateId = payload.gate_id;
    const node = nodes.value.find((n) => n.gateId === gateId);
    if (node) {
      // Return to running — the graph will resume and node_exit will set final status
      node.status = 'running';
      delete node.gateId;
    }
  }
```

Add the subscriptions after the existing `bus.on('graph.error', ...)` line:

```javascript
  bus.on('gate.request', onGateRequest);
  bus.on('gate.response', onGateResponse);
```

- [ ] **Step 2: Add gated status icon to the node card template**

In `ui/index.html`, find the node status icon section in the pipeline timeline. It currently has icons for running (spinner), completed (check), and error (x). Find:

```html
                  <!-- Status Icon -->
```

Within the status icon container, find the pending dot (the last icon in the group):

```html
                    <div v-else class="node-pending-dot"></div>
```

Insert before that `v-else` line:

```html
                    <div v-else-if="node.status === 'gated'" class="node-gate-icon">
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                        <path d="M7 1.167A2.333 2.333 0 0 0 4.667 3.5v2.333H3.5A1.167 1.167 0 0 0 2.333 7v4.667A1.167 1.167 0 0 0 3.5 12.833h7a1.167 1.167 0 0 0 1.167-1.166V7A1.167 1.167 0 0 0 10.5 5.833H9.333V3.5A2.333 2.333 0 0 0 7 1.167Zm0 1.166A1.167 1.167 0 0 1 8.167 3.5v2.333H5.833V3.5A1.167 1.167 0 0 1 7 2.333Z" fill="currentColor"/>
                      </svg>
                    </div>
```

- [ ] **Step 3: Add gated node card and icon styles**

In `ui/css/pipeline.css`, add after the `.node-card.error` styles:

```css
.node-card.gated {
  border-color: var(--accent-amber);
  background: rgba(245, 158, 11, 0.06);
}

.node-gate-icon {
  color: var(--accent-amber);
  animation: gate-pulse 2s ease-in-out infinite;
}

@keyframes gate-pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
}
```

- [ ] **Step 4: Add gated class to node card element**

In `ui/index.html`, find the node card element that applies status classes. It currently has something like:

```html
                <div class="node-card" :class="node.status">
```

This already works — the `gated` status string will be applied as a CSS class automatically since we set `node.status = 'gated'` in the composable.

- [ ] **Step 5: Commit**

```bash
git add ui/js/pipeline.js ui/index.html ui/css/pipeline.css
git commit -m "feat: add gated status indicator for pipeline node cards"
```

---

### Task 10: Pipeline Status — Gated State

**Files:**
- Modify: `ui/js/pipeline.js`
- Modify: `ui/css/pipeline.css`

When any node is in "gated" status, the pipeline header should show a "gated" status badge (amber) instead of "running", making it immediately clear the pipeline is waiting for human input.

- [ ] **Step 1: Update pipeline status tracking**

In `ui/js/pipeline.js`, the `onGateRequest` handler (added in Task 9) should also update the pipeline status. Modify the `onGateRequest` function to add:

```javascript
  function onGateRequest(event) {
    const payload = event.payload || event;
    const nodeName = payload.node;
    const node = nodes.value.find((n) => n.name === nodeName);
    if (node) {
      node.status = 'gated';
      node.gateId = payload.gate_id;
    }
    status.value = 'gated';
  }
```

And `onGateResponse` should restore the running status:

```javascript
  function onGateResponse(event) {
    const payload = event.payload || event;
    const gateId = payload.gate_id;
    const node = nodes.value.find((n) => n.gateId === gateId);
    if (node) {
      node.status = 'running';
      delete node.gateId;
    }
    status.value = 'running';
  }
```

- [ ] **Step 2: Add gated status badge style**

In `ui/css/pipeline.css`, find the status badge variants (`.pipeline-status-badge.idle`, `.running`, etc.) and add after `.cancelled`:

```css
.pipeline-status-badge.gated {
  background: rgba(245, 158, 11, 0.12);
  color: var(--accent-amber);
}
```

Also add a gated variant for the status dot animation. Find `.pipeline-status-dot` styles and add:

```css
.pipeline-status-badge.gated .pipeline-status-dot {
  background: var(--accent-amber);
  animation: gate-pulse 2s ease-in-out infinite;
}
```

- [ ] **Step 3: Commit**

```bash
git add ui/js/pipeline.js ui/css/pipeline.css
git commit -m "feat: add gated pipeline status badge"
```

---

## Summary

| Task | Component | Files | Tests |
|------|-----------|-------|-------|
| 1 | GateEventEmitter | `agent/gate_events.py` | 7 tests |
| 2 | GateManager | `agent/gate_manager.py` | 12 tests |
| 3 | Server wiring | `agent/repl/server.py` | 2 tests |
| 4 | E2E WebSocket | `tests/agent/repl/test_server.py` | 2 tests |
| 5 | useGates composable | `ui/js/gates.js` | — |
| 6 | App integration | `ui/js/app.js` | — |
| 7 | Dialog markup | `ui/index.html`, `ui/js/app.js` | — |
| 8 | Dialog CSS | `ui/css/gates.css` | — |
| 9 | Node gate status | `ui/js/pipeline.js`, `ui/index.html`, `ui/css/pipeline.css` | — |
| 10 | Pipeline gated badge | `ui/js/pipeline.js`, `ui/css/pipeline.css` | — |

**Total: 10 tasks, 23 backend tests, 10 commits**
