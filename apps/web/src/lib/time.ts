import type { TimeMapSegment } from '../api/types';
export function time(seconds: number) {
  const safe = Math.max(0, seconds);
  return `${Math.floor(safe / 60).toString().padStart(2, '0')}:${(Math.floor(safe * 10) / 10 % 60).toFixed(1).padStart(4, '0')}`;
}
export function mapTime(value: number, segments: TimeMapSegment[], reverse = false): number | null {
  if (!Number.isFinite(value) || value < 0) return null;
  for (const s of segments) {
    const a = reverse ? s.preview_start_sec : s.source_start_sec;
    const b = reverse ? s.preview_end_sec : s.source_end_sec;
    const c = reverse ? s.source_start_sec : s.preview_start_sec;
    const d = reverse ? s.source_end_sec : s.preview_end_sec;
    if (b <= a || d <= c) continue;
    if (value >= a && value <= b) return c + (value - a) / (b - a) * (d - c);
  }
  return null;
}
export function mappedInterval(start: number, end: number, segments: TimeMapSegment[]): boolean {
  if (end <= start) return false;
  let covered = start;
  for (const segment of [...segments].sort((a, b) => a.source_start_sec - b.source_start_sec)) {
    if (segment.source_end_sec <= covered) continue;
    if (segment.source_start_sec > covered || segment.preview_end_sec <= segment.preview_start_sec) return false;
    covered = segment.source_end_sec;
    if (covered >= end) return true;
  }
  return false;
}
export function legalUrl(raw: string): string | null {
  try { const url = new URL(raw); return url.protocol === 'https:' && !url.username && !url.password && ['adilet.zan.kz', 'old.adilet.zan.kz', 'nationalbank.kz', 'www.nationalbank.kz'].includes(url.hostname) ? url.href : null; } catch { return null; }
}
