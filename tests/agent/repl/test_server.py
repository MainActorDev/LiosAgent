import pytest
from fastapi.testclient import TestClient
from agent.repl.server import app
from fastapi.websockets import WebSocketDisconnect

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert "Lios" in response.text or "html" in response.text.lower()

def test_websocket_echo():
    with client.websocket_connect("/ws/chat") as websocket:
        websocket.send_json({"text": "Hello"})
        data = websocket.receive_json()
        assert data["text"] == "Echo: Hello"
