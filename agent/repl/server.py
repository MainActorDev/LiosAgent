from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI()

# Mount the ui directory to serve static files like index.html
ui_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "ui")
app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")
