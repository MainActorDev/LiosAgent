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
