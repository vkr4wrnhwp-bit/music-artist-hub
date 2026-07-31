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
