import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch


client = None


def _get_client():
    """Lazy-import to allow patching before module-level side effects."""
    global client
    if client is None:
        from agent.repl.server import app
        client = TestClient(app)
    return client


def test_read_main():
    c = _get_client()
    response = c.get("/")
    assert response.status_code == 200
    assert "Lios" in response.text or "html" in response.text.lower()


def _make_mock_bridge():
    """Create a mock LLMBridge with default stats."""
    mock = MagicMock()
    mock.model_name = "test-model"
    mock.total_input_tokens = 0
    mock.total_output_tokens = 0
    mock.total_tokens = 0
    mock.total_cost = 0.0

    def mock_stream():
        yield "Hello"
        yield " "
        yield "World"
        mock.total_tokens = 2
        mock.total_cost = 0.001

    mock.stream = mock_stream
    return mock


def test_websocket_new_protocol():
    """Test the new event-based WS protocol on /ws."""
    mock_bridge = _make_mock_bridge()

    with patch("agent.repl.llm_bridge.LLMBridge", return_value=mock_bridge):
        c = _get_client()
        # Patch the ws_manager's bridge cache so it returns our mock
        from agent.repl.server import ws_manager
        ws_manager._bridges.clear()

        with c.websocket_connect("/ws") as ws:
            # Expect initial stats event envelope
            init = ws.receive_json()
            assert init["type"] == "event"
            assert init["event_type"] == "system.stats_update"
            assert init["payload"]["model"] == "test-model"

            # Send using new command protocol
            ws.send_json({
                "type": "command",
                "command": "chat.send",
                "payload": {"text": "Hello"},
            })

            # Collect event envelopes for chat.chunk, chat.done, system.stats_update
            events = []
            for _ in range(5):  # 3 chunks + done + stats
                events.append(ws.receive_json())

            chunk_events = [e for e in events if e.get("event_type") == "chat.chunk"]
            assert len(chunk_events) == 3
            assert chunk_events[0]["payload"]["text"] == "Hello"
            assert chunk_events[1]["payload"]["text"] == " "
            assert chunk_events[2]["payload"]["text"] == "World"

            done_events = [e for e in events if e.get("event_type") == "chat.done"]
            assert len(done_events) == 1

            stats_events = [e for e in events if e.get("event_type") == "system.stats_update"]
            assert len(stats_events) == 1
            assert stats_events[0]["payload"]["total_tokens"] == 2

            mock_bridge.add_user_message.assert_called_once_with("Hello")


def test_websocket_legacy_protocol():
    """Test backwards-compatible legacy {text} format on /ws/chat."""
    mock_bridge = _make_mock_bridge()

    with patch("agent.repl.llm_bridge.LLMBridge", return_value=mock_bridge):
        c = _get_client()
        from agent.repl.server import ws_manager
        ws_manager._bridges.clear()

        with c.websocket_connect("/ws/chat") as ws:
            # Expect initial stats event
            init = ws.receive_json()
            assert init["type"] == "event"
            assert init["event_type"] == "system.stats_update"

            # Send using legacy format
            ws.send_json({"text": "Hello"})

            events = []
            for _ in range(5):
                events.append(ws.receive_json())

            chunk_events = [e for e in events if e.get("event_type") == "chat.chunk"]
            assert len(chunk_events) == 3
            assert chunk_events[0]["payload"]["text"] == "Hello"

            mock_bridge.add_user_message.assert_called_once_with("Hello")
