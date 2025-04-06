#!/bin/bash

# Exit on error
set -e

echo "Installing Hermione Electron App..."

# Run setup if node_modules doesn't exist
if [ ! -d "node_modules" ]; then
    ./setup.sh
fi

# Build the app
npm run build

# Find the app directory (handles both arm64 and x64 builds)
APP_PATH=$(find dist -name "Hermione.app" -type d | head -n 1)

if [ -n "$APP_PATH" ]; then
    # Remove existing installation
    rm -rf "/Applications/Hermione.app"
    # Copy new version
    cp -R "$APP_PATH" "/Applications/"
    # Set up auto-launch
    osascript -e 'tell application "System Events" to make login item at end with properties {path:"/Applications/Hermione.app", hidden:false}'
    echo "✅ Installation complete! App installed to /Applications/Hermione.app"
else
    echo "❌ Build failed - app not found in dist/"
    echo "Build output directories:"
    ls -la dist/
    exit 1
fi