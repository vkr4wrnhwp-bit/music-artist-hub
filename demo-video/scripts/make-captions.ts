/**
 * CAPTIONS — generated from the same scene script the film renders from, so
 * they can never drift out of sync with what is on screen.
 *
 *   npx tsx scripts/make-captions.ts
 *
 * The films carry no dialogue, so these are subtitles of the on-screen
 * explanation layer plus a description of each silent title card. That is what
 * a viewer with sound off — or with a screen reader on the player — needs.
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { brand } from '../src/brand.config';
import { pickScenes } from '../src/compositions/Film';
import { salesSceneIds, socialSceneIds, type Scene } from '../src/script';

const OUT = join(dirname(fileURLToPath(import.meta.url)), '..', 'renders', 'captions');

/** what a caption says for a scene that has no explanation copy of its own */
const cardText = (s: Scene): string => {
  if (s.kind === 'title') return `[${brand.productName} — ${brand.tagline}]`;
  if (s.kind === 'end') return `[${brand.productName}] Evidence, not opinion — on every change. ${brand.callToAction}. ${brand.disclosure}`;
  return '';
};

const lines = (s: Scene): string[] => {
  const card = cardText(s);
  if (card) return [card];
  return [s.label ? `[${s.label}]` : '', s.headline ?? '', s.why ?? ''].filter(Boolean);
};

const stamp = (sec: number, comma: boolean) => {
  const ms = Math.round(sec * 1000);
  const h = String(Math.floor(ms / 3600000)).padStart(2, '0');
  const m = String(Math.floor(ms / 60000) % 60).padStart(2, '0');
  const s = String(Math.floor(ms / 1000) % 60).padStart(2, '0');
  const f = String(ms % 1000).padStart(3, '0');
  return `${h}:${m}:${s}${comma ? ',' : '.'}${f}`;
};

/** a caption is held slightly short of the cut so it never straddles two scenes */
const build = (ids: string[] | undefined, pace: number) => {
  const scenes = pickScenes(ids);
  let cursor = 0;
  return scenes.map((s, i) => {
    const dur = s.seconds * pace;
    const from = cursor + Math.min(0.35, dur * 0.06);
    const to = cursor + dur - 0.12;
    cursor += dur;
    return { index: i + 1, from, to, text: lines(s).join('\n') };
  }).filter((cue) => cue.text.length > 0);
};

const toSrt = (cues: ReturnType<typeof build>) =>
  cues.map((c) => `${c.index}\n${stamp(c.from, true)} --> ${stamp(c.to, true)}\n${c.text}\n`).join('\n');

const toVtt = (cues: ReturnType<typeof build>) =>
  `WEBVTT\n\n${cues.map((c) => `${stamp(c.from, false)} --> ${stamp(c.to, false)}\n${c.text}\n`).join('\n')}`;

const deliverables: Array<[string, string[] | undefined, number]> = [
  ['hero-1080', undefined, 1],
  ['sales-1080', salesSceneIds, 0.62],
  ['social-1080x1920', socialSceneIds, 0.5],
];

mkdirSync(OUT, { recursive: true });
for (const [name, ids, pace] of deliverables) {
  const cues = build(ids, pace);
  writeFileSync(join(OUT, `${name}.srt`), toSrt(cues));
  writeFileSync(join(OUT, `${name}.vtt`), toVtt(cues));
  console.log(`${name}: ${cues.length} cues`);
}
