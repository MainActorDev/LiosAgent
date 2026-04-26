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
        self.cancel_all_gates()
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

        target_loop = loop or asyncio.get_running_loop()
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
