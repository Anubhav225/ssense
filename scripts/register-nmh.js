// scripts/register-nmh.js
const { writeFileSync, mkdirSync, existsSync } = require('fs');
const { join, resolve } = require('path');
const { homedir, platform } = require('os');
const { execSync } = require('child_process');

const EXT_ID = process.argv[2];

if (!EXT_ID) {
  console.error('❌ Usage: node scripts/register-nmh.js <YOUR_EXTENSION_ID>');
  console.error('   Get your Extension ID from chrome://extensions (Enable Developer Mode)');
  process.exit(1);
}

// Resolve the absolute path to the compiled Rust binary
const osPlatform = platform();
const ext = osPlatform === 'win32' ? '.exe' : '';

const candidatePaths = [
  resolve(__dirname, '../target/release/ssense-native-daemon' + ext),
  resolve(__dirname, '../apps/native-daemon/target/release/ssense-native-daemon' + ext),
  resolve(__dirname, '../target/debug/ssense-native-daemon' + ext),
  resolve(__dirname, '../apps/native-daemon/target/debug/ssense-native-daemon' + ext),
];

let binPath = candidatePaths.find(p => existsSync(p));

if (!binPath) {
  console.error(`❌ Rust binary not found in candidates:\n  ${candidatePaths.join('\n  ')}\nRun 'cargo build --release' first.`);
  process.exit(1);
}

const manifest = {
  name: 'com.ssense.daemon',
  description: 'Ssense DPDP Edge AI',
  path: binPath,
  type: 'stdio',
  allowed_origins: [`chrome-extension://${EXT_ID}/`]
};

try {
  if (osPlatform === 'win32') {
    // Write JSON to a safe, space-free location on Windows
    const appData = process.env.APPDATA || join(homedir(), 'AppData', 'Roaming');
    const ssenseDir = join(appData, 'Ssense');
    if (!existsSync(ssenseDir)) mkdirSync(ssenseDir, { recursive: true });
    
    const jsonPath = join(ssenseDir, 'com.ssense.daemon.json');
    writeFileSync(jsonPath, JSON.stringify(manifest, null, 2));
    
    // Register in Windows Registry
    execSync(`reg add "HKCU\\Software\\Google\\Chrome\\NativeMessagingHosts\\com.ssense.daemon" /ve /t REG_SZ /d "${jsonPath}" /f`);
    console.log('✅ Registered Native Messaging Host in Windows Registry.');
  } else {
    let dir = osPlatform === 'darwin' 
      ? join(homedir(), 'Library/Application Support/Google/Chrome/NativeMessagingHosts')
      : join(homedir(), '.config/google-chrome/NativeMessagingHosts');
    
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
    writeFileSync(join(dir, 'com.ssense.daemon.json'), JSON.stringify(manifest, null, 2));
    console.log(`✅ Registered Native Messaging Host at ${dir}`);
  }
  console.log('🚀 Native Messaging Host successfully linked to Chrome Extension!');
} catch (err) {
  console.error('❌ Failed to register Native Messaging Host:', err.message);
  process.exit(1);
}
