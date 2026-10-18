const path = require('node:path');
const fs = require('node:fs');

function serverOrigin(raw) {
  const url = new URL(raw);
  const local = url.hostname === '127.0.0.1' || url.hostname === 'localhost' || url.hostname === '[::1]';
  if ((url.protocol !== 'https:' && !(local && url.protocol === 'http:')) || url.username || url.password || url.pathname !== '/' || url.search || url.hash) throw new Error('Укажите HTTPS-адрес сервера без пути, ключа и параметров. HTTP разрешён только для loopback.');
  return url.origin;
}
function sourceUrl(raw) {
  const url = new URL(raw);
  if (url.protocol !== 'https:' || url.username || url.password || !['adilet.zan.kz','old.adilet.zan.kz','nationalbank.kz','www.nationalbank.kz'].includes(url.hostname)) throw new Error('Разрешены только проверенные официальные источники.');
  return url.href;
}
function insideBundle(root, value) {
  if (!value || path.isAbsolute(value)) throw new Error('Путь runtime должен быть относительным.');
  const absolute = path.resolve(root, value); const relative = path.relative(root, absolute);
  if (relative === '..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) throw new Error('Путь runtime выходит за пределы bundle.');
  const realRoot = fs.realpathSync(root); const realTarget = fs.realpathSync(absolute); const actualRelative = path.relative(realRoot, realTarget);
  if (actualRelative === '..' || actualRelative.startsWith(`..${path.sep}`) || path.isAbsolute(actualRelative)) throw new Error('Ссылка runtime выходит за пределы bundle.');
  return absolute;
}
function backendArguments(prefix, dataDir, frontendDir) {
  return [...prefix, '-m', 'cashproof.bootstrap', '--host', '127.0.0.1', '--port', '0', '--data-dir', dataDir, '--frontend-dir', frontendDir];
}
function checkHealthContract(health) {
  if (health.contract_version && health.contract_version !== '1.0.0') {
    const error = new Error('Несовместимая версия интерфейса сервиса анализа.');
    error.code = 'CONTRACT_MISMATCH';
    throw error;
  }
}
module.exports = { serverOrigin, sourceUrl, insideBundle, backendArguments, checkHealthContract };
