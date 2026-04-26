# Reactive UI Web Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the hardcoded HTML prototype in `ui/index.html` to be fully driven by Vue reactive state and fix the chat streaming chunk aggregation.

**Architecture:** We will replace the hardcoded lists for conversations, files, and context stats with Vue `ref` variables in the `<script>` block. The websocket `onmessage` handler will be updated to correctly append text to the active assistant message rather than creating a new message bubble per chunk. The backend will send an initial stats payload upon connection, and update stats after every stream completion.

**Tech Stack:** Vue 3 (CDN), WebSockets, FastAPI, Python.

---

### Task 1: Fix Chat Chunk Aggregation

**Files:**
- Modify: `ui/index.html`

- [ ] **Step 1: Update the Vue `onmessage` handler**
Update the `ws.onmessage` function inside `ui/index.html` to append chunks to the existing assistant message if it is the latest message, or create a new one. Also handle different message types.

```javascript
        ws.onmessage = (event) => {
          const data = JSON.parse(event.data);
          
          if (data.type === 'chunk') {
            const lastMsg = messages.value[messages.value.length - 1];
            if (lastMsg && lastMsg.role === 'assistant') {
              lastMsg.text += data.text;
            } else {
              messages.value.push({ role: 'assistant', text: data.text });
            }
          } else if (data.type === 'stats') {
             // We'll wire this in Task 3
             console.log("Stats received:", data);
          }
          scrollToBottom();
        };
```

- [ ] **Step 2: Commit**

```bash
git add ui/index.html
git commit -m "ui: fix streaming chunk aggregation in chat"
```

### Task 2: Reactive UI State for Sidebar & Stats

**Files:**
- Modify: `ui/index.html`

- [ ] **Step 1: Add reactive state variables to `setup()`**
Add empty arrays and stat placeholders to the `setup()` function.

```javascript
      const conversations = ref([]);
      const files = ref([]);
      const stats = ref({
        model: 'Unknown',
        inputTokens: 0,
        outputTokens: 0,
        totalTokens: 0,
        cost: 0.0,
      });
      const activeTools = ref([]);
```

- [ ] **Step 2: Expose state variables**
Update the return statement of `setup()`:

```javascript
      return { 
        messages, 
        inputText, 
        sendMessage, 
        conversations, 
        files, 
        stats, 
        activeTools 
      };
```

- [ ] **Step 3: Update HTML templates to use reactive state**
Replace the hardcoded sections in the sidebar:
1. `conv-list`: Iterate over `conversations` (if empty, show "No recent conversations").
2. `file-tree`: Iterate over `files` (if empty, show "No files").
3. `context-panel`: Bind `stats.model`, tokens, and cost.

*(Note to engineer: Find the sections `<div class="conv-list">`, `<div class="file-tree">`, and `<div class="context-panel">` and replace their inner contents with `v-if`/`v-else` and `v-for` logic using the reactive vars. Replace the hardcoded `gpt-4o` and token numbers with `{{ stats.model }}` etc.)*

- [ ] **Step 4: Update Stats handler**
Update the `ws.onmessage` handler from Task 1 to update the `stats` ref:

```javascript
          } else if (data.type === 'stats') {
            stats.value = {
              model: data.model || 'Unknown',
              inputTokens: data.input_tokens || 0,
              outputTokens: data.output_tokens || 0,
              totalTokens: data.total_tokens || 0,
              cost: data.cost || 0.0,
            };
          }
```

- [ ] **Step 5: Commit**

```bash
git add ui/index.html
git commit -m "ui: make sidebar and context stats reactive"
```

### Task 3: Backend Stats Broadcasting

**Files:**
- Modify: `agent/repl/server.py`
- Modify: `tests/agent/repl/test_server.py`

- [ ] **Step 1: Send initial stats on connection**
In `agent/repl/server.py`, right after `await websocket.accept()`, send an initial stats payload:

```python
    await websocket.accept()
    # Create an LLMBridge per connection so conversation history isn't shared
    llm_agent = LLMBridge()

    # Send initial stats
    await websocket.send_json({
        "type": "stats",
        "model": llm_agent.model_name,
        "input_tokens": llm_agent.total_input_tokens,
        "output_tokens": llm_agent.total_output_tokens,
        "total_tokens": llm_agent.total_tokens,
        "cost": llm_agent.total_cost,
    })
```

- [ ] **Step 2: Send stats after stream completes**
In `agent/repl/server.py`, inside the `while True:` queue reading loop, after it breaks (meaning the stream is done), send the updated stats payload:

```python
            # Consume from the queue asynchronously
            while True:
                event = await queue.get()
                if event is None:
                    break
                response_data = {
                    "text": str(event),
                    "type": "chunk"
                }
                await websocket.send_json(response_data)

            # Stream finished, send updated stats
            await websocket.send_json({
                "type": "stats",
                "model": llm_agent.model_name,
                "input_tokens": llm_agent.total_input_tokens,
                "output_tokens": llm_agent.total_output_tokens,
                "total_tokens": llm_agent.total_tokens,
                "cost": llm_agent.total_cost,
            })
```

- [ ] **Step 3: Update tests**
Modify `tests/agent/repl/test_server.py` to expect the initial `stats` payload, the `chunk` payloads, and the final `stats` payload.

```python
def test_websocket_llm_stream():
    # We will mock the LLMBridge class so that we can intercept instantiations per connection.
    mock_llm_agent = MagicMock()
    mock_llm_agent.model_name = "test-model"
    mock_llm_agent.total_input_tokens = 0
    mock_llm_agent.total_output_tokens = 0
    mock_llm_agent.total_tokens = 0
    mock_llm_agent.total_cost = 0.0
    
    def mock_stream():
        yield "Hello"
        yield " "
        yield "World"
        
        # Simulate stats update after streaming
        mock_llm_agent.total_tokens = 2
        mock_llm_agent.total_cost = 0.001
        
    mock_llm_agent.stream = mock_stream
    mock_add_msg = MagicMock()
    mock_llm_agent.add_user_message = mock_add_msg

    with patch("agent.repl.server.LLMBridge", return_value=mock_llm_agent):
        with client.websocket_connect("/ws/chat") as websocket:
            # Expect initial stats
            init_stats = websocket.receive_json()
            assert init_stats["type"] == "stats"
            assert init_stats["model"] == "test-model"
            
            websocket.send_json({"text": "Hello"})
            
            data1 = websocket.receive_json()
            assert data1["text"] == "Hello"
            assert data1["type"] == "chunk"
            
            data2 = websocket.receive_json()
            assert data2["text"] == " "
            assert data2["type"] == "chunk"
            
            data3 = websocket.receive_json()
            assert data3["text"] == "World"
            assert data3["type"] == "chunk"
            
            # Expect final stats
            final_stats = websocket.receive_json()
            assert final_stats["type"] == "stats"
            assert final_stats["total_tokens"] == 2
            
            # Check that add_user_message was called on the mock instance created per connection
            mock_add_msg.assert_called_once_with("Hello")
```

- [ ] **Step 4: Commit**

```bash
git add agent/repl/server.py tests/agent/repl/test_server.py
git commit -m "feat(repl): broadcast llm token and cost stats over websocket"
```

