import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';

// Only public installed-package metadata is read. Case data is never inspected.
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const web = path.join(root, 'apps/web');
const seen = new Map();
function visit(name, parent) {
  const require = createRequire(path.join(parent, 'package.json'));
  let directory;
  try { directory = path.dirname(require.resolve(`${name}/package.json`)); }
  catch {
    directory = path.dirname(require.resolve(name));
    while (!fs.existsSync(path.join(directory, 'package.json'))) {
      const next = path.dirname(directory);
      if (next === directory) throw new Error(`Cannot resolve package metadata: ${name}`);
      directory = next;
    }
  }
  const pkg = JSON.parse(fs.readFileSync(path.join(directory, 'package.json'), 'utf8'));
  const key = `${pkg.name}@${pkg.version}`;
  if (seen.has(key)) return;
  const notices = fs.readdirSync(directory).filter(file => /^(licen[cs]e|copying|notice)([.-]|$)/i.test(file) && fs.statSync(path.join(directory, file)).isFile()).sort().map(file => {
    const bytes = fs.readFileSync(path.join(directory, file));
    return { file, sha256: createHash('sha256').update(bytes).digest('hex'), text: bytes.toString('utf8') };
  });
  if (!notices.length) throw new Error(`License text missing for shipped dependency ${key}`);
  seen.set(key, { name: pkg.name, version: pkg.version, license: pkg.license, notices });
  for (const dependency of Object.keys(pkg.dependencies ?? {}).sort()) visit(dependency, directory);
}
const pkg = JSON.parse(fs.readFileSync(path.join(web, 'package.json'), 'utf8'));
for (const name of Object.keys(pkg.dependencies).sort()) visit(name, web);
const packages = [...seen.values()].sort((a, b) => a.name.localeCompare(b.name));
const font = fs.readFileSync(path.join(web, 'public/fonts/OFL.txt'));
const inventory = { scope: 'web runtime dependencies and bundled font; build tools excluded', packages, font: { name: 'Open Sans', license: 'OFL-1.1', sha256: createHash('sha256').update(font).digest('hex'), text: font.toString('utf8') } };
const text = ['CashProof third-party notices', inventory.scope, 'These notices do not certify redistribution compliance of the backend or native desktop components.', ...packages.flatMap(item => [`\n${item.name} ${item.version} (${item.license})`, ...item.notices.map(notice => `${notice.file}\nSHA-256 ${notice.sha256}\n${notice.text}`)]), '\nOpen Sans (OFL-1.1)', inventory.font.text].join('\n\n');
fs.mkdirSync(path.join(web, 'src/generated'), { recursive: true });
fs.writeFileSync(path.join(web, 'src/generated/third-party-notices.txt'), text);
fs.writeFileSync(path.join(web, 'public/third-party-notices.txt'), text);
fs.writeFileSync(path.join(web, 'public/third-party-inventory.json'), JSON.stringify(inventory, null, 2) + '\n');
console.log(`Recorded ${packages.length} installed runtime packages and Open Sans; no private inputs.`);
