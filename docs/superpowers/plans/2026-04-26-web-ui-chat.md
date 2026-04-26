# Web UI Chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Textual TUI with a modern Web UI served via FastAPI and PyWebView, connecting the existing LangGraph backend via WebSockets.

**Architecture:** A FastAPI server running in a background thread will serve the static `cli_ui_prototype.html` (renamed to `index.html` and modified to include Vue) and provide a WebSocket endpoint. A PyWebView window will point to the local FastAPI server URL. The Vue frontend will communicate with the LangGraph LLM loop via the WebSocket.

**Tech Stack:** `fastapi`, `uvicorn`, `websockets`, `pywebview`, Vue.js (CDN)

---

### Task 1: Add Dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add required dependencies to `requirements.txt`**

```text
fastapi
uvicorn
websockets
pywebview
```

- [ ] **Step 2: Install dependencies**

Run: `pip install -r requirements.txt`
Expected: Successfully installs fastapi, uvicorn, websockets, and pywebview.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add fastapi, pywebview and websockets dependencies"
```

### Task 2: Create Basic FastAPI Server

**Files:**
- Create: `agent/repl/server.py`
- Create: `tests/agent/repl/test_server.py`

- [ ] **Step 1: Write the failing test**

Create `tests/agent/repl/test_server.py`:
```python
import pytest
from fastapi.testclient import TestClient
from agent.repl.server import app

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/agent/repl/test_server.py -v`
Expected: FAIL with "ModuleNotFoundError" or similar because `server.py` doesn't exist.

- [ ] **Step 3: Write minimal implementation**

Create `agent/repl/server.py`:
```python
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

@app.get("/")
def read_root():
    return HTMLResponse("<h1>Lios-Agent Web UI</h1>")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/agent/repl/test_server.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/agent/repl/test_server.py agent/repl/server.py
git commit -m "feat: basic FastAPI server setup"
```

### Task 3: Setup the Web UI Frontend

**Files:**
- Create: `ui/` directory
- Move: `docs/cli_ui_prototype.html` -> `ui/index.html`
- Modify: `agent/repl/server.py`

- [ ] **Step 1: Create UI directory and move prototype**

Run:
```bash
mkdir -p ui
mv docs/cli_ui_prototype.html ui/index.html
```

- [ ] **Step 2: Update FastAPI to serve the `ui` directory**

Update `agent/repl/server.py`:
```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI()

# Mount the ui directory to serve static files like index.html
ui_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "ui")
app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")
```

- [ ] **Step 3: Update test to expect the prototype file**

Update `tests/agent/repl/test_server.py`:
```python
import pytest
from fastapi.testclient import TestClient
from agent.repl.server import app

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert "Lios" in response.text or "html" in response.text.lower()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/agent/repl/test_server.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/ agent/repl/server.py tests/agent/repl/test_server.py docs/cli_ui_prototype.html
git commit -m "feat: serve web UI prototype via FastAPI"
```

### Task 4: Add WebSocket Echo Endpoint

**Files:**
- Modify: `agent/repl/server.py`
- Modify: `tests/agent/repl/test_server.py`

- [ ] **Step 1: Write the failing test**

Update `tests/agent/repl/test_server.py`:
```python
import pytest
from fastapi.testclient import TestClient
from agent.repl.server import app
from fastapi.websockets import WebSocketDisconnect

client = TestClient(app)

def test_websocket_echo():
    with client.websocket_connect("/ws/chat") as websocket:
        websocket.send_json({"text": "Hello"})
        data = websocket.receive_json()
        assert data["text"] == "Echo: Hello"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/agent/repl/test_server.py -v`
Expected: FAIL because `/ws/chat` endpoint does not exist.

- [ ] **Step 3: Write minimal implementation**

Update `agent/repl/server.py` to add the WebSocket endpoint:
```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI()

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            await websocket.send_json({"text": f"Echo: {data.get('text', '')}"})
    except WebSocketDisconnect:
        pass

ui_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "ui")
app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/agent/repl/test_server.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent/repl/server.py tests/agent/repl/test_server.py
git commit -m "feat: add websocket echo endpoint"
```

### Task 5: Integrate Vue.js and WebSocket Client

**Files:**
- Modify: `ui/index.html`

- [ ] **Step 1: Update `ui/index.html`**

Update `ui/index.html` to load Vue 3 from CDN, add a simple chat interface, and connect to the WebSocket. Replace the static content of the `<body>` (or where appropriate based on the prototype) with a basic Vue app mount point.

Here is an example snippet to insert into `ui/index.html`:

```html
<!-- Add Vue CDN to <head> -->
<script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>

<!-- Replace existing chat content with this Vue template -->
<div id="app" class="flex flex-col h-full w-full bg-[#0a0a0c] text-white">
  <div class="flex-1 overflow-y-auto p-4 space-y-4">
    <div v-for="(msg, i) in messages" :key="i" class="p-3 rounded-lg max-w-[80%]"
         :class="msg.role === 'user' ? 'bg-blue-600 ml-auto' : 'bg-gray-800'">
      {{ msg.text }}
    </div>
  </div>
  <div class="p-4 bg-gray-900">
    <form @submit.prevent="sendMessage" class="flex space-x-2">
      <input v-model="inputText" type="text" class="flex-1 p-2 bg-gray-800 rounded border border-gray-700" placeholder="Type a message...">
      <button type="submit" class="p-2 bg-blue-600 rounded">Send</button>
    </form>
  </div>
</div>

<script>
  const { createApp, ref, onMounted } = Vue;

  createApp({
    setup() {
      const messages = ref([{role: 'assistant', text: 'Hello! I am Lios.'}]);
      const inputText = ref('');
      let ws = null;

      onMounted(() => {
        // Connect to WebSocket using the current host
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        ws = new WebSocket(`${protocol}//${window.location.host}/ws/chat`);
        
        ws.onmessage = (event) => {
          const data = JSON.parse(event.data);
          messages.value.push({ role: 'assistant', text: data.text });
        };
      });

      const sendMessage = () => {
        if (!inputText.value.trim() || !ws) return;
        
        messages.value.push({ role: 'user', text: inputText.value });
        ws.send(JSON.stringify({ text: inputText.value }));
        inputText.value = '';
      };

      return { messages, inputText, sendMessage };
    }
  }).mount('#app');
</script>
```

*(Note: Integrate the Vue logic cleanly into the existing Tailwind classes in the `cli_ui_prototype.html`.)*

- [ ] **Step 2: Manually test the UI**

Run the server temporarily: `uvicorn agent.repl.server:app --port 8000`
Open browser at `http://localhost:8000`.
Verify that sending a message displays it as a user message and returns an "Echo: ..." assistant message.

- [ ] **Step 3: Commit**

```bash
git add ui/index.html
git commit -m "feat: integrate Vue.js and connect websocket client"
```

### Task 6: Integrate LangGraph LLM Backend

**Files:**
- Modify: `agent/repl/server.py`

- [ ] **Step 1: Replace Echo Logic with LangGraph Backend**

Update `agent/repl/server.py` to use `AgentApp.stream_events()` from the LLM bridge.

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
import os
import json
from agent.repl.llm_bridge import AgentApp

app = FastAPI()
llm_agent = AgentApp()

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    thread_id = "web-session" # or generate a UUID per connection
    
    try:
        while True:
            data = await websocket.receive_json()
            user_text = data.get("text", "")
            
            # Send events back to client as they stream from LangGraph
            async for event in llm_agent.stream_events(user_text, thread_id):
                # Format event for frontend (adjust format based on stream_events output)
                response_data = {
                    "text": str(event),
                    "type": "chunk" # or "complete", "tool_call", etc. depending on your event structure
                }
                await websocket.send_json(response_data)
                
    except WebSocketDisconnect:
        pass

ui_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "ui")
app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")
```

- [ ] **Step 2: Commit**

```bash
git add agent/repl/server.py
git commit -m "feat: connect websocket to LangGraph agent"
```

### Task 7: PyWebView Desktop Launcher

**Files:**
- Modify: `agent/repl/legacy.py`

- [ ] **Step 1: Update `UniversalREPL` to launch PyWebView**

Update `agent/repl/legacy.py` to run `uvicorn` in a thread and start `webview`.

```python
"""Legacy facade preserving the UniversalREPL static method API."""

from __future__ import annotations
import threading
import time
import uvicorn
import webview
from rich.console import Console

console = Console()

def start_server():
    from agent.repl.server import app
    # Run uvicorn on a specific port, log_level="warning" to keep terminal clean
    uvicorn.run(app, host="127.0.0.1", port=8123, log_level="warning")

class UniversalREPL:
    """Facade over the Web UI."""

    @staticmethod
    def start_interactive_session() -> None:
        """Launch the PyWebView Desktop App."""
        # Start FastAPI server in a background daemon thread
        server_thread = threading.Thread(target=start_server, daemon=True)
        server_thread.start()
        
        # Wait briefly to ensure server is up
        time.sleep(1)
        
        # Launch PyWebView window
        webview.create_window(
            'Lios-Agent', 
            'http://127.0.0.1:8123',
            width=1200, 
            height=800,
            background_color='#0a0a0c'
        )
        webview.start()

    @staticmethod
    def interactive_intake_session(
        epic_name: str, workspace_root: str = "."
    ) -> str:
        """Launch the UI in intake mode (Fallback for now)."""
        console.print("[yellow]Web UI intake mode not yet fully implemented, falling back to basic chat[/yellow]")
        UniversalREPL.start_interactive_session()
        return "Web UI Session Completed"

    @staticmethod
    def parse_input(user_input: str, workspace_root: str = ".") -> str:
        from agent.repl.parse_input import parse_input as _parse_input
        return _parse_input(user_input, workspace_root)
```

- [ ] **Step 2: Test the Desktop App**

Run: `python cli.py`
Expected: A native desktop window opens showing the Vue UI, and you can chat with the LangGraph agent.

- [ ] **Step 3: Commit**

```bash
git add agent/repl/legacy.py
git commit -m "feat: launch pywebview from cli"
```