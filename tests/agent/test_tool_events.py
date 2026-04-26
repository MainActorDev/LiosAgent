"""Tests for ToolEventEmitter."""

import pytest

from agent.event_bus import EventBus
from agent.tool_events import ToolEventEmitter


class TestToolEventEmitterStart:
    """Tests for tool.start event emission."""

    def test_emits_tool_start_event(self) -> None:
        bus = EventBus()
        emitter = ToolEventEmitter(bus=bus)
        received: list = []
        bus.on("tool.start", lambda e: received.append(e))

        emitter.start(
            tool_call_id="tc_001",
            run_id="run_abc",
            tool_name="file_write",
            input_data={"path": "src/main.py", "content": "print('hello')"},
        )

        assert len(received) == 1
        assert received[0].type == "tool.start"
        assert received[0].payload["tool_call_id"] == "tc_001"
        assert received[0].payload["tool_name"] == "file_write"
        assert received[0].payload["input_data"]["path"] == "src/main.py"
        assert received[0].correlation_id == "run_abc"

    def test_tool_start_with_node_context(self) -> None:
        bus = EventBus()
        emitter = ToolEventEmitter(bus=bus)
        received: list = []
        bus.on("tool.start", lambda e: received.append(e))

        emitter.start(
            tool_call_id="tc_002",
            run_id="run_abc",
            tool_name="bash",
            input_data={"command": "ls -la"},
            node="architect_coder",
        )

        assert received[0].payload["node"] == "architect_coder"


class TestToolEventEmitterResult:
    """Tests for tool.result event emission."""

    def test_emits_tool_result_event(self) -> None:
        bus = EventBus()
        emitter = ToolEventEmitter(bus=bus)
        received: list = []
        bus.on("tool.result", lambda e: received.append(e))

        emitter.result(
            tool_call_id="tc_001",
            run_id="run_abc",
            tool_name="file_write",
            output_data={"success": True, "bytes_written": 42},
            duration_ms=150,
        )

        assert len(received) == 1
        assert received[0].type == "tool.result"
        assert received[0].payload["tool_call_id"] == "tc_001"
        assert received[0].payload["tool_name"] == "file_write"
        assert received[0].payload["output_data"]["success"] is True
        assert received[0].payload["duration_ms"] == 150
        assert received[0].correlation_id == "run_abc"

    def test_tool_result_with_truncated_output(self) -> None:
        bus = EventBus()
        emitter = ToolEventEmitter(bus=bus)
        received: list = []
        bus.on("tool.result", lambda e: received.append(e))

        large_output = "x" * 10000
        emitter.result(
            tool_call_id="tc_003",
            run_id="run_abc",
            tool_name="bash",
            output_data={"stdout": large_output},
            duration_ms=500,
            truncated=True,
        )

        assert received[0].payload["truncated"] is True


class TestToolEventEmitterError:
    """Tests for tool.error event emission."""

    def test_emits_tool_error_event(self) -> None:
        bus = EventBus()
        emitter = ToolEventEmitter(bus=bus)
        received: list = []
        bus.on("tool.error", lambda e: received.append(e))

        emitter.error(
            tool_call_id="tc_001",
            run_id="run_abc",
            tool_name="file_write",
            error="Permission denied: /etc/passwd",
        )

        assert len(received) == 1
        assert received[0].type == "tool.error"
        assert received[0].payload["tool_call_id"] == "tc_001"
        assert received[0].payload["tool_name"] == "file_write"
        assert received[0].payload["error"] == "Permission denied: /etc/passwd"
        assert received[0].correlation_id == "run_abc"

    def test_tool_error_with_node_context(self) -> None:
        bus = EventBus()
        emitter = ToolEventEmitter(bus=bus)
        received: list = []
        bus.on("tool.error", lambda e: received.append(e))

        emitter.error(
            tool_call_id="tc_004",
            run_id="run_abc",
            tool_name="bash",
            error="Command timed out",
            node="architect_coder",
        )

        assert received[0].payload["node"] == "architect_coder"


class TestToolEventEmitterNoBus:
    """Tests that emitter is safe to use without a bus."""

    def test_no_bus_does_not_raise(self) -> None:
        emitter = ToolEventEmitter(bus=None)

        # All methods should be no-ops when bus is None
        emitter.start(
            tool_call_id="tc_001",
            run_id="run_abc",
            tool_name="file_write",
            input_data={},
        )
        emitter.result(
            tool_call_id="tc_001",
            run_id="run_abc",
            tool_name="file_write",
            output_data={},
            duration_ms=100,
        )
        emitter.error(
            tool_call_id="tc_001",
            run_id="run_abc",
            tool_name="file_write",
            error="fail",
        )
        # No exception means pass
