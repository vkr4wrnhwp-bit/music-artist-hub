# Studio Control Room

`/studio/session/<project_id>` is the record's home. The song is the hero,
the waveform is the instrument, and everything the platform knows about the
project sits underneath in three columns. Nothing on the page is a number
that came from bookkeeping dressed as a reading of the audio.

## The shape of the page

```
eyebrow · Street Banker Studio · Control Room
TITLE                                                   [first gap button] [Open the Rack]
artist
file · duration · size · Lossless · Rights confirmed · status · versions

waveform deck (markers · canvas · playhead · transport · keys)

CREATE ─ FINISH ─ APPROVE ─ PROTECT ─ DELIVER ─ RELEASE ─ MARKET ─ MONETIZE   (each opens its conditions)

Control Room | Rack | Mix | Master | Versions | Deliver                         (gold underline)

LEFT                 CENTER                  RIGHT
Session overview     Rack chain              Master directions
Mix readiness        Mix Doctor              Master readiness
Recent activity      On this record          Playback translation
                     Ask the Room            Delivery readiness
                                             Notes

System status (collapsed) → plain sentences → Engineering detail · build
```

Under 900 px the columns dissolve and the panels reorder: Doctor, Mix
readiness, Master readiness, Playback translation, Delivery, Rack, Team,
Overview, Notes, Ask, Activity.

## Three readiness questions, kept apart

| Panel | Answers | Source |
| --- | --- | --- |
| Mix readiness | How does the mix measure? | `studio_metrics.mix_metrics(measurements)` |
| Master readiness | How does it stand as a master? | `studio_metrics.master_metrics(measurements)` |
| Delivery readiness | Can the project ship? | `studio_metrics.delivery(checklist)` |

Every row is a **word**, never a score for a yes/no test:

`Pass · Clear · Healthy · In range · Watch · Review · Low confidence ·
Medium confidence · High confidence · Not measured · Not available ·
Needs stems · Needs reference · Simulation`

The measured value sits next to the word (`-6.1 dBTP`, `-13.8 LUFS`,
`8.4 LU range`, `94 BPM`, `E minor`). Tempo and key show the detected value
with its confidence; below 0.5 confidence the row says "Not confident enough
to report" and shows no value. Stereo image and tonal balance say "Not
measured" because those measurements are not built. Vocal balance says
"Needs stems". Low-end says "Needs reference".

The section-level line on Mix readiness is `studio_metrics.mix_score`, in
words, counted over the four audio tests only (headroom, clipping, loudness,
dynamics): "All 4 audio tests pass", "1 of 3 pass · 2 review", "1 of 4
measured, all pass". A number there would read as a grade of the mix, and
"100" on a set of pass/fail tests says "perfect", which nothing measured.
Tempo confidence and version completeness are still scored by
`studio_score.mix_readiness` for the Mix room, but they never appear on this
line. Until an audio test is measured the panel says "unmeasured" and shows
the Measure button.

Red is reserved for an over (clipping, headroom "Review"). Everything else
is gold, green, or grey.

## Mix Doctor

`studio_metrics.mix_doctor(findings, rulings, metrics)` picks one primary
observation, in this order:

1. an open finding from the analysis (blocking first, then by severity),
2. a platform ruling from `audio_readiness.assess()` at level problem or watch,
3. a metric in Watch or Review,
4. "Nothing has been measured yet" when nothing has,
5. "Nothing is flagged" with the list of what could not be measured.

"See why" opens the provenance: what was measured, the confidence, the
source, what was not measured, and a test worth running. The panel keeps the
sentence the architecture is built on: it reads what the project holds, it
has no ears, and it says so.

## The lifecycle rail

`studio_score.lifecycle` still decides each stage's state from project
facts. `studio_metrics.lifecycle_detail` adds the conditions behind each
stage as `(label, ok)` pairs and the next action. Each stage is a `<details>`
that opens a small panel. Nobody can tick a stage by hand.

## Delivery

The checklist is `studio_store.delivery_checklist`, computed, never ticked.
The one button in the hero and in the Delivery panel is the **first failing
required line**:

| First gap | Button | Goes to |
| --- | --- | --- |
| source | Upload the source | session |
| rights | Confirm rights | session |
| measured | Measure the audio | the Measure control |
| blocking | Resolve the blocking finding | mix |
| locked | Lock final version | version-lock dialog |
| title | Add project title | session |
| none | Prepare delivery | deliver |

The version-lock dialog lists each version with a "Lock" form that posts the
existing `studio_version_status` route with `status=locked`.

## On this record

`studio_metrics.team_state(member)` → `active`, `invite_pending`, `credit`.
A name is a credit. Access comes from an accepted team invite. The chips say
exactly that, and `data-access` stays `live` or `credit` as before.

## System status

Collapsed at the foot of the page. It opens on plain sentences from
`studio_metrics.system_notes(readiness)` ("Master rendering is not enabled
on this workspace yet…", "Long processing jobs are queued here…"). Under
those, a second disclosure, Engineering detail, carries the build number and
the component rows from `studio_config.readiness()`. The build number
appears nowhere else on the page.

## Files

- `studio_metrics.py` — the view models above. Pure functions, no I/O.
- `studio.py` `_room()` — hands `stages`, `mix_metrics`, `mix_score`,
  `master_metrics`, `doctor`, `delivery`, `activity`, `team_state`,
  `system_notes`, `transport_inline` to the template.
- `templates/studio/session.html` — the room.
- `templates/studio/_console.html` `rooms` macro — the tab row and the
  stylesheet link, shared by every Studio room.
- `templates/studio/_transport.html` — inline in the deck on the session
  (`transport_inline`), sticky elsewhere; playback chips carry
  `aria-pressed`, the selected one is drawn in gold.
- `static/css/studio-room.css` — `sr-*` classes. Hand-written because the
  Tailwind build is frozen.
- `tests/test_studio_control_room.py` — the states, the Doctor's order, the
  first-gap button, the lifecycle conditions, the activity fold, the team
  states, and the page pins.

## What is not built, and says so

Stereo correlation, tonal balance, vocal balance, low-end against a
reference, and section (hook) contrast are not measured. Their rows say
"Not measured", "Needs stems", or "Needs reference". The Doctor lists them
as "Not measured" rather than guessing. When a measurement lands, add it to
`studio_metrics` and the rows change on their own.
