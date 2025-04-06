#!/bin/bash

# Exit on error
set -e

echo "Setting up Snitch Electron App..."

# Install npm dependencies
npm install

# Create python virtual environment if it doesn't exist
if [ ! -d "../.venv" ]; then
    python3 -m venv ../.venv
    source ../.venv/bin/activate
    pip install -r ../src/requirements.txt
fi

echo "✅ Setup complete!"
echo "To run in development: npm start"
echo "To build: npm run build"

# Show running Python processes (without sudo)
ps aux | grep python