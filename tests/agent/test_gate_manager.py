"""Tests for GateManager – pending gate lifecycle."""

import asyncio

import pytest

from agent.event_bus import EventBus
from agent.gate_manager import GateManager


class TestGateManagerInit:
    """Initialization and wiring."""

    def test_creates_with_bus(self):
        bus = EventBus()
        manager = GateManager(bus=bus)
        assert manager._bus is bus

    def test_start_subscribes_to_gate_response(self):
        bus = EventBus()
        manager = GateManager(bus=bus)
        manager.start()
        assert len(manager._sub_ids) == 1

    def test_stop_unsubscribes(self):
        bus = EventBus()
        manager = GateManager(bus=bus)
        manager.start()
        manager.stop()
        assert len(manager._sub_ids) == 0

    def test_no_pending_gates_initially(self):
        bus = EventBus()
        manager = GateManager(bus=bus)
        assert manager.pending_gates == {}


class TestGateManagerRequestGate:
    """request_gate() emits gate.request and creates a pending future."""

    def test_emits_gate_request_event(self):
        bus = EventBus()
        manager = GateManager(bus=bus)
        manager.start()
        received = []
        bus.on("gate.request", lambda e: received.append(e))

        loop = asyncio.new_event_loop()
        try:
            future = loop.run_until_complete(
                self._request_gate(manager, loop)
            )
            assert len(received) == 1
            evt = received[0]
            assert evt.type == "gate.request"
            assert evt.payload["gate_id"] == "g-001"
            assert evt.payload["node"] == "blueprint_approval_gate"
            assert evt.payload["title"] == "Approve Blueprint"
        finally:
            loop.close()

    def test_creates_pending_gate(self):
        bus = EventBus()
        manager = GateManager(bus=bus)
        manager.start()

        loop = asyncio.new_event_loop()
        try:
            future = loop.run_until_complete(
                self._request_gate(manager, loop)
            )
            assert "g-001" in manager.pending_gates
            assert not future.done()
        finally:
            loop.close()

    def test_generates_gate_id_when_not_provided(self):
        bus = EventBus()
        manager = GateManager(bus=bus)
        manager.start()
        received = []
        bus.on("gate.request", lambda e: received.append(e))

        loop = asyncio.new_event_loop()
        try:
            future = loop.run_until_complete(
                self._request_gate_no_id(manager, loop)
            )
            gate_id = received[0].payload["gate_id"]
            assert gate_id  # non-empty
            assert gate_id in manager.pending_gates
        finally:
            loop.close()

    @staticmethod
    async def _request_gate(manager, loop):
        return manager.request_gate(
            gate_id="g-001",
            run_id="run-abc",
            node="blueprint_approval_gate",
            title="Approve Blueprint",
            description="Review the blueprint.",
            loop=loop,
        )

    @staticmethod
    async def _request_gate_no_id(manager, loop):
        return manager.request_gate(
            run_id="run-abc",
            node="push",
            title="Approve Push",
            description="Push to remote?",
            loop=loop,
        )


class TestGateManagerResolveGate:
    """gate.response resolves the pending future."""

    def test_approve_resolves_future(self):
        bus = EventBus()
        manager = GateManager(bus=bus)
        manager.start()

        loop = asyncio.new_event_loop()
        try:
            future = manager.request_gate(
                gate_id="g-001",
                run_id="run-abc",
                node="blueprint_approval_gate",
                title="Approve Blueprint",
                description="Review.",
                loop=loop,
            )

            # Simulate gate.response from WSManager
            bus.emit("gate.response", {
                "gate_id": "g-001",
                "approved": True,
                "feedback": "",
            })

            assert future.done()
            result = future.result()
            assert result["approved"] is True
            assert result["feedback"] == ""
            assert "g-001" not in manager.pending_gates
        finally:
            loop.close()

    def test_reject_resolves_future_with_feedback(self):
        bus = EventBus()
        manager = GateManager(bus=bus)
        manager.start()

        loop = asyncio.new_event_loop()
        try:
            future = manager.request_gate(
                gate_id="g-001",
                run_id="run-abc",
                node="blueprint_approval_gate",
                title="Approve Blueprint",
                description="Review.",
                loop=loop,
            )

            bus.emit("gate.response", {
                "gate_id": "g-001",
                "approved": False,
                "feedback": "Needs more detail on auth.",
            })

            assert future.done()
            result = future.result()
            assert result["approved"] is False
            assert result["feedback"] == "Needs more detail on auth."
        finally:
            loop.close()

    def test_ignores_response_for_unknown_gate(self):
        bus = EventBus()
        manager = GateManager(bus=bus)
        manager.start()

        # Should not raise
        bus.emit("gate.response", {
            "gate_id": "nonexistent",
            "approved": True,
            "feedback": "",
        })

    def test_multiple_gates_resolved_independently(self):
        bus = EventBus()
        manager = GateManager(bus=bus)
        manager.start()

        loop = asyncio.new_event_loop()
        try:
            future_1 = manager.request_gate(
                gate_id="g-001",
                run_id="run-abc",
                node="blueprint_approval_gate",
                title="Approve Blueprint",
                description="Review.",
                loop=loop,
            )
            future_2 = manager.request_gate(
                gate_id="g-002",
                run_id="run-abc",
                node="push",
                title="Approve Push",
                description="Push?",
                loop=loop,
            )

            bus.emit("gate.response", {
                "gate_id": "g-002",
                "approved": True,
                "feedback": "",
            })

            assert future_2.done()
            assert not future_1.done()
            assert "g-001" in manager.pending_gates
            assert "g-002" not in manager.pending_gates
        finally:
            loop.close()


class TestGateManagerCancelGate:
    """cancel_gate() cancels a pending future."""

    def test_cancel_gate_cancels_future(self):
        bus = EventBus()
        manager = GateManager(bus=bus)
        manager.start()

        loop = asyncio.new_event_loop()
        try:
            future = manager.request_gate(
                gate_id="g-001",
                run_id="run-abc",
                node="push",
                title="Approve Push",
                description="Push?",
                loop=loop,
            )

            manager.cancel_gate("g-001")

            assert future.cancelled()
            assert "g-001" not in manager.pending_gates
        finally:
            loop.close()

    def test_cancel_nonexistent_gate_is_noop(self):
        bus = EventBus()
        manager = GateManager(bus=bus)
        manager.start()
        # Should not raise
        manager.cancel_gate("nonexistent")

    def test_cancel_all_gates(self):
        bus = EventBus()
        manager = GateManager(bus=bus)
        manager.start()

        loop = asyncio.new_event_loop()
        try:
            f1 = manager.request_gate(
                gate_id="g-001", run_id="run-abc", node="push",
                title="T1", description="D1", loop=loop,
            )
            f2 = manager.request_gate(
                gate_id="g-002", run_id="run-abc", node="push",
                title="T2", description="D2", loop=loop,
            )

            manager.cancel_all_gates()

            assert f1.cancelled()
            assert f2.cancelled()
            assert manager.pending_gates == {}
        finally:
            loop.close()
