import os
from unittest.mock import patch, MagicMock
from agent.repl import UniversalREPL

@patch("agent.repl.PromptSession")
@patch("agent.repl.os.makedirs")
def test_history_initialization(mock_makedirs, mock_prompt_session):
    # Setup mock to immediately raise EOFError to exit the loop
    mock_instance = MagicMock()
    mock_instance.prompt.side_effect = EOFError()
    mock_prompt_session.return_value = mock_instance
    
    try:
        UniversalREPL.start_interactive_session()
    except EOFError:
        pass # Expected since we mock prompt to exit immediately, or if the REPL catches it, it's fine
    
    # Verify os.makedirs was called to ensure ~/.config/lios exists
    expected_path = os.path.expanduser("~/.config/lios")
    mock_makedirs.assert_called_with(expected_path, exist_ok=True)
    
    # Verify PromptSession was called with history and lexer args
    call_kwargs = mock_prompt_session.call_args[1]
    assert "history" in call_kwargs
    assert "lexer" in call_kwargs
    assert "style" in call_kwargs
