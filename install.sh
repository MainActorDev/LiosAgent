#!/bin/bash
# Lios-Agent Global Installer

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
TARGET_LINK="/usr/local/bin/lios"

echo "Installing Lios-Agent globally..."

# Ensure the lios wrapper is executable
chmod +x "$DIR/lios"

# Create symlink
if [ -L "$TARGET_LINK" ]; then
    echo "Removing existing symlink at $TARGET_LINK..."
    sudo rm "$TARGET_LINK"
fi

echo "Creating symlink to $TARGET_LINK..."
sudo ln -s "$DIR/lios" "$TARGET_LINK"

echo "✅ Lios-Agent successfully installed!"
echo "You can now run 'lios --help' from any iOS repository."
