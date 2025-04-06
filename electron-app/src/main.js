const { app, BrowserWindow, Tray, Menu, globalShortcut, ipcMain, clipboard, screen } = require('electron');
const path = require('path');
const { spawn, exec } = require('child_process');
const fs = require('fs');
const fetch = require('node-fetch');
const log = require('electron-log');

let tray = null;
let mainWindow = null;
let pythonProcess = null;
let isQuitting = false;
let popupWindow = null;

// Get environment variables
const IS_DEV = process.env.NODE_ENV === 'development';
const DEFAULT_PORT = 8123;
const API_PORT = process.env.API_PORT || (IS_DEV ? 8124 : DEFAULT_PORT);
const API_HOST = '127.0.0.1';

// Path to the Python executable in the virtual environment
const pythonPath = IS_DEV
  ? path.join(__dirname, '..', '..', '.venv', 'bin', 'python')
  : path.join(process.resourcesPath, '.venv', 'bin', 'python');

const apiScriptPath = IS_DEV
  ? path.join(__dirname, '..', '..', 'src', 'api.py')
  : path.join(process.resourcesPath, 'src', 'api.py');

// Create the tray icon
function createTray() {
  tray = new Tray(path.join(__dirname, 'assets', 'icon.png'));
  tray.setToolTip('Snitch');

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Show',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
        }
      }
    },
    { type: 'separator' },
    {
      label: 'Debug Info',
      click: () => {
        showDebugInfo();
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
    width: 800,
    height: 600,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    },
    show: IS_DEV // Only show the window in development mode
  });

  mainWindow.loadFile(path.join(__dirname, 'index.html'));
  
  if (IS_DEV) {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
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
async function startPythonServer() {
  log.info(`Starting Python server with: ${pythonPath} ${apiScriptPath}`);
  log.info(`Environment: ${IS_DEV ? 'development' : 'production'}`);
  log.info(`API Host: ${API_HOST}`);
  log.info(`API Port: ${API_PORT}`);
  
  if (!fs.existsSync(pythonPath)) {
    log.error(`Python executable not found at: ${pythonPath}`);
    throw new Error(`Python executable not found at: ${pythonPath}`);
  }

  if (!fs.existsSync(apiScriptPath)) {
    log.error(`API script not found at: ${apiScriptPath}`);
    throw new Error(`API script not found at: ${apiScriptPath}`);
  }

  const env = {
    ...process.env,
    NODE_ENV: IS_DEV ? 'development' : 'production',
    API_PORT: API_PORT.toString(),
    PYTHONUNBUFFERED: '1'
  };

  return new Promise((resolve, reject) => {
    pythonProcess = spawn(pythonPath, [apiScriptPath], {
      stdio: ['pipe', 'pipe', 'pipe'],
      env
    });

    pythonProcess.stdout.on('data', (data) => {
      log.info(`Python stdout: ${data}`);
    });

    pythonProcess.stderr.on('data', (data) => {
      log.error(`Python stderr: ${data}`);
    });

    pythonProcess.on('error', (error) => {
      log.error(`Failed to start Python process: ${error}`);
      reject(error);
    });

    pythonProcess.on('exit', (code, signal) => {
      log.info(`Python process exited with code ${code} and signal ${signal}`);
      pythonProcess = null;
      if (!isQuitting && code !== 0) {
        reject(new Error(`Python process exited with code ${code}`));
      }
    });

    // Wait for server to start
    setTimeout(() => {
      resolve();
    }, 2000);
  });
}

// Handle the global shortcut
function registerShortcut() {
  globalShortcut.register('Option+H', () => {
    if (process.platform === 'darwin') {
      const selectedText = clipboard.readText();

      if (selectedText) {
        fetch(`http://${API_HOST}:${API_PORT}/runs`, {
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

// Function to check system logs for clues
function checkSystemLogs() {
  console.log('Checking system logs for clues...');
  
  // On macOS, we can check the system log for our app
  if (process.platform === 'darwin') {
    const appName = app.getName();
    const logCommand = `log show --predicate 'process == "${appName}"' --last 5m | grep -i "quit\\|exit\\|terminate\\|kill"`;
    
    exec(logCommand, (error, stdout, stderr) => {
      if (error) {
        console.error('Error checking system logs:', error);
        return;
      }
      
      console.log('System log entries related to quitting:');
      console.log(stdout);
      
      // If we found relevant logs, show them in a window
      if (stdout.trim()) {
        const logWindow = new BrowserWindow({
          width: 800,
          height: 400,
          title: 'System Logs',
          webPreferences: {
            nodeIntegration: true,
            contextIsolation: false
          }
        });
        
        const htmlContent = `
          <!DOCTYPE html>
          <html>
          <head>
            <style>
              body { font-family: monospace; padding: 20px; }
              h2 { color: #333; }
              pre { background: #f5f5f5; padding: 10px; border-radius: 5px; white-space: pre-wrap; }
            </style>
          </head>
          <body>
            <h2>System Logs Related to Quitting</h2>
            <pre>${stdout.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</pre>
          </body>
          </html>
        `;
        
        logWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(htmlContent)}`);
      }
    });
  }
}

// Function to forcefully kill the Python process
async function killPythonProcess() {
  if (!pythonProcess) return;

  log.info('Attempting to kill Python process');
  
  return new Promise((resolve) => {
    // Set up exit handler
    pythonProcess.once('exit', (code, signal) => {
      log.info(`Python process exited with code ${code} and signal ${signal}`);
      pythonProcess = null;
      resolve();
    });
    
    // First try SIGTERM
    pythonProcess.kill('SIGTERM');
    
    // If process doesn't exit within 5 seconds, use SIGKILL
    setTimeout(() => {
      if (pythonProcess) {
        log.info('Python process still running, sending SIGKILL');
        pythonProcess.kill('SIGKILL');
        
        // On macOS, also try pkill with a more specific pattern
        if (process.platform === 'darwin') {
          exec('pkill -f "python.*api.py"', (error) => {
            if (error) {
              log.error('Error killing Python processes:', error);
            }
            // Additional cleanup for macOS
            exec(`lsof -ti:${API_PORT} | xargs kill -9`, (error) => {
              if (error) {
                log.error(`Error killing process on port ${API_PORT}:`, error);
              }
            });
          });
        }
      }
    }, 5000);
  });
}

// Properly quit the application
async function quitApp() {
  if (isQuitting) return;
  isQuitting = true;
  
  log.info('Quitting application');
  
  try {
    // Kill Python process first and wait for it to complete
    await killPythonProcess();
    
    // Additional cleanup for macOS
    if (process.platform === 'darwin') {
      await new Promise(resolve => {
        exec(`lsof -ti:${API_PORT} | xargs kill -9`, (error) => {
          if (error) {
            log.error('Error in final port cleanup:', error);
          }
          resolve();
        });
      });
    }
    
    // Clean up windows and tray
    if (mainWindow) {
      log.info('Destroying main window');
      mainWindow.destroy();
      mainWindow = null;
    }
    
    if (popupWindow) {
      log.info('Destroying popup window');
      popupWindow.destroy();
      popupWindow = null;
    }
    
    if (tray) {
      log.info('Destroying tray icon');
      tray.destroy();
      tray = null;
    }
    
    app.quit();
  } catch (error) {
    log.error('Error during quit:', error);
    app.exit(1);
  }
}

// App ready event
app.on('ready', async () => {
  try {
    await startPythonServer();
    createTray();
    
    if (IS_DEV) {
      createWindow();
    }
    
    registerShortcut();

    app.on('activate', () => {
      if (IS_DEV && BrowserWindow.getAllWindows().length === 0) {
        createWindow();
      }
    });
  } catch (error) {
    log.error('Failed to start application:', error);
    app.exit(1);
  }
});

// Quit when all windows are closed
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    quitApp();
  }
});

// Clean up resources on quit
app.on('before-quit', async (event) => {
  if (!isQuitting) {
    event.preventDefault();
    await quitApp();
  }
});

app.on('will-quit', () => {
  console.log('will-quit event fired');
  if (pythonProcess) {
    console.log('Killing Python process from will-quit handler');
    killPythonProcess();
  }
});

app.on('quit', () => {
  console.log('quit event fired');
  if (pythonProcess) {
    console.log('Killing Python process from quit handler');
    killPythonProcess();
  }
});

// Set up auto-launch on startup
app.setLoginItemSettings({
  openAtLogin: true,
  path: app.getPath('exe')
});

// Function to show debug information
function showDebugInfo() {
  const debugWindow = new BrowserWindow({
    width: 600,
    height: 400,
    title: 'Debug Information',
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    }
  });

  // Get process information
  const processInfo = {
    pythonProcess: pythonProcess ? {
      pid: pythonProcess.pid,
      killed: pythonProcess.killed,
      exitCode: pythonProcess.exitCode
    } : null,
    mainWindow: mainWindow ? {
      isDestroyed: mainWindow.isDestroyed(),
      isVisible: mainWindow.isVisible(),
      isMinimized: mainWindow.isMinimized()
    } : null,
    popupWindow: popupWindow ? {
      isDestroyed: popupWindow.isDestroyed(),
      isVisible: popupWindow.isVisible(),
      isMinimized: popupWindow.isMinimized()
    } : null,
    tray: tray ? 'exists' : null,
    isQuitting: isQuitting
  };

  // Get running Python processes
  exec('ps aux | grep python | grep -v grep', (error, stdout, stderr) => {
    const pythonProcesses = stdout.split('\n').filter(line => line.trim() !== '');
    
    const htmlContent = `
      <!DOCTYPE html>
      <html>
      <head>
        <style>
          body { font-family: monospace; padding: 20px; }
          h2 { color: #333; }
          pre { background: #f5f5f5; padding: 10px; border-radius: 5px; }
          button { margin: 10px 0; padding: 5px 10px; }
        </style>
      </head>
      <body>
        <h2>Debug Information</h2>
        <h3>Process State</h3>
        <pre>${JSON.stringify(processInfo, null, 2)}</pre>
        
        <h3>Running Python Processes</h3>
        <pre>${pythonProcesses.join('\n')}</pre>
        
        <button id="forceQuit">Force Quit App</button>
        <button id="killPython">Kill All Python Processes</button>
        
        <script>
          const { ipcRenderer } = require('electron');
          
          document.getElementById('forceQuit').addEventListener('click', () => {
            ipcRenderer.send('force-quit');
          });
          
          document.getElementById('killPython').addEventListener('click', () => {
            ipcRenderer.send('kill-python');
          });
        </script>
      </body>
      </html>
    `;
    
    debugWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(htmlContent)}`);
  });
}

// Add IPC handlers for debug actions
ipcMain.on('force-quit', () => {
  console.log('Force quit requested from debug window');
  // Kill Python process first
  killPythonProcess();
  // Then exit the app
  app.exit(0);
});

ipcMain.on('kill-python', () => {
  console.log('Kill Python requested from debug window');
  killPythonProcess();
});

// Handle IPC messages
ipcMain.on('quit-app', async () => {
  await quitApp();
});