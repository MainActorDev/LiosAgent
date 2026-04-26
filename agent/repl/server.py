"""FastAPI server with EventBus-driven WebSocket endpoint.

The server initialises a shared EventBus and WSManager.  The ``/ws``
endpoint delegates all connection handling to the WSManager which
bridges EventBus events to/from WebSocket clients.
"""

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
import os
from dotenv import load_dotenv

load_dotenv()

from agent.event_bus import EventBus
from agent.repl.ws_manager import WSManager
from agent.repl.pipeline_runner import PipelineRunner

# ------------------------------------------------------------------
# Shared instances
# ------------------------------------------------------------------
bus = EventBus()
ws_manager = WSManager(bus)
ws_manager.start()
pipeline_runner = PipelineRunner(bus)
pipeline_runner.start()

app = FastAPI()


# ------------------------------------------------------------------
# WebSocket endpoint (unified)
# ------------------------------------------------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.handle_connection(websocket)


# ------------------------------------------------------------------
# Legacy endpoint (redirect-compatible)
# ------------------------------------------------------------------
@app.websocket("/ws/chat")
async def websocket_legacy_endpoint(websocket: WebSocket):
    """Backwards-compatible endpoint — delegates to the same WSManager."""
    await ws_manager.handle_connection(websocket)


# ------------------------------------------------------------------
# Static files (UI)
# ------------------------------------------------------------------
ui_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "ui")
app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")
