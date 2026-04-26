"""Tests for Textual app widget composition (replaces old PromptSession tests)."""

import pytest
from agent.repl import UniversalREPL, FileMentionCompleter, LiosLexer


def test_repl_imports_are_available():
    """Verify backward-compatible imports still work."""
    assert UniversalREPL is not None
    assert FileMentionCompleter is not None
    assert LiosLexer is not None


def test_universal_repl_has_expected_methods():
    """Verify the facade exposes all expected static methods."""
    assert callable(UniversalREPL.start_interactive_session)
    assert callable(UniversalREPL.interactive_intake_session)
    assert callable(UniversalREPL.single_prompt)
    assert callable(UniversalREPL.parse_input)
    assert callable(UniversalREPL.print_agent_message)


def test_app_composes_expected_widgets():
    """Verify LiosChatApp composes the required widget tree."""
    from agent.repl.app import LiosChatApp
    from agent.repl.widgets.welcome import WelcomeBanner
    from agent.repl.widgets.chat_log import ChatLog
    from agent.repl.widgets.input_bar import ChatInput
    from agent.repl.widgets.status_bar import StatusBar

    app = LiosChatApp(mode="chat")

    # Use Textual's pilot for headless testing
    async def check_widgets():
        async with app.run_test() as pilot:
            assert app.query_one(WelcomeBanner) is not None
            assert app.query_one("#chat-log", ChatLog) is not None
            assert app.query_one("#input", ChatInput) is not None
            assert app.query_one("#status", StatusBar) is not None

    import asyncio
    asyncio.run(check_widgets())
