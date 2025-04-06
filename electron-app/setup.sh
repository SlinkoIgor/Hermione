#!/bin/bash

# Exit on error
set -e

echo "Setting up Hermione Electron App..."

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "Node.js is not installed. Please install Node.js first."
    exit 1
fi

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo "npm is not installed. Please install npm first."
    exit 1
fi

# Install dependencies
echo "Installing dependencies..."
npm install

echo "Setup complete!"
echo "To run the app in development mode, use: npm start"
echo "To build the app, use: npm run build"

# Show running Python processes (without sudo)
ps aux | grep python 