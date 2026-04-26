# Web UI Full Execution Interface Design

## Goal

Transform the Lios Web UI from a simple chat prototype into a full-featured execution dashboard capable of driving the entire agent pipeline — graph execution, HITL gates, tool calls, file diffs, simulation results — all through a unified event-driven architecture.

## Architecture Overview

### Event Bus (Backend)

A synchronous, in-process pub/sub system that decouples all agent subsystems.

```python
@dataclass
class Event:
    type: str           # e.g. "chat.chunk", "gate.request", "tool.start"
    payload: dict       # event-specific data
    timestamp: float    # time.time()
    correlation_id: str # groups related events (e.g. a single pipeline run)
```

**Event Taxonomy:**

| Prefix     | Purpose                        | Examples                                      |
|------------|--------------------------------|-----------------------------------------------|
| `graph.*`  | LangGraph execution lifecycle  | `graph.start`, `graph.node_enter`, `graph.end`|
| `chat.*`   | LLM streaming                  | `chat.chunk`, `chat.done`, `chat.error`       |
| `gate.*`   | HITL approval gates            | `gate.request`, `gate.response`               |
| `tool.*`   | Tool invocations               | `tool.start`, `tool.result`, `tool.error`     |
| `story.*`  | Story/epic lifecycle           | `story.created`, `story.status_change`        |
| `build.*`  | Build/test results             | `build.start`, `build.result`                 |
| `agent.*`  | Agent state changes            | `agent.thinking`, `agent.idle`                |
| `file.*`   | File operations                | `file.read`, `file.write`, `file.diff`        |
| `sim.*`    | Simulator events               | `sim.launch`, `sim.screenshot`, `sim.result`  |
| `system.*` | System-level                   | `system.stats_update`, `system.error`         |

**API:**

```python
bus = EventBus()
bus.emit("chat.chunk", {"text": "Hello"}, correlation_id="run-123")
bus.on("chat.*", callback)       # wildcard matching
bus.on("gate.request", callback) # exact matching
bus.off(subscription_id)
bus.once("graph.end", callback)  # auto-unsubscribe after first fire
```

### WebSocket Manager

Bridges EventBus to WebSocket clients. Replaces the current per-connection LLM logic.

- Subscribes to `*` on the EventBus, broadcasts all events to connected WS clients as JSON
- Routes incoming client messages to appropriate handlers:
  - `chat.send` → adds user message, triggers LLM stream
  - `gate.response` → resolves a pending HITL gate
  - `pipeline.start` → kicks off a graph execution
  - `pipeline.cancel` → cancels running execution

**Wire Protocol:**

```json
// Server → Client (event envelope)
{
  "type": "event",
  "event_type": "chat.chunk",
  "payload": {"text": "Hello"},
  "timestamp": 1714100000.0,
  "correlation_id": "run-123"
}

// Client → Server (command)
{
  "type": "command",
  "command": "chat.send",
  "payload": {"text": "Build a login screen"}
}
```

### HITL Gate Protocol

Event-driven instead of interrupt-driven:

1. Agent emits `gate.request` with approval details
2. WSManager broadcasts to UI
3. UI renders approval dialog
4. User clicks approve/reject → sends `gate.response` command
5. WSManager resolves the pending gate future

### Application Shell Layout

```
┌──────────────────────────────────────────────────────┐
│ Activity Bar (48px left rail)                        │
│ ┌────┬───────────┬───────────────────────────────────┤
│ │    │ Sidebar   │ Main Content Area                 │
│ │ AB │ (280px,   │ (flex, panel-specific)             │
│ │    │ collapsible│                                   │
│ │    │           │                                   │
│ │    │           ├───────────────────────────────────┤
│ │    │           │ Bottom Panel (collapsible)        │
│ └────┴───────────┴───────────────────────────────────┘
```

**Activity Bar Icons:**
- Chat (default) — current terminal/chat interface
- Pipeline — graph execution dashboard
- Files — file explorer with diff viewer
- Simulator — iOS simulator panel
- Settings — configuration

### Frontend Module Split

```
ui/
├── index.html          # Shell only — loads modules
├── css/
│   ├── tokens.css      # Design system variables
│   ├── layout.css      # App shell, activity bar, sidebar
│   └── chat.css        # Chat-specific styles
└── js/
    ├── event-bus.js    # Client-side EventBus (mirrors backend)
    ├── app.js          # Vue app, routing, shell logic
    └── panels/
        └── chat.js     # Chat panel component (future)
```

## Implementation Phases

### Phase 1: Foundation (Current)
- EventBus with sync pub/sub and wildcard matching
- WSManager bridging EventBus ↔ WebSocket
- Refactor server.py to use EventBus/WSManager
- Split UI into modular CSS/JS files
- Activity Bar shell layout (Chat as default panel)

### Phase 2: Graph Execution Dashboard
- `graph.*` event emission from LangGraph callbacks
- Pipeline panel with node-level progress
- Real-time execution timeline

### Phase 3: HITL Gates
- `gate.*` event protocol
- Approval dialog UI component
- Gate resolution via WebSocket commands

### Phase 4: Tool Call Visualization
- `tool.*` events with input/output display
- Collapsible tool call cards in chat
- File diff viewer for `file.write` events

### Phase 5: File Explorer
- `file.*` events for read/write tracking
- Tree view with modification badges
- Inline diff viewer

### Phase 6: Simulator Integration
- `sim.*` events for simulator lifecycle
- Screenshot streaming panel
- Build/test result display

### Phase 7: Story/Epic Management
- `story.*` events for lifecycle tracking
- Kanban-style board view
- Epic → Story → Task hierarchy

### Phase 8: Build & Test Dashboard
- `build.*` events for CI-like feedback
- Test result aggregation
- Error log viewer

### Phase 9: Multi-Conversation Support
- Conversation persistence and switching
- Sidebar conversation list with search
- Context isolation per conversation

### Phase 10: Settings & Configuration
- Model selection and parameter tuning
- Tool enable/disable toggles
- Theme customization

### Phase 11: Keyboard Shortcuts & Command Palette
- VS Code-style command palette (Ctrl+Shift+P)
- Configurable keybindings
- Quick actions

### Phase 12: Skills & Workflows Editor
- Visual workflow builder
- Skill template library
- Custom pipeline composition

## Deprecations

The following will be deprecated as the Web UI becomes the primary interface:
- Textual TUI (`agent/repl/tui.py` and related)
- TUI-specific commands, completer, lexer, theme modules
- Direct terminal-based HITL interaction

## Migration Strategy

Each phase is independently deployable. The existing chat functionality continues working throughout migration. New panels are additive — the Activity Bar simply gains new icons as panels are implemented.
