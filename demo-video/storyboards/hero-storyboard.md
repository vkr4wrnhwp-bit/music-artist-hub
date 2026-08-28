# Hero film storyboard — 78s @ 30fps (2340 frames)

Text model throughout: an **ACTION LABEL** (what is happening now) plus a
**value line** (why the customer cares). The words never narrate the cursor.

| # | Time | Screen / state | User action | System response | ACTION LABEL | Value line | Camera | Transition |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.0–5.5 | Black → brand | — | — | MASTERCLIP OS | Cinematic render factory | Slow rise from black, title settles | Cut on beat |
| 2 | 5.5–13.5 | Shot Builder | Shot spec already written; reveal | Canonical shot validated | ONE CANONICAL SHOT | Lighting, lens, continuity and rights are written once — every provider renders the same intent. | Establish full frame, push toward the spec panel | Match cut |
| 3 | 13.5–23.0 | Candidate matrix | Price this matrix | Every model × seed priced | PRICED BEFORE YOU SPEND | You approve a number, not an invoice you find out about afterwards. | Hold wide, then punch to the price column | Cut |
| 4 | 23.0–31.0 | Render queue | Submit batch | Jobs queued, worker picks up | BATCH DISPATCHED | Generation never blocks the desk. A worker carries it from here. | Gentle drift down the queue | Cut |
| 5 | 31.0–43.0 | Review grid, QC badges | — | QC decodes and measures every output | DEFECTS REJECTED AUTOMATICALLY | A black or frozen take never costs a human a minute of attention. | Push to a QC_FAILED tile, hold | Hard cut on the verdict |
| 6 | 43.0–54.0 | Review grid, approve | Approve a take | Decision recorded, routing updated | ONE DECISION PER TAKE | Rejection reasons feed model routing, so the next batch starts better. | Reframe to the approved tile | Dissolve |
| 7 | 54.0–65.0 | Cost lab | Compare | Spend resolved per approved second | COST PER APPROVED SECOND | Not cost per render — the only number that reflects shippable footage. | Static hold, counter animates | Cut |
| 8 | 65.0–72.0 | Masters | Promote → finish | Master rendered and packaged | PACKAGED WITH ITS PROVENANCE | Every delivery carries the spec, the seed, the QC record and the cost. | Slow push on the master row | Fade |
| 9 | 72.0–78.0 | Brand close | — | — | ONE SHOT SPEC. EVERY PROVIDER. ONE HONEST NUMBER. | MASTERCLIP OS | Static, generous margins | Fade to black |

## Sound cues

Low sustained pad throughout, built from the product's own synth engine.
Beat marks at scene 1 title settle, scene 3 price reveal, scene 5 QC verdict
(the hardest accent in the film), scene 7 counter landing, scene 9 close.
Soft interface ticks on the two real click moments (scenes 3 and 6) only.

## Derived cuts

**Sales — 30s.** Scenes 1 (2.5s) → 3 (7s) → 5 (9s) → 7 (7s) → 9 (4.5s).
Keeps problem, differentiator, and outcome. The QC beat is the centrepiece
because it is the least replicable claim.

**Social — 15s, 1080×1920.** Scenes 5 (6s) → 7 (5s) → 9 (4s), recomposed
vertically: the interface is scaled and cropped to the active region with the
label stack beneath it, never a letterboxed 16:9 crop.

## Required data

- Project "Neon Rain" with a written creative brief.
- One shot, "Nova under the sign", 4s, 480p, with lighting and continuity fields
  populated.
- A candidate matrix of 8 takes at $0.20 each.
- Deterministic outcomes: 6 cinematic takes, 2 deliberate defects (one `black`,
  one `frozen`) so the QC beat is guaranteed rather than hoped for.
- One approved take, promoted to a master.
