# Web UI Chat Architecture Spec

## Overview
This document specifies the architecture for replacing the current textual interface with a PyWebView + FastAPI + Vue 3 HTML UI. The goal is to provide a pixel-perfect HTML/CSS user interface while maintaining native application characteristics. The system transitions from a purely terminal-based approach to a rich web interface embedded in a desktop window, offering enhanced styling capabilities, smooth animations, and a modern chat experience.

## Architecture
The system consists of three distinct layers:
1.  **Frontend**: A Single Page Application (SPA) built with Vue 3 (via CDN, without a build step), providing the user interface.
2.  **Backend**: A FastAPI server handling REST endpoints and WebSocket connections for real-time bi-directional communication.
3.  **Delivery**: A PyWebView window that hosts the frontend, acting as a lightweight cross-platform native launcher.

## Components

### 1. The FastAPI Server
The backend is powered by FastAPI and Uvicorn.
*   **Role**: Serves the static HTML frontend, handles initialization, and manages real-time chat via WebSockets.
*   **Routing**:
    *   `GET /`: Serves the `index.html` file.
    *   `WS /ws/chat`: The WebSocket endpoint for bi-directional communication between the Vue frontend and the LangGraph agent logic.
*   **Dependencies**: `fastapi`, `uvicorn`, `websockets`.

### 2. The PyWebView Launcher
This component creates the native application window.
*   **Role**: Initializes the FastAPI server in a background thread and launches a webview window pointing to the local server URL.
*   **Implementation**: Uses the `webview.create_window()` and `webview.start()` APIs.
*   **Dependencies**: `pywebview`.

### 3. The Static Vue HTML/JS File
The frontend is a single `index.html` file containing HTML, CSS, and Vue 3 JavaScript logic.
*   **Role**: Renders the chat interface, handles user input, and communicates with the FastAPI server via WebSockets.
*   **Implementation**: Uses Vue 3 imported via CDN (`https://unpkg.com/vue@3/dist/vue.global.js`). It connects to `ws://localhost:<port>/ws/chat` to send and receive messages.
*   **UI Elements**: Chat history container, message input area, send button, and connection status indicator.

## Data Flow
The flow of data from user input to agent response is as follows:
1.  **User Input**: The user types a message in the Vue frontend and clicks "Send" (or presses Enter).
2.  **Frontend Emission**: The Vue application serializes the message (e.g., `{"type": "user_message", "content": "Hello"}`) and sends it over the established WebSocket connection.
3.  **Backend Reception**: The FastAPI WebSocket endpoint receives the message.
4.  **Agent Processing**: The message is passed to the LangGraph execution environment.
5.  **Backend Emission**: The LangGraph agent produces a response, which the FastAPI server sends back over the WebSocket (e.g., `{"type": "agent_response", "content": "Hi there!"}`).
6.  **Frontend Update**: The Vue application receives the WebSocket message, updates its internal state, and reactivity renders the new message in the chat UI.

## Error Handling & Shutdown

### 1. WebSocket Disconnect Handling
*   **Frontend**: The Vue application must implement reconnection logic. If the `onclose` or `onerror` events fire, it should display a "Disconnected" state to the user and attempt to reconnect after a short delay (e.g., 2000ms).
*   **Backend**: The FastAPI WebSocket endpoint must gracefully handle `WebSocketDisconnect` exceptions, ensuring that any resources associated with that connection are cleaned up without crashing the server.

### 2. Graceful Shutdown
*   When the PyWebView window is closed by the user, the application must shut down cleanly.
*   The PyWebView API provides a `closed` event. We will bind a callback to this event that signals the Uvicorn server to stop.
*   This ensures no orphan background processes are left running after the user closes the application window.

## Testing

### 1. Unit Tests for FastAPI
*   **Implementation**: Use `pytest` and `fastapi.testclient.TestClient`.
*   **Coverage**:
    *   Test that `GET /` returns a `200 OK` and serves the HTML content.
    *   Test the WebSocket endpoint `WS /ws/chat` by establishing a connection, sending a mock user message, and asserting that a valid response is received.
    *   Test the graceful handling of WebSocket disconnects by simulating a client drop.

### 2. Manual Testing for PyWebView
*   **Execution**: Run the main application entry point (e.g., `python main.py`).
*   **Verification**:
    *   Ensure the native window opens correctly.
    *   Verify the Vue UI loads without console errors.
    *   Verify that messages can be sent and received via the UI.
    *   Close the window and verify via task manager/process list that the Python process exits cleanly.