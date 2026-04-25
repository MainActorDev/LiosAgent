"""Main Textual application for the Lios TUI REPL."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.worker import Worker, get_current_worker

from agent.repl.theme import APP_CSS
from agent.repl.widgets.welcome import WelcomeBanner
from agent.repl.widgets.chat_log import ChatLog
from agent.repl.widgets.message_bubble import (
    AgentMessage,
    ThinkingIndicator,
    UserMessage,
)
from agent.repl.widgets.input_bar import ChatInput
from agent.repl.widgets.status_bar import StatusBar
from agent.repl.llm_bridge import LLMBridge, SYSTEM_PROMPT, INTAKE_SYSTEM_PROMPT
from agent.repl.parse_input import parse_input
from agent.repl.commands import is_command, route_command


class LiosChatApp(App):
    """Textual TUI for the Lios-Agent interactive REPL."""

    CSS = APP_CSS

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("ctrl+l", "clear_chat", "Clear", show=False),
    ]

    def __init__(
        self,
        mode: str = "chat",
        epic_name: str = "",
        workspace_root: str = ".",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.mode = mode
        self.epic_name = epic_name
        self.workspace_root = workspace_root
        self.llm_bridge = LLMBridge()
        self._intake_result: str = ""

    def compose(self) -> ComposeResult:
        yield WelcomeBanner()
        yield ChatLog(id="chat-log")
        yield ChatInput(id="input")
        yield StatusBar(id="status")

    def on_mount(self) -> None:
        """Initialize LLM bridge and set up the system prompt."""
        if self.mode == "chat":
            self.llm_bridge.add_system_prompt(SYSTEM_PROMPT)
        elif self.mode == "intake":
            self.llm_bridge.add_system_prompt(INTAKE_SYSTEM_PROMPT)

        # Focus the input
        self.query_one("#input").focus()

    async def on_input_submitted(self, event: ChatInput.Submitted) -> None:
        """Handle user input submission."""
        text = event.value.strip()
        if not text:
            return

        # Clear the input
        input_widget = self.query_one("#input", ChatInput)
        input_widget.value = ""

        # Handle commands
        if is_command(text):
            result = route_command(text, self)
            if result == "unknown":
                self._add_system_message(f"Unknown command: `{text.split()[0]}`")
            return

        # Handle intake /done
        if self.mode == "intake" and text.strip() in ("/exit", "/done"):
            self.exit(result=self._intake_result)
            return

        # Parse @file mentions
        processed_text, attachments = parse_input(text, self.workspace_root)

        # Add user message to chat log
        chat_log = self.query_one("#chat-log", ChatLog)
        user_msg = UserMessage(text, attachments=attachments)
        await chat_log.mount(user_msg)

        # Add thinking indicator
        thinking = ThinkingIndicator(id="thinking")
        await chat_log.mount(thinking)
        chat_log.scroll_end(animate=False)

        # Add to LLM history and start streaming
        self.llm_bridge.add_user_message(processed_text)
        self._stream_response()

    def _stream_response(self) -> None:
        """Start the streaming worker."""
        self.run_worker(self._do_stream, thread=True)

    def _do_stream(self) -> None:
        """Run LLM streaming in a background thread."""
        worker = get_current_worker()

        # Create agent message widget
        model_name = self.llm_bridge.model_name
        agent_msg = AgentMessage(model_name=model_name)

        # Mount agent message and connect status bar (from thread)
        self.call_from_thread(self._mount_agent_message, agent_msg)

        # Stream tokens
        full_response = ""
        first_token = True

        for chunk in self.llm_bridge.stream():
            if worker.is_cancelled:
                break

            full_response += chunk

            if first_token:
                # Remove thinking indicator
                self.call_from_thread(self._remove_thinking)
                first_token = False

            # Update the markdown widget
            self.call_from_thread(self._update_agent_markdown, agent_msg, full_response)

        # Add AI message to history
        self.llm_bridge.add_ai_message(full_response)

        # Update status bar
        self.call_from_thread(self._update_status_bar)

        # For intake mode, accumulate context
        if self.mode == "intake":
            self._intake_result += f"User: {self.llm_bridge.history[-2].content}\n\n"
            self._intake_result += f"Agent: {full_response}\n\n"

            if "READY_TO_ARCHITECT" in full_response:
                self.call_from_thread(self.exit, self._intake_result)

    def _mount_agent_message(self, agent_msg: AgentMessage) -> None:
        """Mount agent message widget (must be called from main thread)."""
        chat_log = self.query_one("#chat-log", ChatLog)
        chat_log.mount(agent_msg)
        chat_log.scroll_end(animate=False)

        # Update status bar connection
        status = self.query_one("#status", StatusBar)
        status.set_connected(self.llm_bridge.model_name)

    def _remove_thinking(self) -> None:
        """Remove the thinking indicator (must be called from main thread)."""
        try:
            thinking = self.query_one("#thinking", ThinkingIndicator)
            thinking.remove()
        except Exception:
            pass

    def _update_agent_markdown(self, agent_msg: AgentMessage, content: str) -> None:
        """Update the agent message markdown (must be called from main thread)."""
        try:
            md_widget = agent_msg.get_markdown_widget()
            md_widget.update(content)
            chat_log = self.query_one("#chat-log", ChatLog)
            chat_log.scroll_end(animate=False)
        except Exception:
            pass

    def _update_status_bar(self) -> None:
        """Update status bar with latest token/cost stats (main thread)."""
        status = self.query_one("#status", StatusBar)
        status.update_stats(
            self.llm_bridge.total_tokens,
            self.llm_bridge.total_cost,
        )

    def _add_system_message(self, text: str) -> None:
        """Add a system message to the chat log."""
        from agent.repl.widgets.message_bubble import AgentMessage

        chat_log = self.query_one("#chat-log", ChatLog)
        msg = AgentMessage(model_name="system")
        chat_log.mount(msg)
        msg.get_markdown_widget().update(text)

    def action_clear_chat(self) -> None:
        """Clear the chat log."""
        chat_log = self.query_one("#chat-log", ChatLog)
        chat_log.remove_children()

    def action_quit(self) -> None:
        """Quit the application."""
        self.exit()
