from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI()

@app.get("/")
async def get():
    with open("ui/index.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_json()
        await websocket.send_json({"text": f"Echo: {data['text']}"})
