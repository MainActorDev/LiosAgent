"""Unit tests for agent.event_bus."""

import time
from agent.event_bus import Event, EventBus


# ------------------------------------------------------------------
# Event dataclass
# ------------------------------------------------------------------

class TestEvent:
    def test_defaults(self):
        e = Event(type="chat.chunk")
        assert e.type == "chat.chunk"
        assert e.payload == {}
        assert isinstance(e.timestamp, float)
        assert len(e.correlation_id) == 12

    def test_custom_payload(self):
        e = Event(type="tool.start", payload={"name": "grep"}, correlation_id="abc")
        assert e.payload == {"name": "grep"}
        assert e.correlation_id == "abc"

    def test_to_dict(self):
        e = Event(type="x", payload={"k": 1}, timestamp=1.0, correlation_id="cid")
        d = e.to_dict()
        assert d == {
            "type": "x",
            "payload": {"k": 1},
            "timestamp": 1.0,
            "correlation_id": "cid",
        }


# ------------------------------------------------------------------
# EventBus — basic subscribe / emit
# ------------------------------------------------------------------

class TestEventBusBasic:
    def test_exact_match(self):
        bus = EventBus()
        received = []
        bus.on("chat.chunk", lambda e: received.append(e))
        bus.emit("chat.chunk", {"text": "hi"})
        assert len(received) == 1
        assert received[0].payload == {"text": "hi"}

    def test_no_match(self):
        bus = EventBus()
        received = []
        bus.on("chat.chunk", lambda e: received.append(e))
        bus.emit("tool.start")
        assert received == []

    def test_multiple_subscribers(self):
        bus = EventBus()
        a, b = [], []
        bus.on("x", lambda e: a.append(1))
        bus.on("x", lambda e: b.append(1))
        bus.emit("x")
        assert len(a) == 1
        assert len(b) == 1


# ------------------------------------------------------------------
# Wildcard matching
# ------------------------------------------------------------------

class TestWildcard:
    def test_star_suffix(self):
        bus = EventBus()
        received = []
        bus.on("chat.*", lambda e: received.append(e.type))
        bus.emit("chat.chunk")
        bus.emit("chat.done")
        bus.emit("tool.start")
        assert received == ["chat.chunk", "chat.done"]

    def test_global_wildcard(self):
        bus = EventBus()
        received = []
        bus.on("*", lambda e: received.append(e.type))
        bus.emit("chat.chunk")
        bus.emit("tool.start")
        assert len(received) == 2

    def test_star_does_not_match_nested(self):
        """fnmatch '*' does not match dots by default — but in our
        event taxonomy dots are part of the name, so '*' matches everything."""
        bus = EventBus()
        received = []
        bus.on("*", lambda e: received.append(e.type))
        bus.emit("a.b.c")
        # fnmatch("a.b.c", "*") is True
        assert received == ["a.b.c"]


# ------------------------------------------------------------------
# once()
# ------------------------------------------------------------------

class TestOnce:
    def test_fires_once(self):
        bus = EventBus()
        received = []
        bus.once("done", lambda e: received.append(1))
        bus.emit("done")
        bus.emit("done")
        assert received == [1]

    def test_once_unsubscribes(self):
        bus = EventBus()
        initial = bus.subscriber_count
        bus.once("x", lambda e: None)
        assert bus.subscriber_count == initial + 1
        bus.emit("x")
        assert bus.subscriber_count == initial


# ------------------------------------------------------------------
# off()
# ------------------------------------------------------------------

class TestOff:
    def test_unsubscribe(self):
        bus = EventBus()
        received = []
        sid = bus.on("x", lambda e: received.append(1))
        bus.emit("x")
        bus.off(sid)
        bus.emit("x")
        assert received == [1]

    def test_off_returns_false_for_unknown(self):
        bus = EventBus()
        assert bus.off("nonexistent") is False

    def test_off_returns_true(self):
        bus = EventBus()
        sid = bus.on("x", lambda e: None)
        assert bus.off(sid) is True


# ------------------------------------------------------------------
# emit() return value
# ------------------------------------------------------------------

class TestEmitReturn:
    def test_returns_event(self):
        bus = EventBus()
        event = bus.emit("chat.chunk", {"text": "hi"})
        assert isinstance(event, Event)
        assert event.type == "chat.chunk"
        assert event.payload == {"text": "hi"}

    def test_custom_correlation_id(self):
        bus = EventBus()
        event = bus.emit("x", correlation_id="my-id")
        assert event.correlation_id == "my-id"


# ------------------------------------------------------------------
# Edge cases
# ------------------------------------------------------------------

class TestEdgeCases:
    def test_callback_can_subscribe(self):
        """Subscribing inside a callback should not cause issues."""
        bus = EventBus()
        inner_received = []

        def outer(e):
            bus.on("y", lambda e2: inner_received.append(e2.type))

        bus.on("x", outer)
        bus.emit("x")
        bus.emit("y")
        assert inner_received == ["y"]

    def test_callback_can_unsubscribe_self(self):
        bus = EventBus()
        received = []
        sid_holder = [None]

        def cb(e):
            received.append(1)
            bus.off(sid_holder[0])

        sid_holder[0] = bus.on("x", cb)
        bus.emit("x")
        bus.emit("x")
        assert received == [1]

    def test_empty_bus_emit(self):
        """Emitting with no subscribers should not raise."""
        bus = EventBus()
        event = bus.emit("anything")
        assert event.type == "anything"

    def test_subscriber_count(self):
        bus = EventBus()
        assert bus.subscriber_count == 0
        s1 = bus.on("a", lambda e: None)
        s2 = bus.on("b", lambda e: None)
        assert bus.subscriber_count == 2
        bus.off(s1)
        assert bus.subscriber_count == 1
