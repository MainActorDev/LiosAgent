# REPL Textual TUI Refactor — Design Spec

**Date:** 2026-04-25
**Goal:** Refactor `agent/repl.py` from Rich+prompt_toolkit to a Textual TUI application, achieving ~95% visual fidelity to the prototype in `docs/cli_ui_prototype.html`.

## Motivation

The current REPL uses Rich for output and prompt_toolkit for input. This combination cannot achieve:
- Layered backgrounds with distinct surface colors
- Persistent status bar during streaming output
- Left-border styling on agent message containers
- Coordinated layout (scrollable chat + fixed input + fixed status bar)

Textual provides a full TUI framework with CSS styling, widget composition, and built-in streaming markdown support.

## Architecture

### File Structure

```
agent/
  repl.py                    # Thin shim: re-exports from agent/repl/ for backward compat
  repl/
    __init__.py              # Re-exports: UniversalREPL, FileMentionCompleter, LiosLexer
    app.py                   # LiosChatApp(textual.App) — main application
    widgets/
      __init__.py
      chat_log.py            # ChatLog(VerticalScroll) — scrollable message container
      message_bubble.py      # UserMessage, AgentMessage, ThinkingIndicator
      input_bar.py           # ChatInput(Input) with highlighter + suggester
      status_bar.py          # StatusBar(Static) — model, tokens, cost
      welcome.py             # WelcomeBanner(Static)
    theme.py                 # Design tokens + APP_CSS string
    completer.py             # FileMentionCompleter (preserved API)
    lexer.py                 # LiosLexer (preserved API)
    parse_input.py           # parse_input() pure function (returns tuple: processed_text, attachments)
    llm_bridge.py            # Async streaming wrapper, token/cost tracking
    commands.py              # Command routing (/help, /exit, /epic, etc.)
    legacy.py                # UniversalREPL facade class
```

### Backward Compatibility

`agent/repl.py` becomes:
```python
from agent.repl import UniversalREPL, FileMentionCompleter, LiosLexer
```

All existing call sites (`from agent.repl import X`) continue to work unchanged.

## Design Tokens

From the prototype (`docs/cli_ui_prototype.html`):

| Token | Value | Usage |
|---|---|---|
| bg-deep | #0B1120 | Input area, status bar |
| bg-primary | #0F172A | Screen background |
| bg-surface | #1E293B | Code blocks, elevated surfaces |
| bg-elevated | #334155 | Agent message border, hover states |
| green | #22C55E | User chevron, connected indicator |
| cyan | #06B6D4 | @file mentions |
| purple | #A78BFA | Agent label, thinking indicator |
| amber | #F59E0B | /commands |
| red | #EF4444 | Error states |
| text-primary | #F8FAFC | Main text |
| text-secondary | #94A3B8 | Agent response body |
| text-muted | #64748B | Hints, metadata, status bar |

Terminal constraint: all text renders in the terminal's monospace font. The prototype's JetBrains Mono / IBM Plex Sans distinction is not achievable.

## Widgets

### WelcomeBanner (Static)
```
  ⬢  Lios Agent v0.4.2
  Type a message to chat, /help for commands, @ to mention files
```
- Green icon, bold white title, muted hint text
- Padding: 1 vertical, 2 horizontal

### ChatLog (VerticalScroll)
- Contains UserMessage, AgentMessage, ThinkingIndicator children
- Auto-scrolls to bottom via `.anchor()` when streaming
- `height: 1fr` — fills available space between welcome banner and input

### UserMessage (Static)
```
  ❯  Tell me about the auth module @src/auth.py
     📎 Attached src/auth.py (186 lines)
```
- Green chevron `❯` prefix
- Rich markup: cyan for @mentions within the text
- Optional file attachment line in muted text (shown when parse_input found @file)
- Padding: 0 vertical, 2 horizontal

### AgentMessage (Vertical container)
```
  │  ☀ LIOS · gpt-4o
  │  Response content in markdown...
```
- Left border: solid #334155
- Agent label: purple "☀ LIOS" + muted model name
- Content: Textual `Markdown` widget for rich rendering (headers, code blocks, lists)
- Padding-left: 2 (inside the border)
- Margin: 1 vertical

### ThinkingIndicator (Horizontal container)
- Textual `LoadingIndicator` (pulsating dots) + "Thinking..." label
- Muted text color (#64748B)
- Removed from DOM when first token arrives
- Padding-left: 2 to align with agent messages

### ChatInput (Input)
- Highlighter: `ChatInputHighlighter(Highlighter)` — colors `/commands` amber, `@file` cyan
- Suggester: `FileMentionSuggester(Suggester)` — wraps FileMentionCompleter logic, triggers on `@`, suggests file paths as ghost text
- Placeholder: "Type a message..." in muted
- Background: #0B1120 (bg-deep)
- Focus border: solid #22C55E (green)
- Submits on Enter

### StatusBar (Static, docked bottom)
```
  ● Connected · claude-opus-4                1,234 tokens · $0.05
```
- Left: green dot + "Connected" + model name
- Right: cumulative token count + cost (right-padded)
- Height: 1 line
- Background: #0B1120
- Text: #64748B (muted)
- Updated after each LM response

## LLM Bridge

`LLMBridge` class wraps `get_llm()` with:

### Streaming
- Uses LangChain ChatOpenAI `.stream()` which yields `AIMessageChunk` objects
- Each chunk's `.content` is yielded as a string
- Runs in a thread via Textual's `@work(thread=True)` to avoid blocking the UI event loop
- Chunks posted to UI thread via `self.app.call_from_thread()`

### Token/Cost Tracking
- Extracts `usage_metadata` from the final aggregated chunk (LangChain populates this with `input_tokens`, `output_tokens`)
- Maintains cumulative totals: `total_input_tokens`, `total_output_tokens`, `total_cost`
- Pricing table: dict mapping model name prefixes to per-token input/output costs
- Covers: gpt-4o, gpt-4o-mini, gpt-3.5-turbo, glm-4 (ZhipuAI)
- Unknown models: tokens tracked, cost shows $0.00

### State
- `history: list` — LangChain message objects (SystemMessage, HumanMessage, AIMessage)
- `model_name: str` — extracted from LLM instance
- Lazy initialization: LLM created on first message

## Command Routing

Extracted to `commands.py`:

| Command | Handler | Behavior |
|---|---|---|
| /help | handle_help | Show available commands in chat log |
| /exit, /quit | handle_exit | Call app.exit() |
| /epic | handle_epic | Launch epic creation flow |
| /story | handle_story | Launch story creation flow |
| /execute | handle_execute | Trigger agent graph execution |
| /board | handle_board | Show board status |

Each handler receives `(args: list[str], app: LiosChatApp)`.

Commands that launch sub-flows (/epic, /story, /execute) will need to integrate with the Textual app's event loop. For the initial implementation, these can suspend the TUI via `app.suspend()`, run the existing flow, then resume.

## App Lifecycle

### LiosChatApp

```python
class LiosChatApp(App):
    CSS = APP_CSS
    BINDINGS = [("ctrl+c", "quit", "Quit"), ("ctrl+l", "clear", "Clear")]

    def __init__(self, mode="chat", **kwargs):
        # mode: "chat" (main REPL) or "intake" (requirement refinement)
        self.llm_bridge = LLMBridge()
        self.mode = mode

    def compose(self):
        yield WelcomeBanner()
        yield ChatLog(id="chat-log")
        yield ChatInput(id="input")
        yield StatusBar(id="status")

    async def on_input_submitted(self, event):
        # 1. Route commands
        # 2. Parse @file mentions
        # 3. Add UserMessage to chat log
        # 4. Add ThinkingIndicator
        # 5. Start streaming worker

    @work(thread=True)
    def stream_response(self, processed_text):
        # 1. Build LangChain messages
        # 2. Stream via llm_bridge
        # 3. Post chunks to AgentMessage's Markdown widget
        # 4. Remove ThinkingIndicator on first chunk
        # 5. Update StatusBar with new token/cost stats
```

### Legacy Facade

`UniversalREPL` in `legacy.py` preserves the existing static method API:

- `start_interactive_session()` → `LiosChatApp(mode="chat").run()`
- `interactive_intake_session(epic_name, workspace_root)` → `LiosChatApp(mode="intake", ..).run()`
- `single_prompt(prompt_text, workspace_root)` → Kept as-is with Rich console (no TUI for single-turn)
- `parse_input(user_input, workspace_root)` → Delegates to `parse_input.parse_input()`. Minor API change: now returns `(processed_text: str, attachments: list[dict])` tuple instead of just the processed string. Each attachment dict has `{"path": str, "lines": int}` for display in UserMessage.
- `print_agent_message(message, title)` → Kept as-is for non-TUI contexts

## Dependencies

Add to `requirements.txt`:
```
textual>=0.50.0
```

prompt_toolkit remains as a dependency (used elsewhere in the project or by Textual internally). Rich remains (Textual depends on it).

## Test Strategy

### Preserved Tests (no changes needed)
- `tests/test_repl_completer.py` (5 tests) — imports `FileMentionCompleter` from `agent.repl`, which re-exports from `agent.repl.completer`
- `tests/test_repl_lexer.py` (1 test) — imports `LiosLexer` from `agent.repl`, which re-exports from `agent.repl.lexer`

### Updated Tests
- `tests/test_repl_history.py` (2 tests) — currently tests PromptSession initialization. Must be rewritten to test Textual app widget composition (verify ChatInput, StatusBar, ChatLog exist).

### New Tests
- `tests/test_repl_parse_input.py` — test parse_input() as a pure function
- `tests/test_repl_commands.py` — test command routing
- `tests/test_repl_llm_bridge.py` — test token/cost accumulation with mocked LLM
- `tests/test_repl_app.py` — Textual pilot tests for chat flow integration

## Scope Exclusions
- Tool use indicators (REPL chat doesn't invoke tools)
- Sidebar / conversation list (GUI-only in prototype)
- Autocomplete dropdown popup (using ghost-text suggestion instead — achievable with Textual's Suggester)
- Multi-line input editing (single-line Input widget is sufficient for chat)
