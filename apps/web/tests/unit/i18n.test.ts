import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
import english from '../../src/i18n/en.json';
import { translate } from '../../src/i18n';
import { demoText } from '../../src/mocks/localize';

describe('English localization', () => {
  it('translates literal and interpolated UI messages without altering values', () => {
    expect(translate('Новый анализ', 'en')).toBe('New analysis');
    expect(translate('Новый анализ', 'ru')).toBe('Новый анализ');
    expect(translate('Удалить дело {0}', 'en', ['$&.mov'])).toBe('Delete case $&.mov');
    expect(translate('original server text', 'en')).toBe('original server text');
  });
  it('translates dynamic errors and retry-after messages at render time', () => {
    expect(translate('Ошибка сервера (500).', 'en')).toBe('Server error (500).');
    expect(translate('Загрузка не принята (502).', 'en')).toBe('Upload rejected (502).');
    expect(translate('Ответ сервера не соответствует контракту 1.0.0 (CaseDetail).', 'en')).toContain('(CaseDetail)');
    expect(translate('Очередь заполнена. Повторите загрузку позже. Сервер рекомендует подождать 12 сек.', 'en')).toBe('The queue is full. Try uploading again later. The server recommends waiting 12 seconds.');
  });
  it('has translations for every explicit UI translation call and matches placeholders', () => {
    const files = ['App.tsx','components/ui.tsx','features/QuickStart.tsx','features/Cases.tsx','features/ReviewDrafts.tsx','features/Upload.tsx','features/Rules.tsx','features/Evidence.tsx'];
    const missing: string[] = [];
    for (const file of files) {
      const tree = ts.createSourceFile(file, readFileSync(`apps/web/src/${file}`,'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
      function visit(n: ts.Node) {
        if (ts.isCallExpression(n) && ts.isIdentifier(n.expression) && n.expression.text === 't' && n.arguments[0] && ts.isStringLiteral(n.arguments[0])) {
          const key = n.arguments[0].text;
          if (!(key in english) && !['О','Л','А'].includes(key)) missing.push(`${file}: ${key}`);
        }
        ts.forEachChild(n, visit);
      }
      visit(tree);
    }
    expect(missing).toEqual([]);
    for (const [ru, en] of Object.entries(english)) expect(en.match(/\{\d+\}/g) ?? []).toEqual(ru.match(/\{\d+\}/g) ?? []);
  });
  it('translates demo presentation without altering unknown source text or input strings', () => {
    expect(demoText('Учебное событие 1', 'en')).toBe('Demo event 1');
    expect(demoText('Учебное событие 1', 'ru')).toBe('Учебное событие 1');
    expect(demoText('My original note', 'en')).toBe('My original note');
  });
});
