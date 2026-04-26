# Reactive UI Web Wiring Design

## Goal
Replace the hardcoded mock HTML in `ui/index.html` with Vue reactive state. Wire up the backend `LLMBridge` and FastAPI websocket endpoint to send token/cost updates and properly stream chat chunks (aggregating them into single message blocks rather than creating a new block per chunk). The mock sidebar data will be replaced by empty reactive arrays for now, establishing the architecture without implementing the full backend fetch logic for conversations/files.

## Architecture

### Frontend (`ui/index.html`)
1.  **State Management (Vue ref):**
    *   `messages`: Array of `{role, text}`.
    *   `conversations`: Empty array `[]`.
    *   `files`: Empty array `[]`.
    *   `contextData`: Object containing `modelName`, `tokenUsage`, `cost`.
    *   `activeTools`: Array of currently active tools.
2.  **Streaming Fix:**
    *   Currently, the websocket `onmessage` pushes a *new* message to the array for each chunk.
    *   **Fix:** Maintain the current message being streamed. The backend will send `{ type: "chunk", text: "..." }` and a new event `{ type: "end_turn" }` (or we can just aggregate chunks until a new user message is sent, or the backend explicitly marks the turn as done). We will track the *index* of the current assistant message and append chunks to its `text`.
3.  **Reactive Sidebar:**
    *   Replace hardcoded `.conv-item` list with `v-for="conv in conversations"`.
    *   Replace hardcoded `.file-tree-item` list with `v-for="file in files"`.
    *   Replace hardcoded context tokens/cost with bindings to `contextData`.

### Backend (`agent/repl/server.py` & `agent/repl/llm_bridge.py`)
1.  **Streaming Fix in Server:**
    *   When receiving a stream from `llm_agent.stream()`, send chunks.
    *   After the stream finishes, we have access to the `usage_metadata` (via the returned value or by checking `llm_agent.total_input_tokens`, etc.).
    *   Send a final message over the websocket containing the updated stats: `{ type: "stats", model: llm_agent.model_name, input_tokens: ..., output_tokens: ..., cost: ... }`.
    *   Send `{ type: "done" }` to signal the end of the generation.
2.  **Initial State payload:**
    *   When a client connects, send an initial stats payload so the UI shows `0 tokens`, `$0.00`, etc., based on the bridge state.

## Trade-offs & Decisions
*   **Message Aggregation:** We'll aggregate chunks on the frontend. The backend sends `"chunk"` messages. The frontend finds the last message (if it's an assistant message) and appends to it. If the last message is from the user, it pushes a new assistant message.
*   **Sidebar Data:** We're leaving the actual backend population of the file tree and conversations for a future PR to keep this PR focused purely on the UI state wiring.

## Testing
*   Update `tests/agent/repl/test_server.py` to assert that the `stats` and `done` messages are sent after the stream completes.
