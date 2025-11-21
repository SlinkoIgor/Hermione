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
let isPopupShowingContent = false;
let lastPopupBounds = {
  width: 400,
  height: 200,
  x: undefined,
  y: undefined
};
let lastActiveTab = 0;

// Get environment variables
const IS_DEV = process.env.NODE_ENV === 'development';
const DEFAULT_PORT = 8123;
const API_PORT = process.env.API_PORT || DEFAULT_PORT;
const API_HOST = '127.0.0.1';
const PROVIDER_MODE = process.env.PROVIDER_MODE || 'litellm_only';

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

  // Check if we have content to show
  const hasContent = responseText && responseText.output && Object.keys(responseText.output).length > 0;

  // Function to generate HTML content
  const generateHtmlContent = (response, loading) => {
    // Only show loading screen if loading is true AND we have no content
    const shouldShowLoading = loading && (!response || !response.output || Object.keys(response.output).length === 0);
    
    if (shouldShowLoading) {
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
              background-color: #f5f5f5;
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

    const output = response.output || {};
    console.log('Output dictionary:', JSON.stringify(output));

    // Create tabs for each section
    const tabs = [];
    const tabContents = [];
    let activeTab = 0;

    // First, find if 'existent' exists and add it first
    const outputEntries = Object.entries(output);
    const existentEntry = outputEntries.find(([key]) => key === 'existent');
    const otherEntries = outputEntries.filter(([key]) => key !== 'existent');

    // Add existent tab first if it exists
    let startTabIndex = 0;
    if (existentEntry) {
      const [key, value] = existentEntry;
      if (Array.isArray(value) && value.length > 0 && typeof value[0] === 'object' && value[0].value !== undefined) {
        value.forEach((item, itemIndex) => {
          const tag = item.tag || '';
          const tabName = `${key} ${tag}`.trim();
          const isActive = startTabIndex === lastActiveTab;
          const uniqueId = `${key}-array-${itemIndex}`;
          tabs.push(`<div class="tab ${isActive ? 'active' : ''}" data-tab="${startTabIndex}" data-unique-id="${uniqueId}">${tabName}</div>`);
          tabContents.push(`<div class="tab-content ${isActive ? 'active' : ''}" id="tab-${startTabIndex}">${item.value}</div>`);
          startTabIndex++;
        });
      } else {
        const isActive = startTabIndex === lastActiveTab;
        const uniqueId = `${key}-string`;
        tabs.push(`<div class="tab ${isActive ? 'active' : ''}" data-tab="${startTabIndex}" data-unique-id="${uniqueId}">${key}</div>`);
        tabContents.push(`<div class="tab-content ${isActive ? 'active' : ''}" id="tab-${startTabIndex}">${value}</div>`);
        startTabIndex = 1;
      }
    }

    // Add remaining tabs
    let globalTabIndex = startTabIndex;
    otherEntries.forEach(([key, value]) => {
      if (Array.isArray(value) && value.length > 0 && typeof value[0] === 'object' && value[0].value !== undefined) {
        value.forEach((item, itemIndex) => {
          const tag = item.tag || '';
          const tabName = `${key} ${tag}`.trim();
          const isActive = globalTabIndex === lastActiveTab;
          const uniqueId = `${key}-array-${itemIndex}`;
          tabs.push(`<div class="tab ${isActive ? 'active' : ''}" data-tab="${globalTabIndex}" data-unique-id="${uniqueId}">${tabName}</div>`);
          tabContents.push(`<div class="tab-content ${isActive ? 'active' : ''}" id="tab-${globalTabIndex}">${item.value}</div>`);
          globalTabIndex++;
        });
      } else {
        const isActive = globalTabIndex === lastActiveTab;
        const uniqueId = `${key}-string`;
        tabs.push(`<div class="tab ${isActive ? 'active' : ''}" data-tab="${globalTabIndex}" data-unique-id="${uniqueId}">${key}</div>`);
        tabContents.push(`<div class="tab-content ${isActive ? 'active' : ''}" id="tab-${globalTabIndex}">${value}</div>`);
        globalTabIndex++;
      }
    });

    // Ensure at least one tab is active if no tabs were added
    if (tabs.length === 0) {
      tabs.push(`<div class="tab active" data-tab="0">No Content</div>`);
      tabContents.push(`<div class="tab-content active" id="tab-0">No content available</div>`);
    }
    
    // If no tab is active (lastActiveTab is beyond current tabs), activate first tab
    const hasActiveTab = tabs.some(tab => tab.includes('class="tab active"'));
    if (!hasActiveTab && tabs.length > 0) {
      tabs[0] = tabs[0].replace('class="tab"', 'class="tab active"');
      tabContents[0] = tabContents[0].replace('class="tab-content"', 'class="tab-content active"');
    }

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
            font-family: "SF Mono", SFMono-Regular, ui-monospace, Menlo, Monaco, Consolas, monospace;
          }
          .container {
            position: relative;
            margin: 0;
            padding: 8px;
            background-color: #f5f5f5;
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
            justify-content: space-between;
            padding: 0 10px;
            z-index: 1000;
            border-bottom: 1px solid rgba(0, 0, 0, 0.06);
          }
          .drag-area {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 30px;
            -webkit-app-region: drag;
            z-index: 1001;
          }
          .tabs-container {
            display: flex;
            align-items: center;
            overflow-x: auto;
            flex-grow: 1;
            margin-right: 10px;
            scrollbar-width: none;
            -ms-overflow-style: none;
            position: relative;
            z-index: 1002;
            pointer-events: auto;
          }
          .tabs-container::-webkit-scrollbar {
            display: none;
          }
          .tab {
            padding: 4px 10px;
            margin-right: 4px;
            background-color: rgba(0, 0, 0, 0.05);
            border-radius: 4px;
            font-size: 11px;
            cursor: pointer;
            white-space: nowrap;
            transition: all 0.2s ease;
            -webkit-app-region: no-drag;
          }
          .tab:hover {
            background-color: rgba(0, 0, 0, 0.1);
          }
          .tab.active {
            background-color: rgba(0, 0, 0, 0.15);
            font-weight: bold;
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
            -webkit-app-region: no-drag;
            transition: all 0.2s ease;
          }
          .close-btn:hover {
            background-color: rgba(0, 0, 0, 0.1);
            color: #333;
          }
          .tab-content {
            display: none;
            padding: 8px;
            background: transparent;
            font-size: 12px;
            line-height: 1.4;
            white-space: pre-wrap;
            color: #1a1a1a;
          }
          .tab-content.active {
            display: block;
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
            border-radius: 4px;
          }
        </style>
      </head>
      <body>
        <div class="container">
          <div class="titlebar" id="titlebar">
            <div class="drag-area"></div>
            <div class="tabs-container" id="tabsContainer">
              ${tabs.join('\n')}
            </div>
            <div class="close-btn" id="closeBtn">×</div>
          </div>
          <div class="content-wrapper" id="content">
            ${tabContents.join('\n')}
          </div>
        </div>
        <script>
          document.addEventListener('DOMContentLoaded', function() {
            // Tab switching functionality
            // Use event delegation for better handling of dynamic elements
            const tabsContainer = document.getElementById('tabsContainer');
            
            if (tabsContainer) {
              tabsContainer.addEventListener('click', function(e) {
                const tab = e.target.closest('.tab');
                if (!tab) return;
                
                // Update active tab
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                
                // Update active content
                const tabIndex = tab.getAttribute('data-tab');
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                
                const content = document.getElementById('tab-' + tabIndex);
                if (content) {
                  content.classList.add('active');
                }
              });
            }
            
            // Close button functionality
            document.getElementById('closeBtn').addEventListener('click', function() {
              window.close();
            });
            
            // Keyboard navigation
            document.addEventListener('keydown', function(e) {
              if (e.key === 'Escape') {
                window.close();
              } else if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
                const activeTab = document.querySelector('.tab.active');
                if (!activeTab) return;
                
                const activeTabIndex = parseInt(activeTab.getAttribute('data-tab'));
                const tabs = document.querySelectorAll('.tab');
                const tabsCount = tabs.length;
                
                let newTabIndex;
                if (e.key === 'ArrowLeft') {
                  newTabIndex = (activeTabIndex - 1 + tabsCount) % tabsCount;
                } else {
                  newTabIndex = (activeTabIndex + 1) % tabsCount;
                }
                
                // Find the tab with this data-tab attribute and click it
                const targetTab = document.querySelector('.tab[data-tab="' + newTabIndex + '"]');
                if (targetTab) targetTab.click();
              }
            });

            // Handle copy event to ensure plain text copying
            document.addEventListener('copy', function(e) {
              const selection = window.getSelection();
              const selectedText = selection.toString();
              if (selectedText) {
                e.preventDefault();
                e.clipboardData.setData('text/plain', selectedText);
              }
            });
          });
        </script>
      </body>
      </html>
    `;
  }

  // Determine if we need to create a new window or reload the existing one
  let shouldCreateOrReload = false;
  
  if (!popupWindow || popupWindow.isDestroyed()) {
    shouldCreateOrReload = true;
    isPopupShowingContent = false;
  } else {
    // If we have content but the window is currently showing the loading screen (isPopupShowingContent is false),
    // we MUST reload to switch to the content layout.
    if (hasContent && !isPopupShowingContent) {
      shouldCreateOrReload = true;
    }
  }

  if (shouldCreateOrReload) {
    // Create window if needed
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

      popupWindow.on('closed', () => {
        popupWindow = null;
        isPopupShowingContent = false;
      });

      // Setup IPC listeners
      popupWindow.webContents.on('did-finish-load', () => {
        popupWindow.webContents.executeJavaScript(`
          const { ipcRenderer } = require('electron');
          const closeBtn = document.getElementById('closeBtn');
          if (closeBtn) {
            closeBtn.addEventListener('click', () => {
              ipcRenderer.send('close-popup');
            });
          }
          
          // Handle dynamic tab additions
          ipcRenderer.on('add-tab', (event, output) => {
            const tabsContainer = document.getElementById('tabsContainer');
            const tabContentsContainer = document.getElementById('content');
            
            if (!tabsContainer || !tabContentsContainer) return;
            
            // Remove loading if present
            const loadingDiv = document.querySelector('.loading-dots');
            if (loadingDiv) {
              loadingDiv.closest('.content-wrapper').innerHTML = '';
            }
            
            for (const [key, value] of Object.entries(output)) {
              // Helper to process adding a tab
              const processTab = (itemValue, itemTag, uniqueId) => {
                // Check if tab already exists
                const existingTab = document.querySelector(\`.tab[data-unique-id="\${uniqueId}"]\`);
                if (existingTab) {
                  const tabIndex = existingTab.getAttribute('data-tab');
                  const contentDiv = document.getElementById('tab-' + tabIndex);
                  if (contentDiv) {
                    contentDiv.textContent = itemValue;
                  }
                  return;
                }
                
                const tabCount = document.querySelectorAll('.tab').length;
                const tabName = (key + ' ' + (itemTag || '')).trim();
                
                const newTab = document.createElement('div');
                newTab.className = 'tab';
                newTab.setAttribute('data-tab', tabCount);
                newTab.setAttribute('data-unique-id', uniqueId);
                newTab.textContent = tabName;
                
                const newContent = document.createElement('div');
                newContent.className = 'tab-content';
                newContent.id = 'tab-' + tabCount;
                newContent.textContent = itemValue;
                
                tabsContainer.appendChild(newTab);
                tabContentsContainer.appendChild(newContent);
                
                // Auto-show the new tab if it's the first one or "existent"
                const isFirst = tabCount === 0;
                const isExistent = key === 'existent';
                
                if (isFirst || isExistent) {
                   // Use a small timeout to ensure UI update if rapidly adding
                   setTimeout(() => {
                      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                      newTab.classList.add('active');
                      newContent.classList.add('active');
                   }, 10);
                }
              };

              if (Array.isArray(value) && value.length > 0 && typeof value[0] === 'object' && value[0].value !== undefined) {
                value.forEach((item, index) => {
                  const uniqueId = \`\${key}-array-\${index}\`;
                  processTab(item.value, item.tag, uniqueId);
                });
              } else if (value) {
                const uniqueId = \`\${key}-string\`;
                processTab(value, '', uniqueId);
              }
            }
          });
          
          ipcRenderer.on('loading-complete', () => {
            const loadingDiv = document.querySelector('.loading-dots');
            if (loadingDiv) {
               // Optional: show "No content" if empty? 
               // For now do nothing, as content replaces loading.
            }
          });
          true; // Return serializable value
        `);
      });
    }

    // Load the content
    const htmlContent = generateHtmlContent(responseText, isLoading);
    popupWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(htmlContent)}`);
    popupWindow.show();
    
    // Update state
    isPopupShowingContent = hasContent;
    
  } else {
    // Window exists and we are already showing content (or compatible state).
    // Send update via IPC.
    popupWindow.webContents.send('add-tab', responseText.output);
    
    // Update state just in case
    if (hasContent) {
       isPopupShowingContent = true;
    }
    
    if (!isLoading) {
      popupWindow.webContents.send('loading-complete');
    }
  }
  
  return popupWindow;
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
        let accumulatedOutput = {};
        let allComplete = false;

        const updatePopup = async (output, isLoading) => {
          // Save active tab before closing window
          if (popupWindow && !popupWindow.isDestroyed()) {
            try {
              const activeIndex = await popupWindow.webContents.executeJavaScript(`
                (() => {
                  const activeTab = document.querySelector('.tab.active');
                  return activeTab ? parseInt(activeTab.getAttribute('data-tab')) : 0;
                })()
              `);
              lastActiveTab = activeIndex || 0;
            } catch (e) {
              // Ignore errors, keep last value
            }
          }
          
          const responseData = {
            tool_warning: false,
            output: output
          };
          createPopupWindow(responseData, isLoading);
        };

        updatePopup({}, true);

        fetch(`http://${API_HOST}:${API_PORT}/runs/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            content: selectedText,
            provider_mode: PROVIDER_MODE
          }),
        })
        .then(async response => {
          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
          }

          const stream = response.body;
          const decoder = new TextDecoder();
          let buffer = '';

          return new Promise((resolve, reject) => {
            stream.on('data', (chunk) => {
              buffer += decoder.decode(chunk, { stream: true });
              const lines = buffer.split('\n');
              buffer = lines.pop() || '';

              for (const line of lines) {
                if (line.startsWith('data: ')) {
                  try {
                    const data = JSON.parse(line.slice(6));
                    
                    if (data.error) {
                      console.error('Stream error:', data.error);
                      updatePopup({ error: data.error }, false);
                      reject(new Error(data.error));
                      return;
                    }

                    if (data.output_key) {
                      if (!accumulatedOutput[data.output_key]) {
                        accumulatedOutput[data.output_key] = [];
                      }
                      
                      const newItem = {
                        value: data.value,
                        tag: data.tag,
                        model: data.model
                      };
                      
                      accumulatedOutput[data.output_key].push(newItem);

                      // Update popup with accumulated output
                      updatePopup(accumulatedOutput, !data.all_complete);
                      
                      if (data.all_complete) {
                        allComplete = true;
                        if (mainWindow && !mainWindow.isDestroyed()) {
                          mainWindow.webContents.send('response-ready', {
                            tool_warning: false,
                            output: accumulatedOutput
                          });
                        }
                        resolve();
                      }
                    } else if (data.output) {
                      Object.assign(accumulatedOutput, data.output);
                      
                      updatePopup(accumulatedOutput, !data.all_complete);
                      
                      if (data.all_complete) {
                        allComplete = true;
                        if (mainWindow && !mainWindow.isDestroyed()) {
                          mainWindow.webContents.send('response-ready', {
                            tool_warning: false,
                            output: accumulatedOutput
                          });
                        }
                        resolve();
                      }
                    }
                  } catch (e) {
                    console.error('Error parsing stream data:', e);
                  }
                }
              }
            });

            stream.on('end', () => {
              if (buffer.trim()) {
                const line = buffer.trim();
                if (line.startsWith('data: ')) {
                  try {
                    const data = JSON.parse(line.slice(6));
                    if (data.output_key) {
                      if (!accumulatedOutput[data.output_key]) {
                        accumulatedOutput[data.output_key] = [];
                      }
                      const newItem = {
                        value: data.value,
                        tag: data.tag,
                        model: data.model
                      };
                      accumulatedOutput[data.output_key].push(newItem);
                      
                      updatePopup(accumulatedOutput, false);
                    } else if (data.output) {
                      Object.assign(accumulatedOutput, data.output);
                      
                      updatePopup(accumulatedOutput, false);
                    }
                  } catch (e) {
                    console.error('Error parsing final stream data:', e);
                  }
                }
              }
              if (!allComplete) {
                resolve();
              }
            });

            stream.on('error', (error) => {
              console.error('Stream error:', error);
              reject(error);
            });
          });
        })
        .catch(error => {
          console.error('Error calling API:', error);
          updatePopup({ error: `Failed to get response from API: ${error.message}` }, false);
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

// Add this near the other IPC handlers
ipcMain.on('close-popup', () => {
  if (popupWindow && !popupWindow.isDestroyed()) {
    popupWindow.destroy();
    popupWindow = null;
  }
});
