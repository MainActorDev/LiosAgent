#!/bin/bash

echo "Checking for Node.js (required for OpenCode)..."
# Load NVM if it is already installed
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

if ! command -v node &> /dev/null; then
    echo "Node.js not found. Installing NVM and Node v20 automatically..."
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    nvm install 20
    nvm use 20
else
    echo "Node.js found: $(node -v)"
fi

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
ngrok http 8000 --log=stdout

# When ngrok shuts down, gracefully stop the fastapi server
kill $FASTAPI_PID
