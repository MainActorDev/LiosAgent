"""Tests for OpenCode stdout tool call parser."""

import pytest

from agent.tool_output_parser import ToolOutputParser, ToolCallEvent


class TestToolOutputParserBasic:
    """Tests for basic tool call detection."""

    def test_detects_tool_call_start(self) -> None:
        parser = ToolOutputParser(run_id="run_abc")
        lines = [
            '{"type":"tool_call","tool":"Write","id":"tc_001","input":{"filePath":"/tmp/test.py","content":"print(1)"}}\n',
        ]

        events = []
        for line in lines:
            events.extend(parser.feed_line(line))

        assert len(events) == 1
        assert events[0].event_type == "tool.start"
        assert events[0].tool_call_id == "tc_001"
        assert events[0].tool_name == "Write"
        assert events[0].input_data["filePath"] == "/tmp/test.py"

    def test_detects_tool_call_result(self) -> None:
        parser = ToolOutputParser(run_id="run_abc")
        lines = [
            '{"type":"tool_call","tool":"Write","id":"tc_001","input":{"filePath":"/tmp/test.py","content":"print(1)"}}\n',
            '{"type":"tool_result","id":"tc_001","output":{"success":true},"duration_ms":120}\n',
        ]

        events = []
        for line in lines:
            events.extend(parser.feed_line(line))

        assert len(events) == 2
        assert events[1].event_type == "tool.result"
        assert events[1].tool_call_id == "tc_001"
        assert events[1].output_data["success"] is True
        assert events[1].duration_ms == 120

    def test_detects_tool_call_error(self) -> None:
        parser = ToolOutputParser(run_id="run_abc")
        lines = [
            '{"type":"tool_call","tool":"Bash","id":"tc_002","input":{"command":"rm -rf /"}}\n',
            '{"type":"tool_error","id":"tc_002","error":"Permission denied"}\n',
        ]

        events = []
        for line in lines:
            events.extend(parser.feed_line(line))

        assert len(events) == 2
        assert events[1].event_type == "tool.error"
        assert events[1].tool_call_id == "tc_002"
        assert events[1].error == "Permission denied"

    def test_ignores_non_json_lines(self) -> None:
        parser = ToolOutputParser(run_id="run_abc")
        lines = [
            "Starting OpenCode session...\n",
            "Processing request...\n",
            "Done.\n",
        ]

        events = []
        for line in lines:
            events.extend(parser.feed_line(line))

        assert len(events) == 0

    def test_ignores_json_without_tool_type(self) -> None:
        parser = ToolOutputParser(run_id="run_abc")
        lines = [
            '{"type":"message","content":"Hello world"}\n',
            '{"status":"ok"}\n',
        ]

        events = []
        for line in lines:
            events.extend(parser.feed_line(line))

        assert len(events) == 0
