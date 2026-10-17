const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { serverOrigin, sourceUrl, insideBundle, backendArguments, checkHealthContract } = require('../security.cjs');

test('connected mode accepts only HTTPS or loopback HTTP origins', () => {
  assert.equal(serverOrigin('https://cashproof.example/'), 'https://cashproof.example');
  assert.equal(serverOrigin('http://127.0.0.1:8000'), 'http://127.0.0.1:8000');
  for (const value of ['file:///C:/Windows','javascript:alert(1)','http://192.168.1.5:8000','https://user:key@example.com','https://example.com/?key=secret','https://example.com/path']) assert.throws(() => serverOrigin(value));
});
test('external source policy rejects unexpected schemes and lookalike domains', () => {
  assert.ok(sourceUrl('https://nationalbank.kz/ru/news'));
  for (const value of ['https://adilet.zan.kz.example.com','https://example.com','file:///tmp/file','javascript:alert(1)']) assert.throws(() => sourceUrl(value));
});
test('bundle paths retain spaces and Cyrillic and cannot escape', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cashproof-'));
  try {
    const dir = path.join(root, 'Моя папка'); fs.mkdirSync(dir); fs.writeFileSync(path.join(dir, 'runtime.exe'), 'synthetic fixture');
    assert.equal(insideBundle(root, 'Моя папка/runtime.exe'), path.join(dir, 'runtime.exe'));
    assert.throws(() => insideBundle(root, '../outside.exe'));
    assert.throws(() => insideBundle(root, path.resolve(root, 'absolute.exe')));
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});

test('A manifest prefix is followed by the Python module before runtime arguments', () => {
  const prefix = ['-s'];
  assert.deepEqual(backendArguments(prefix, 'C:\\Мои дела', 'C:\\Shared web'), ['-s', '-m', 'cashproof.bootstrap', '--host', '127.0.0.1', '--port', '0', '--data-dir', 'C:\\Мои дела', '--frontend-dir', 'C:\\Shared web']);
  assert.deepEqual(prefix, ['-s']);
});

test('contract mismatch is identifiable independently of translated message text', () => {
  assert.doesNotThrow(() => checkHealthContract({ready:false,contract_version:'1.0.0'}));
  assert.throws(() => checkHealthContract({ready:true,contract_version:'2.0.0'}), {code:'CONTRACT_MISMATCH'});
});
