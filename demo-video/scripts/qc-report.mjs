#!/usr/bin/env node
/**
 * FRAME QC — renders a dense series of stills and reports, per frame, the
 * mean luminance and its spread.
 *
 *   node scripts/qc-report.mjs [compositionId] [sampleCount]
 *
 * A frame that is blank, or that failed to load its capture, has almost no
 * spread; a frame that is entirely ground colour has almost no luminance.
 * Eyeballing two dozen stills catches composition problems but not a single
 * dropped frame in the middle of a 2880-frame film, so this checks every
 * sample numerically and exits non-zero if any looks empty.
 */
import { bundle } from '@remotion/bundler';
import { renderStill, selectComposition } from '@remotion/renderer';
import { PNG } from 'pngjs';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const BROWSER = '/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell';
const compId = process.argv[2] ?? 'HeroLandscape';
const samples = Number(process.argv[3] ?? 48);

// A frame darker than this with essentially no variation is either blank or a
// failed image load. Title and end cards are legitimately dark but always
// carry type, which shows up as spread.
const MIN_SPREAD = 3.0;

const stats = (file) => {
  const png = PNG.sync.read(readFileSync(file));
  const { data, width, height } = png;
  let sum = 0, sumSq = 0, n = 0;
  // sample a grid rather than every pixel: enough for a distribution, fast
  for (let y = 0; y < height; y += 4) {
    for (let x = 0; x < width; x += 4) {
      const i = (y * width + x) * 4;
      const l = 0.2126 * data[i] + 0.7152 * data[i + 1] + 0.0722 * data[i + 2];
      sum += l; sumSq += l * l; n++;
    }
  }
  const mean = sum / n;
  return { mean, spread: Math.sqrt(Math.max(0, sumSq / n - mean * mean)) };
};

const serveUrl = await bundle({ entryPoint: join(root, 'src/index.ts'), onProgress: () => {} });
const composition = await selectComposition({
  serveUrl, id: compId, inputProps: {},
  browserExecutable: BROWSER, chromiumOptions: { gl: 'swangle' }, logLevel: 'error',
});
const total = composition.durationInFrames;
const dir = mkdtempSync(join(tmpdir(), 'qc-'));
const suspect = [];

console.log(`${compId}: ${composition.width}x${composition.height}, ${total} frames, sampling ${samples}`);
for (let i = 0; i < samples; i++) {
  const frame = Math.min(total - 1, Math.round((i * (total - 1)) / (samples - 1)));
  const output = join(dir, `f${frame}.png`);
  await renderStill({
    composition, serveUrl, output, frame, imageFormat: 'png',
    browserExecutable: BROWSER, chromiumOptions: { gl: 'swangle' }, logLevel: 'error',
  });
  const { mean, spread } = stats(output);
  const bad = spread < MIN_SPREAD;
  if (bad) suspect.push({ frame, mean: mean.toFixed(2), spread: spread.toFixed(2) });
  process.stdout.write(bad ? 'X' : '.');
}
rmSync(dir, { recursive: true, force: true });

console.log();
if (suspect.length) {
  console.log(`SUSPECT FRAMES (spread < ${MIN_SPREAD}):`);
  console.table(suspect);
  process.exit(1);
}
console.log(`ok — all ${samples} sampled frames carry content`);
