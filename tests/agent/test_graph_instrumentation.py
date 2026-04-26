"""Tests for graph node instrumentation with event emission."""
import pytest
from unittest.mock import MagicMock, patch
from agent.event_bus import EventBus
from agent.graph_events import GraphEventEmitter


class TestWrapNodeWithEvents:
    """Test the _wrap_node_with_events helper."""

    def test_sync_node_emits_enter_and_exit(self):
        from agent.graph import _wrap_node_with_events

        bus = EventBus()
        emitter = GraphEventEmitter(bus)
        events = []
        bus.on("graph.*", lambda e: events.append(e))

        def fake_node(state):
            return {"history": ["did something"]}

        wrapped = _wrap_node_with_events(fake_node, "planner", emitter, "run-1")
        result = wrapped({"history": []})

        assert result == {"history": ["did something"]}
        assert len(events) == 2
        assert events[0].type == "graph.node_enter"
        assert events[0].payload["node"] == "planner"
        assert events[1].type == "graph.node_exit"
        assert events[1].payload["node"] == "planner"
        assert events[1].payload["status"] == "completed"
        assert events[1].payload["duration_ms"] >= 0

    def test_async_node_emits_enter_and_exit(self):
        import asyncio
        from agent.graph import _wrap_node_with_events

        bus = EventBus()
        emitter = GraphEventEmitter(bus)
        events = []
        bus.on("graph.*", lambda e: events.append(e))

        async def fake_async_node(state):
            return {"history": ["async result"]}

        wrapped = _wrap_node_with_events(fake_async_node, "context_aggregator", emitter, "run-2")
        result = asyncio.run(wrapped({"history": []}))

        assert result == {"history": ["async result"]}
        assert len(events) == 2
        assert events[0].type == "graph.node_enter"
        assert events[1].type == "graph.node_exit"

    def test_node_error_emits_error_event(self):
        from agent.graph import _wrap_node_with_events

        bus = EventBus()
        emitter = GraphEventEmitter(bus)
        events = []
        bus.on("graph.*", lambda e: events.append(e))

        def failing_node(state):
            raise ValueError("something broke")

        wrapped = _wrap_node_with_events(failing_node, "validator", emitter, "run-3")

        with pytest.raises(ValueError, match="something broke"):
            wrapped({"history": []})

        assert len(events) == 2
        assert events[0].type == "graph.node_enter"
        assert events[1].type == "graph.node_exit"
        assert events[1].payload["status"] == "error"

    def test_no_emitter_passthrough(self):
        from agent.graph import _wrap_node_with_events

        def fake_node(state):
            return {"history": ["ok"]}

        wrapped = _wrap_node_with_events(fake_node, "planner", None, "run-4")
        result = wrapped({"history": []})
        assert result == {"history": ["ok"]}


class TestBuildGraphWithEmitter:
    """Test that build_graph accepts event_emitter parameter."""

    @patch("agent.graph.get_llm")
    def test_build_graph_accepts_emitter(self, mock_llm):
        mock_llm.return_value = MagicMock()

        from agent.graph import build_graph

        bus = EventBus()
        emitter = GraphEventEmitter(bus)
        # Should not raise
        graph = build_graph(checkpointer=None, event_emitter=emitter)
        assert graph is not None

    def test_build_graph_works_without_emitter(self):
        """Backward compatibility — no emitter means no instrumentation."""
        from agent.graph import build_graph

        # Should not raise (existing behavior)
        graph = build_graph(checkpointer=None)
        assert graph is not None
