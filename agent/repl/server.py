from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
import os
import asyncio
from starlette.concurrency import run_in_threadpool
from agent.repl.llm_bridge import LLMBridge

app = FastAPI()

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    # Create an LLMBridge per connection so conversation history isn't shared
    llm_agent = LLMBridge()

    try:
        while True:
            data = await websocket.receive_json()
            user_text = data.get("text", "")

            llm_agent.add_user_message(user_text)

            # We use an asyncio queue to pass events from the worker thread to the async event loop
            # so we can stream them to the websocket in real-time without blocking the event loop.
            loop = asyncio.get_running_loop()
            queue = asyncio.Queue()

            def _run_stream():
                try:
                    for event in llm_agent.stream():
                        loop.call_soon_threadsafe(queue.put_nowait, event)
                finally:
                    # Send a sentinel value to indicate completion
                    loop.call_soon_threadsafe(queue.put_nowait, None)

            # Start the blocking stream in a background thread
            asyncio.create_task(asyncio.to_thread(_run_stream))

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

    except WebSocketDisconnect:
        pass

ui_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "ui")
app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")

