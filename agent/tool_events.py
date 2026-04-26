"""Typed event emitter for tool call lifecycle events.

Emits tool.start, tool.result, and tool.error events through the EventBus.
Safe to use without a bus (all methods become no-ops).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from agent.event_bus import EventBus


class ToolEventEmitter:
    """Emits tool.* events for tool call visualization."""

    def __init__(self, *, bus: Optional["EventBus"] = None) -> None:
        self._bus = bus

    def start(
        self,
        *,
        tool_call_id: str,
        run_id: str,
        tool_name: str,
        input_data: dict[str, Any],
        node: Optional[str] = None,
    ) -> None:
        """Emit tool.start when a tool call begins."""
        if self._bus is None:
            return
        payload: dict[str, Any] = {
            "tool_call_id": tool_call_id,
            "run_id": run_id,
            "tool_name": tool_name,
            "input_data": input_data,
        }
        if node is not None:
            payload["node"] = node
        self._bus.emit("tool.start", payload, correlation_id=run_id)

    def result(
        self,
        *,
        tool_call_id: str,
        run_id: str,
        tool_name: str,
        output_data: dict[str, Any],
        duration_ms: int,
        truncated: bool = False,
    ) -> None:
        """Emit tool.result when a tool call completes successfully."""
        if self._bus is None:
            return
        payload: dict[str, Any] = {
            "tool_call_id": tool_call_id,
            "run_id": run_id,
            "tool_name": tool_name,
            "output_data": output_data,
            "duration_ms": duration_ms,
        }
        if truncated:
            payload["truncated"] = True
        self._bus.emit("tool.result", payload, correlation_id=run_id)

    def error(
        self,
        *,
        tool_call_id: str,
        run_id: str,
        tool_name: str,
        error: str,
        node: Optional[str] = None,
    ) -> None:
        """Emit tool.error when a tool call fails."""
        if self._bus is None:
            return
        payload: dict[str, Any] = {
            "tool_call_id": tool_call_id,
            "run_id": run_id,
            "tool_name": tool_name,
            "error": error,
        }
        if node is not None:
            payload["node"] = node
        self._bus.emit("tool.error", payload, correlation_id=run_id)
