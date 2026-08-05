# Homepage implementation log

Phase-by-phase account of the coordinated implementation pass. Written to
be checkable: where a phase is partial or not done, it says so and why.

| Phase | Status |
| --- | --- |
| 0 — Audit, backup, documentation | **Done** |
| 1 — Public bugs, routes, status consistency | **Done** |
| 2 — Human voice copy | **Done** |
| 3 — Page rhythm and composition | **Partial** |
| 4 — Full-width Artist EQ | **Done** |
| 5 — Interactive Three Lanes | **Done** |
| 6 — Mobile responsive rebuild | **Partial** |
| 7 — Visible content reduction | **Missed the target** |
| 8 — Image credibility audit | **Blocked** |
| 9 — Release Signal | **Done, disabled by design** |
| 10 — Product tour and conversion | **Partial** |
| 11 — Trust, accessibility, performance | **Partial** |
| 12 — Advanced product roadmap | **Done** |
| 13 — Footer | **Done** |

---

## Phase 0 — audit, backup, documentation

Backup taken before any edit: `backups/homepage-2026-08-05/` plus git tag
`pre-real-photography`, containing every image derivative for the three
sections due for replacement, the configs, templates, stylesheets and the
production-rendered homepage.

Documents produced: `HOMEPAGE_MASTER_AUDIT.md`,
`HOMEPAGE_IMPLEMENTATION_LOG.md` (this file), `CTA_ROUTE_MAP.md`,
`PUBLIC_ROUTE_MAP.md`, `CAPABILITY_STATUS.md`,
`HOMEPAGE_IMAGE_REPLACEMENT_MAP.md`, `IMAGE_ASSET_MANIFEST.md`,
`ACCESSIBILITY_AUDIT.md`, `PERFORMANCE_AUDIT.md`,
`FIVE_YEAR_PRODUCT_ROADMAP.md`.

`PUBLIC_ROUTE_MAP.md` and `CAPABILITY_STATUS.md` are generated from the
running application rather than written by hand, so they cannot drift.

## Phase 1 — public bugs, routes, status

Five object-string leaks, two of them live. Three missing public pages
built. Four classes of routing failure fixed. One capability-status
module replacing three independent copies. Full detail in
`HOMEPAGE_MASTER_AUDIT.md`.

The Spotify ambiguity is resolved by construction: the status is probed
against the environment, and the privacy language about token handling is
conditional on the same probe.

## Phase 2 — human voice

Approved copy applied to hero, Artist EQ, Departments, Artist Twin,
Lanes, Creative Studio, Rollout Engine, Royalty Sweep, Global
Distribution, Metadata Passport, Trust Band and Closing. Six unsupported
claims removed, 31 British spellings standardized, `Rollout Studio`
renamed to `Rollout Engine` across 17 files.

## Phase 3 — page rhythm — PARTIAL

Not attempted as a systematic pass. The approved layouts were largely
already in place from the section-by-section builds: hero is full-bleed
editorial, Artist EQ is now full-width centred with no competing
photography, Lanes and Departments are centred hardware, Creative Studio
is copy-left/image-right, Rollout is image-left with a photographic
bleed, Sweep/Distribution/Passport are centred, Trust Band is typography
only and Closing is full-bleed with copy in the natural negative space.

What was **not** done: the spacing audit against the specified
120–160px / 72–96px scales, and verification that no composition system
repeats three times consecutively. Both need to be seen rendered, which
was not possible.

## Phase 4 — Artist EQ — DONE

Inner width 1152px → 1480px. Split 66/34 → 68/32. Reasoning moved behind
a "Why this plan?" disclosure so the panel shows the answer, not the
argument; the lane reasoning inside it is kept in step with the panel so
it can never argue for a superseded plan.

Already correct before this pass and left alone: presets above the
controls and matching the six specified names, six full-width horizontal
sliders on mobile with 44px targets, no duplicated preset controls. The
trace was checked against "no decorative random waveform motion" — it
plots the six channel values, so it is data, and it stays.

State now persists the recommended lane, which is what Phase 5 reads.

## Phase 5 — Three Lanes — DONE

Live controls overlaid on the approved rack rather than animating the
baked JPEG: a VU per channel, a fader, and a lamp. Only those three move.
Decorative knobs stay still — a decorative control that responds to
dragging teaches people the controls are fake.

VU response is fast rise, 7° overshoot, settle at 190ms. No idle loop, no
randomness, no audio. Honours `prefers-reduced-motion`.

The fader is **depth of support** — Core, Guided, High-touch — not
volume. Partnership stays review-based at every position and the readout
says so at the top detent.

EQ connection: the lane the console recommended is engaged here and named
("Based on your Artist EQ: …"). With no EQ interaction the line stays
hidden rather than defaulting to a recommendation nobody asked for.

CTAs: Start a release / Build my artist plan / See if I qualify.

## Phase 6 — mobile — PARTIAL

**Done:** the Three Lanes rack no longer scrolls horizontally. It used to
render at 175vw inside an overflow-x rail, which put a scrollbar on the
homepage and hid two of three channels behind an unadvertised gesture.
The complete rack now scales to the viewport with `object-fit: contain`,
all three meters visible, and real buttons underneath.

**Not done:** the Six Departments horizontal carousel is still a swipe
strip; the per-section mobile recompositions for Twin, Creative Studio,
Rollout, Sweep, Distribution and Passport were not individually rebuilt;
no testing at 320/375/390/430/768/1024 because nothing could be rendered.

## Phase 7 — content reduction — MISSED

Target 35–45%. **Achieved 6.0%** (1691 → 1589 visible words).

Two reasons, both worth stating plainly rather than dressing up:

1. **The deep blocks the brief lists were already collapsed.** The lane
   comparison, the Sweep recovery case and the Rollout sample were
   already behind `[hidden]` toggles before this pass. Collapsing the
   Passport documentation and the Distribution checklist — the two that
   genuinely were not — is what produced the 6%.
2. **The rest of the visible text is Phase 2's approved copy.** Reaching
   35% means removing roughly 490 more visible words, and after the
   collapses there is no deep content left to move. What remains is the
   headline, support line and labels the same brief specifies verbatim.

Both cannot be satisfied. I collapsed everything collapsible and left the
approved copy intact, on the basis that specified copy is a harder
constraint than a word-count ratio. If the ratio is the priority, the
next cut has to come out of the approved copy and that is a decision to
take deliberately.

Measurement is `tools/visible_words.py`, which excludes closed
`<details>`, `[hidden]`, and eight visually-hidden classes discovered
from the stylesheets. Counting the screen-reader fallbacks would have
inflated the baseline by about 20% and made the reduction look far
better than it is.

## Phase 8 — image credibility — BLOCKED

Classification is in `HOMEPAGE_IMAGE_REPLACEMENT_MAP.md`.

Blocked on the stop condition the brief names: **a real artist image
lacking confirmed usage permission.** Two documentary photographs were
selected for the hero and Rollout Engine, but they were never transferred
to disk — they were posted into the chat, which renders them without
creating files. A third candidate carried a visible photographer's
watermark, which contradicts the stated ownership and was not used.

No AI images were generated. No watermark was removed.

## Phase 9 — Release Signal — DONE, DISABLED

Provider-neutral analysis layer (`release_signal.py`): an
`AnalysisProvider` interface, a `NullProvider` that refuses rather than
inventing, and a Chartmetric adapter that is written but not enabled.

Chartmetric is **not** connected. Its `configured()` requires both a
token and an explicit rights-confirmed flag, because credentials alone do
not establish commercial display rights, caching rights,
derived-recommendation rights or retention terms. None of those are
settled, so the honest state is off.

The public page states it cannot read a track on this deployment and does
not accept an upload. The compact homepage entry sits inside the Artist
EQ band rather than as another cinematic section, and its status chip
resolves from `capability_status`, so connecting a provider flips it to
Live without anyone editing copy.

Output vocabulary excludes Hit Score, Viral Probability, Industry
Approval and Algorithm Score by construction. The three comparison axes
are kept apart.

## Phase 10 — product tour — PARTIAL

The tour exists at `/product-tour` with twelve steps, a status key and an
example workspace at `/product-tour/smart-link`. Its statuses now resolve
from `capability_status` rather than being written out separately.

**Not done:** Release Signal and Release Builder are not yet steps in the
journey, and visitor selections from Artist EQ are not carried into the
tour (they are carried into `/start`).

## Phase 11 — accessibility and performance — PARTIAL

**Done:** disclosures use native `<details>`/`<summary>`, which gives
correct expanded semantics, keyboard operation and find-in-page without
a scripted widget. Touch targets on the new surfaces are 44–54px. The new
pages have one `h1`, no heading-level skips, `alt` on every image and a
visible focus ring. Reduced motion is honoured by every new transition.

**Not done:** no screen-reader pass, no axe-core run, no Lighthouse, no
contrast verification of the new chips against their backgrounds beyond
computed values, and no layout-shift measurement — all require rendering.

## Phase 12 — roadmap — DONE

`FIVE_YEAR_PRODUCT_ROADMAP.md`. Ten items across three tiers, each with
user problem, behaviour, data, permissions, dependencies, risks,
monetization, MVP and V2. Nothing is claimed live and nothing appears on
a public surface.

## Phase 13 — footer — DONE

Five columns exactly as specified. Every destination public and verified
by test. Only the one real social account is linked.
