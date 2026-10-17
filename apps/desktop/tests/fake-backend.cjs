// Synthetic desktop lifecycle fixture only. No video processing or inference.
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const argument = name => process.argv[process.argv.indexOf(name) + 1];
// This Node shim must receive the same fixed module arguments as Python.
// It is only a lifecycle fixture; it never claims to execute Python or inference.
if (process.argv[2] !== '-m' || process.argv[3] !== 'cashproof.bootstrap' || process.argv[4] !== '--host') process.exit(3);
const frontend = path.resolve(argument('--frontend-dir'));
const dataDir = argument('--data-dir');
if (argument('--host') !== '127.0.0.1' || argument('--port') !== '0' || process.env.CASHPROOF_API_KEY?.length !== 64 || process.env.CASHPROOF_MODE !== 'offline') process.exit(2);
fs.mkdirSync(dataDir, { recursive: true });
const server = http.createServer((request, response) => {
  if (request.url === '/health/ready') { response.writeHead(200, {'Content-Type':'application/json'}); response.end(JSON.stringify({ready:true,mode:'offline',contract_version:process.env.CASHPROOF_TEST_HEALTH_VERSION || '1.0.0'})); return; }
  if (request.url === '/api/ui/cases') {
    const accepted = request.headers['x-api-key'] === process.env.CASHPROOF_API_KEY;
    response.writeHead(accepted ? 200 : 401, {'Content-Type':'application/json'}); response.end(JSON.stringify(accepted ? {items:[]} : {error:{code:'UNAUTHORIZED',message:'Synthetic fixture'}})); return;
  }
  const pathname = new URL(request.url, 'http://127.0.0.1').pathname;
  const file = path.resolve(frontend, '.' + (pathname === '/' ? '/index.html' : pathname));
  if (!file.startsWith(frontend + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) { response.writeHead(404); response.end(); return; }
  response.writeHead(200, {'Content-Type':{'.html':'text/html','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml'}[path.extname(file)] || 'application/octet-stream'});
  fs.createReadStream(file).pipe(response);
});
server.listen(0, '127.0.0.1', () => process.stdout.write(JSON.stringify({event:'http_ready',port:server.address().port}) + '\n'));
