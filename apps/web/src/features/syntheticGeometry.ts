export type Side = 'left' | 'on' | 'right';
export type SourceFrame = { frame_id: string; timestamp_sec: number };
export type Crossing = { time_sec: number; direction: 'left_to_right' | 'right_to_left'; frame_id: string };

// Explicit blue-object/red-line synthetic geometry. No reference labels or times.
export function measureSide(data: Uint8ClampedArray, width: number, height: number): Side {
  if (data.length !== width * height * 4) throw new Error('Invalid pixels');
  let minX = width, maxX = -1, minY = height, maxY = -1, blueCount = 0;
  const columns = new Uint32Array(width);
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    const i = (y * width + x) * 4, r = data[i], g = data[i + 1], b = data[i + 2];
    if (b > 150 && r < 90 && g < 90) { minX = Math.min(minX, x); maxX = Math.max(maxX, x); minY = Math.min(minY, y); maxY = Math.max(maxY, y); blueCount++; }
    if (r > 150 && g < 90 && b < 90) columns[x]++;
  }
  if (blueCount < 40 || blueCount / ((maxX - minX + 1) * (maxY - minY + 1)) < 0.9) throw new Error('Object not visible or ambiguous');
  const support: number[] = [];
  for (let x = 0; x < width; x++) if (columns[x] >= Math.max(12, height * 0.2)) support.push(x);
  if (!support.length || support.at(-1)! - support[0] > 10) throw new Error('Line not visible or ambiguous');
  const offset = (minX + maxX) / 2 - support.reduce((a, b) => a + b, 0) / support.length;
  return Math.abs(offset) <= 2 ? 'on' : offset < 0 ? 'left' : 'right';
}

export function crossingsFromSides(sides: Side[], frames: SourceFrame[]): Crossing[] {
  if (sides.length !== frames.length) throw new Error('Missing frame observations');
  let previous: number | null = null, contact: number | null = null;
  const result: Crossing[] = [];
  sides.forEach((side, i) => {
    if (side === 'on') { if (previous !== null && contact === null) contact = i; return; }
    if (previous !== null && sides[previous] !== side) {
      const frame = frames[contact ?? i];
      result.push({ time_sec: frame.timestamp_sec, direction: side === 'right' ? 'left_to_right' : 'right_to_left', frame_id: frame.frame_id });
    }
    previous = i; contact = null;
  });
  return result;
}

export function ambiguousIndices(sides: Side[]): number[] {
  const selected = new Set<number>();
  sides.forEach((side, i) => { if (side === 'on') for (const n of [i - 1, i, i + 1]) if (n >= 0 && n < sides.length) selected.add(n); });
  return [...selected].sort((a, b) => a - b);
}

function seek(video: HTMLVideoElement, seconds: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const cleanup = () => { clearTimeout(timer); video.removeEventListener('seeked', done); video.removeEventListener('error', failed); signal.removeEventListener('abort', failed); };
    const done = () => { cleanup(); resolve(); };
    const failed = () => { cleanup(); reject(new Error(signal.aborted ? 'Cancelled' : 'Video unavailable')); };
    const timer = setTimeout(failed, 8000);
    if (signal.aborted || video.error) { failed(); return; }
    video.addEventListener('seeked', done, { once: true }); video.addEventListener('error', failed, { once: true }); signal.addEventListener('abort', failed, { once: true });
    // Place the seek just inside this source frame, avoiding a float boundary.
    const target = Math.min(seconds + 0.001, video.duration - 0.001);
    if (Math.abs(video.currentTime - target) < 0.00001 && video.readyState >= 2) done(); else video.currentTime = target;
  });
}

export async function refineInBrowser(video: HTMLVideoElement, frames: SourceFrame[], observations: Side[], signal: AbortSignal, progress: (done: number, total: number) => void): Promise<Side[]> {
  const indices = ambiguousIndices(observations), result = [...observations];
  const canvas = document.createElement('canvas'); canvas.width = video.videoWidth; canvas.height = video.videoHeight;
  const context = canvas.getContext('2d', { willReadFrequently: true });
  if (!context || !canvas.width || !canvas.height) throw new Error('Video is not ready');
  video.pause(); progress(0, indices.length);
  for (let i = 0; i < indices.length; i++) {
    const index = indices[i]; await seek(video, frames[index].timestamp_sec, signal);
    if (signal.aborted) throw new Error('Cancelled');
    context.drawImage(video, 0, 0);
    result[index] = measureSide(context.getImageData(0, 0, canvas.width, canvas.height).data, canvas.width, canvas.height);
    progress(i + 1, indices.length);
  }
  return result;
}
