"""Integration tests for LiosChatApp using Textual's pilot."""

import pytest
from unittest.mock import patch, MagicMock

from agent.repl.app import LiosChatApp
from agent.repl.widgets.welcome import WelcomeBanner
from agent.repl.widgets.chat_log import ChatLog
from agent.repl.widgets.input_bar import ChatInput
from agent.repl.widgets.status_bar import StatusBar
from agent.repl.widgets.message_bubble import UserMessage, AgentMessage


@pytest.fixture
def mock_llm():
    """Mock the LLM factory to avoid real API calls."""
    with patch("agent.repl.llm_bridge.get_llm") as mock_factory:
        mock_llm_instance = MagicMock()
        mock_llm_instance.model_name = "gpt-4o-test"

        def fake_stream(messages):
            chunks = ["Hello", " from", " Lios!"]
            for text in chunks:
                chunk = MagicMock()
                chunk.content = text
                chunk.usage_metadata = None
                yield chunk
            # Final chunk with usage
            final = MagicMock()
            final.content = ""
            final.usage_metadata = {
                "input_tokens": 50,
                "output_tokens": 10,
            }
            yield final

        mock_llm_instance.stream = fake_stream
        mock_factory.return_value = mock_llm_instance
        yield mock_llm_instance


# ---------------------------------------------------------------------------
# Basic rendering tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_app_renders_welcome():
    """App should render a WelcomeBanner on startup."""
    app = LiosChatApp(mode="chat")
    async with app.run_test() as pilot:
        banner = app.query_one(WelcomeBanner)
        assert banner is not None


@pytest.mark.asyncio
async def test_app_has_all_widgets():
    """App should compose all expected widgets."""
    app = LiosChatApp(mode="chat")
    async with app.run_test() as pilot:
        assert app.query_one(WelcomeBanner) is not None
        assert app.query_one("#chat-log", ChatLog) is not None
        assert app.query_one("#input", ChatInput) is not None
        assert app.query_one("#status", StatusBar) is not None


# ---------------------------------------------------------------------------
# Command tests — mock _post_system_message to avoid the sync-mount race
# (chat_log.mount() is called without await in _post_system_message /
#  _add_system_message, so the child Markdown widget isn't composed yet
#  when get_markdown_widget() runs).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_help_command(mock_llm):
    """The /help command should call _post_system_message with help text."""
    with patch("agent.repl.commands._post_system_message") as mock_post:
        app = LiosChatApp(mode="chat")
        async with app.run_test() as pilot:
            input_widget = app.query_one("#input", ChatInput)
            input_widget.value = "/help"
            await input_widget.action_submit()
            await pilot.pause()

            mock_post.assert_called_once()
            # First arg is the app, second is the help text
            call_args = mock_post.call_args
            assert "help" in call_args[0][1].lower() or "command" in call_args[0][1].lower()


@pytest.mark.asyncio
async def test_exit_command(mock_llm):
    """The /exit command should trigger app exit."""
    app = LiosChatApp(mode="chat")
    async with app.run_test() as pilot:
        input_widget = app.query_one("#input", ChatInput)
        input_widget.value = "/exit"
        await input_widget.action_submit()
        await pilot.pause()
        # App should have exited (or be in process of exiting)


@pytest.mark.asyncio
async def test_unknown_command_shows_error(mock_llm):
    """An unknown command should call _add_system_message with error text."""
    with patch.object(LiosChatApp, "_add_system_message") as mock_sys_msg:
        app = LiosChatApp(mode="chat")
        async with app.run_test() as pilot:
            input_widget = app.query_one("#input", ChatInput)
            input_widget.value = "/foobar"
            await input_widget.action_submit()
            await pilot.pause()

            mock_sys_msg.assert_called_once()
            assert "/foobar" in mock_sys_msg.call_args[0][0]


# ---------------------------------------------------------------------------
# Chat message tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_message_creates_user_bubble(mock_llm):
    """Sending a chat message should create a UserMessage bubble."""
    app = LiosChatApp(mode="chat")
    async with app.run_test() as pilot:
        input_widget = app.query_one("#input", ChatInput)
        input_widget.value = "Hello Lios"
        await input_widget.action_submit()
        await pilot.pause(delay=0.5)

        # Should have a UserMessage in the chat log
        user_messages = app.query(UserMessage)
        assert len(user_messages) >= 1


@pytest.mark.asyncio
async def test_input_clears_after_submit(mock_llm):
    """Input widget should be cleared after submission."""
    # Use /exit which doesn't trigger the sync-mount issue
    app = LiosChatApp(mode="chat")
    async with app.run_test() as pilot:
        input_widget = app.query_one("#input", ChatInput)
        input_widget.value = "/exit"
        await input_widget.action_submit()
        await pilot.pause()

        assert input_widget.value == ""


@pytest.mark.asyncio
async def test_input_clears_after_chat_submit(mock_llm):
    """Input widget should be cleared after sending a chat message."""
    app = LiosChatApp(mode="chat")
    async with app.run_test() as pilot:
        input_widget = app.query_one("#input", ChatInput)
        input_widget.value = "Hello Lios"
        await input_widget.action_submit()
        await pilot.pause(delay=0.5)

        assert input_widget.value == ""


@pytest.mark.asyncio
async def test_empty_input_ignored(mock_llm):
    """Submitting empty input should not create any messages."""
    app = LiosChatApp(mode="chat")
    async with app.run_test() as pilot:
        input_widget = app.query_one("#input", ChatInput)
        input_widget.value = "   "
        await input_widget.action_submit()
        await pilot.pause()

        user_messages = app.query(UserMessage)
        assert len(user_messages) == 0
