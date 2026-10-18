import { expect, test } from 'vitest';
const luminance = (hex: string) => {
  const [r,g,b] = hex.match(/../g)!.map(v => parseInt(v,16)/255).map(v => v <= .04045 ? v/12.92 : ((v+.055)/1.055)**2.4);
  return .2126*r + .7152*g + .0722*b;
};
for (const [foreground,background] of [['ffffff','a31551'],['ffffff','871044'],['6c6c6c','ffffff'],['a31551','f9edf2'],['19735b','edf8f2'],['875700','fff7e6'],['b4233d','fff0f2']]) {
  test(`small text contrast ${foreground}/${background} >= 4.5`, () => {
    const a = luminance(foreground), b = luminance(background);
    expect((Math.max(a,b)+.05)/(Math.min(a,b)+.05)).toBeGreaterThanOrEqual(4.5);
  });
}
