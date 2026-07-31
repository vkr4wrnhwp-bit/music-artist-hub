# Implementation Log

Newest first. Each entry states what changed and what evidence drove it.

## Rack measurements reach the rest of the app

**Why:** an audit proved the Rack's loudness engine produced real,
standards-compliant measurements that no engine ever read, while Release
Readiness was scored entirely from campaign and artwork metadata. See
`PRODUCT_GAP_ANALYSIS.md`.

**Changed**

- `audio_readiness.py` *(new)* — rulings from stored measurements. True
  peak against the −1 dBTP ceiling, loudness against published platform
  targets, EBU 3342 range, tempo/key gated on detector confidence.
- `db.py` — `track_analysis` table; `save_track_analysis`,
  `get_track_analyses`, `latest_track_analysis`.
- `app.py` — `POST /rack/analysis`. Stores only; computes nothing.
  Rejects non-finite values and reports back the assessment.
- `static/js/rackdsp.js` — `reportAnalysis()` posts after each
  measurement, de-duplicated, and fails silently so a network error
  cannot break the meter.
- `qualification.py` — **Master Quality** category.
- `artist_twin.py` — `rack` added to `SOURCES`; `gather_context` reads
  the latest measurement under consent.
- `tests/test_audio_readiness.py` — 22 tests.

**A real bug the tests caught.** A master that is quiet *and* already
peaking fell through both branches to "sits in the normal band". That
combination is diagnostic, not neutral: the average is far below target
while the peaks are at the ceiling, so it cannot be raised without
clipping — usually one stray transient holding the record down. It is
now its own ruling.

**Verification:** 22 new tests; full suite green.

## Two more arrows: the Twin's master read, and money sorted by money

**Why:** a severed-signal audit traced every place the app computes real
data. Of 56 signals across the Rack, smart links and the money side, 42
came back severed. Two were worth closing immediately.

**The Twin was apologising for a capability it has.** `artist_os.py`
listed "Hook / structure notes — audio analysis, planned, not faked"
among the sections waiting on data that had not landed. It landed this
session. `twin_report` now takes the latest Rack measurement and reports
a **Master read**: what the loudness meter found, which rulings are
problems, and what to do. When nothing has been measured it says what
unlocks it rather than sitting empty.

**Recovery cases sorted by recency, not by value.** `list_recovery_cases`
ordered by status then `updated DESC`, so a $4 case sat above a $4,000
one purely because someone opened it more recently — in a list that is
worked from the top down. Now ordered by `estimated_amount` within
status, so open cases lead and the biggest money leads within them.

**A finding I refuted.** The audit claimed the Money Queue sorted a
$4,000 action identically to a $4 one. It does not: `action_queue` sorts
on `(not critical, -impact)`. Release-blocking items lead, then value.
Reported as a correction rather than "fixed".

**Verification:** 5 new tests, 489 in the suite, all green.

## The audit caught a bug I had just shipped

**The tempo and key pipe was dead on arrival.** `reportAnalysis` read
`tk.bpm.bpm` and `tk.key.key`, but `tkFound` stores `bpm` as a *number*
and `key` as a *string*. Both evaluated to `undefined`, `JSON.stringify`
drops undefined keys, and every tempo and key column landed NULL — while
`audio_readiness.tempo_key_ruling` and the Twin sat waiting for values
that could never arrive. The pipe was laid end to end and carried
nothing.

Two breaks, both fixed: detection was also discarding `bpm.confidence`
and `key.score` one line after computing them — the confidence being
exactly the number that decides whether a tempo is safe to quote.

**`sample_peak` was written on every pass and read by nothing.** It is
now evidence in the true-peak ruling, and it is the clearest statement of
the whole problem: *"A normal peak meter reads −0.31 dBFS on this file,
so 0.28 dB of it sits between the samples where that meter cannot see."*

**Two copies of the platform targets.** `loudness.js` has seven,
`audio_readiness.py` six. A test now refuses to let the overlapping six
disagree — the Rack must not tell an artist one figure while the score is
computed from another. They are deliberately not merged: the browser
needs its copy and the server needs its own.

**Verification:** 30 tests in this module, 492 in the suite, all green.

## Still severed (from the completed audit, unverified)

- Per-post click heat — the thesis in miniature: rollout posts carry real
  attribution, derived per request, never persisted, never informing the
  next rollout's platform choice.
- Catalog valuation from real statements — computed, discarded, so no
  trend exists.
- Territory splits — flagged as possibly *wrong*, not merely unused.
  Check before building on it.
- Hook windows — the Rack finds them, snapped to the downbeat; Rollout
  Studio generates clip ideas without them.
- `short_term_max` / `momentary_max` — stored on every pass, read by no
  ruling. These are the numbers broadcast delivery specs are written in.

## Territories: the claim was wrong, the danger was real

The audit flagged this as *"worse than unused — the Territories insight
the app actually surfaces is built from invented data."* Checked, and
that is **not true**:

- `/territories` renders `royalty_types.territory_report(user_id)`, which
  reads the real `statement_rows.territory` column.
- `/insights` renders `insights_engine.build_insights(user_id)`, which is
  real-data driven.
- The fabricated path, `insights_config.get_insights_data`, was **never
  called** — imported at `app.py:63` and invoked nowhere.

A second claim, that ingestion is "territory-blind by construction"
because `app.py:818` rebuilds rows as a 4-key dict, is technically true
and harmless: `statements_engine.analyze` consumes exactly `title`,
`source`, `amount`, `period`. Dropping territory matches the contract.

**But the investigation found something worth acting on.**
`insights_config.py` built a ranked list of *money the artist is not
collecting* — `"Close collection gaps in N territories"` with an `impact`
figure and a CTA — entirely from `_TERRITORY_SHARES`, hardcoded
percentages. It was dead, but it was imported into `app.py`, so wiring it
into the insights template was one line, and that line would have looked
completely reasonable to anyone.

Fabricated audio measurements would be embarrassing. Fabricated *money
owed* is the one number this product cannot get wrong.

Deleted `insights_config.py` and both dead imports. `territories_config`
survives — a test asserts real invariants on it — but now carries a
header saying it is wired to nothing, must stay that way, and where the
real per-country money actually lives.

**Verification:** 492 tests green.

## Rollout learns from its own rollouts

The audit called this *"the product thesis in miniature and it is
severed."* Two of its three claims held; the third — and the most
alarming — did not.

**Held.** `rollout_engine.generate_rollout(campaign, lyrics,
video_asset_id, image_asset_id)` takes no performance argument.
`next_action` reads only post statuses and asset types, and its final
line is *"Rollout is live — watch the performance page for what
converts."* The app told the artist to watch what converts and did not
watch it itself.

**Did not hold.** The claim that `clear_posts()` destroys the evidence
"at the exact moment the next decision is made" is wrong.
`variant_name()` encodes `rollout_{platform}_{phase}_{date}`,
`create_variant` stores `utm_source={platform}`, and `clear_posts` only
touches `ro_posts` — `ml_variants` and their events are never deleted.
The attribution survives every regenerate.

That correction is what made this cheap: **no schema change, no
migration, and the history already reaches back to the first rollout the
account ever ran.**

`rollout_learning.py` rolls those variants up by platform and by phase
and reports conversion *rates*. Two disciplines:

1. **It refuses to speak on thin evidence.** Under 25 visits on a
   platform, or 60 across everything, it says so and stops. A 75% click
   rate on 8 visits is noise, and an artist who reweights a campaign on
   it is worse off than one told nothing.
2. **Rates, not totals.** The platform with the most clicks is usually
   just the one with the most posts.

Wired in two places: an empty platform selection now defaults to what
converted rather than a fixed list (falling back to the fixed list when
evidence is thin, so new accounts behave exactly as before), and
`next_action` says something true when there is something true to say.

**Verification:** 14 new tests, 506 in the suite, all green.
