import os
from unittest.mock import patch, MagicMock
from agent.repl import UniversalREPL

@patch("agent.repl.PromptSession")
@patch("agent.repl.os.makedirs")
@patch("agent.repl.os.getenv")
def test_history_initialization(mock_getenv, mock_makedirs, mock_prompt_session):
    mock_getenv.return_value = None
    mock_instance = MagicMock()
    mock_instance.prompt.side_effect = EOFError()
    mock_prompt_session.return_value = mock_instance

    try:
        UniversalREPL.start_interactive_session()
    except EOFError:
        pass # Expected since we mock prompt to exit immediately, or if the REPL catches it, it's fine

    expected_path = os.path.expanduser("~/.config/lios")
    mock_makedirs.assert_called_with(expected_path, exist_ok=True)

    call_kwargs = mock_prompt_session.call_args[1]
    assert "history" in call_kwargs
    assert "lexer" in call_kwargs
    assert "style" in call_kwargs

@patch("agent.repl.PromptSession")
@patch("agent.repl.os.makedirs")
@patch("agent.repl.os.getenv")
def test_history_initialization_with_xdg(mock_getenv, mock_makedirs, mock_prompt_session):
    mock_getenv.return_value = "/tmp/custom_config"
    mock_instance = MagicMock()
    mock_instance.prompt.side_effect = EOFError()
    mock_prompt_session.return_value = mock_instance

    try:
        UniversalREPL.start_interactive_session()
    except EOFError:
        pass

    expected_path = "/tmp/custom_config/lios"
    mock_makedirs.assert_called_with(expected_path, exist_ok=True)
