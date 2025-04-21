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
let lastPopupBounds = {
  width: 400,
  height: 200,
  x: undefined,
  y: undefined
};

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
  tray.setToolTip('CheatKey');

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
function createPopupWindow(responseText, isLoading = false) {
  // Get the cursor position
  const cursorPosition = screen.getCursorScreenPoint();
  const display = screen.getDisplayNearestPoint(cursorPosition);

  // Function to generate HTML content
  const generateHtmlContent = (response, loading) => {
    if (loading) {
      return `
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
              background-color: rgb(255, 255, 255);
              backdrop-filter: blur(16px);
              -webkit-backdrop-filter: blur(16px);
              border-radius: 12px;
              box-shadow: 0 4px 24px rgba(0, 0, 0, 0.12);
              height: 100%;
              color: #1a1a1a;
              box-sizing: border-box;
              border: 1px solid rgba(0, 0, 0, 0.06);
            }
            .content-wrapper {
              height: calc(100% - 30px);
              margin-top: 30px;
              overflow-y: auto;
              overflow-x: hidden;
              padding: 0 4px 16px 4px;
              box-sizing: border-box;
            }
            .titlebar {
              position: absolute;
              top: 0;
              left: 0;
              right: 0;
              height: 30px;
              background-color: rgb(255, 255, 255);
              backdrop-filter: blur(16px);
              -webkit-backdrop-filter: blur(16px);
              border-top-left-radius: 12px;
              border-top-right-radius: 12px;
              cursor: move;
              display: flex;
              align-items: center;
              justify-content: flex-end;
              padding-right: 10px;
              -webkit-app-region: drag;
              z-index: 1000;
              border-bottom: 1px solid rgba(0, 0, 0, 0.06);
            }
            .close-btn {
              width: 20px;
              height: 20px;
              border-radius: 50%;
              background-color: rgba(0, 0, 0, 0.05);
              display: flex;
              align-items: center;
              justify-content: center;
              cursor: pointer;
              font-size: 14px;
              color: #666;
              margin-left: 5px;
              -webkit-app-region: no-drag;
              transition: all 0.2s ease;
            }
            .close-btn:hover {
              background-color: rgba(0, 0, 0, 0.1);
              color: #333;
            }
            .loading-dots {
              display: flex;
              align-items: center;
              justify-content: center;
              height: 100%;
              font-size: 24px;
              color: #666;
            }
            .dot {
              opacity: 0;
              animation: fadeInOut 1s infinite;
            }
            .dot:nth-child(2) { animation-delay: 0.333s; }
            .dot:nth-child(3) { animation-delay: 0.666s; }
            @keyframes fadeInOut {
              0%, 100% { opacity: 0; }
              50% { opacity: 1; }
            }
          </style>
        </head>
        <body>
          <div class="container">
            <div class="titlebar" id="titlebar">
              <div class="close-btn" id="closeBtn">×</div>
            </div>
            <div class="content-wrapper" id="content">
              <div class="loading-dots">
                <span class="dot">.</span>
                <span class="dot">.</span>
                <span class="dot">.</span>
              </div>
            </div>
          </div>
        </body>
        </html>
      `;
    }

    console.log('Generating HTML for response:', JSON.stringify(response));

    const sections = [];
    const output = response.output || {};

    console.log('Output dictionary:', JSON.stringify(output));

    // Add a section for each key in the output dictionary
    Object.entries(output).forEach(([key, value]) => {
      console.log(`Processing key: ${key}, value: ${value}`);

      if (key === 'math_result' || key === 'math_script') {
        // Skip these as they're handled together
        return;
      }

      // Format the key for display (e.g., "tz_conversion" -> "TZ Conversion")
      const displayKey = key.split('_').map(word =>
        word.charAt(0).toUpperCase() + word.slice(1)
      ).join(' ');

      sections.push(`<div class="section"><b>${displayKey}</b><div class="content">${value}</div></div>`);
    });

    // Handle math result and script together
    if (output.math_result || output.math_script) {
      sections.push(`<div class="section"><b>Math</b><div class="content">${output.math_result}</div><div class="script">${output.math_script}</div></div>`);
    }

    console.log('Generated sections:', sections);

    return `
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
            background-color: rgb(255, 255, 255);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border-radius: 12px;
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.12);
            height: 100%;
            color: #1a1a1a;
            box-sizing: border-box;
            border: 1px solid rgba(0, 0, 0, 0.06);
          }
          .content-wrapper {
            height: calc(100% - 30px);
            margin-top: 30px;
            overflow-y: auto;
            overflow-x: hidden;
            padding: 0 4px 16px 4px;
            box-sizing: border-box;
          }
          .titlebar {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 30px;
            background-color: rgb(255, 255, 255);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border-top-left-radius: 12px;
            border-top-right-radius: 12px;
            cursor: move;
            display: flex;
            align-items: center;
            justify-content: flex-end;
            padding-right: 10px;
            -webkit-app-region: drag;
            z-index: 1000;
            border-bottom: 1px solid rgba(0, 0, 0, 0.06);
          }
          .close-btn {
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background-color: rgba(0, 0, 0, 0.05);
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            font-size: 14px;
            color: #666;
            margin-left: 5px;
            -webkit-app-region: no-drag;
            transition: all 0.2s ease;
          }
          .close-btn:hover {
            background-color: rgba(0, 0, 0, 0.1);
            color: #333;
          }
          .section {
            margin-bottom: 16px;
            padding: 8px;
            background: rgba(0, 0, 0, 0.02);
            border-radius: 8px;
          }
          .section b {
            display: block;
            margin-bottom: 8px;
            color: #666;
            font-size: 12px;
            text-transform: uppercase;
          }
          .content {
            font-family: "SF Mono", SFMono-Regular, ui-monospace, Menlo, Monaco, Consolas, monospace;
            font-size: 12px;
            line-height: 1.4;
            white-space: pre-wrap;
            color: #1a1a1a;
          }
          .script {
            margin-top: 8px;
            padding-top: 8px;
            border-top: 1px solid rgba(0, 0, 0, 0.06);
            font-family: "SF Mono", SFMono-Regular, ui-monospace, Menlo, Monaco, Consolas, monospace;
            font-size: 11px;
            line-height: 1.4;
            white-space: pre-wrap;
            color: #666;
          }
          ::-webkit-scrollbar {
            width: 8px;
          }
          ::-webkit-scrollbar-track {
            background: transparent;
          }
          ::-webkit-scrollbar-thumb {
            background: rgba(0, 0, 0, 0.1);
            border-radius: 4px;
          }
          ::-webkit-scrollbar-thumb:hover {
            background: rgba(0, 0, 0, 0.15);
          }
        </style>
      </head>
      <body>
        <div class="container">
          <div class="titlebar" id="titlebar">
            <div class="close-btn" id="closeBtn">×</div>
          </div>
          <div class="content-wrapper" id="content">
            ${sections.join('\n')}
          </div>
        </div>
      </body>
      </html>
    `;
  }

  // Create or update the popup window
  if (!popupWindow || popupWindow.isDestroyed()) {
    popupWindow = new BrowserWindow({
      width: lastPopupBounds.width,
      height: lastPopupBounds.height,
      x: lastPopupBounds.x || cursorPosition.x,
      y: lastPopupBounds.y || cursorPosition.y,
      frame: false,
      transparent: true,
      resizable: true,
      webPreferences: {
        nodeIntegration: true,
        contextIsolation: false
      }
    });

    // Store window bounds when resized
    popupWindow.on('resize', () => {
      const bounds = popupWindow.getBounds();
      lastPopupBounds.width = bounds.width;
      lastPopupBounds.height = bounds.height;
      lastPopupBounds.x = bounds.x;
      lastPopupBounds.y = bounds.y;
    });

    // Close popup when clicking the close button
    popupWindow.webContents.on('did-finish-load', () => {
      popupWindow.webContents.executeJavaScript(`
        document.getElementById('closeBtn').addEventListener('click', () => {
          window.close();
        });
      `);
    });
  }

  // Load the content
  const htmlContent = generateHtmlContent(responseText, isLoading);
  popupWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(htmlContent)}`);
  popupWindow.show();
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
  globalShortcut.register('Command+Option+H', () => {
    if (process.platform === 'darwin') {
      const selectedText = clipboard.readText();

      if (selectedText) {
        // Show loading popup immediately
        createPopupWindow('', true);

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

          // Update the existing popup with actual content
          createPopupWindow(responseData, false);

          if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('response-ready', responseData);
          }
        })
        .catch(error => {
          console.error('Error calling API:', error);
          // Show error in popup
          createPopupWindow('Error: Failed to get response from API', false);
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
      if (stdout && stdout.trim()) {
        const logWindow = new BrowserWindow({
          width: 800,
          height: 400,
          title: 'System Logs',
          webPreferences: {
            nodeIntegration: true,
            contextIsolation: false
          }
        });

        // Convert stdout to string if it's not already
        const logText = String(stdout);

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
            <pre>${logText.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</pre>
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

// Handle process info request
ipcMain.on('get-process-info', (event) => {
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
    isQuitting: isQuitting,
    env: {
      NODE_ENV: process.env.NODE_ENV,
      API_PORT: API_PORT,
      IS_DEV: IS_DEV
    }
  };

  event.reply('process-info-response', processInfo);
});