import { build, Platform } from 'electron-builder';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const require = createRequire(import.meta.url);
const connected = process.argv.includes('--connected');
const backend = path.join(root, 'releases/backend');
if (!connected && !fs.existsSync(path.join(backend, 'launch.json'))) throw new Error('Offline release requires participant A’s releases/backend/launch.json. Use build:desktop:connected only for an explicitly connected-only build.');
if (!fs.existsSync(path.join(root, 'apps/web/dist/index.html'))) throw new Error('Run build:web first.');
await build({ targets: Platform.WINDOWS.createTarget('dir'), config: {
  electronDist: path.dirname(require('electron')),
  appId: 'team.cashproof.desktop', productName: connected ? 'CashProof Connected' : 'CashProof',
  directories: { app: path.join(root, 'apps/desktop'), output: path.join(root, 'apps/desktop/dist', connected ? 'connected' : 'offline') },
  files: ['main.cjs', 'security.cjs', '*preload.cjs', 'launcher.*', 'assets/**', 'package.json'],
  extraResources: [
    { from: path.join(root, 'apps/web/dist'), to: 'web', filter: ['index.html', 'mark.svg', 'assets/**', 'fonts/**'] },
    { from: path.join(root, 'packages/contracts/desktop-launch.schema.json'), to: 'contracts/desktop-launch.schema.json' },
    ...(!connected ? [{ from: backend, to: 'backend' }] : []),
  ],
  asar: true, npmRebuild: false,
  win: { signAndEditExecutable: false, icon: path.join(root, 'apps/desktop/assets/app.ico'), target: 'dir' },
} });
console.log(connected ? 'Connected-only Windows folder built. No offline inference bundle included.' : 'Offline resources packaged; actual offline inference still requires verification on the qualified GPU host.');
