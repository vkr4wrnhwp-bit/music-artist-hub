# The eight rooms: redundancy, workflow, design

Audit of 2026-09-22, against `staging-fixes` at the green/fill commit
(`7e4cb418`, build `sb-v317`). Every claim below was checked by walking
a real account through the app — a brand-new one and one seeded with
fans, statements, a programmed show, a catalogue, a rollout and an
announcement — not read off the templates.

Scripts, kept so the walk can be repeated:
`scratchpad/room_audit.py` (structure) and `scratchpad/room_links.py`
(follows every link a room draws). Raw output in `audit-rooms.json`
and `audit-links.json`.

---

## The headline

**Navigation is clean.** Every one of the 74 links the eight rooms draw
on a filled account returns 200, and every destination carries a way
back to its room. There is no dead tile, no 404, no orphan page. That
was the thing most likely to embarrass a launch week and it is not
there.

What is left is not broken plumbing. It is **three names for one page,
one room with sixteen doors, and one room that never asked you to do
anything.** The third is fixed; the first two need your call.

---

## FIXED IN THIS PASS

### 1. Publishing had no way in
Every other room opens with a gold pill — *Upload a statement*, *Open
the plot editor*, *Launch fan campaign*. Publishing's *Add a song* was
an `rk-chip`: the same grey object as the account-name badge sitting
beside it. The room with the most set-up work to do was the only one
whose first step did not look like one.

Now the shared `rk-cta`. The kit did not even have a `.pb-cta` alias,
which is why it had drifted — fixed there too, so it cannot drift back.

### 2. The kit lock guarded half the rooms
`tests/test_room_kit.py` held Fans, Marketing, Releases and Publishing
to the shared kit. Stage, Studio, Analytics and Business were
unguarded — any of them could have redeclared a shared hero, tile or
panel and nothing would have said so. **They had not** (I checked all
four sheets: zero redeclarations). The lock now covers all eight, so
that stays true by test rather than by luck.

### 3. Two pieces of prose that lied about the code
- `rooms.py` said Publishing "draws ONE tile" over Beats and
  Fingerprints. It draws two (`publishing_room.py:343`), for a good
  reason recorded right there. The comment now matches.
- The **Deals** tile read *"The Deal Room and the simulator."* while
  **Deal Simulator** sat as its own tile two along. The description
  named the tile beside it. Now: *"Offers, terms and what you signed."*

---

## YOUR CALL — ranked

### A. One page, three names *(redundancy, worst of the set)*
`/links/new` is the campaign builder. It is titled **"New Campaign —
Links"**. It is reached from:

| Room | The button says |
|---|---|
| Releases | **Create a release** |
| Fans | **Launch fan campaign** |

So the room whose job is getting a record to the stores sends you to a
page that does not use the word release in its title, and the room
about fans sends you to the same place with a different promise. A
person who does both, once each, has met three vocabularies for one
object.

This is not a bug — the Releases room genuinely is built on campaigns
(`rr.campaign`, `rr.campaigns`). It is a naming decision that was never
made. **Recommendation: pick one word — I would use *release* — and
change the page title and the Fans button to match it.** Roughly a
day's careful sweep, because the word appears in the links product too.

### B. Business is sixteen doors *(redundancy)*
Tiles per room: Business **16**, Publishing 6, Studio 6, Stage 4,
Analytics 3, Releases 3, Fans 4 (own markup), Marketing 3.

Sixteen is not wrong — I checked, and the known pairs are deliberate
(Statements/Tax and Vault/Contracts are two real pages behind one
handler; deleting either deletes its only door). But four of them are
one job:

> **Recovery** · **Claims** · **Missing money** · **Disputes**

All four are *chasing money you are owed*. The plate above them already
has a **What you're chasing** panel. And three more — **Royalties**,
**Profit & Loss**, **Valuation** — are all *reading money you have*.

**Recommendation: group, do not delete.** Two labelled bands on the
board — *The money you have* and *The money you're owed* — over the
existing tiles. No page moves, no address changes, nothing to test
beyond the template. That turns a wall into two short lists. If you
want it, say the word and it is a small job.

### C. Analytics sends you to the same page twice *(redundancy)*
Two money insights in that room:

- *"Income breakdown"* → `/royalties`
- *"See what's missing"* → `/publishing`, which **redirects to
  `/royalties#streams`** (`app.py:12036`)

Same page, two promises. The second one predates the Publishing room,
whose plate literally reads **Money going uncollected** — which is what
"see what's missing" means. **Recommendation: point it at
`/room/publishing`.** One line, `insights_engine.py:48`. I did not
change it because it changes what the insight means, and that is
yours.

### D. Beats and Fingerprints are still two pages *(open work)*
Your ruling was *"beats and fingerprints should become like beat
fingerprints... not be two different ones in publishing."* The room
still draws two tiles, correctly — a single tile over two pages is a
door that lies. **The tiles merge when the pages do.** That page merge
is the actual outstanding task; it has not been started.

### E. Marketing's *"Add link"* goes to Rollout Studio *(wording)*
The finding is *"Rollout with no smart link connected"* and the fix
genuinely happens in Rollout Studio — but a button called *Add link*
reads as "make me a smart link". **Recommendation: *"Connect a
link"*.** `marketing_room.py:98`. One word; left it to you because it
sits in the same vocabulary question as A.

---

## Design: where the rooms stand

**The eight are one object now.** Same hero, same plate, same gold
ring, same tiles, same footer, all from `room-kit.css`, all in the
screen's green since this morning. Fans and Marketing keep their own
class prefixes (`fr-`, `mk-`) but the kit claims those names, so they
get the shared rules — verified by test.

Two notes rather than defects:

- **Fans and Marketing draw their tiles from their own markup** rather
  than the `rk-tile` the other six use. They *look* identical (the kit
  aliases them) but a future tile change has to remember five prefixes.
  Worth collapsing eventually; not urgent, and now locked either way.
- **Three of eight templates carry the `<!--room:key-->` markers.** Only
  a tooling nicety — it is what lets a script find a room's own content
  — but it cost me a wrong first pass on this audit. Cheap to add to
  the other five.

---

## What I would do with the rest of the week

1. **A — settle the vocabulary.** It is the only finding a new user
   meets in their first ten minutes.
2. **B — group the Business board.** Half a day, big visual return.
3. **C and E — two one-line wording fixes.** Minutes.
4. **D — merge the Beats and Fingerprints pages.** The real build job,
   and the one thing here that is a feature rather than a finish.

Nothing in this list blocks a launch. A, B and C are the difference
between *it works* and *it reads like one product*.
