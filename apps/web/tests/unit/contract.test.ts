import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { validate, validateCase } from '../../src/api/validation';
import { mapTime, mappedInterval, legalUrl, time } from '../../src/lib/time';

const fixture = (name: string) => JSON.parse(readFileSync(`packages/contracts/fixtures/${name}.json`, 'utf8'));
describe('frozen contract 1.0.0', () => {
  for (const name of ['positive', 'negative', 'processing', 'failed']) it(`accepts synthetic ${name} only in allowed mode`, () => { expect(validateCase(fixture(`ui-${name}`), true)).toBeTruthy(); expect(() => validateCase(fixture(`ui-${name}`))).toThrow(/синтетический/); });
  it('rejects malformed and third-verdict responses', () => { const data = fixture('ui-positive'); data.model_result.verdict = 'unknown'; expect(() => validateCase(data, true)).toThrow(); });
  it('rejects completed without a result', () => { const data = fixture('ui-negative'); data.model_result = null; expect(() => validateCase(data, true)).toThrow(); });
  it('rejects duplicate stable event IDs', () => { const data = fixture('ui-positive'); data.events[1].event_id = data.events[0].event_id; expect(() => validateCase(data, true)).toThrow(); });
  it('rejects mismatched jury indices', () => { const data = fixture('ui-positive'); data.events[1].jury_violation_index = 0; expect(() => validateCase(data, true)).toThrow(); });
  it('rejects inactive source in real responses', () => { const data = fixture('ui-positive'); data.is_synthetic = false; expect(() => validateCase(data)).toThrow(/норма/); });
  it('requires API readiness shape', () => { expect(validate('HealthReady', { ready: false, mode: 'offline', contract_version: '1.0.0' })).toBeTruthy(); expect(() => validate('HealthReady', {})).toThrow(); });
});
describe('time mapping and URLs', () => {
  const segments = [{ source_start_sec: 5, source_end_sec: 15, preview_start_sec: 0, preview_end_sec: 20 }];
  it('maps both directions without assuming frame rate', () => { expect(mapTime(10, segments)).toBe(10); expect(mapTime(4, segments, true)).toBe(7); });
  it('refuses missing map, gaps and zero-length segments', () => { expect(mapTime(0, segments)).toBeNull(); expect(mapTime(10, [])).toBeNull(); expect(mapTime(5, [{...segments[0], source_end_sec: 5}])).toBeNull(); expect(mapTime(NaN, segments)).toBeNull(); });
  it('requires full context coverage, not only valid endpoints', () => { expect(mappedInterval(6,14,segments)).toBeTruthy(); expect(mappedInterval(0,14,segments)).toBeFalsy(); expect(mappedInterval(5,20,[...segments,{source_start_sec:16,source_end_sec:20,preview_start_sec:21,preview_end_sec:25}])).toBeFalsy(); });
  it('formats original time to tenths', () => { expect(time(12.49)).toBe('00:12.4'); expect(time(61.2)).toBe('01:01.2'); });
  it('only allows official HTTPS sources', () => { expect(legalUrl('https://adilet.zan.kz/rus/docs/1')).toBeTruthy(); for (const url of ['javascript:alert(1)','https://adilet.zan.kz.evil.com/','http://adilet.zan.kz/','https://name:password@adilet.zan.kz/','https://example.invalid/']) expect(legalUrl(url)).toBeNull(); });
});
