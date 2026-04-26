from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
import os
import asyncio
from dotenv import load_dotenv
import traceback
import sys

load_dotenv()

from agent.repl.llm_bridge import LLMBridge

app = FastAPI()

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    print("WebSocket connected", flush=True)
    await websocket.accept()
    llm_agent = LLMBridge()

    await websocket.send_json({
        "type": "stats",
        "model": llm_agent.model_name,
        "input_tokens": llm_agent.total_input_tokens,
        "output_tokens": llm_agent.total_output_tokens,
        "total_tokens": llm_agent.total_tokens,
        "cost": llm_agent.total_cost,
    })

    try:
        while True:
            data = await websocket.receive_json()
            user_text = data.get("text", "")
            print(f"Received user text: {user_text}", flush=True)

            llm_agent.add_user_message(user_text)

            try:
                # The issue is the ChatOpenAI initialized inside the thread
                # Langchain initializes HTTP clients and expects to be in the same thread/loop
                print("Getting response from LLM...", flush=True)
                
                # Get the full stream but run it in an executor properly
                def _get_stream():
                    print("Executing LLM request...", flush=True)
                    result = []
                    for chunk in llm_agent.stream():
                        result.append(chunk)
                    return result
                
                # Use default executor
                loop = asyncio.get_running_loop()
                chunks = await loop.run_in_executor(None, _get_stream)
                
                for chunk in chunks:
                    response_data = {
                        "text": str(chunk),
                        "type": "chunk"
                    }
                    print(f"Sending chunk: {response_data}", flush=True)
                    await websocket.send_json(response_data)
                
                print("Finished sending all chunks", flush=True)

            except Exception as stream_err:
                print(f"Error during stream: {stream_err}", flush=True)
                traceback.print_exc()
                await websocket.send_json({"text": f"Error: {stream_err}", "type": "chunk"})

            await websocket.send_json({
                "type": "stats",
                "model": llm_agent.model_name,
                "input_tokens": llm_agent.total_input_tokens,
                "output_tokens": llm_agent.total_output_tokens,
                "total_tokens": llm_agent.total_tokens,
                "cost": llm_agent.total_cost,
            })

    except WebSocketDisconnect:
        print("WebSocket disconnected", flush=True)
    except Exception as e:
        print(f"Unexpected WS error: {e}", flush=True)
        traceback.print_exc()

ui_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "ui")
app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")
