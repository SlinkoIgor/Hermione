# Hermione Electron App

This Electron application provides a convenient way to interact with the Hermione API. It runs in the background and allows you to quickly send selected text to the API using a keyboard shortcut.

## Features

- Runs on computer startup
- Shows an icon in the menu bar
- Automatically starts the Hermione API server
- Allows sending selected text to the API using Option+H shortcut

## Prerequisites

Before you can install the Electron app, you need to have the following installed:

1. **Node.js and npm**: The Electron app is built using Node.js. You can install it from [nodejs.org](https://nodejs.org/).
2. **Python**: The app requires Python to run the FastAPI server. Make sure you have Python installed and the virtual environment set up.

## Installation

### Option 1: Using the installation script

1. Make sure you have Node.js and npm installed.
2. Open Terminal and navigate to the electron-app directory.
3. Run the installation script:

```bash
chmod +x install-mac.sh
./install-mac.sh
```

### Option 2: Manual installation

1. Make sure you have Node.js and npm installed.
2. Open Terminal and navigate to the electron-app directory.
3. Install dependencies:

```bash
npm install
```

4. Build the application:

```bash
npm run build
```

5. The built application will be available in the `dist` directory

## Development

To run the application in development mode:

```bash
npm start
```

## Usage

1. Launch the application
2. The app will start automatically when your computer boots up
3. Select any text in any application
4. Press Cmd+Option+H to send the selected text to the Hermione API
5. The response will be processed by the API

## Requirements

- macOS
- Node.js
- The Hermione API server (included in the main project)

## Troubleshooting

If the application doesn't start the API server correctly, check the following:

1. Make sure the Python virtual environment is properly set up
2. Verify that the path to the Python executable and API script is correct in `main.js`
3. Check the console logs for any error messages 