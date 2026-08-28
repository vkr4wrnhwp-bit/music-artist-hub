/**
 * AUDIO BED — synthesized here, so it is unambiguously licence-free.
 *
 * A restrained electronic bed: a low drone that breathes, a quiet pulse to
 * carry momentum, and a soft mark at each scene boundary. Deliberately not
 * trailer music — it must never compete with reading the interface.
 *
 *   npx tsx scripts/make-audio.ts [seconds]
 *
 * Length and scene boundaries are read from the scene script, so the bed
 * cannot drift out of step with the film when a scene's duration changes.
 */
import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { scenes } from '../src/script';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const RATE = 48000;

/** cumulative scene starts — the bed lifts where the film cuts */
const BOUNDARIES: number[] = [];
const filmSeconds = scenes.reduce((t, s) => {
  BOUNDARIES.push(t);
  return t + s.seconds;
}, 0);

// a little tail past the last frame so the fade-out is never clipped
const SECONDS = Number(process.argv[2] ?? Math.ceil(filmSeconds + 4));
const N = RATE * SECONDS;

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

const left = new Float64Array(N);
const right = new Float64Array(N);

for (let i = 0; i < N; i++) {
  const t = i / RATE;

  // --- drone: A1 with a detuned partner and a fifth, breathing slowly
  const breathe = 0.5 + 0.5 * Math.sin((2 * Math.PI * t) / 17);
  let s = 0;
  s += 0.19 * Math.sin(2 * Math.PI * 55 * t);
  s += 0.13 * Math.sin(2 * Math.PI * 55.31 * t);
  s += 0.085 * Math.sin(2 * Math.PI * 110 * t) * (0.6 + 0.4 * breathe);
  s += 0.05 * Math.sin(2 * Math.PI * 164.81 * t) * breathe;

  // --- pad: a distant fifth that swells across the film
  const swell = 0.5 + 0.5 * Math.sin((2 * Math.PI * t) / 29 - 1.2);
  s += 0.035 * Math.sin(2 * Math.PI * 220 * t) * swell;
  s += 0.022 * Math.sin(2 * Math.PI * 329.63 * t) * swell * 0.7;

  // --- pulse: a quiet heartbeat, 40 per minute, soft attack
  const period = 1.5;
  const ph = t % period;
  const env = Math.exp(-ph * 7) * (1 - Math.exp(-ph * 120));
  s += 0.055 * env * Math.sin(2 * Math.PI * 116 * t);
  s += 0.016 * env * Math.sin(2 * Math.PI * 464 * t);

  // --- scene marks: a soft, short lift just after each cut
  for (const b of BOUNDARIES) {
    const d = t - b;
    if (d >= 0 && d < 1.1) {
      const e = Math.exp(-d * 4.2) * (1 - Math.exp(-d * 60));
      s += 0.03 * e * Math.sin(2 * Math.PI * 587.33 * t);
      s += 0.018 * e * Math.sin(2 * Math.PI * 880 * t);
    }
  }

  // gentle stereo width from a slow phase offset, never phasey
  const wob = 0.0009 * Math.sin((2 * Math.PI * t) / 11);
  left[i] = s * (1 + wob);
  right[i] = s * (1 - wob);
}

// program fades
const fadeIn = RATE * 1.2, fadeOut = RATE * 2.4;
for (let i = 0; i < N; i++) {
  let g = 1;
  if (i < fadeIn) g *= i / fadeIn;
  if (i > N - fadeOut) g *= (N - i) / fadeOut;
  left[i] *= g; right[i] *= g;
}

// normalize with headroom so nothing clips and the bed sits under speech
let peak = 0;
for (let i = 0; i < N; i++) peak = Math.max(peak, Math.abs(left[i]), Math.abs(right[i]));
const target = 0.32;                       // ~ -10 dBFS peak: a bed, not a feature
const gain = peak > 0 ? target / peak : 1;

const bytes = Buffer.alloc(44 + N * 4);
bytes.write('RIFF', 0); bytes.writeUInt32LE(36 + N * 4, 4); bytes.write('WAVE', 8);
bytes.write('fmt ', 12); bytes.writeUInt32LE(16, 16); bytes.writeUInt16LE(1, 20);
bytes.writeUInt16LE(2, 22); bytes.writeUInt32LE(RATE, 24);
bytes.writeUInt32LE(RATE * 4, 28); bytes.writeUInt16LE(4, 32); bytes.writeUInt16LE(16, 34);
bytes.write('data', 36); bytes.writeUInt32LE(N * 4, 40);
for (let i = 0; i < N; i++) {
  bytes.writeInt16LE(clamp(Math.round(left[i] * gain * 32767), -32768, 32767), 44 + i * 4);
  bytes.writeInt16LE(clamp(Math.round(right[i] * gain * 32767), -32768, 32767), 46 + i * 4);
}
mkdirSync(join(ROOT, 'public', 'audio'), { recursive: true });
const out = join(ROOT, 'public', 'audio', 'bed.wav');
writeFileSync(out, bytes);
console.log(`audio bed: ${SECONDS}s, 48kHz stereo, peak ${(20 * Math.log10(target)).toFixed(1)} dBFS -> ${out}`);
