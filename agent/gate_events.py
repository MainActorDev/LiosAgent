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
