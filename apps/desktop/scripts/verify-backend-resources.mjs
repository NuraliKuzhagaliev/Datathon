import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';

const sha256 = async file => {
  const hash = createHash('sha256');
  for await (const block of fs.createReadStream(file)) hash.update(block);
  return hash.digest('hex');
};

async function checkedPath(root, name, makeParents = false) {
  const parts = name.split('/');
  if (parts.some(part => !part || part === '.' || part === '..' || /[\\:\0]/.test(part) || /[. ]$/.test(part))) throw new Error('Unsafe manifest resource path');
  let current = root;
  for (const [index, part] of parts.entries()) {
    current = path.join(current, part);
    let stat;
    try { stat = await fs.promises.lstat(current); }
    catch (error) {
      if (error.code !== 'ENOENT') throw error;
      if (makeParents && index < parts.length - 1) {
        await fs.promises.mkdir(current);
        stat = await fs.promises.lstat(current);
      }
    }
    if (stat?.isSymbolicLink()) throw new Error('Manifest resource must not traverse a symlink');
    if (index < parts.length - 1 && stat && !stat.isDirectory()) throw new Error('Invalid resource parent');
  }
  return current;
}

export async function verifyBackendResources(source, destination) {
  const original = await fs.promises.realpath(source);
  const packaged = await fs.promises.realpath(destination);
  const bytes = await fs.promises.readFile(path.join(original, 'manifest.json'));
  if (!bytes.equals(await fs.promises.readFile(path.join(packaged, 'manifest.json')))) throw new Error('Packaged backend manifest changed');
  const manifest = JSON.parse(bytes);
  if (!manifest.files || Array.isArray(manifest.files) || typeof manifest.files !== 'object') throw new Error('Backend file inventory missing');
  let restored = 0;
  for (const [name, expected] of Object.entries(manifest.files)) {
    if (typeof expected !== 'string' || !/^[a-f0-9]{64}$/.test(expected)) throw new Error('Invalid resource checksum');
    const target = await checkedPath(packaged, name, true);
    try { await fs.promises.access(target); }
    catch (error) {
      if (error.code !== 'ENOENT') throw error;
      // electron-builder excludes some dotfiles. Restore only manifest-listed,
      // hash-checked source bytes; never weaken or rewrite the trusted manifest.
      const input = await checkedPath(original, name);
      if (await sha256(input) !== expected) throw new Error('Original backend resource checksum mismatch');
      await fs.promises.copyFile(input, target, fs.constants.COPYFILE_EXCL);
      restored++;
    }
    if (await sha256(target) !== expected) throw new Error('Packaged backend resource checksum mismatch');
  }
  return { backend_files_verified: Object.keys(manifest.files).length, filtered_files_restored: restored, manifest_sha256: createHash('sha256').update(bytes).digest('hex') };
}
