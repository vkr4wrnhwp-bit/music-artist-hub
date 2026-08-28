# Demo film system

A reusable pipeline for making high-end product demo films from a real running
application: **Playwright** captures the product deterministically, **Remotion**
composes the film, and one scene script drives every deliverable and its
captions.

It is deliberately isolated from the application source. Nothing in
`mx-lab/` imports anything here, and the only thing this directory needs from
the product is a URL it can drive.

---

## Deliverables

| File | Format | Length | What it is for |
|---|---|---|---|
| `renders/hero-1080.mp4` | 1920×1080 | 96 s | The full argument. Site hero, sales calls, investor decks. |
| `renders/sales-1080.mp4` | 1920×1080 | ~30 s | Cutdown: problem, differentiator, honest outcome. |
| `renders/social-1080x1920.mp4` | 1080×1920 | ~15 s | Vertical teaser, **recomposed** for the frame, not cropped. |
| `renders/clean-1080.mp4` | 1920×1080 | 96 s | No explanation layer — narrate live, or localise. |
| `renders/thumb-*.png` | PNG | — | Poster frames. |
| `renders/captions/*.srt`, `*.vtt` | text | — | Subtitles, generated from the same script. |

---

## Running it

```bash
npm install

# 1. serve the product somewhere the rig can reach (see shots.trace.mjs APP)
#    e.g. from mx-lab:  npm run build && node scripts/demo.mjs
# 2. capture the product
npm run capture

# 3. make the audio bed (synthesised, no licensing to clear)
#    Do not regenerate it while a render is running — Remotion reads it from
#    disk as it renders, and replacing it mid-run fails the render.
npm run audio

# 4. render
npm run render:hero
npm run render:sales
npm run render:social
npm run render:clean
npm run still            # poster frame

# review interactively
npm run studio
```

### QC

```bash
node scripts/qc-stills.mjs HeroLandscape            # 24 stills across the film
node scripts/qc-stills.mjs SocialVertical 40,120,260
node scripts/probe-mp4.mjs renders/*.mp4            # size, duration, fps, codec
```

```bash
node scripts/qc-report.mjs HeroLandscape 48       # numeric blank-frame check
```

`qc-stills` bundles once and renders stills directly, which is much faster than
`remotion still` when you are reviewing a whole film. `probe-mp4` reads the MP4
boxes, because there is no usable `ffprobe` here. `qc-report` samples frames
across a composition and measures each one's luminance spread, so a dropped or
blank frame in the middle of a 2880-frame film is caught numerically rather
than hoped away — it exits non-zero if any sample looks empty.

The same caution applies as for audio: **do not re-run `npm run capture` while
a render is in progress.** The rig clears `public/recordings` first, and
Remotion serves those stills from disk as it renders.

---

## Reusing this for another product

Change three files. Nothing else.

| File | What it holds |
|---|---|
| `src/brand.config.ts` | Name, tagline, palette, fonts, fps, disclosure, call to action. |
| `scripts/shots.<product>.mjs` | The URL, the persona, and the shot list. |
| `src/script.ts` | The scenes: copy, durations, which shot, where the camera settles. |

The components (`src/components`), the timing engine
(`src/compositions/Film.tsx`), the capture rig (`scripts/capture.mjs`), the
caption generator and the audio synthesiser are product-agnostic.

### The shot list

```js
{
  name: 'compare',                       // -> public/recordings/compare.png
  route: '#/compare/sess-4/sess-5',
  settle: 2200,                          // ms to let charts finish
  scrollTo: 'text=Linked test plan',     // optional: frame this element
  async prep(page) { /* optional clicks */ },
}
```

The shot list captures two shots the current film does not use — `analyze` and
`pitboard`. They are kept because cutdowns and future scenes draw from the same
library, and capturing is cheap next to re-running the rig.

The rig reloads on every shot, so a shot never inherits state from the one
before it — with a hash-routed SPA, a fragment change alone leaves component
state (an active tab, say) untouched, and captures silently duplicate.

### The scene script

```ts
{
  id: 'compare', seconds: 11, kind: 'screen', shot: 'compare', copyAt: 'bottom',
  focus: { x: 0.06, y: 0.29, w: 0.88, h: 0.25 },   // normalised region to settle on
  label: 'WHAT CHANGED · WHAT HAPPENED · WHAT CAUSED IT',
  headline: 'The rider preferred it. The data disagreed.',
  why: 'Confidence rose 3 points while best lap fell 1.79s — and the uncontrolled variable is flagged.',
}
```

`focus.w` sets the push (zoom is `1/w`, capped at 2.1×); `focus` also sets where
the camera centres. The pan is clamped so the capture always covers the frame.

---

## Design rules the system enforces

- **One camera move.** A slow push to a named region, settling at 72 % of the
  scene so every result is held while it is being read.
- **Two levels of text, never three.** Mono eyebrow, display headline, one line
  of why.
- **The copy band reaches the ground colour.** A partly transparent scrim lets
  interface text show through a headline, which reads as a bug.
- **Capture above delivery.** 1440×900 at 2× device scale = 2880×1800, so a
  2.1× push still resamples above 1080p.
- **Vertical is recomposed.** `tightenForVertical` narrows each focus rect and
  all copy moves to the lower third; the 9:16 cut is composed, not cropped.

## Honesty rules

These are constraints on the film, not stylistic preferences.

- Only real screens from the running application. No mocked-up UI, no invented
  numbers, no fake cursors.
- The application's own `SIMULATED` banners and pills stay in frame.
- The closing card carries the build's real limitations.
- Copy is checked against the frame it sits on. Where the seeded record showed
  one person as both author and approver, the copy was changed to describe the
  change sheet rather than claim a second reviewer.
- The A/B result in the film is the one the product actually produces —
  a change the rider preferred and the lap times did not.

## Audio

`scripts/make-audio.ts` synthesises the bed from scratch (a low drone, a slow
pad swell, a 1.5 s pulse, and marks on the scene boundaries) and writes a
48 kHz stereo WAV normalised to about −10 dBFS. Nothing is sampled or
downloaded, so there is no licence to clear and no attribution to carry.

```bash
npm run audio          # length and cut points come from src/script.ts
npm run audio -- 120   # or force a length in seconds
```

It reads the scene list, so the marks land on the film's cuts and the bed
cannot drift when a scene's duration changes. Re-run it after editing
durations.

## Environment notes

- Remotion cannot download its own headless shell here (`remotion.media` is
  outside the network policy). `remotion.config.ts` points it at the Chromium
  that ships for Playwright instead.
- Fonts come from `@fontsource/*` npm packages rather than the Google Fonts
  CDN, which is also outside the policy. They are bundled into the render.
