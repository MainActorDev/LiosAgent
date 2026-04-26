import pytest
from unittest.mock import patch, MagicMock

@patch('agent.repl.legacy.webview')
@patch('agent.repl.legacy.threading')
def test_start_interactive_session_spawns_server_and_webview(mock_threading, mock_webview):
    from agent.repl.legacy import UniversalREPL
    
    mock_thread = MagicMock()
    mock_threading.Thread.return_value = mock_thread
    
    with patch('agent.repl.legacy.time.sleep'):
        UniversalREPL.start_interactive_session()
        
    mock_threading.Thread.assert_called_once()
    assert mock_threading.Thread.call_args[1]['daemon'] is True
    # The target should be start_server (or something similar depending on implementation)
    mock_thread.start.assert_called_once()
    
    mock_webview.create_window.assert_called_once_with(
        'Lios-Agent', 
        'http://127.0.0.1:8123',
        width=1200, 
        height=800,
        background_color='#0a0a0c'
    )
    mock_webview.start.assert_called_once()
