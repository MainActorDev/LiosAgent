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

        self._bus.emit(
            "graph.end",
            {"run_id": run_id, "total_duration_ms": duration_ms, "cancelled": True},
            correlation_id=run_id,
        )
