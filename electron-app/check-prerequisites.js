const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

console.log('Checking prerequisites for Snitch Electron App...');

// Check if Node.js is installed
try {
  const nodeVersion = execSync('node --version').toString().trim();
  console.log(`✅ Node.js version: ${nodeVersion}`);
} catch (error) {
  console.error('❌ Node.js is not installed.');
  console.log('\nPlease install Node.js from https://nodejs.org/');
  console.log('After installation, restart your terminal and try again.');
  process.exit(1);
}

// Check if npm is installed
try {
  const npmVersion = execSync('npm --version').toString().trim();
  console.log(`✅ npm version: ${npmVersion}`);
} catch (error) {
  console.error('❌ npm is not installed.');
  console.log('\nPlease install npm or reinstall Node.js from https://nodejs.org/');
  console.log('After installation, restart your terminal and try again.');
  process.exit(1);
}

// Check if Python is installed
try {
  const pythonVersion = execSync('python --version').toString().trim();
  console.log(`✅ Python is installed: ${pythonVersion}`);
} catch (error) {
  console.warn('⚠️ Python is not installed or not in PATH.');
  console.log('\nPlease install Python from https://www.python.org/');
  console.log('After installation, restart your terminal and try again.');
}

// Check if the virtual environment exists
const venvPath = path.join(__dirname, '..', '.venv');
if (fs.existsSync(venvPath)) {
  console.log('✅ Virtual environment exists');
} else {
  console.warn('⚠️ Virtual environment not found.');
  console.log('\nPlease make sure the virtual environment is set up correctly.');
  console.log('You can create it using:');
  console.log('  python -m venv .venv');
  console.log('  source .venv/bin/activate');
  console.log('  pip install -r src/requirements.txt');
}

// Check if the API script exists
const apiScriptPath = path.join(__dirname, '..', 'src', 'api.py');
if (fs.existsSync(apiScriptPath)) {
  console.log('✅ API script exists');
} else {
  console.error('❌ API script not found.');
  console.log('\nPlease make sure the API script exists at:', apiScriptPath);
  process.exit(1);
}

console.log('\nAll prerequisites are satisfied!');
console.log('You can now run the setup script:');
console.log('  ./setup.sh'); 