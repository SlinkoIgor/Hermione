#!/bin/bash

# Exit on error
set -e

echo "Installing Hermione Electron App on macOS..."

# Check if the app is built
if [ ! -d "dist/mac" ]; then
    echo "The app is not built yet. Building the app..."
    npm run build
fi

# Find the app in the dist directory
APP_PATH=$(find dist -name "Hermione.app" | head -n 1)

if [ -z "$APP_PATH" ]; then
    echo "Error: Could not find the built app in the dist directory."
    exit 1
fi

# Copy the app to the Applications folder
echo "Copying the app to the Applications folder..."
cp -R "$APP_PATH" "/Applications/"

# Set up auto-launch on startup
echo "Setting up auto-launch on startup..."
osascript -e 'tell application "System Events" to make login item at end with properties {path:"/Applications/Hermione.app", hidden:false}'

echo "Installation complete!"
echo "The app has been installed to /Applications/Hermione.app"
echo "It will start automatically when you log in."