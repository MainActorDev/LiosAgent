"""Tests for tool event emission from architect_coder_node stdout parsing."""

import pytest

from agent.event_bus import EventBus
from agent.tool_events import ToolEventEmitter
from agent.tool_output_parser import ToolOutputParser


class TestGraphToolEventIntegration:
    """Integration tests: parser events -> emitter -> bus."""

    def test_parser_events_emitted_through_bus(self) -> None:
        """Verify that parsed tool call events are correctly emitted to the bus."""
        bus = EventBus()
        emitter = ToolEventEmitter(bus=bus)
        parser = ToolOutputParser(run_id="run_123")

        received: list = []
        bus.on("tool.*", lambda e: received.append(e))

        # Simulate stdout lines from OpenCode
        lines = [
            '{"type":"tool_call","tool":"Write","id":"tc_001","input":{"filePath":"test.py","content":"x"}}\n',
            '{"type":"tool_result","id":"tc_001","output":{"success":true},"duration_ms":50}\n',
        ]

        for line in lines:
            for event in parser.feed_line(line):
                if event.event_type == "tool.start":
                    emitter.start(
                        tool_call_id=event.tool_call_id,
                        run_id=event.run_id,
                        tool_name=event.tool_name,
                        input_data=event.input_data,
                        node="architect_coder",
                    )
                elif event.event_type == "tool.result":
                    emitter.result(
                        tool_call_id=event.tool_call_id,
                        run_id=event.run_id,
                        tool_name=event.tool_name,
                        output_data=event.output_data,
                        duration_ms=event.duration_ms,
                    )
                elif event.event_type == "tool.error":
                    emitter.error(
                        tool_call_id=event.tool_call_id,
                        run_id=event.run_id,
                        tool_name=event.tool_name,
                        error=event.error,
                        node="architect_coder",
                    )

        assert len(received) == 2
        assert received[0].type == "tool.start"
        assert received[0].payload["tool_name"] == "Write"
        assert received[0].payload["node"] == "architect_coder"
        assert received[1].type == "tool.result"
        assert received[1].payload["duration_ms"] == 50

    def test_file_write_events_emitted_for_write_tool(self) -> None:
        """Verify that Write tool calls also emit file.write events."""
        bus = EventBus()
        emitter = ToolEventEmitter(bus=bus)
        parser = ToolOutputParser(run_id="run_123")

        file_events: list = []
        bus.on("file.*", lambda e: file_events.append(e))

        lines = [
            '{"type":"tool_call","tool":"Write","id":"tc_010","input":{"filePath":"src/app.py","content":"print(1)"}}\n',
            '{"type":"tool_result","id":"tc_010","output":{"success":true},"duration_ms":30}\n',
        ]

        for line in lines:
            for event in parser.feed_line(line):
                if event.event_type == "tool.start" and event.tool_name == "Write":
                    emitter.file_write(
                        tool_call_id=event.tool_call_id,
                        run_id=event.run_id,
                        path=event.input_data.get("filePath", ""),
                        diff=event.input_data.get("content", ""),
                        lines_added=event.input_data.get("content", "").count("\n") + 1,
                        lines_removed=0,
                        is_new_file=True,
                    )

        assert len(file_events) == 1
        assert file_events[0].type == "file.write"
        assert file_events[0].payload["path"] == "src/app.py"

    def test_error_events_emitted_for_failed_tools(self) -> None:
        """Verify that tool errors are correctly emitted."""
        bus = EventBus()
        emitter = ToolEventEmitter(bus=bus)
        parser = ToolOutputParser(run_id="run_123")

        received: list = []
        bus.on("tool.error", lambda e: received.append(e))

        lines = [
            '{"type":"tool_call","tool":"Bash","id":"tc_err","input":{"command":"bad"}}\n',
            '{"type":"tool_error","id":"tc_err","error":"Command failed"}\n',
        ]

        for line in lines:
            for event in parser.feed_line(line):
                if event.event_type == "tool.error":
                    emitter.error(
                        tool_call_id=event.tool_call_id,
                        run_id=event.run_id,
                        tool_name=event.tool_name,
                        error=event.error,
                        node="architect_coder",
                    )

        assert len(received) == 1
        assert received[0].payload["error"] == "Command failed"

    def test_non_tool_lines_produce_no_events(self) -> None:
        """Verify that regular stdout lines don't produce events."""
        bus = EventBus()
        parser = ToolOutputParser(run_id="run_123")

        received: list = []
        bus.on("tool.*", lambda e: received.append(e))

        lines = [
            "Starting session...\n",
            "Working on task...\n",
            '{"type":"message","content":"thinking..."}\n',
            "Done.\n",
        ]

        for line in lines:
            events = parser.feed_line(line)
            assert len(events) == 0

        assert len(received) == 0
