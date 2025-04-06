const { app, BrowserWindow, Tray, Menu, globalShortcut, ipcMain, clipboard, screen } = require('electron');
const path = require('path');
const { spawn, exec } = require('child_process');
const fs = require('fs');
const fetch = require('node-fetch');

let tray = null;
let mainWindow = null;
let pythonProcess = null;
let isQuitting = false;
let popupWindow = null;

// Path to the Python executable in the virtual environment
const pythonPath = path.join(__dirname, '../../.venv/bin/python');
const apiScriptPath = path.join(__dirname, '../../src/api.py');

// Create the tray icon
function createTray() {
  const iconPath = path.join(__dirname, 'assets/icon.png');
  tray = new Tray(iconPath);
  tray.setToolTip('Hermione');

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Show Status',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
        }
      }
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        quitApp();
      }
    }
  ]);

  tray.setContextMenu(contextMenu);
}

// Create the main window
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 400,
    height: 300,
    show: false,
    frame: true,
    resizable: true,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    }
  });

  mainWindow.loadFile(path.join(__dirname, 'index.html'));
  mainWindow.webContents.openDevTools();

  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow.hide();
      return false;
    }
    return true;
  });
}

// Create a popup window near the cursor
function createPopupWindow(responseText) {
  // Get the cursor position
  const cursorPosition = screen.getCursorScreenPoint();
  const display = screen.getDisplayNearestPoint(cursorPosition);

  // Close any existing popup
  if (popupWindow) {
    popupWindow.close();
    popupWindow = null;
  }

  // Create a new popup window
  popupWindow = new BrowserWindow({
    width: 400,
    height: 200,
    x: cursorPosition.x,
    y: cursorPosition.y,
    frame: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    transparent: true,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    }
  });

  // Load HTML content directly
  const htmlContent = `
    <!DOCTYPE html>
    <html>
    <head>
      <style>
        html, body {
          margin: 0;
          padding: 0;
          height: 100%;
          background: transparent;
          overflow: hidden;
        }
        .container {
          position: relative;
          margin: 0;
          padding: 8px;
          background-color: rgba(255, 255, 255, 0.95);
          border-radius: 8px;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
          height: 100%;
          color: #333;
        }
        .content-wrapper {
          height: calc(100% - 30px);
          margin-top: 30px;
          overflow-y: auto;
          overflow-x: hidden;
          padding: 0 4px;
        }
        .titlebar {
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          height: 30px;
          background-color: rgba(240, 240, 240, 0.8);
          border-top-left-radius: 8px;
          border-top-right-radius: 8px;
          cursor: move;
          display: flex;
          align-items: center;
          justify-content: flex-end;
          padding-right: 10px;
          -webkit-app-region: drag;
          z-index: 1000;
        }
        .close-btn {
          width: 20px;
          height: 20px;
          border-radius: 50%;
          background-color: #f1f1f1;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          font-size: 14px;
          color: #666;
          margin-left: 5px;
          -webkit-app-region: no-drag;
        }
        .response-text {
          font-family: "SF Mono", SFMono-Regular, ui-monospace, Menlo, Monaco, Consolas, monospace;
          font-size: 11px;
          line-height: 1.4;
          padding: 0;
          user-select: text;
          white-space: pre-wrap;
        }
        ::-webkit-scrollbar {
          width: 8px;
        }
        ::-webkit-scrollbar-track {
          background: transparent;
        }
        ::-webkit-scrollbar-thumb {
          background: rgba(0, 0, 0, 0.2);
          border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
          background: rgba(0, 0, 0, 0.3);
        }
      </style>
    </head>
    <body>
      <div class="container">
        <div class="titlebar" id="titlebar">
          <div class="close-btn" id="closeBtn">×</div>
        </div>
        <div class="content-wrapper">
          <div class="response-text">${responseText.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</div>
        </div>
      </div>
      <script>
        document.getElementById('closeBtn').addEventListener('click', () => {
          window.close();
        });
      </script>
    </body>
    </html>
  `;

  popupWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(htmlContent)}`);

  // Close the popup when it loses focus and is not being dragged
  let isMouseOver = false;

  // Add event listener for Escape key to close the popup
  popupWindow.webContents.on('before-input-event', (event, input) => {
    if (input.key === 'Escape') {
      popupWindow.close();
      popupWindow = null;
      event.preventDefault();
    }
  });

  popupWindow.on('blur', () => {
    if (!isMouseOver && popupWindow && !popupWindow.isDestroyed()) {
      popupWindow.close();
      popupWindow = null;
    }
  });

  if (popupWindow && !popupWindow.isDestroyed()) {
    popupWindow.webContents.on('dom-ready', () => {
      if (popupWindow && !popupWindow.isDestroyed()) {
        popupWindow.webContents.executeJavaScript(`
          document.addEventListener('mouseenter', () => {
            window.electronAPI.setMouseOver(true);
          });
          document.addEventListener('mouseleave', () => {
            window.electronAPI.setMouseOver(false);
          });
        `);
      }
    });
  }

  // Handle IPC for mouse over state
  ipcMain.on('set-mouse-over', (event, value) => {
    isMouseOver = value;
  });

  // Handle window close event
  popupWindow.on('closed', () => {
    popupWindow = null;
  });
}

// Start the Python API server
function startPythonServer() {
  console.log('Starting Python server...');
  console.log('Python path:', pythonPath);
  console.log('API script path:', apiScriptPath);

  // Check if the Python executable exists
  if (!fs.existsSync(pythonPath)) {
    console.error('Python executable not found at:', pythonPath);
    return;
  }

  // Check if the API script exists
  if (!fs.existsSync(apiScriptPath)) {
    console.error('API script not found at:', apiScriptPath);
    return;
  }

  pythonProcess = spawn(pythonPath, [apiScriptPath]);

  pythonProcess.stdout.on('data', (data) => {
    console.log(`Python server output: ${data}`);
  });

  pythonProcess.stderr.on('data', (data) => {
    console.error(`Python server error: ${data}`);
  });

  pythonProcess.on('close', (code) => {
    console.log(`Python server process exited with code ${code}`);
  });
}

// Handle the global shortcut
function registerShortcut() {
  globalShortcut.register('Option+H', () => {
    if (process.platform === 'darwin') {
      const selectedText = clipboard.readText();

      if (selectedText) {
        fetch('http://127.0.0.1:8123/runs', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            content: selectedText
          }),
        })
        .then(response => response.json())
        .then(responseData => {
          console.log('API response:', responseData);

          let content = responseData;
          if (typeof responseData === 'string') {
            try {
              content = JSON.parse(responseData);
            } catch (e) {
              content = responseData;
            }
          }

          createPopupWindow(content);

          if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('response-ready', content);
          }
        })
        .catch(error => {
          console.error('Error calling API:', error);
        });
      }
    }
  });
}

// Properly quit the application
function quitApp() {
  isQuitting = true;

  // Kill the Python process if it exists
  if (pythonProcess) {
    pythonProcess.kill();
    pythonProcess = null;
  }

  // Close the main window
  if (mainWindow) {
    mainWindow.close();
    mainWindow = null;
  }

  // Close the popup window if it exists
  if (popupWindow) {
    popupWindow.close();
    popupWindow = null;
  }

  // Remove the tray icon
  if (tray) {
    tray.destroy();
    tray = null;
  }

  // Quit the app
  app.quit();
}

// App ready event
app.whenReady().then(() => {
  createTray();
  createWindow();
  startPythonServer();
  registerShortcut();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

// Quit when all windows are closed
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    quitApp();
  }
});

// Clean up resources on quit
app.on('will-quit', () => {
  globalShortcut.unregisterAll();

  if (pythonProcess) {
    pythonProcess.kill();
    pythonProcess = null;
  }
});

// Set up auto-launch on startup
app.setLoginItemSettings({
  openAtLogin: true,
  path: app.getPath('exe')
});