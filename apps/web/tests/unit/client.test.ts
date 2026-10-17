import { afterEach, expect, test, vi } from 'vitest';
import { HttpApi, errorText } from '../../src/api/client';

afterEach(() => vi.unstubAllGlobals());
for (const [status, expected] of [[401,'Ключ доступа'],[404,'не найден сервис анализа'],[413,'размер'],[415,'формат'],[422,'отклонил'],[429,'Очередь'],[503,'не готовы']] as const) {
  test(`HTTP ${status} gives a safe recovery message`, async () => {
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({error:{code:'TEST',message:'Untrusted server detail must not be exposed'}}),{status,headers:{'Retry-After':'15'}})));
    const api = new HttpApi('synthetic-test-key');
    try { await api.list(); throw new Error('Expected rejection'); } catch(error) { expect(errorText(error)).toContain(expected); expect(errorText(error)).not.toContain('Untrusted'); if(status===429)expect(errorText(error)).toContain('15 сек.'); }
  });
}
test('API request attaches key, refuses redirects and avoids persistent cache', async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response('{"items":[]}',{status:200})); vi.stubGlobal('fetch',fetchMock);
  await new HttpApi('synthetic-test-key').list();
  expect(fetchMock.mock.calls[0][1]).toMatchObject({headers:{'X-API-Key':'synthetic-test-key'},redirect:'error',cache:'no-store',credentials:'omit'});
});
test('health preserves 503 not-ready and rejects incompatible contract', async () => {
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response('{"ready":false,"mode":"offline","contract_version":"1.0.0"}',{status:503})));
  expect((await new HttpApi('synthetic-test-key').health()).ready).toBe(false);
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response('{"ready":true,"mode":"offline","contract_version":"2.0.0"}',{status:200})));
  await expect(new HttpApi('synthetic-test-key').health()).rejects.toThrow('несовместима');
});
test('download does not accept an HTML error as a ZIP', async () => {
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response('<html>Error</html>',{status:200,headers:{'Content-Type':'text/html'}})));
  await expect(new HttpApi('synthetic-test-key').blob('synthetic','bundle')).rejects.toThrow('формате');
});
