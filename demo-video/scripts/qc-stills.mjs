#!/usr/bin/env node
/**
 * QC rig: bundle once, render a still at every requested frame.
 *
 * Rendering stills through the CLI re-bundles each time; for a 13-scene
 * review pass that is minutes of pure waste. This keeps one bundle and
 * drives the renderer directly.
 *
 *   node scripts/qc-stills.mjs [compositionId] [frame,frame,...]
 */
import { bundle } from '@remotion/bundler';
import { renderStill, selectComposition } from '@remotion/renderer';
import { mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const BROWSER = '/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell';

const compId = process.argv[2] ?? 'HeroLandscape';
const outDir = join(root, 'renders/qc', compId.toLowerCase());
mkdirSync(outDir, { recursive: true });

const serveUrl = await bundle({ entryPoint: join(root, 'src/index.ts'), onProgress: () => {} });
const composition = await selectComposition({ serveUrl, id: compId, inputProps: {}, browserExecutable: BROWSER, chromiumOptions: { gl: 'swangle' }, logLevel: 'error' });
console.log(`${compId}: ${composition.width}x${composition.height} @ ${composition.fps}fps, ${composition.durationInFrames} frames`);

const frames = process.argv[3]
  ? process.argv[3].split(',').map(Number)
  : Array.from({ length: 24 }, (_, i) => Math.round((i * (composition.durationInFrames - 1)) / 23));

for (const frame of frames) {
  const output = join(outDir, `f${String(frame).padStart(5, '0')}.png`);
  await renderStill({
    composition, serveUrl, output, frame, imageFormat: 'png',
    browserExecutable: BROWSER, chromiumOptions: { gl: 'swangle' }, logLevel: 'error',
  });
  process.stdout.write(`.`);
}
console.log(`\n${frames.length} stills -> ${outDir}`);
