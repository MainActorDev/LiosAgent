import pytest
from fastapi.testclient import TestClient
from agent.repl.server import app
from fastapi.websockets import WebSocketDisconnect
from unittest.mock import MagicMock, patch
import asyncio

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert "Lios" in response.text or "html" in response.text.lower()

def test_websocket_llm_stream():
    # We will mock the LLMBridge class so that we can intercept instantiations per connection.
    mock_llm_agent = MagicMock()
    mock_llm_agent.model_name = "test-model"
    mock_llm_agent.total_input_tokens = 0
    mock_llm_agent.total_output_tokens = 0
    mock_llm_agent.total_tokens = 0
    mock_llm_agent.total_cost = 0.0
    
    def mock_stream():
        yield "Hello"
        yield " "
        yield "World"
        
        # Simulate stats update after streaming
        mock_llm_agent.total_tokens = 2
        mock_llm_agent.total_cost = 0.001
        
    mock_llm_agent.stream = mock_stream
    mock_add_msg = MagicMock()
    mock_llm_agent.add_user_message = mock_add_msg

    with patch("agent.repl.server.LLMBridge", return_value=mock_llm_agent):
        with client.websocket_connect("/ws/chat") as websocket:
            # Expect initial stats
            init_stats = websocket.receive_json()
            assert init_stats["type"] == "stats"
            assert init_stats["model"] == "test-model"
            
            websocket.send_json({"text": "Hello"})
            
            data1 = websocket.receive_json()
            assert data1["text"] == "Hello"
            assert data1["type"] == "chunk"
            
            data2 = websocket.receive_json()
            assert data2["text"] == " "
            assert data2["type"] == "chunk"
            
            data3 = websocket.receive_json()
            assert data3["text"] == "World"
            assert data3["type"] == "chunk"
            
            # Expect final stats
            final_stats = websocket.receive_json()
            assert final_stats["type"] == "stats"
            assert final_stats["total_tokens"] == 2
            
            # Check that add_user_message was called on the mock instance created per connection
            mock_add_msg.assert_called_once_with("Hello")

