# Light Studio

`/lights`. A browser light-show tool: load a song (Web Audio, never
uploaded), cue looks to it on a simulated stage, and drive real fixtures
over Web Serial (ENTTEC USB Pro framing, `0x7E … 0xE7`, 30 fps).

## Files

| File | Role |
| --- | --- |
| `static/js/lights-engine.js` | Pure maths, no DOM — groups, fade resolver, DMX framing, waveform peaks, onset/BPM detection, beat snap, tap tempo, looks. Loads in Node (`tests/js/check_lights.js`) and the browser (`window.LightsEngine`). |
| `static/js/lights.js` | The studio: transport, waveform lane, hi-DPI stage, cue list, group picker, looks, bar selection, keyboard, library/autosave, focus mode, phone dock. Test hooks on `window.__lightsTest`. |
| `static/css/light-studio.css` | Hand-written `lx-*` styles (the Tailwind build is frozen). |
| `templates/lights.html` | Page. Every `$("id")` in `lights.js` must exist here — `tests/test_light_studio.py` enforces it. |
| `lights_store.py` | Library: `light_show_library` (named shows, track + tour-date links) and `light_show_versions` (snapshot per explicit save, last 20). The one-per-user working copy stays in `light_shows`. |
| `tools/dev_preview.py` | Local preview on a throwaway DB for the in-app browser pane (`.claude/launch.json` → `sb-preview`). |

## What the overhaul added

- **Waveform timeline** under the transport: decoded peaks (max/min per
  pixel, hi-DPI), draggable cue flags (blackouts are dashed diamonds with
  a cross), click to seek, wheel to zoom / shift-wheel to pan / pinch on
  touch, playhead, beat grid when a tempo is known.
- **Focus mode**: `body.lx-focus` tightens the shell and folds the sidebar
  to its rail (`body.sb-rail`, desktop). Remembered in `localStorage`
  (`lxFocus`, `lxRail`); the header button and the rail toggle both undo
  it. Desktop: stage and cue list share the viewport; phones stack.
- **Transport**: sticky; big tabular-mono timecode; status text wraps and
  never collapses; DMX state chip (`Preview only` / `Connected · universe
  1 · N fps` measured from real writes / error). Phones get a fixed
  bottom dock (Play, + Cue, Blackout, clock) instead of the tall sticky
  bar.
- **Stage**: renders at `devicePixelRatio`, fills its container, redraws
  on resize; ≥44 px hit areas; hover / selected / mirror-partner /
  group-hover rings; arrow keys nudge the selected bar (`R` flips);
  Hung / Side-stick segmented control for the selected bar; a bars table
  as the screen-reader twin of the canvas.
- **Group picker**: mini stage diagram per group with the firing bars lit;
  hover previews on the stage; sets the selected cue's group or the
  default for new cues.
- **Cue rows**: mono timecode, colour swatch (blackout ✕), group glyph,
  fade, editable note, delete; click previews the stage at that time.
  “+ Cue” disabled with a hint until a song is loaded (or Run cues only).
- **Looks** chips (amber wash, cold blue, red alert, white full, violet
  haze, blackout) + keys 1–6.
- **Beats**: onset/BPM detection on load (parabolic-refined
  autocorrelation), snap-to-beat toggle, tap tempo, grid toggle.
- **Library**: named shows, autosave (1.5 s debounce) to the working
  copy + the active library entry, “Saved ✓ hh:mm”, version history with
  restore, link to a track and a tour date (validated server-side).
- **Keyboard**: Space play/pause, C cue, B blackout, 1–6 looks, 7–0 your
  looks, X all off, ←/→ seek, Esc closes the gel book / deselects;
  visible focus rings; helper text ≥12 px.

## Unsaved work, undo, accessibility (polish pass)

- **Draft vs library.** Every change autosaves the *draft* (the
  `light_shows` working copy) 1.5 s later with `draftDirty` /
  `draftSavedAt`. A library row changes **only** on "Save to library",
  which also takes a version. A dirty draft of a library show prompts on
  load: keep the draft, or open the last library save. `beforeunload`
  warns while there are unsaved changes relative to the last library
  save (or an autosave is pending). The indicator by the Save button
  reads *unsaved changes* / *saved to library* / *not in library yet*.
- **Undo/redo.** `LightsEngine.makeHistory(50, 800)` — snapshots of
  cues/pos/rot/bars/chans; gestures coalesce by key inside 800 ms;
  Ctrl/Cmd+Z, Ctrl/Cmd+Shift+Z, Ctrl+Y (ignored while typing in a
  field); Undo/Redo buttons in the cue pane.
- **A11y.** Labelled transport; `role=list` cue rows with timecode+look
  labels; waveform as a keyboard slider; bars table with Select buttons
  (updated in place); `#lx-live` polite announcements; focus rings.
- **Focus rail.** `body.lx-focus` at ≥1024 px hides `#sb-aside` and
  shows `#lx-rail` (56 px, icon links + expand control).
- **Known-good interactions (self-tested with a real WAV through the
  file input):** click-seek, flag drag at any zoom, zoom anchoring, pan,
  pinch, Fit song, Detect beats, Snap to beat.

## Colour, looks, output, patch (audit pass)

- **Stage art.** Background is `static/img/stage-bg-2.jpg` (the supplied
  stage photo); fixtures are `static/img/light-bar.png`, an 8-lens LED bar
  sprite drawn to scale (rotated for a side stick) with its lenses lit in
  the look's colour. Lens geometry lives in `LENS_X` / `LENS_CY` /
  `LENS_R` in `lights.js` (measured from the sprite once). A drawn housing
  is the fallback until the sprite loads.
- **Gel book.** Every cue swatch is a button that opens `#lx-gel`, one
  shared popover: 30 named gels (Lee numbers people actually carry),
  recent colours (`localStorage` `lxRecentGels`), a hex field, and
  "Custom picker…" which clicks the cue's hidden native `<input
  type=color>`. Intensity is never part of colour — it stays the slider
  on the cue. Esc closes and returns focus to the swatch.
- **Your looks.** "Save selected cue as look" stores up to four
  `{name,color,intensity,fade}` in `show.looks`, so they travel with the
  working copy and every library save/version. Keys `7 8 9 0` apply them;
  `1–6` stay the house looks, `B` blackout. Removable with ×. Covered by
  undo.
- **Per-group colour at one timecode.** Not a per-cue field — instead two
  cues at the same time on different groups resolve per fixture
  (`lightingAt` is per bar; later cue wins for a bar in both). Proved in
  `check_lights.js` ("same-timecode cues merge per bar").
- **Hand-picked groups.** `shift-click` bars on the stage toggles them in
  a custom group key `b1+b3+b6` (`LightsEngine.customGroup` /
  `toggleInGroup`); the cue row's dropdown shows it as "Bars 1 + 3 + 6
  (picked)". The visual group picker is folded by default.
- **Grand master + All off.** Live state, not part of the show:
  `LightsEngine.scaleLooks(looks, master, panic)` feeds the stage, the
  bar list and the DMX frame (`outLooks(t)`). `X` toggles All off; the
  button goes red and `body.lx-panic` outlines the stage. When a DMX
  interface is connected the rig is also fed a slow heartbeat while idle
  so it holds what the stage shows.
- **DMX patch.** `show.dmxStart` (first address), `show.dmxAddr[bar]`
  (per-bar override, from the bar drawer), `show.dmxUniverse` (label on
  the chip; the USB Pro drives one universe).
  `LightsEngine.fixtureAddress(show, bar)` resolves; `patchOverlaps` warns
  in the drawer; a fixture patched past 512 is skipped, never wrapped.
- **Bar drawer.** Clicking a bar (canvas or the All-bars list) opens
  `#lx-barctl`: orientation, across/down %, DMX start, look now, mirror
  partner, prev/next. The All-bars list (`#lx-bars-list`) replaced the
  table as the screen-reader twin.
- **Audio controls.** Volume (gain node), rate (½× … 1½× —
  `now()` scales elapsed context time by the rate so the clock and cues
  stay in song time), and a scrub slider mirroring the playhead.
- **Auto-cue (epic 1).** `Auto-cue` in the wave bar runs
  `LightsEngine.analyzeTrack` (sections, drops, hard stops, tempo) and
  `generateCues` on the loaded song: one editable cue per section, a
  three-beat accent burst on a drop, blackout + restore around hard
  stops. Auto cues carry `auto:true`, wear an "auto" badge and become
  yours the moment you edit any field (`own()`); "Clear N auto cues"
  removes only the untouched ones. Sections/stops are kept in
  `show.sections` / `show.stops` and drawn as tinted, labelled bands on
  the waveform; re-running replaces the auto set, never your cues.
- **Import / export.** `Export JSON` downloads
  `{format:"street-banker-lights", version:1, show}`; `Import JSON`
  sanitises every field (`importShow`) and replaces the working copy only
  (confirm first when cues exist) — library saves are untouched.

## Endpoints

`GET /lights` · `POST /lights/save` (working copy) · `GET /lights/library`
· `POST /lights/library/save` (`id?`, `name`, `data`, `track_id`,
`tour_show_id`, `autosave`, `note`) · `GET /lights/library/<id>` ·
`GET /lights/library/<id>/versions` · `POST /lights/library/<id>/restore`
(`version_id` → `data`) · `POST /lights/library/<id>/delete`.

## Testing in the browser pane

The service worker caches static assets cache-first, so after editing
`lights.js`/`light-studio.css` unregister it and clear caches before
reloading (or bump `?v=`). `requestAnimationFrame` is frozen while the
pane is hidden — use `__lightsTest.tick()` to force a repaint and
`__lightsTest.loadBuffer(audioBuffer, name)` to load a synthesized song
without a file dialog.
