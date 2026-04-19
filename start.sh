#!/bin/bash
echo "Setting up Python Environment..."
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

echo "Starting FastAPI server on port 8000..."
# Run uvicorn in the background
uvicorn main:fastapi_app --host 0.0.0.0 --port 8000 --reload &
FASTAPI_PID=$!

echo "Starting ngrok to expose port 8000..."
# Note: make sure ngrok is installed and authenticated locally
rtk ngrok http 8000 --log=stdout

# When ngrok shuts down, gracefully stop the fastapi server
kill $FASTAPI_PID
