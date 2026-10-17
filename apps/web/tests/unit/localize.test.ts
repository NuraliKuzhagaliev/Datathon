import { expect, test } from 'vitest';
import { readFileSync } from 'node:fs';
import { localizeDemo } from '../../src/mocks/localize';
import { validateCase } from '../../src/api/validation';

test('demo translation retains case identity, timestamps, images and event/result agreement', () => {
  const original = JSON.parse(readFileSync('packages/contracts/fixtures/ui-positive.json', 'utf8'));
  const before = JSON.stringify(original);
  const translated = validateCase(localizeDemo(original), true);
  expect(JSON.stringify(original)).toBe(before);
  expect(translated.job_id).toBe(original.job_id);
  expect(translated.is_synthetic).toBe(true);
  expect(translated.events[0].type).toBe('Учебное событие 1');
  expect(translated.events[0].timecode_sec).toBe(original.events[0].timecode_sec);
  expect(translated.events[0].evidence_frames).toEqual(original.events[0].evidence_frames);
  expect(translated.rules[0].enabled).toBe(false);
});

test('translation maps only known demo labels and preserves unknown text and keys', () => {
  const translated = localizeDemo({ job_id: 'synthetic-positive', filename: 'Пользовательский файл.mov', note: 'Free text', rule: 'Synthetic fixture rule' });
  expect(translated).toEqual({job_id:'synthetic-positive',filename:'Пользовательский файл.mov',note:'Free text',rule:'Учебное основание'});
});
