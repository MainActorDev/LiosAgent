#!/bin/bash
# Lios-Agent Global Installer

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
TARGET_LINK="/usr/local/bin/lios"

echo "🚀 Starting Lios-Agent installation..."

# Step 1: Pre-flight checks
echo "🔍 Checking system dependencies..."

if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is not installed."
    echo "💡 Please install it using: brew install python"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo "❌ Error: npm is not installed."
    echo "💡 Please install Node.js using: brew install node"
    exit 1
fi

if ! command -v xcodebuild &> /dev/null; then
    echo "❌ Error: xcodebuild is not installed."
    echo "💡 Please install Xcode Command Line Tools using: xcode-select --install"
    exit 1
fi

echo "✅ All system dependencies found."

# Step 2: Automate Python Environment
echo "🐍 Setting up Python virtual environment..."
cd "$DIR"

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Created new virtual environment in $DIR/venv"
fi

echo "📦 Installing Python dependencies..."
./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install -r requirements.txt -q
echo "✅ Python dependencies installed."

# Step 3: Automate OpenCode-AI Installation
echo "🤖 Checking OpenCode-AI CLI..."
if ! command -v opencode-ai &> /dev/null; then
    echo "📦 Installing opencode-ai globally via npm..."
    npm install -g opencode-ai@latest
else
    echo "✅ opencode-ai is already installed."
fi

# Step 4: Automate Maestro CLI Installation
echo "📱 Checking Maestro CLI..."
MAESTRO_BIN="$HOME/.maestro/bin/maestro"
if ! command -v maestro &> /dev/null && [ ! -f "$MAESTRO_BIN" ]; then
    echo "📦 Installing Maestro CLI via curl..."
    curl -Ls "https://get.maestro.mobile.dev" | bash
    
    # Check if we need to remind the user to add it to their PATH
    if [[ ":$PATH:" != *":$HOME/.maestro/bin:"* ]]; then
        echo "⚠️  Maestro installed, but you may need to add it to your PATH."
        echo "💡 Add 'export PATH=\"\$PATH:\$HOME/.maestro/bin\"' to your ~/.zshrc or ~/.bash_profile"
    fi
else
    echo "✅ Maestro CLI is already installed."
fi

# Step 5: Finalize and Symlink
echo "🔗 Setting up global CLI access..."

# Ensure the lios wrapper is executable
chmod +x "$DIR/lios"

# Create symlink
if [ -L "$TARGET_LINK" ]; then
    echo "♻️ Removing existing symlink at $TARGET_LINK..."
    sudo rm "$TARGET_LINK"
fi

echo "Creating symlink to $TARGET_LINK..."
sudo ln -s "$DIR/lios" "$TARGET_LINK"

echo "🎉 Lios-Agent successfully installed!"
echo "👉 You can now run 'lios --help' from any iOS repository."
