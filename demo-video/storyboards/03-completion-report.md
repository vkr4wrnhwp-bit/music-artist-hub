# Completion report — TRACE demo film system

## COMPLETED

A reusable product-demo film system in `demo-video/`, isolated from the
application: nothing in `mx-lab/` imports it, and all it needs from the product
is a URL it can drive.

**Films** (all 30 fps, H.264 + AAC):

| File | Format | Duration | Size |
|---|---|---|---|
| `renders/hero-1080.mp4` | 1920×1080 | 96.04 s | 42.8 MB (CRF 16 master) |
| `renders/hero-1080-web.mp4` | 1920×1080 | 96.04 s | 14.2 MB (CRF 25, web) |
| `renders/sales-1080.mp4` | 1920×1080 | 26.75 s | 8.7 MB |
| `renders/social-1080x1920.mp4` | 1080×1920 | 13.85 s | 2.9 MB |
| `renders/clean-1080.mp4` | 1920×1080 | 96.04 s | 60.0 MB (no copy layer) |

**Also:** three poster stills, SRT and VTT captions for the three copy-bearing
cuts, a synthesised audio bed, a product brief, a hero storyboard, and a
handoff README.

**Pipeline:** Playwright captures the running application at two viewports →
Remotion composes → one scene script drives every deliverable and its captions.

**Retargeting** to another product means editing three files: `brand.config.ts`
(identity, palette, type, disclosure), `scripts/shots.<product>.mjs` (URL,
persona, shot list), `src/script.ts` (scenes, copy, camera). Components, the
timing engine, the capture rig, the caption generator and the audio
synthesiser are product-agnostic.

## VERIFIED

- **`npx tsc --noEmit` clean.**
- **Every scene inspected as a full-resolution still**, not just sampled — all
  thirteen scenes of the hero plus the vertical's four.
- **Container probe** (`scripts/probe-mp4.mjs`) on all five MP4s: dimensions,
  duration, frame rate and track codecs as tabled above. Every file carries
  both an `avc1` video track and an `mp4a` audio track.
- **Blank-frame sweep** (`scripts/qc-report.mjs`) on all four compositions at
  40–60 samples each: nothing blank outside the film's deliberate opening fade
  from black.
- **Dense boundary sweep**: both sides of all thirteen scene boundaries plus
  two frames either side — 42 frames measured, minimum luminance spread 5.59
  against a threshold of 3.0.
- **Fonts render** (Archivo, IBM Plex Sans, IBM Plex Mono all visible in
  stills; no fallback silently substituted).
- **Capture integrity**: all twenty stills across both viewports are distinct,
  and the rig reports zero page errors.

### Defects found by that review, and fixed

1. `telemetry.png` and `markers.png` were byte-identical — a hash-only
   navigation does not remount a hash-routed SPA, so the session tab never
   changed. Every shot now reloads.
2. The telemetry chart was framed so the full 720 s session rendered as an
   unreadable hairball, then over-magnified past the point the raster could
   resolve. Reframed at capture time.
3. Interface text bled through the engineer scene's headline — the scrim was
   semi-transparent where the copy sits. It now reaches the ground colour.
4. `+3 RIDER CONFIDENCE`, the number the film builds to, fell inside the copy
   band. Fixed by scrolling the capture, not by over-zooming.
5. The revision table's NOTES column was clipped mid-word by the side scrim.
   Reframed so columns end where the band begins.
6. The change-sheet scene claimed "a second person verifies it" while the
   screen showed the same tuner as author and approver. Copy now describes the
   change sheet.
7. "best lap fell 1.79s" reads, in lap-time language, as *faster* — inverting
   the film's entire climax. Now "the best lap went 1.79s slower".
8. "moves one region" understated a diff the screen itself reports as 26 cells
   across two areas.
9. **Every transition landed on black frames.** Sequences did not overlap, each
   scene paints an opaque ground, and each scene's contents started at zero
   opacity. Scenes now cross-dissolve over six frames.
10. Cards also faded *themselves* to black over their last sixteen frames,
    which fought the new dissolve and left the frame before each cut nearly
    empty. Retired; card content now rises from frame 0.

Defects 9 and 10 were caught by the numeric sweep, not by eye — an even sample
grid had missed them twice.

## ASSUMPTIONS

- The **tuner** is the audience: the persona the capture rig signs in as, and
  the person who decides whether a change ships.
- The film is an **argument, not a feature tour**. Two of ten captured screens
  (`analyze`, `pitboard`) are deliberately unused; they are kept for future
  cuts.
- **96 s** for the hero, from the brief's 60–90 s guidance plus the extra beat
  the honest ending needs. The cutdowns are ~27 s and ~14 s.
- The **audio bed is synthesised from scratch**, so there is no licence to
  clear and no attribution to carry. It is a bed, not trailer music: peak
  −9.9 dBFS, and it never competes with reading the interface.
- The application's own `SIMULATED` banners are **left in frame on purpose**.
  They are the product being honest; cropping them out would misrepresent it.

## LIMITATIONS

- **No 4K master.** Capture is 2880×1800, and the film's pushes reach 2.1×, so
  a 2160p render would upscale on most shots. 1080p is the honest ceiling for
  consistent quality at the current capture scale.
- **No voiceover.** The films are silent but for the bed; the captions are
  subtitles of the on-screen copy, not a transcript of narration.
- **Seeded demonstration data throughout.** Phase 1 of TRACE runs on simulated
  telemetry and no ECU write path exists in the build; the closing card says
  so.
- **The change-sheet scene shows one person as both author and approver**,
  because that is what the seed contains. The product's approval is
  role-gated, but the film does not claim two people, since the frame does not
  show two.
- **The `.mp4` masters are gitignored** — large binaries, reproducible with
  `npm run render:*`. Captions and poster stills are committed.
- **Environment**: Remotion cannot fetch its own headless shell here, so it is
  pointed at the Chromium installed for Playwright; fonts come from
  `@fontsource` packages rather than the blocked Google Fonts CDN; the only
  ffmpeg on the box is a stripped Playwright build with H.264 disabled, so QC
  reads MP4 boxes directly instead of calling ffprobe.
- **One real footgun**, documented in the README: re-running the capture rig or
  the audio generator while a render is in progress fails that render, because
  Remotion serves both from disk as it goes. It cost one render here.

## FILES

```
demo-video/
  README.md                        handoff: run it, retarget it, the rules it enforces
  brand.config.ts                  ← identity, palette, type, fps, disclosure
  src/
    script.ts                      ← scenes: copy, durations, camera
    Root.tsx                       five compositions
    theme.ts                       one type scale
    compositions/Film.tsx          timing engine, scrims, vertical composition
    components/{Screen,Copy,Cards,Marks}.tsx
  scripts/
    shots.trace.mjs                ← URL, persona, shot list, capture variants
    capture.mjs                    deterministic Playwright rig
    make-audio.ts                  synthesised bed, boundaries read from the script
    make-captions.ts               SRT + VTT from the same script
    qc-stills.mjs                  bundle once, render stills at chosen frames
    qc-report.mjs                  numeric blank-frame sweep
    probe-mp4.mjs                  duration / dimensions / fps / codecs from the boxes
  storyboards/
    01-product-brief.md            what the product is, checked against screens
    02-hero-storyboard.md          the 13 scenes and why they are in that order
    03-completion-report.md        this file
  public/recordings/{wide,tall}/   20 captures, committed for reproducibility
  renders/                         films (gitignored), captions, poster stills
```

The three files marked ← are the whole retargeting surface.

## NEXT RECOMMENDATION

**Raise the capture scale to 3× and cut a true 4K hero.** One line in
`capture.mjs` takes captures to 4320×2700, which puts genuine detail behind
even the 2.1× pushes and makes a 2160p master honest. It is the single change
with the largest quality return, and everything else in the pipeline already
supports it.

After that, in order: a voiceover pass over `clean-1080.mp4` (which exists for
exactly this); a second film on the team-sync and grant flow, which is TRACE's
other defensible story and needs only new scenes against captures the rig
already takes; and re-running the rig against the deployed URL rather than a
local build, so the films track what customers actually see.
