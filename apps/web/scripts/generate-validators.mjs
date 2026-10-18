import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import standalone from 'ajv/dist/standalone/index.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const contract = JSON.parse(fs.readFileSync(path.join(root, 'packages/contracts/openapi.json'), 'utf8'));
const ajv = new Ajv2020({ strict: false, allErrors: true, code: { source: true, esm: true } });
addFormats(ajv);
ajv.addSchema({ $id: 'cashproof', components: contract.components });
const names = Object.keys(contract.components.schemas);
for (const name of names) ajv.addSchema({ $id: name, $ref: `cashproof#/components/schemas/${name}` });
let code = standalone(ajv, Object.fromEntries(names.map(name => [name, name])));
// AJV emits CJS runtime helper references even in ESM mode. Turn them into static
// imports during code generation so CSP never needs eval or dynamic code creation.
const imports = new Map();
code = code.replace(/require\("([^"]+)"\)(\.default)?/g, (_all, module, defaultAccess) => {
  if (!imports.has(module)) imports.set(module, `runtime${imports.size}`);
  const name = imports.get(module);
  return defaultAccess ? `(${name}.default ?? ${name})` : name;
});
const header = '// Generated from packages/contracts/openapi.json. Do not edit.\n' + [...imports].map(([module, name]) => `import ${name} from '${module}';`).join('\n') + '\n';
const out = path.join(root, 'apps/web/src/api/generated');
fs.mkdirSync(out, { recursive: true });
fs.writeFileSync(path.join(out, 'validators.js'), header + code);
fs.writeFileSync(path.join(out, 'validators.d.ts'), '// Generated. Do not edit.\n' + names.map(name => `export declare const ${name}: (value: unknown) => boolean;`).join('\n') + '\n');
console.log(`Generated ${names.length} CSP-safe validators from contract ${contract.info.version}.`);
