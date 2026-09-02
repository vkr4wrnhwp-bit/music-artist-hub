# Remix Lab page

`/remix-lab` is the public front of Remix Lab: a dark studio page built from
photograph and light, and a brief builder whose every control is the real
form. The engine and the honesty rules live in `REMIX_LAB_ENGINE.md`; this
note is about the page.

## What is real on the page

- **The rights gate.** Two switches. The upload input carries the `disabled`
  attribute server-side and `aria-disabled` on its proxy until both are on;
  the script keeps enforcing it and the server re-checks both on POST.
- **The form.** Every field name, option value, checkbox text and anchor is
  the one the tests pin. The vibe rows are `<select>`s; the segmented
  switches beside them are a progressive enhancement the script wires to the
  select (roving tabindex, arrow keys, select change mirrored back). The
  `sbrl-js` class that swaps them in is added by the script, not the head,
  so a page whose script never ran keeps its working selects.
- **The state indicators.** The four steps, the four chips in the bottom
  bar, the lock on the gate and the Rights safe zone rows all mirror the
  real form. Nothing on them is a score.
- **The hero canvas.** Once a file is chosen the browser decodes it locally
  and draws its amplitude in the hero. The note beside it says it was drawn
  in the browser and that nothing was uploaded in the preview.

## What is honest by omission

The mockup's Track Insights (BPM / key / length), energy curve, readiness
gauge, creative score, outputs-ready count and activity feed have no data
source before an upload, so none of them appear. The "What the brief reads"
card describes what a live brief measures and carries the state ("Not
measured in this preview" or "After upload"); values appear only on the
brief page, each line badged **measured**, **convention** or **chosen**. On
a placeholder plan (no provider configured) every line the engine marked
measured is re-badged **placeholder** and its sentence opens with
"Placeholder figure, not a reading of your track."

## The visual system

Tokens only (`--rl-*` aliases over `--sb-*`), translucents as
`rgb(r g b / a)` over the token's own triplet, the three radii, nothing
under 12px. Light is radial gradients and soft box-shadows; no blur
filters. Photographs: `sweep-wide` / `sweep-close` in the hero,
`distro-close` beside the features, `eq-room` under the outputs,
`distro-wide` under the rights band. Icons are a hand-drawn sprite
(`templates/partials/remix_lab_icons.html`, 49 symbols at a 24 box, stroke
1.5, `currentColor`); every lane, use, step and feature carries one on a
lit disc.

## Files

- `templates/remix_lab.html`, `templates/partials/remix_lab_icons.html`
- `templates/remix_lab_brief.html` (the result page, same system)
- `static/css/remix-lab.css` (`sbrl-*`, hand-written; the Tailwind build is frozen)
- `static/js/remix-lab.js`
- `tests/test_remix_lab.py`

## Responsive

Three breakpoints: three columns above 1100px, two to 640px, one below.
Below 640px the submit bar is no longer sticky (it was a quarter of the
screen) and the submit note stays visible so a blocked submit still says
why. The page never scrolls sideways at 375px.
