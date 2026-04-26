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
