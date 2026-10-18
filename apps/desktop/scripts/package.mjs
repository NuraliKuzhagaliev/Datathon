import { build, Platform } from 'electron-builder';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { verifyBackendResources } from './verify-backend-resources.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const require = createRequire(import.meta.url);
const connected = process.argv.includes('--connected');
const outputFlag = process.argv.indexOf('--output-name');
const outputName = outputFlag < 0 ? (connected ? 'connected' : 'offline') : process.argv[outputFlag + 1];
if (!outputName || !/^[a-z0-9][a-z0-9-]{0,48}$/.test(outputName)) throw new Error('--output-name must be a simple folder name.');
const backendFlag = process.argv.indexOf('--backend-dir');
if (backendFlag >= 0 && (!process.argv[backendFlag + 1] || process.argv[backendFlag + 1].startsWith('--'))) throw new Error('--backend-dir requires a bundle directory.');
const backend = backendFlag < 0 ? path.join(root, 'releases/backend') : path.resolve(root, process.argv[backendFlag + 1]);
if (!connected && !fs.existsSync(path.join(backend, 'launch.json'))) throw new Error('Offline release requires Codex A’s releases/backend/launch.json. Use build:desktop:connected only for an explicitly connected-only build.');
if (!fs.existsSync(path.join(root, 'apps/web/dist/index.html'))) throw new Error('Run build:web first.');
await build({ targets: Platform.WINDOWS.createTarget('dir'), config: {
  electronDist: path.dirname(require('electron')),
  appId: 'team.cashproof.desktop', productName: connected ? 'CashProof Connected' : 'CashProof',
  directories: { app: path.join(root, 'apps/desktop'), output: path.join(root, 'apps/desktop/dist', outputName) },
  files: ['main.cjs', 'security.cjs', '*preload.cjs', 'launcher.*', 'assets/**', 'package.json'],
  extraResources: [
    { from: path.join(root, 'apps/web/dist'), to: 'web', filter: ['index.html', 'mark.svg', 'assets/**', 'fonts/**', 'third-party-notices.txt', 'third-party-inventory.json'] },
    { from: path.join(root, 'packages/contracts/desktop-launch.schema.json'), to: 'contracts/desktop-launch.schema.json' },
    ...(!connected ? [{ from: backend, to: 'backend' }] : []),
  ],
  asar: true, npmRebuild: false,
  afterPack: connected ? undefined : async context => {
    console.log(JSON.stringify(await verifyBackendResources(backend, path.join(context.appOutDir, 'resources/backend'))));
  },
  win: { signAndEditExecutable: false, icon: path.join(root, 'apps/desktop/assets/app.ico'), target: 'dir' },
} });
console.log(connected ? 'Connected-only Windows folder built. No offline inference bundle included.' : 'Offline resources packaged; actual offline inference still requires verification on the qualified GPU host.');
