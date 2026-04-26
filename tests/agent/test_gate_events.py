"""Tests for GateEventEmitter – typed facade for gate.* events."""

import pytest

from agent.event_bus import EventBus
from agent.gate_events import GateEventEmitter


class TestGateEventEmitterRequest:
    """gate.request event emission."""

    def test_emits_gate_request_with_payload(self):
        bus = EventBus()
        emitter = GateEventEmitter(bus=bus)
        received = []
        bus.on("gate.request", lambda e: received.append(e))

        emitter.request(
            gate_id="g-001",
            run_id="run-abc",
            node="blueprint_approval_gate",
            title="Approve Blueprint",
            description="Review the generated blueprint before proceeding.",
        )

        assert len(received) == 1
        evt = received[0]
        assert evt.type == "gate.request"
        assert evt.payload["gate_id"] == "g-001"
        assert evt.payload["run_id"] == "run-abc"
        assert evt.payload["node"] == "blueprint_approval_gate"
        assert evt.payload["title"] == "Approve Blueprint"
        assert evt.payload["description"] == "Review the generated blueprint before proceeding."
        assert evt.correlation_id == "run-abc"

    def test_emits_gate_request_with_optional_context(self):
        bus = EventBus()
        emitter = GateEventEmitter(bus=bus)
        received = []
        bus.on("gate.request", lambda e: received.append(e))

        emitter.request(
            gate_id="g-002",
            run_id="run-xyz",
            node="push",
            title="Approve Push",
            description="Push changes to remote?",
            context={"branch": "feat/login", "files_changed": 5},
        )

        assert received[0].payload["context"] == {"branch": "feat/login", "files_changed": 5}

    def test_emits_gate_request_without_context_defaults_to_empty(self):
        bus = EventBus()
        emitter = GateEventEmitter(bus=bus)
        received = []
        bus.on("gate.request", lambda e: received.append(e))

        emitter.request(
            gate_id="g-003",
            run_id="run-123",
            node="await_clarification",
            title="Clarification Needed",
            description="Waiting for developer input.",
        )

        assert received[0].payload["context"] == {}


class TestGateEventEmitterResponse:
    """gate.response event emission."""

    def test_emits_gate_response_approved(self):
        bus = EventBus()
        emitter = GateEventEmitter(bus=bus)
        received = []
        bus.on("gate.response", lambda e: received.append(e))

        emitter.response(
            gate_id="g-001",
            run_id="run-abc",
            approved=True,
        )

        assert len(received) == 1
        evt = received[0]
        assert evt.type == "gate.response"
        assert evt.payload["gate_id"] == "g-001"
        assert evt.payload["approved"] is True
        assert evt.payload["feedback"] == ""
        assert evt.correlation_id == "run-abc"

    def test_emits_gate_response_rejected_with_feedback(self):
        bus = EventBus()
        emitter = GateEventEmitter(bus=bus)
        received = []
        bus.on("gate.response", lambda e: received.append(e))

        emitter.response(
            gate_id="g-001",
            run_id="run-abc",
            approved=False,
            feedback="Needs more error handling in the auth module.",
        )

        evt = received[0]
        assert evt.payload["approved"] is False
        assert evt.payload["feedback"] == "Needs more error handling in the auth module."


class TestGateEventEmitterNoBus:
    """No-op when bus is None."""

    def test_request_noop_without_bus(self):
        emitter = GateEventEmitter(bus=None)
        # Should not raise
        emitter.request(
            gate_id="g-001",
            run_id="run-abc",
            node="push",
            title="Test",
            description="Test",
        )

    def test_response_noop_without_bus(self):
        emitter = GateEventEmitter(bus=None)
        # Should not raise
        emitter.response(
            gate_id="g-001",
            run_id="run-abc",
            approved=True,
        )
