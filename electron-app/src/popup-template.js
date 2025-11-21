function generateHtmlContent(response, loading, lastActiveTab = 0) {
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

  const output = response.output || {};

  // Create tabs for each section
  const tabs = [];
  const tabContents = [];

  // First, find if 'existent' exists and add it first
  const outputEntries = Object.entries(output);
  const existentEntry = outputEntries.find(([key]) => key === 'existent');
  const otherEntries = outputEntries.filter(([key]) => key !== 'existent');

  let startTabIndex = 0;
  const processedEntries = existentEntry ? [existentEntry, ...otherEntries] : otherEntries;

  processedEntries.forEach(([key, value]) => {
    if (Array.isArray(value) && value.length > 0 && typeof value[0] === 'object' && value[0].value !== undefined) {
      value.forEach((item, itemIndex) => {
        const tag = item.tag || '';
        const tabName = `${key} ${tag}`.trim();
        const uniqueId = `${key}-array-${itemIndex}`;
        const isActive = startTabIndex === lastActiveTab;
        tabs.push(`<div class="tab ${isActive ? 'active' : ''}" data-tab="${startTabIndex}" data-unique-id="${uniqueId}">${tabName}</div>`);
        tabContents.push(`<div class="tab-content ${isActive ? 'active' : ''}" id="tab-${startTabIndex}">${item.value}</div>`);
        startTabIndex++;
      });
    } else {
      const uniqueId = `${key}-string`;
      const isActive = startTabIndex === lastActiveTab;
      tabs.push(`<div class="tab ${isActive ? 'active' : ''}" data-tab="${startTabIndex}" data-unique-id="${uniqueId}">${key}</div>`);
      tabContents.push(`<div class="tab-content ${isActive ? 'active' : ''}" id="tab-${startTabIndex}">${value}</div>`);
      startTabIndex++;
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

module.exports = { generateHtmlContent };
