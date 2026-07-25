const { app, BrowserWindow, globalShortcut, ipcMain, clipboard, screen, Menu, dialog, systemPreferences } = require('electron');
const path = require('path');
const { spawn, exec, execFile } = require('child_process');
const fs = require('fs');
const fetch = require('node-fetch');
const log = require('electron-log');
const { TAB_ICONS, TAB_ORDER } = require('./constants');

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
let hasShownPopupForCurrentRequest = false;
let userClosedPopupForCurrentRequest = false;
let isShortcutHandling = false;
let handleTextRequest = null;
let activeRequestToken = 0;
let activeRequestController = null;

// Get environment variables
const IS_DEV = process.env.NODE_ENV === 'development';
const DEFAULT_PORT = 8123;
const API_PORT = process.env.API_PORT || DEFAULT_PORT;
const API_HOST = '127.0.0.1';
const PROVIDER_MODE = process.env.PROVIDER_MODE || 'openai_only';

// Path to the Python executable in the virtual environment
const pythonPath = IS_DEV
  ? path.join(__dirname, '..', '..', '.venv', 'bin', 'python')
  : path.join(process.resourcesPath, '.venv', 'bin', 'python');

const apiScriptPath = IS_DEV
  ? path.join(__dirname, '..', '..', 'src', 'api.py')
  : path.join(process.resourcesPath, 'src', 'api.py');

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
  // If user closed the popup for this request, don't create/show it again
  if (userClosedPopupForCurrentRequest) {
    return null;
  }

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
              font-family: "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", sans-serif;
              filter: grayscale(100%) contrast(150%);
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
            .manual-text-input {
              box-sizing: border-box;
              width: 100%;
              height: 100%;
              min-height: 120px;
              padding: 0;
              resize: none;
              border: 0;
              border-radius: 0;
              outline: none;
              background: transparent;
              color: #1a1a1a;
              font: inherit;
              line-height: 1.4;
            }
            .manual-text-input:focus {
              background: transparent;
            }
            .manual-input-content {
              box-sizing: border-box;
              height: 100%;
            }
            .error-text {
              color: #c0392b;
              font-size: 12px;
              line-height: 1.5;
              white-space: pre-wrap;
              word-break: break-word;
            }
            .loading-dots {
              display: flex;
              align-items: center;
              justify-content: center;
              height: 100%;
              font-size: 32px;
              color: #666;
              font-family: -apple-system, BlinkMacSystemFont, sans-serif;
              letter-spacing: 2px;
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
            .copy-btn {
              position: absolute;
              bottom: 8px;
              right: 8px;
              width: 24px;
              height: 24px;
              border-radius: 4px;
              background-color: transparent;
              display: flex;
              align-items: center;
              justify-content: center;
              cursor: pointer;
              color: #ccc;
              -webkit-app-region: no-drag;
              z-index: 100;
            }
            .copy-btn.copied {
              color: #666;
            }
          </style>
        </head>
        <body>
          <div class="container">
            <div class="titlebar" id="titlebar">
              <div class="drag-area"></div>
              <div class="tabs-container" id="tabsContainer"></div>
              <div class="close-btn" id="closeBtn">×</div>
            </div>
            <div class="content-wrapper" id="content">
              <div class="loading-dots" id="loadingDots">
                <span class="dot">.</span>
                <span class="dot">.</span>
                <span class="dot">.</span>
              </div>
            </div>
            <div class="copy-btn" id="copyBtn" title="Copy">
              <svg width="13" height="13" viewBox="0 0 13 13" fill="none" overflow="visible" xmlns="http://www.w3.org/2000/svg">
                <rect x="3.5" y="0.5" width="8.5" height="9.5" rx="1.2" stroke="currentColor" stroke-width="1.1"/>
                <rect x="0.5" y="3.5" width="8.5" height="9.5" rx="1.2" stroke="currentColor" stroke-width="1.1" fill="#f5f5f5"/>
              </svg>
            </div>
          </div>
          <script>
            const { ipcRenderer } = require('electron');
            const tabIcons = ${JSON.stringify(TAB_ICONS)};
            const tabOrder = ${JSON.stringify(TAB_ORDER)};
            const getTabIcon = (key) => tabIcons[key] || '';
            const getTabOrder = (key) => tabOrder[key] !== undefined ? tabOrder[key] : 99;

            document.addEventListener('DOMContentLoaded', function() {
              const tabsContainer = document.getElementById('tabsContainer');
              const tabContentsContainer = document.getElementById('content');

              if (tabsContainer) {
                tabsContainer.addEventListener('click', function(e) {
                  const tab = e.target.closest('.tab');
                  if (!tab) return;

                  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                  tab.classList.add('active');

                  const tabIndex = tab.getAttribute('data-tab');
                  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

                  const content = document.getElementById('tab-' + tabIndex);
                  if (content) {
                    content.classList.add('active');
                  }
                });
              }

              document.getElementById('closeBtn').addEventListener('click', function() {
                ipcRenderer.send('close-popup');
              });

              const doCopy = () => {
                const active = document.querySelector('.tab-content.active');
                if (!active) return;
                const { clipboard } = require('electron');
                clipboard.writeText(active.innerText);
                const btn = document.getElementById('copyBtn');
                if (btn) {
                  btn.classList.add('copied');
                  setTimeout(() => btn.classList.remove('copied'), 1500);
                }
              };

              document.getElementById('copyBtn').addEventListener('click', doCopy);

              document.addEventListener('keydown', function(e) {
                if (e.key === 'Escape') {
                  ipcRenderer.send('close-popup');
                } else if (e.key === ' ') {
                  e.preventDefault();
                  doCopy();
                } else if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
                  const tabs = Array.from(document.querySelectorAll('.tab'));
                  if (!tabs.length) return;
                  const activeIdx = tabs.findIndex(t => t.classList.contains('active'));
                  if (activeIdx === -1) return;
                  const next = e.key === 'ArrowLeft'
                    ? (activeIdx - 1 + tabs.length) % tabs.length
                    : (activeIdx + 1) % tabs.length;
                  tabs[next].click();
                } else if (e.metaKey || e.ctrlKey) {
                  if (e.key === 'c') {
                    const selectedText = window.getSelection().toString();
                    if (selectedText) {
                      e.preventDefault();
                      require('electron').clipboard.writeText(selectedText);
                    }
                  } else {
                    const { webFrame } = require('electron');
                    if (e.key === '=' || e.key === '+') {
                      e.preventDefault();
                      webFrame.setZoomFactor(webFrame.getZoomFactor() + 0.1);
                    } else if (e.key === '-') {
                      e.preventDefault();
                      webFrame.setZoomFactor(Math.max(0.5, webFrame.getZoomFactor() - 0.1));
                    } else if (e.key === '0') {
                      e.preventDefault();
                      webFrame.setZoomFactor(1.0);
                    }
                  }
                }
              });

              ipcRenderer.on('add-tab', (event, output) => {
                if (!tabsContainer || !tabContentsContainer) return;

                const loadingDiv = document.getElementById('loadingDots');
                if (loadingDiv) {
                  loadingDiv.remove();
                }

                for (const [key, value] of Object.entries(output)) {
                  const processTab = (itemValue, itemTag, uniqueId, itemElapsed) => {
                    const existingTab = document.querySelector('.tab[data-unique-id="' + uniqueId + '"]');
                    if (existingTab) {
                      const tabIndex = existingTab.getAttribute('data-tab');
                      const contentDiv = document.getElementById('tab-' + tabIndex);
                      if (contentDiv) {
                        contentDiv.innerHTML = itemValue;
                      }
                      return;
                    }

                    const tabCount = document.querySelectorAll('.tab').length;
                    const tabName = (getTabIcon(key) + ' ' + (itemTag || '')).trim();
                    if (!tabName) return;

                    const myOrder = getTabOrder(key);

                    const newTab = document.createElement('div');
                    newTab.className = 'tab';
                    newTab.setAttribute('data-tab', tabCount);
                    newTab.setAttribute('data-unique-id', uniqueId);
                    newTab.setAttribute('data-order', myOrder);
                    newTab.textContent = tabName;

                    const newContent = document.createElement('div');
                    newContent.className = 'tab-content';
                    newContent.id = 'tab-' + tabCount;
                    newContent.innerHTML = key === 'error'
                      ? '<span class="error-text">' + itemValue + '</span>'
                      : itemValue;

                    let inserted = false;
                    const existingTabs = tabsContainer.querySelectorAll('.tab');
                    for (const t of existingTabs) {
                      if (parseInt(t.getAttribute('data-order')) > myOrder) {
                        tabsContainer.insertBefore(newTab, t);
                        inserted = true;
                        break;
                      }
                    }
                    if (!inserted) tabsContainer.appendChild(newTab);
                    tabContentsContainer.appendChild(newContent);

                    const isFirst = tabCount === 0;
                    const isExistent = key === 'existent';

                    if (isFirst || isExistent) {
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
                      const uniqueId = key + '-array-' + index;
                      processTab(item.value, item.tag, uniqueId, item.elapsed);
                    });
                  } else if (value) {
                    const uniqueId = key + '-string';
                    processTab(value, '', uniqueId, null);
                  }
                }
              });
            });
          </script>
        </body>
        </html>
      `;
    }

    console.log('Generating HTML for response:', JSON.stringify(response));

    const output = response.output || {};
    console.log('Output dictionary:', JSON.stringify(output));

    const getTabIcon = (key) => TAB_ICONS[key] || '';

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
          const tabName = `${getTabIcon(key)} ${tag}`.trim();
          if (!tabName) return;
          const isActive = startTabIndex === lastActiveTab;
          const uniqueId = `${key}-array-${itemIndex}`;
          tabs.push(`<div class="tab ${isActive ? 'active' : ''}" data-tab="${startTabIndex}" data-unique-id="${uniqueId}">${tabName}</div>`);
          tabContents.push(`<div class="tab-content ${isActive ? 'active' : ''}" id="tab-${startTabIndex}">${item.value}</div>`);
          startTabIndex++;
        });
      } else {
        const isActive = startTabIndex === lastActiveTab;
        const uniqueId = `${key}-string`;
        const tabName = getTabIcon(key);
        if (tabName) {
          tabs.push(`<div class="tab ${isActive ? 'active' : ''}" data-tab="${startTabIndex}" data-unique-id="${uniqueId}">${tabName}</div>`);
          tabContents.push(`<div class="tab-content ${isActive ? 'active' : ''}" id="tab-${startTabIndex}">${value}</div>`);
          startTabIndex = 1;
        }
      }
    }

    // Add remaining tabs
    let globalTabIndex = startTabIndex;
    otherEntries.forEach(([key, value]) => {
      if (Array.isArray(value) && value.length > 0 && typeof value[0] === 'object' && value[0].value !== undefined) {
        value.forEach((item, itemIndex) => {
          const tag = item.tag || '';
          const tabName = `${getTabIcon(key)} ${tag}`.trim();
          if (!tabName) return;
          const isActive = globalTabIndex === lastActiveTab;
          const uniqueId = `${key}-array-${itemIndex}`;
          tabs.push(`<div class="tab ${isActive ? 'active' : ''}" data-tab="${globalTabIndex}" data-unique-id="${uniqueId}">${tabName}</div>`);
          tabContents.push(`<div class="tab-content ${isActive ? 'active' : ''}" id="tab-${globalTabIndex}">${item.value}</div>`);
          globalTabIndex++;
        });
      } else {
        const isActive = globalTabIndex === lastActiveTab;
        const uniqueId = `${key}-string`;
        const tabName = getTabIcon(key);
        if (tabName) {
          tabs.push(`<div class="tab ${isActive ? 'active' : ''}" data-tab="${globalTabIndex}" data-unique-id="${uniqueId}">${tabName}</div>`);
          const tabValue = key === 'error'
            ? `<span class="error-text">${String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</span>`
            : value;
          tabContents.push(`<div class="tab-content ${isActive ? 'active' : ''}" id="tab-${globalTabIndex}">${tabValue}</div>`);
          globalTabIndex++;
        }
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
            font-family: "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", sans-serif;
            filter: grayscale(100%) contrast(150%);
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
          .manual-text-input {
            box-sizing: border-box;
            width: 100%;
            height: 100%;
            min-height: 120px;
            padding: 0;
            resize: none;
            border: 0;
            border-radius: 0;
            outline: none;
            background: transparent;
            color: #1a1a1a;
            font: inherit;
            line-height: 1.4;
          }
          .manual-text-input:focus {
            background: transparent;
          }
          .manual-input-content {
            box-sizing: border-box;
            height: 100%;
          }
          .error-text {
            color: #c0392b;
            font-size: 12px;
            line-height: 1.5;
            white-space: pre-wrap;
            word-break: break-word;
          }
          .loading-dots {
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100%;
            font-size: 32px;
            color: #666;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            letter-spacing: 2px;
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
          .copy-btn {
            position: absolute;
            bottom: 8px;
            right: 8px;
            width: 24px;
            height: 24px;
            border-radius: 4px;
            background-color: transparent;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            color: #ccc;
            -webkit-app-region: no-drag;
            z-index: 100;
          }
          .copy-btn.copied {
            color: #666;
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
          <div class="copy-btn" id="copyBtn" title="Copy">
            <svg width="13" height="13" viewBox="0 0 13 13" fill="none" overflow="visible" xmlns="http://www.w3.org/2000/svg">
              <rect x="3.5" y="0.5" width="8.5" height="9.5" rx="1.2" stroke="currentColor" stroke-width="1.1"/>
              <rect x="0.5" y="3.5" width="8.5" height="9.5" rx="1.2" stroke="currentColor" stroke-width="1.1" fill="#f5f5f5"/>
            </svg>
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

            const doCopy = () => {
              const active = document.querySelector('.tab-content.active');
              if (!active) return;
              const { clipboard } = require('electron');
              clipboard.writeText(active.innerText);
              const btn = document.getElementById('copyBtn');
              if (btn) {
                btn.classList.add('copied');
                setTimeout(() => btn.classList.remove('copied'), 1500);
              }
            };

            document.getElementById('copyBtn').addEventListener('click', doCopy);

            document.addEventListener('keydown', function(e) {
              if (e.key === 'Escape') {
                ipcRenderer.send('close-popup');
              } else if (e.key === ' ') {
                e.preventDefault();
                doCopy();
              } else if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
                const tabs = Array.from(document.querySelectorAll('.tab'));
                if (!tabs.length) return;
                const activeIdx = tabs.findIndex(t => t.classList.contains('active'));
                if (activeIdx === -1) return;
                const next = e.key === 'ArrowLeft'
                  ? (activeIdx - 1 + tabs.length) % tabs.length
                  : (activeIdx + 1) % tabs.length;
                tabs[next].click();
              } else if (e.metaKey || e.ctrlKey) {
                if (e.key === 'c') {
                  const selectedText = window.getSelection().toString();
                  if (selectedText) {
                    e.preventDefault();
                    require('electron').clipboard.writeText(selectedText);
                  }
                } else {
                  const { webFrame } = require('electron');
                  if (e.key === '=' || e.key === '+') {
                    e.preventDefault();
                    webFrame.setZoomFactor(webFrame.getZoomFactor() + 0.1);
                  } else if (e.key === '-') {
                    e.preventDefault();
                    webFrame.setZoomFactor(Math.max(0.5, webFrame.getZoomFactor() - 0.1));
                  } else if (e.key === '0') {
                    e.preventDefault();
                    webFrame.setZoomFactor(1.0);
                  }
                }
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
    // Only reload if we are starting a new request (loading, no content) and the window is currently showing content.
    if (!hasContent && isLoading && isPopupShowingContent) {
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

            const tabIcons = ${JSON.stringify(TAB_ICONS)};
            const tabOrder = ${JSON.stringify(TAB_ORDER)};
            const getTabIcon = (key) => tabIcons[key] || '';
            const getTabOrder = (key) => tabOrder[key] !== undefined ? tabOrder[key] : 99;

            const loadingDiv = document.getElementById('loadingDots');
            if (loadingDiv) {
              loadingDiv.remove();
            }

            for (const [key, value] of Object.entries(output)) {
              const processTab = (itemValue, itemTag, uniqueId, itemElapsed) => {
                const existingTab = document.querySelector(\`.tab[data-unique-id="\${uniqueId}"]\`);
                if (existingTab) {
                  const tabIndex = existingTab.getAttribute('data-tab');
                  const contentDiv = document.getElementById('tab-' + tabIndex);
                  if (contentDiv) {
                    contentDiv.innerHTML = itemValue;
                  }
                  return;
                }

                const tabCount = document.querySelectorAll('.tab').length;
                const tabName = (getTabIcon(key) + ' ' + (itemTag || '')).trim();
                if (!tabName) return;

                const myOrder = getTabOrder(key);

                const newTab = document.createElement('div');
                newTab.className = 'tab';
                newTab.setAttribute('data-tab', tabCount);
                newTab.setAttribute('data-unique-id', uniqueId);
                newTab.setAttribute('data-order', myOrder);
                newTab.textContent = tabName;

                const newContent = document.createElement('div');
                newContent.className = 'tab-content';
                newContent.id = 'tab-' + tabCount;
                newContent.innerHTML = key === 'error'
                  ? '<span class="error-text">' + itemValue + '</span>'
                  : itemValue;

                let inserted = false;
                const existingTabs = tabsContainer.querySelectorAll('.tab');
                for (const t of existingTabs) {
                  if (parseInt(t.getAttribute('data-order')) > myOrder) {
                    tabsContainer.insertBefore(newTab, t);
                    inserted = true;
                    break;
                  }
                }
                if (!inserted) tabsContainer.appendChild(newTab);
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
                  processTab(item.value, item.tag, uniqueId, item.elapsed);
                });
              } else if (value) {
                const uniqueId = \`\${key}-string\`;
                processTab(value, '', uniqueId, null);
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
        `).catch(err => {
          console.error('Error executing script in popup:', err);
        });
      });
    }

    // Load the content
    const htmlContent = generateHtmlContent(responseText, isLoading);
    popupWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(htmlContent)}`);

    if (!hasShownPopupForCurrentRequest) {
      app.focus({ steal: true });
      popupWindow.show();
      popupWindow.focus();
      hasShownPopupForCurrentRequest = true;
    }

    // Update state
    isPopupShowingContent = hasContent;
    
  } else {
    // Window exists - send update via IPC (works for both loading screen and content).
    if (hasContent) {
      popupWindow.webContents.send('add-tab', responseText.output);
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

function delay(milliseconds) {
  return new Promise(resolve => setTimeout(resolve, milliseconds));
}

function sendCopyShortcut() {
  return new Promise((resolve, reject) => {
    execFile(
      '/usr/bin/osascript',
      [
        '-e',
        'tell application "System Events" to key code 8 using command down'
      ],
      error => {
        if (error) {
          reject(error);
          return;
        }
        resolve();
      }
    );
  });
}

function readPasteboardChangeCount() {
  return new Promise((resolve, reject) => {
    execFile(
      '/usr/bin/osascript',
      [
        '-l',
        'JavaScript',
        '-e',
        'ObjC.import("AppKit"); Number($.NSPasteboard.generalPasteboard.changeCount)'
      ],
      (error, stdout) => {
        if (error) {
          reject(error);
          return;
        }
        const changeCount = Number.parseInt(stdout.trim(), 10);
        if (!Number.isInteger(changeCount)) {
          reject(new Error('Unable to read pasteboard change count'));
          return;
        }
        resolve(changeCount);
      }
    );
  });
}

function readSelectedTextViaAccessibility() {
  return new Promise((resolve, reject) => {
    execFile(
      '/usr/bin/osascript',
      [
        '-e',
        'tell application "System Events"',
        '-e',
        'try',
        '-e',
        'set activeProcess to first application process whose frontmost is true',
        '-e',
        'set focusedElement to value of attribute "AXFocusedUIElement" of activeProcess',
        '-e',
        'set selectedText to value of attribute "AXSelectedText" of focusedElement',
        '-e',
        'if selectedText is missing value then return "__CHEATKEY_NO_SELECTION__"',
        '-e',
        'return "__CHEATKEY_SELECTED__" & selectedText',
        '-e',
        'on error',
        '-e',
        'return "__CHEATKEY_UNSUPPORTED__"',
        '-e',
        'end try',
        '-e',
        'end tell'
      ],
      (error, stdout) => {
        if (error) {
          reject(error);
          return;
        }
        const result = stdout.replace(/\r?\n$/, '');
        if (result.startsWith('__CHEATKEY_SELECTED__')) {
          resolve({
            status: 'selected',
            text: result.slice('__CHEATKEY_SELECTED__'.length)
          });
          return;
        }
        if (result === '__CHEATKEY_NO_SELECTION__') {
          resolve({ status: 'none', text: '' });
          return;
        }
        resolve({ status: 'unsupported', text: '' });
      }
    );
  });
}

function waitForShortcutRelease() {
  return new Promise((resolve, reject) => {
    const script = `
      ObjC.import('CoreGraphics');
      ObjC.import('Foundation');
      const deadline = Date.now() + 5000;
      const isPressed = () => {
        const state = $.kCGEventSourceStateCombinedSessionState;
        const flags = Number($.CGEventSourceFlagsState(state));
        const hPressed = Number($.CGEventSourceKeyState(state, 4)) !== 0;
        return (flags & 1572864) !== 0 || hPressed;
      };
      while (isPressed() && Date.now() < deadline) {
        $.NSThread.sleepForTimeInterval(0.025);
      }
      if (isPressed()) {
        throw new Error('Timed out waiting for shortcut release');
      }
    `;

    execFile(
      '/usr/bin/osascript',
      ['-l', 'JavaScript', '-e', script],
      error => {
        if (error) {
          reject(error);
          return;
        }
        resolve();
      }
    );
  });
}

async function copySelectedText() {
  if (!systemPreferences.isTrustedAccessibilityClient(true)) {
    await dialog.showMessageBox({
      type: 'warning',
      title: 'Accessibility Permission Required',
      message: 'CheatKey needs Accessibility access to copy selected text.',
      detail: 'Enable CheatKey in System Settings → Privacy & Security → Accessibility, then try again.',
      buttons: ['OK']
    });
    return null;
  }

  const accessibilitySelection = await readSelectedTextViaAccessibility();
  if (accessibilitySelection.status === 'selected') {
    if (!accessibilitySelection.text.trim()) {
      return null;
    }
    clipboard.writeText(accessibilitySelection.text);
    return accessibilitySelection.text;
  }
  if (accessibilitySelection.status === 'none') {
    return null;
  }

  await waitForShortcutRelease();
  const previousChangeCount = await readPasteboardChangeCount();
  await sendCopyShortcut();
  await delay(50);
  const currentChangeCount = await readPasteboardChangeCount();

  if (currentChangeCount === previousChangeCount) {
    return null;
  }

  const copiedText = clipboard.readText();
  return copiedText.trim() ? copiedText : null;
}

function createTextInputWindow() {
  if (popupWindow && !popupWindow.isDestroyed()) {
    popupWindow.destroy();
  }

  lastActiveTab = 0;
  hasShownPopupForCurrentRequest = false;
  userClosedPopupForCurrentRequest = false;

  const inputWindow = createPopupWindow({
    tool_warning: false,
    output: {
      existent: '<textarea id="manualTextInput" class="manual-text-input" placeholder="Enter text and press Enter"></textarea>'
    }
  }, false);

  if (!inputWindow) {
    return;
  }

  inputWindow.webContents.once('did-finish-load', () => {
    inputWindow.webContents.executeJavaScript(`
      (() => {
        const input = document.getElementById('manualTextInput');
        if (!input) return;
        const { ipcRenderer } = require('electron');
        input.closest('.tab-content')?.classList.add('manual-input-content');
        document.getElementById('copyBtn')?.remove();
        input.addEventListener('keydown', event => {
          event.stopPropagation();
          if (event.key === 'Escape') {
            event.preventDefault();
            ipcRenderer.send('close-popup');
            return;
          }
          if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            if (input.value.trim()) {
              ipcRenderer.send('submit-manual-text', input.value);
            }
          }
        });
        input.focus();
      })()
    `);
  });
}

// Handle the global shortcut
function registerShortcut() {
  handleTextRequest = async (providedText = null) => {
    if (process.platform === 'darwin') {
      if (isShortcutHandling) {
        return;
      }

      isShortcutHandling = true;
      const requestToken = ++activeRequestToken;
      if (activeRequestController) {
        activeRequestController.abort();
        activeRequestController = null;
      }
      const isManualInput = (
        typeof providedText === 'string' && Boolean(providedText.trim())
      );
      let selectedText;

      try {
        selectedText = isManualInput ? providedText : await copySelectedText();
      } catch (error) {
        log.error(`Failed to copy selected text: ${error}`);
        await dialog.showMessageBox({
          type: 'error',
          title: 'Unable to Copy Selected Text',
          message: 'CheatKey could not copy the selected text.',
          detail: 'Check that CheatKey is enabled in System Settings → Privacy & Security → Accessibility.',
          buttons: ['OK']
        });
        return;
      } finally {
        isShortcutHandling = false;
      }

      if (selectedText) {
        let accumulatedOutput = {};
        let allComplete = false;

        const updatePopup = async (output, isLoading) => {
          if (requestToken !== activeRequestToken) {
            return;
          }

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
          if (requestToken !== activeRequestToken) {
            return;
          }
          createPopupWindow(responseData, isLoading);
        };

        if (
          isManualInput &&
          popupWindow &&
          !popupWindow.isDestroyed()
        ) {
          await popupWindow.webContents.executeJavaScript(`
            (() => {
              const tabs = document.getElementById('tabsContainer');
              const content = document.getElementById('content');
              if (tabs) tabs.innerHTML = '';
              if (content) {
                content.innerHTML = \`
                  <div class="loading-dots" id="loadingDots">
                    <span class="dot">.</span>
                    <span class="dot">.</span>
                    <span class="dot">.</span>
                  </div>
                \`;
              }
              document.getElementById('copyBtn')?.remove();
            })()
          `);
          isPopupShowingContent = false;
        } else if (popupWindow && !popupWindow.isDestroyed()) {
          popupWindow.destroy();
          popupWindow = null;
          isPopupShowingContent = false;
        }

        // Reset flags for new request
        lastActiveTab = 0;
        hasShownPopupForCurrentRequest = isManualInput;
        userClosedPopupForCurrentRequest = false;

        if (!isManualInput) {
          updatePopup({}, true);
        }

        const requestStartTime = Date.now();
        const requestController = new AbortController();
        activeRequestController = requestController;

        fetch(`http://${API_HOST}:${API_PORT}/runs/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            content: selectedText,
            provider_mode: PROVIDER_MODE
          }),
          signal: requestController.signal
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
              if (requestToken !== activeRequestToken) {
                return;
              }
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

                      const elapsedMs = Date.now() - requestStartTime;
                      const newItem = {
                        value: data.value,
                        tag: data.tag,
                        model: data.model,
                        elapsed: elapsedMs
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
                      for (const [k, v] of Object.entries(data.output)) {
                        if (!accumulatedOutput[k]) {
                          accumulatedOutput[k] = v;
                        }
                      }

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
              if (requestToken !== activeRequestToken) {
                resolve();
                return;
              }
              if (buffer.trim()) {
                const line = buffer.trim();
                if (line.startsWith('data: ')) {
                  try {
                    const data = JSON.parse(line.slice(6));
                    if (data.output_key) {
                      if (!accumulatedOutput[data.output_key]) {
                        accumulatedOutput[data.output_key] = [];
                      }
                      const elapsedMs = Date.now() - requestStartTime;
                      const newItem = {
                        value: data.value,
                        tag: data.tag,
                        model: data.model,
                        elapsed: elapsedMs
                      };
                      accumulatedOutput[data.output_key].push(newItem);

                      updatePopup(accumulatedOutput, false);
                    } else if (data.output) {
                      for (const [k, v] of Object.entries(data.output)) {
                        if (!accumulatedOutput[k]) {
                          accumulatedOutput[k] = v;
                        }
                      }

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
          if (error.name === 'AbortError') {
            return;
          }
          console.error('Error calling API:', error);
          updatePopup({ error: `Failed to get response from API: ${error.message}` }, false);
        })
        .finally(() => {
          if (activeRequestController === requestController) {
            activeRequestController = null;
          }
        });
      } else {
        createTextInputWindow();
      }
    }
  };

  globalShortcut.register('Command+Option+H', () => {
    handleTextRequest();
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

    // Clean up windows
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

    app.quit();
  } catch (error) {
    log.error('Error during quit:', error);
    app.exit(1);
  }
}

// App ready event
app.on('ready', async () => {
  const menu = Menu.buildFromTemplate([
    {
      label: app.name,
      submenu: [
        {
          label: `About CheatKey`,
          click: () => {
            dialog.showMessageBox({
              type: 'info',
              title: 'About CheatKey',
              message: `CheatKey`,
              detail: `Version ${app.getVersion()}`,
              buttons: ['OK']
            });
          }
        },
        { type: 'separator' },
        { role: 'quit' }
      ]
    },
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        { role: 'selectAll' }
      ]
    }
  ]);
  Menu.setApplicationMenu(menu);

  try {
    await startPythonServer();

    if (IS_DEV) {
      createWindow();
    }

    registerShortcut();

    app.on('activate', () => {
      if (popupWindow && !popupWindow.isDestroyed() && !popupWindow.isVisible()) {
        popupWindow.show();
      } else if (IS_DEV && BrowserWindow.getAllWindows().length === 0) {
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
    popupWindow.hide();
  }
});

ipcMain.on('submit-manual-text', (event, text) => {
  if (typeof text !== 'string' || !text.trim() || !handleTextRequest) {
    return;
  }
  handleTextRequest(text);
});
