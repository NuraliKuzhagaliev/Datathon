import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { ambiguousIndices, crossingsFromSides, measureSide } from '../../src/features/syntheticGeometry';

describe('synthetic pixel verification', () => {
  function pixels(line: number, center: number) {
    const data = new Uint8ClampedArray(200 * 120 * 4).fill(255);
    const paint = (x: number, y: number, rgb: number[]) => { const i = (y * 200 + x) * 4; data.set([...rgb, 255], i); };
    for (let y = 0; y < 120; y++) for (let x = line - 1; x <= line + 1; x++) paint(x, y, [255, 0, 0]);
    for (let y = 40; y <= 80; y++) for (let x = center - 20; x <= center + 20; x++) paint(x, y, [0, 0, 255]);
    return data;
  }
  it('measures the center separately from an overlapping edge, with a movable line', () => {
    expect(measureSide(pixels(140, 130), 200, 120)).toBe('left');
    expect(measureSide(pixels(60, 70), 200, 120)).toBe('right');
    expect(measureSide(pixels(100, 100), 200, 120)).toBe('on');
  });
  it('rejects missing geometry instead of guessing', () => {
    expect(() => measureSide(new Uint8ClampedArray(200 * 120 * 4).fill(255), 200, 120)).toThrow();
  });
  it('never assumes initial contact was a previous left state', () => {
    const frames = [0, 0.3, 0.5].map((timestamp_sec, i) => ({ frame_id: `f${i}`, timestamp_sec }));
    expect(crossingsFromSides(['on', 'on', 'right'], frames)).toEqual([]);
    expect(crossingsFromSides(['left', 'on', 'right'], frames)[0].time_sec).toBe(0.3);
    expect(crossingsFromSides(['left', 'on', 'left'], frames)).toEqual([]);
    expect(crossingsFromSides(['right', 'on', 'left'], frames)[0].direction).toBe('right_to_left');
    expect(ambiguousIndices(['left', 'on', 'right'])).toEqual([0, 1, 2]);
  });
});

describe('published synthetic recordings', () => {
  const data = JSON.parse(readFileSync('apps/web/public/synthetic-demo/recordings.json', 'utf8'));
  it('contains eight explicitly synthetic recorded cases, not a claimed fresh eight-case API pass', () => {
    expect(data.synthetic_only).toBe(true); expect(data.cases).toHaveLength(8);
    expect(data.fresh_api_completed).toBe(3); expect(data.fresh_api_planned).toBe(8);
    expect(data.mode).toBe('recorded_gemini_and_live_browser_geometry');
    for (const c of data.cases) {
      const bytes = readFileSync(`apps/web/public${c.video_url}`);
      expect(createHash('sha256').update(bytes).digest('hex')).toBe(c.video_sha256);
      expect(c.gemini_sides.length).toBe(c.frames.length);
      expect(c.frames.some((f: object) => 'synthetic_expected_side' in f)).toBe(false);
      expect(c.recorded_hybrid_event_times_sec).toEqual(c.reference_event_times_sec);
    }
  });
});
