const { ipcRenderer, clipboard } = require('electron')

document.getElementById('checkClipboard').addEventListener('click', () => {
  const text = clipboard.readText()
  document.getElementById('debugOutput').textContent = `Clipboard content: ${text}`
})

document.getElementById('testAPI').addEventListener('click', async () => {
  try {
    const response = await fetch('http://127.0.0.1:8000/api/test')
    const data = await response.json()
    document.getElementById('debugOutput').textContent = `API Response: ${JSON.stringify(data, null, 2)}`
  } catch (error) {
    document.getElementById('debugOutput').textContent = `API Error: ${error.message}`
  }
})

document.getElementById('showProcessInfo').addEventListener('click', () => {
  const info = {
    platform: process.platform,
    arch: process.arch,
    versions: process.versions
  }
  document.getElementById('debugOutput').textContent = `Process Info: ${JSON.stringify(info, null, 2)}`
})

document.getElementById('clearLogs').addEventListener('click', () => {
  document.getElementById('debugOutput').textContent = 'Debug output will appear here...'
})