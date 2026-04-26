"""Parser for extracting tool call events from OpenCode stdout.

Processes stdout line-by-line, detecting JSON-structured tool call
information and converting it into typed ToolCallEvent objects.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolCallEvent:
    """A parsed tool call event from OpenCode stdout."""

    event_type: str  # "tool.start", "tool.result", "tool.error"
    tool_call_id: str
    run_id: str
    tool_name: str = ""
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    duration_ms: int = 0


class ToolOutputParser:
    """Parses OpenCode stdout to extract tool call events.

    Feed lines one at a time via feed_line(). Each call returns
    a list of ToolCallEvent objects (usually 0 or 1).
    """

    def __init__(self, run_id: str) -> None:
        self._run_id = run_id
        self._active_tools: dict[str, str] = {}  # tool_call_id -> tool_name

    def feed_line(self, line: str) -> list[ToolCallEvent]:
        """Process a single stdout line. Returns parsed events (if any)."""
        line = line.strip()
        if not line:
            return []

        try:
            data = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            return []

        if not isinstance(data, dict) or "type" not in data:
            return []

        msg_type = data["type"]

        if msg_type == "tool_call":
            return self._handle_tool_call(data)
        elif msg_type == "tool_result":
            return self._handle_tool_result(data)
        elif msg_type == "tool_error":
            return self._handle_tool_error(data)

        return []

    def _handle_tool_call(self, data: dict[str, Any]) -> list[ToolCallEvent]:
        tool_call_id = data.get("id", "")
        tool_name = data.get("tool", "")
        input_data = data.get("input", {})

        self._active_tools[tool_call_id] = tool_name

        return [
            ToolCallEvent(
                event_type="tool.start",
                tool_call_id=tool_call_id,
                run_id=self._run_id,
                tool_name=tool_name,
                input_data=input_data,
            )
        ]

    def _handle_tool_result(self, data: dict[str, Any]) -> list[ToolCallEvent]:
        tool_call_id = data.get("id", "")
        tool_name = self._active_tools.pop(tool_call_id, "")
        output_data = data.get("output", {})
        duration_ms = data.get("duration_ms", 0)

        return [
            ToolCallEvent(
                event_type="tool.result",
                tool_call_id=tool_call_id,
                run_id=self._run_id,
                tool_name=tool_name,
                output_data=output_data,
                duration_ms=duration_ms,
            )
        ]

    def _handle_tool_error(self, data: dict[str, Any]) -> list[ToolCallEvent]:
        tool_call_id = data.get("id", "")
        tool_name = self._active_tools.pop(tool_call_id, "")
        error = data.get("error", "")

        return [
            ToolCallEvent(
                event_type="tool.error",
                tool_call_id=tool_call_id,
                run_id=self._run_id,
                tool_name=tool_name,
                error=error,
            )
        ]
