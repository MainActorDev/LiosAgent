import asyncio
import websockets
import json

async def hello():
    uri = "ws://localhost:8001/ws/chat"
    async with websockets.connect(uri) as websocket:
        await websocket.send(json.dumps({"text": "Hello, world!"}))
        print(f"> Sent: Hello, world!")

        while True:
            response = await websocket.recv()
            print(f"< Received: {response}")

asyncio.run(hello())
