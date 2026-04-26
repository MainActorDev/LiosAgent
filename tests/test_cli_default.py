from typer.testing import CliRunner
from cli import app

runner = CliRunner()

def test_default_invocation_calls_repl(mocker):
    # Mock the REPL to avoid actual prompt blocking
    mock_repl = mocker.patch("cli.UniversalREPL.start_interactive_session", create=True)
    
    result = runner.invoke(app)
    
    # Assert the mock was called
    mock_repl.assert_called_once()
    assert result.exit_code == 0
