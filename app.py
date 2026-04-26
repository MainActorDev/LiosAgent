import webview
import uvicorn
import threading
from agent.repl.server import app
import time
import requests

def start_server():
    uvicorn.run(app, host="127.0.0.1", port=8123)

def wait_for_server():
    while True:
        try:
            r = requests.get("http://127.0.0.1:8123/")
            if r.status_code == 200:
                break
        except requests.exceptions.ConnectionError:
            time.sleep(0.1)

if __name__ == '__main__':
    t = threading.Thread(target=start_server, daemon=True)
    t.start()
    
    # Wait for the server to be ready before starting the webview
    wait_for_server()

    window = webview.create_window('Lios Agent CLI', 'http://127.0.0.1:8123', width=1200, height=800)
    webview.start()
