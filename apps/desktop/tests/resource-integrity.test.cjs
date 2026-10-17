const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const { createHash } = require('node:crypto');

async function fixture(t, name = 'assets/.gitkeep', value = '') {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'cashproof-manifest-'));
  t.after(() => {
    assert.equal(path.dirname(path.resolve(root)), path.resolve(os.tmpdir()));
    assert.ok(path.basename(root).startsWith('cashproof-manifest-'));
    return fs.rm(root, { recursive: true, force: true });
  });
  const source = path.join(root, 'source'), destination = path.join(root, 'packaged');
  await fs.mkdir(source); await fs.mkdir(destination);
  const manifest = JSON.stringify({ files: { [name]: createHash('sha256').update(value).digest('hex') } });
  await fs.writeFile(path.join(source, 'manifest.json'), manifest);
  await fs.writeFile(path.join(destination, 'manifest.json'), manifest);
  const { verifyBackendResources } = await import('../scripts/verify-backend-resources.mjs');
  return { source, destination, verify: () => verifyBackendResources(source, destination) };
}

test('packaged inventory restores a filtered dotfile without changing the manifest', async t => {
  const f = await fixture(t);
  await fs.mkdir(path.join(f.source, 'assets'));
  await fs.writeFile(path.join(f.source, 'assets/.gitkeep'), '');
  const result = await f.verify();
  assert.equal(result.filtered_files_restored, 1);
  assert.equal(result.backend_files_verified, 1);
  assert.equal(await fs.readFile(path.join(f.destination, 'assets/.gitkeep'), 'utf8'), '');
  assert.deepEqual(await fs.readFile(path.join(f.source, 'manifest.json')), await fs.readFile(path.join(f.destination, 'manifest.json')));
});
test('packaged inventory rejects corrupt bytes instead of rewriting trusted hashes', async t => {
  const f = await fixture(t, 'model.bin', 'correct');
  await fs.writeFile(path.join(f.destination, 'model.bin'), 'corrupt');
  await assert.rejects(f.verify(), /checksum mismatch/);
});
test('packaged inventory refuses traversal before writing outside the bundle', async t => {
  for (const name of ['../escape.txt', 'NUL', 'nested/COM1.txt']) {
    const f = await fixture(t, name);
    await assert.rejects(f.verify(), /Unsafe manifest resource path/);
  }
});
test('packaged inventory refuses a symlink into another directory', async t => {
  const f = await fixture(t, 'linked/model.bin', 'correct');
  await fs.mkdir(path.join(f.source, 'real'));
  await fs.symlink(path.join(f.source, 'real'), path.join(f.destination, 'linked'), 'junction');
  await assert.rejects(f.verify(), /symlink/);
});
test('packaged inventory rejects unlisted artifacts instead of silently shipping them', async t => {
  const f = await fixture(t, 'model.bin', 'correct');
  await fs.writeFile(path.join(f.destination, 'model.bin'), 'correct');
  await fs.writeFile(path.join(f.destination, 'unexpected-test-file.txt'), 'synthetic disposable content');
  await assert.rejects(f.verify(), /Unlisted packaged backend file/);
});
