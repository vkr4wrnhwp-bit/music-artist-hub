# What was asked for and is not there

Every user message in the CANVAS build conversation was read back, every
concrete ask extracted, and each one checked against the code as it stands.
A claim only appears here if someone went and looked and found the thing
absent — every finding was then handed to a second reader whose instructions
were to refute it, and a third of the claims died there.

This is not a backlog of good ideas. It is only things that were asked for.

**Read the status honestly:**

- **REGRESSED** — it worked, or was designed to, and something later broke it.
- **NEVER STARTED** — no trace in the code.
- **DEFERRED** — asked for, answered with "later", and later did not come.
- **PARTIAL** — most of it landed and a named piece did not. This is the
  largest category and the most dangerous one, because a feature that is
  nine-tenths present reads as finished. The specific missing tenth is
  written out for each.

Nothing here is a percentage and nothing here is averaged. A section with
four items done and one missing is not 80% done; the missing one is missing.


## Closed in this pass

- **Setup photographs on the shop-floor tablet** — a record of how the job was held, pinned to the setup
- **Provenance deep dive** — the badge opens; instrument/uncertainty/shop-evidence remain honestly absent
- **NC upload provenance: encoding, line endings and controller family** — and the CR-only parse bug they exposed
- **Every major recommendation supports WHY / CHANGE / I DISAGREE** — mounted on seven surfaces
- **SHOW ME on a review finding updates the 3D scene** — `f0c8ab2`
- **Backend debug jargon purged from the UI** — `15ce8fd`
- **View Environment lighting controls, per preset** — `86ec2cf`
- **The process advisor states what it does not assess** (routing included) — `f6a3935`
- **NEW PART as a core section — a part created from the command bar (DESCRIBE / IMPORT CAD) must be able to reach a manufacturing plan** — `4e62e9f`
- **Measurements must reference the established datums — save relatedDatum with each reading, so a dimension is recorded as measured from Datum A/B/C rather than as an isolated number** — `e5110c4`
- **When a user disagrees, allow them to link the previous comparable job** — `8469e88`
- **Fix the Part Responsibility Profile so filling it out actually clears the readiness issue** — `PENDING`
- **USB/NC export must never bypass a failed manufacturing readiness gate** — `2397510`
- **The safe export workflow must run NC VERIFY before human approval and writing the file** — `2397510`
- **Wire requireWrite through the mutating server actions** — `de230ed`
- **Do the tooling gate (item in the approved 7-task batch)** — `de230ed`

## Fixed after the walkthrough — the app could not complete its own loop

These were not on this list, because the list records promised features. These
were defects in whether the application functions end to end.

### Release was unreachable, which stranded Jobs

The `simulation` gate is `blocking` and has **no PASS branch** — correctly, since
a geometric visualisation is not verified stock removal and must never claim to
be. Release refused while any blocking gate was not PASS, so no part could ever
be released, no job could ever be raised, and the quoted-against-actual
comparison could never fire.

Readiness and release are different questions and conflating them caused this.
`aggregate()` answers "is this verified ready to run" and still answers no — that
is unchanged, and `NOT_READY_TO_RUN` is still what a part with a blocking gate
under review reports. Release answers "did a named human take responsibility for
running it anyway", so the two kinds of shortfall are now separated:

- MISSING / NOT_ATTEMPTED / FAIL on a blocking gate refuses the release. There is
  no evidence to exercise judgement over, and a click cannot substitute for
  evidence that does not exist. No override exists.
- REVIEW on a blocking gate is acknowledged **individually, by gate**, and
  recorded in the release snapshot against the person's name. Never one blanket
  accept: a single click standing for several separate engineering judgements is
  the failure the split exists to avoid. The gate is still REVIEW afterwards.

### A feature could only enter the part by accepting an AI proposal

`db.feature.create` existed in exactly one place: the accept path on
`/proposals`. The feature panel's empty state said *"add features, or accept
the proposals from the intake"* and no add control existed anywhere. So the only
route into a part's geometry was to accept something a model had proposed —
unusable for a shop wanting to type in the 40 mm bore in front of them, and
uncomfortable against principle 3, since every dimension in the system began as
an inference even though a human accepted it.

`/parts/[id]/features` is a real route now: add a feature, see what the part
has, remove one.

Underneath it, a defect that had nothing to do with the missing form.
`parametersJson` was a free record and `featureSuggestionSchema` types
parameters as `Record<string, number | string | boolean>`, so **a proposal
missing a diameter was written straight through** and every engine downstream
met `undefined` where it expected a number. `feature-input.ts` now declares what
each of the fifteen kinds actually needs, the manual form renders from it, and
the accept path validates against it — a suggestion that does not describe a
buildable feature is skipped and the audit records which and why.

Nothing is defaulted. A missing depth is a refusal, not a zero, because a
zero-depth pocket removes no material and every engine downstream would treat it
as real. An empty field is refused as absent even where zero would be a legal
value, which is the case that matters: a blank mouth-Z silently becoming 0 is a
number nobody typed. A blank tolerance is no tolerance rather than a ±0.0000
band that would fail every capability check for a reason nobody stated.

### A machinist could not record what they actually set

`Setup.gripDepth`, `gripLength`, `stockProjection`, `parallelHeight`, `machineId`
and `workholdingId` were written only by the approach generator on the Machinist
page. There was no edit form anywhere. So a machinist who planned 0.250" of grip
and actually set 0.400" had no way to say so — while the holding margin, the
jaw-clearance check, the fixture model in the simulator and the release snapshot
were all computed from the number they could not correct.

The setups page now carries a **Setup as built** form for every setup: machine,
workholding, grip depth and length, stock proud of the jaws, parallel height,
which axis the jaws close on, jaw surface, work offset and datum note.

The part that matters is provenance. `Setup.geometrySource` records PLANNED (the
generator's intent) or MEASURED (what a machinist set), with who recorded it and
when. The arithmetic downstream is identical either way and what it is entitled
to claim is not, so the caveat sits **beside the margin figure** rather than only
inside the form: *"Computed from the planned grip and projection, not a
measurement — this describes a setup nobody has confirmed building."* Existing
rows are deliberately not backfilled to PLANNED; inventing a provenance for them
would be exactly the fabrication the column exists to prevent.

A blank field stays blank. It does not fall back to the planned value and does
not become zero — the workholding engine already names an input it does not
have, and a zero would be a measurement nobody took.

### Generating an NC program made a part read as less ready

The `nc` gate was `blocking: true` when a program existed (REVIEW) and
`blocking: false` when none did — so producing a development post *increased*
the blocking count, the exact inverse of what the act means. A shop running its
own CAM has no CANVAS program and is not less ready for it, and executable NC has
its own export gates that this one does not stand in for. Non-blocking in both
branches now, with a test asserting the two branches agree.

## NEVER STARTED

### Build a Feature Specimen View: selecting a feature isolates and enlarges it, allows rotation, shows dimension lines and nominal vs measured, with GEOMETRY / FUNCTION / MEASURE / MACHINE / INSPECT / HISTORY tabs

> When user selects a feature: - isolate the feature visually - enlarge it - allow rotation - show dimension line - show nominal vs measured - show mating component if available - show tabs:   GEOMETRY   FUNCTION   MEASURE

Nothing renders a specimen view. The only trace is a `specimenMode` boolean and a SPECIMEN action in the interaction reducer with zero consumers — selecting a feature opens the ordinary side panel, and the feature detail page is a form (mating component, fit, verifiability), not an isolated rotatable feature with tabs.

`src/components/workspace/interaction.tsx:55 declares `specimenMode`; `grep -rn "specimenMode\|setSpecimen" src --include=*.tsx --include=*.ts | grep -v interaction.tsx` returns nothing. `grep -ril specimen src` matches only interaction.tsx and two docs.`

### Copilot structured mutations — the copilot should be able to propose a structured change and drive the scene, not only emit text

> 18. COPILOT STRUCTURED MUTATIONS

Built as **two channels, split by what happens if the model is wrong.**

**Scene actions** change what is on screen and nothing else — select a feature, switch context, focus an operation — so a wrong one wastes a click. They take effect immediately, and `references` is no longer a comma-joined caption.

**Proposals** change the part, so they do not take effect at all. They are written into the `AIRecommendation` queue at PROPOSED and accepted by a human on `/proposals`, which is the path every other AI suggestion already takes. The copilot gets no second, softer route to the same data — principle 3: the model may suggest, and may not certify. A test asserts the endpoint writes only a proposal and its own conversation, never part data, and never at ACCEPTED.

Every target is validated against the package the **server** built. A model can name any id; one that is not on this part is dropped rather than handed to the client as something to press — which mattered less when a reference was a caption than it does now that it is a control. Drops are reported rather than silent, so an answer never refers to a button that is not on screen. A feature proposal is held to the same field spec the hand-entry form and the accept path use, so the copilot cannot introduce a feature through a third door in a shape the engines cannot read.

The deterministic provider proposes no changes — it is a grammar parser, not a planner — but it does offer scene actions, because a context switch needs no knowledge of the part. The copilot's actions therefore work with no API key and no network, which is the state most of CANVAS runs in.

**A defect found by running it, not by a type.** `copilot-actions.ts` validated a requested context against `CONTEXTS` imported from `interaction.tsx`, which is a `"use client"` module. Under the server bundle a client module resolves to a client-reference proxy, so `CONTEXTS.includes` is not a function and the endpoint threw — after typechecking perfectly. The vocabulary moved to `lib/workspace-contexts.ts`, which has no boundary, and a test now walks `src/lib` and `src/app/api` for any import of a `"use client"` module.

`src/lib/engines/copilot-actions.ts` (new), `src/lib/workspace-contexts.ts` (new), `src/lib/ai/{provider,deterministic}.ts`, `src/app/api/copilot/route.ts`, `src/components/workspace/{copilot,interaction}.tsx`, `tests/engines/copilot-actions.test.ts` (22 tests).
### When the mating component is a bearing, allow the bearing number to be supplied by uploading a photo, not only by typing it

> Bearing number? Allow: TYPE NUMBER UPLOAD PHOTO UNKNOWN

Built, and the care it needs is not obvious from the ask. **A designation is dimensions, not a label.** `findBearing` turns 6203 into a 17 mm bore and 6208 into a 40 mm one, and `analyseMating` reasons about the fit from that. A misread stamp does not produce a wrong caption; it produces the wrong bore.

So the flow is: photograph → a model reads *characters* → CANVAS resolves them against its own catalogue → a machinist confirms one against the bearing in their hand → only then is anything stored. The reading is an AI inference and stays one (principle 3); the endpoint writes the photograph and nothing else, and a test asserts it never writes a designation.

Specifics that matter:

- The vision prompt asks for the characters as stamped and explicitly forbids guessing a common bearing number or stating dimensions. The dimensions a machinist checks against come from CANVAS's catalogue, never from the model.
- Confusable characters (`O`/`0`, `I`/`1`, `S`/`5`, `B`/`8`) are offered as **separate candidates**, never silently corrected — a correction would hide that the reading was ambiguous, and the machinist is holding the bearing. An alternative is always ranked below the reading it came from, and one that resolves to nothing in the catalogue is not offered at all.
- A designation the catalogue does not hold is storable but gets no invented dimensions.
- With no vision model connected the deterministic provider returns `connected: false` and an empty list — never a plausible guess. The photograph is still stored against the feature, so a machinist can read the stamp themselves. That is worth more than nothing, and it is what the panel says.
- `Feature.matingDesignationSource` records USER or PHOTO_CONFIRMED with the photograph it was confirmed against. Edit the value after picking a candidate and it reverts to USER and drops the evidence link — otherwise a photograph would be attached to a number it does not show.

`src/lib/engines/bearing-stamp.ts` (new), `src/lib/ai/{provider,anthropic,deterministic}.ts` (`readBearingStamp`, and a vision-capable request path), `src/app/api/features/[fid]/bearing-stamp/route.ts` (new), `src/components/{bearing-stamp,mating-designation}.tsx` (new), `prisma/schema.prisma` with both migration trees, `tests/engines/bearing-stamp.test.ts` (18 tests).
### Live Hardware Metrology Sync streaming instrument readings into feature detail records

> **Live Hardware Metrology Sync:** Bluetooth/USB/MTConnect integration streaming digital caliper, micrometer, and CMM probe readings directly into feature detail records.

Nothing was built. No Web Bluetooth, Web Serial or WebHID call exists anywhere in src (`grep -rni 'bluetooth|navigator.serial|WebHID'` returns zero hits outside prose). Measurements are keyboard-entered only — /api/measurements accepts a JSON body with a manually typed `measuredValue`. The only related artefact is src/lib/telemetry.ts, which is machine telemetry (spindle load, cycle times), not instrument readings, and is a type-only shell whose status is hard-typed `"NOT_CONNECTED"`. The refactor spec triaged this as "PHASE — bridge required" while stating "Web Bluetooth reaches BLE calipers/mics in Chromium only; it is a legitimate v1" — that v1 was never started.

``grep -rni 'bluetooth|navigator.serial|WebHID|web serial' src` returns no code hits; src/app/api/measurements/route.ts:17-26 (manual entry schema); docs/REFACTOR_SPEC.md:31`

### Hands-Free Voice Operator for logging dimensions and querying tolerances

> **Hands-Free Voice Operator:** Voice interface allowing operators wearing PPE to log dimensions and query feature tolerances without screen contact.

No trace in the code. `grep -rni 'SpeechRecognition|webkitSpeech|speechSynthesis|getUserMedia'` across src returns nothing; the only matches for "voice" are code comments about writing in a machinist's voice. The refactor spec triaged it as "PILOT ONLY — Web Speech API accuracy on a shop floor is unproven" and sketched a read-back-and-confirm loop in §3, but no pilot, no push-to-talk control and no transcript path was ever built.

``grep -rni 'SpeechRecognition|webkitSpeech|speechSynthesis' src` returns zero hits; docs/REFACTOR_SPEC.md:36 and §3`


## PARTIAL

### QUOTING as a full Phase 1 section (only NETWORK and SHOP INTELLIGENCE were scoped as shell)

> JOBS QUOTING NETWORK Build shell only in Phase 1. SHOP INTELLIGENCE Build shell only in Phase 1. SETTINGS

Built. The page's own subtitle promised that quotes "carry their assumption set… so a quote can be defended, re-run against changed rates, or compared against what the job actually cost" — and nothing in the application wrote a `Quote` or a `CostEstimate`. The Cost panel computed a live figure and discarded it on navigation, while the empty state told the user to open a Cost panel "then attach it to a quote", two controls that did not exist. `/quoting` no longer carries `shell: true`.

**A stored estimate is a snapshot.** The whole assumption set, every cost line, and the engine's own warnings are frozen with the price. A quote that cannot be defended in a customer meeting is worthless, and defending it means showing the inputs as they stood — not recomputing them today and presenting the new answer as the old promise. The price is computed server-side from the package; a price that arrives in a form is a price the caller chose, and this one goes to a customer.

**Warnings travel with the price.** The cost engine already knows which assumptions its arithmetic is not valid over. An estimate stored while one is open is stored *with* it and the quote page renders it under "Assumptions this quote does not stand on" — the shop can quote with caveats, but the caveat cannot be dismissed at the moment of storing.

**Drift, not recomputation.** When a rate moves, the quote is not wrong — it is a record of a promise made at those numbers. So the page shows *which* assumptions moved and what they were, and never folds today's figures into the stored price. Eight assumptions are watched, and a test asserts each one genuinely changes the price.

**Quoted against what the job actually cost.** Rebuilt with the same cost engine and the quote's own assumptions, substituting only what a completed job recorded — so the difference is attributable to the run rather than to a second model. What the job did not record is named as still being the quoted assumption, and a job that recorded nothing produces no comparison at all, because rebuilding from the quote's own numbers would return exactly 1.00× and call it agreement.

**Lifecycle.** DRAFT → SENT → WON / LOST / EXPIRED, all terminal. A sent quote gains no new prices and is not edited back into a draft: the number the customer holds does not change when the shop changes its mind, and a revised price is a new quote. Sending is refused without an estimate, because a quote with none prices nothing. Raising a quote is deliberately *not* gated on readiness — pricing a part CANVAS is not ready to run is ordinary shop work.

`src/lib/engines/quoting.ts` (new), `src/app/(app)/quoting/{actions.ts,page.tsx,[id]/page.tsx}`, `src/components/quoting/*`, `src/app/(app)/parts/[id]/cost/page.tsx`, `tests/engines/quoting.test.ts` (21 tests).
### JOBS as a full Phase 1 section — job outcomes recorded so they can feed the workholding and process models

> JOBS QUOTING NETWORK Build shell only in Phase 1.

Built. The section had a schema, engines and a page, and nothing in the application could write a row — so a shop saw demo data forever. The nav's `shell: true` on `/jobs` is removed, and a test now asserts the label tracks the write path in both directions.

**Release exists now.** Both the Jobs page and the home dashboard said "jobs are created from a released part revision" and nothing anywhere set a revision to RELEASED. Release lives on the readiness page and is refused while any blocking gate is unresolved — the refusal names each gate, and there is no override, because principle 2 says a click does not satisfy an engineering condition. Gates that are short but not blocking are reservations: they do not refuse the release, they are stored with it.

**The readiness picture is snapshotted at release.** What a job outcome has to answer afterwards is what the shop knew when it said run it, and readiness moves as tools, instruments and machines change. The snapshot carries every gate, not just the failures, plus the estimated cycle time.

**The lifecycle is a closed transition table.** PLANNED → SETUP → RUNNING → COMPLETE, with CANCELLED available until it is finished. A job cannot jump from PLANNED to COMPLETE: the actuals recorded against it would describe a setup and a run that never happened. COMPLETE and CANCELLED are terminal — another run is another job.

**Actuals are never seeded from estimates.** A blank field stays null and the page says which side is missing. An actual quietly inherited from the estimate would make the estimated-against-actual comparison agree with itself on every job forever.

**Outcomes are structured, not typed.** The cause comes from the taxonomy already in `network.ts`, chosen against the outcome code — a cause in somebody's own words cannot be counted across jobs, and counting across jobs is the entire reason to record one. A cause valid for a different code is refused rather than filed under OTHER, and a failure with no corrective action is refused outright.

**And it teaches, within its scope.** `job-knowledge.ts` reads outcomes back onto the setups page. Principle 11 governs it: an observation applies only where machine, workholding and material all match, a null on either side matches nothing rather than acting as a wildcard, and nothing an outcome says changes a number the engines computed. It is shown beside the recommendation, never folded into it.

`src/lib/engines/jobs.ts` (new), `src/lib/job-knowledge.ts` (new), `src/app/(app)/jobs/{actions.ts,page.tsx,[id]/page.tsx}`, `src/app/(app)/parts/[id]/release-actions.ts`, `src/components/jobs/*`, `src/components/release-panel.tsx`, `prisma/schema.prisma` with both migration trees, `tests/engines/jobs.test.ts` (29 tests).
### Manufacturing DNA: attach history to a PartRevision and show a timeline of events with provenance labels

> Create: MANUFACTURING DNA Attach history to a PartRevision. Show timeline: - initial release - bore nominal changed - soft jaws added - chatter observed - inspection passed - workholding failure corrected - process revised

Built at `/parts/[id]/history`, and the design decision is that the timeline is **derived, never authored**.

Every event the brief names already happens and is already recorded — an audit entry, an approval, a job outcome, an inspection result, a disagreement, a review-finding resolution, a release. So the timeline reads those records rather than offering somewhere to type history in. A hand-maintained timeline goes stale the moment somebody forgets and can claim an event that never happened; a derived one cannot. Every row says which record it came from, so the claim is checkable, and the engine has no database access and no model calls at all.

Provenance is per event. The actor type is read from the record that states it and is **null where the record does not** — an unrecorded actor is a missing fact, not a human by default. An `actorType` outside HUMAN/AI/SYSTEM is not carried through either.

The page also names the sources that had nothing in them, so a short history reads as "little has happened to this revision" rather than "little was checked".

**And the model has a write site now.** `/intelligence` had always said "each completed job writes an immutable snapshot — geometry, setups, tooling, feeds, workholding, measured results, cycle time, scrap and cost" and nothing ever wrote one; the only row in existence came from the seed. Completing a job writes it, including whether each setup's geometry was MEASURED or PLANNED. `costActual` stays null rather than being derived from today's rates, which would not be what the job cost and would look like it was.

`Job.createdAt` was added because nothing recorded when a job was raised — `dueDate` is a promise and `startedAt` is when it reached the machine. It is nullable and existing rows stay null: a job raised before the column existed contributes no "raised" event rather than one dated to the migration.

`src/lib/engines/dna.ts` (new), `src/app/(app)/parts/[id]/history/page.tsx` (new), `src/app/(app)/jobs/actions.ts`, `src/app/(app)/intelligence/page.tsx`, `tests/engines/dna.test.ts` (21 tests).
### Provenance deep dive — instrument, uncertainty and shop evidence

> Click provenance badge to show: source, method, operator, timestamp, instrument, uncertainty, calculation version, shop evidence

The badge now opens a panel and states all of it, but three rows read "not
recorded" for every value in the app, and that is honest rather than a
wiring gap.

INSTRUMENT and UNCERTAINTY. No `Provenanced` value in CANVAS comes from an
instrument: `measured()` has one call site and it is a units declaration.
Real instrument and uncertainty live on `Measurement.uncertainty` and
`Measurement.deviceId`, on a path that never touches `Provenanced`. Filling
these rows would mean inventing a chain of custody.

SHOP EVIDENCE. `relevantKnowledge()` scopes strictly by machine, tool and
material. There is no honest join from "General tolerance ±0.005" to a
ShopKnowledge row, and showing loosely-related rows beside a value is worse
than showing none.

CALCULATION VERSION is populated only where an engine exports a version
constant. Nothing else invents one.

Closing these means either giving `Provenanced` a link to a Measurement, or
accepting that instrument-grade provenance belongs on measurements and
removing the two rows from the panel. That is a modelling decision.

### Run It Past CANVAS should let a machinist upload an existing job package — STEP, NC program, tool list, setup file, machine, workholding — and review it

> A machinist can upload an existing job package: - STEP - NC program - tool list - setup file - machine - workholding CANVAS reviews the package.

The review workflow exists but runs only against the package CANVAS itself holds (`buildPackage`). There is no import into the review flow: no tool-list importer and no setup-file importer exist anywhere, and the page itself renders a notice saying the job-package import is not built. STEP import and NC upload exist, but as separate new-part intake and analyzer paths, not as a package a shop can hand to the review.

`src/app/(app)/parts/[id]/review/page.tsx:28 builds from `buildPackage`, and line 171 renders the notice "Importing an existing job package is not built". `grep -rn -i "tool list\|setup file" src/app src/lib` finds no importer.`

### Create structured, persisted entities for the review package — ReviewFinding, FindingSeverity, FindingEvidence, FindingResolution (the Imported* entities remain unbuilt)

> Create structured entities for: ImportedModel ImportedNCProgram ImportedToolList ImportedSetup ReviewFinding FindingSeverity FindingEvidence FindingResolution Do not make review findings only chat text.

The finding half is built. `ReviewFinding` and `FindingResolution` are Prisma models, and a finding can now be tracked and answered.

The design decision that matters: **the stored finding is not the source of truth.** The engine is re-run on every review, because a finding has to reflect the setup as it is now. What persists is what the engine cannot know — when a finding was first raised, when it stopped being raised, and what a human concluded about it.

A recorded response is bound to the **evidence digest** of the finding it answered. Change the stickout, re-run, and the digest changes: the earlier answer does not silently carry onto a different engineering condition, it reads as stale and the finding is open again. That is principle 2 surviving the trip through a database — the acknowledgement was of a specific condition, not of a title. The status vocabulary is ACKNOWLEDGED / ACTIONED / DISPUTED, with no RESOLVED, CLOSED or WAIVED, and a test asserts it: a finding goes away when the engine stops raising it and in no other way. A finding that stops being raised is marked cleared, not deleted, and appears under "No longer raised" with the dates it spanned.

This required a prerequisite fix. Finding ids were a positional counter (`finding-1`, `finding-2`), which is an identity only while nothing changes — fix the first finding and every one below it renumbers, so a response recorded against `finding-3` would silently reattach to a different finding on the next review. Findings now carry a `key` derived from the check and the setup, operation or feature it concerns.

Two guards were sharpened rather than loosened along the way. The locked-principle check on audit actors flagged the read path that carries a stored actor back out for display; instead of widening the exemption, it is now two rules — a carry-through read is allowed, and a *second* test asserts no database write anywhere in `src` takes its actor from anything but a literal, which catches exactly the laundering the first exemption would otherwise permit.

**Still unbuilt:** `ImportedModel`, `ImportedToolList` and `ImportedSetup`. Those belong to the job-package import above, not here — there is nothing yet to persist, because STEP import needs a geometry kernel and there is no setup-file parser. `ImportedNCProgram` is partly covered by `NCProgram` with `origin = UPLOADED`, which stores the original bytes, digest, encoding, line ending and detected dialect.

`prisma/schema.prisma` (ReviewFinding, FindingResolution) with both migration trees, `src/lib/review-findings.ts` (digest and vocabulary, no database), `src/lib/review-findings-store.ts`, `src/app/(app)/parts/[id]/review/finding-actions.ts`, `src/components/review/finding-response.tsx`, `src/lib/engines/review.ts` (stable keys), `tests/engines/review-findings.test.ts`.
### During guided measurement, highlight the target feature in the uploaded image and the 3D reconstruction

> Highlight the target feature in the uploaded image and 3D reconstruction.

Half built, and the half that is not is labelled rather than quietly missing — the two halves are not equally possible.

**The reconstruction half is built.** Linking a measurement to a feature now emphasises that feature in the top view, drawn from the parametric geometry CANVAS holds. Emphasis is opacity on the whole feature, never a colour: blue means *critical* in that drawing, and a highlight that changed a stroke colour would make an ordinary feature read as a critical one.

**The photograph half is not, and cannot honestly be.** The upload records which face a photo shows and what scale reference was in frame — not an origin, an orientation, or a pixels-per-inch. There is no transform from part coordinates to image pixels, so a marker on the photo would be placed by guesswork, and an operator would measure whatever it landed on. The panel says so in those words rather than leaving the absence to be inferred.

What the photo panel does do instead is stop being `photos[0]`. Every uploaded view is a labelled button, the operator picks the one they want, and the views photo-set.tsx asks for and did not get are named.

One defect found by driving it in a browser rather than by a test: linking a feature the top view cannot draw — a face, an outside profile, a chamfer — dimmed all eight drawable features to emphasise something that renders as nothing. A highlight pointing at empty space is worse than no highlight. An undrawable highlight is now ignored, the drawing is left alone, and the panel says that feature has no outline in plan.

`src/components/part-thumb.tsx` (`drawnInTopView`, `highlightFeatureId`), `src/components/reverse/guided-measurement.tsx`, `src/app/(app)/reverse-engineer/[id]/page.tsx`, `tests/engines/guided-reference.test.ts` (9 tests).
### The Feature Lens carries DETAIL / MEASURE / MAKE / VERIFY actions

> Actions: DETAIL MEASURE MAKE VERIFY

The lens states all four and MAKE now exists, but the lens does not become
clickable, which is a deviation from the literal ask.

It is `pointer-events-none` and follows the cursor. Making its cells
pressable means the machinist has to drag the cursor across the part to
reach them, passing over other geometry on the way — and what the lens is
about changes as they go. The file's own doctrine already says a form on
hover is a trap. Keyboard accelerators were the other route and collide:
`f`, `v` and `1`-`5` are bound in the workspace, and a binding whose
meaning depends on what happens to be hovered is a surprise at a machine.

So the lens carries the four as named availability, and the click-through
panel carries them as controls. If the intent was literally four buttons on
the hover surface, that is a product decision to overrule this reading.

### In-browser toolpath/stock-removal simulator must verify fixture collision

> **In-Browser Toolpath & Stock Removal Simulator:** Physics-backed cutting visualization in the `CUT` tab to verify tool engagement, retract clearance, and fixture collision.

Built, and a worse problem than the gap was fixed alongside it.

**The lie first.** `collisionChecked: true` was written on every Simulation row while no fixture was modelled at all — and that column's own schema comment says it exists "so no consumer can mistake a visualisation for a verification". The transport also said "No collisions found", which is the sentence an operator acts on. Both now report what actually ran: the flag is true only when the cutter was checked against a fixture, the row records `checksRun` and `checksNotRun`, and the transport says "Nothing hit in stock or the standing wall — the jaws were not modelled" when that is what happened.

**The fixture.** `src/lib/sim/fixture.ts` builds the jaws as two boxes in part coordinates and the simulator gained a `FIXTURE_CONTACT` collision kind. It is a parametric approximation, and it says so: jaw plates, screws, handles and the vise body below the jaws are not in it, and a part nested into machined soft jaws sits lower than it assumes.

**The datum that was missing.** Nothing recorded which axis the jaws close on, so there was no way to know which two faces the vise grips. `Setup.jawAxis` is a new nullable column with no default, and the setups page has a control to record it. Defaulting it would put the modelled vise on the wrong two faces half the time — a collision check that clears exactly the setup that would crash. Where it is absent, `buildFixture` returns null and names the missing number, the simulator reports `fixtureChecked: false`, and nothing claims a check that did not run.

**A declared gap closed as a side effect.** The pre-flight review listed "Whether a flagged lateral rapid actually crosses the jaw — needs the jaw footprint as geometry" under what it could not check. With the axis recorded there is now a footprint, so a rapid well clear of the vise is no longer flagged and one that passes over a jaw is named as such. Setups without an axis are named individually in `checksSkipped` rather than the whole check being declared skipped.

`src/lib/sim/fixture.ts` (new), `src/lib/sim/stock-removal.ts`, `src/lib/engines/review.ts`, `src/components/workspace/{workspace,sim-transport}.tsx`, `src/components/setup-geometry.tsx`, `src/app/(app)/parts/[id]/setups/setup-actions.ts`, `prisma/schema.prisma` with both migration trees, `tests/engines/fixture-collision.test.ts` (20 tests).
### All text and status indicators must pass WCAG AAA contrast

> **Accessibility & Contrast:** All text and status indicators must pass WCAG AAA contrast standards.

Most of it now does, and the audit says exactly what does not.

Fixed: `--c-blue-dim` was a second definition of the standard blue ink and
measured 3.69–4.40:1 — below AA, at 65 call sites; muted and green were
lifted to clear 7:1 on every ground; the 3D datum chips and operation
balloons are opaque with darkened semantic inks at 7.0:1 on white; the
audit reads all eight grounds instead of five.

Still short, and it is not a tuning problem. `--canvas-red` #f0554a has a
relative luminance of 0.2552, so its ceiling is **6.10:1 against pure
black** — no ground can carry it to 7:1. `--canvas-blue` #4d97ff would need
a ground darker than about #020407. Reaching AAA on either means giving up
the saturation that makes red read as blocking and blue read as the
restrained precision blue the visual language locks. That is a change to
CLAUDE.md's Visual language section, so it is a decision rather than an
implementation.

Two ways forward, both honest:
(A) pastel status inks that clear 7:1, losing saturation;
(B) keep the saturated inks as graphical carriers — rings, dots, rules —
    and put the WORDS in `--canvas-text`, which is already 14.65:1.

Also still open under (A): the tinted washes. `bg-precision/10` over card
composites to #132841 and the lifted blue on it is 5.11:1; `bg-risk/15`
gives 4.28:1. 38 sites. (B) resolves them for free.

`tests/engines/contrast.test.ts` carries both inks in a named exception
table with their measured ratio and the reason, and fails if either drifts
or quietly reaches AAA without being promoted — so CI states the shortfall
rather than reporting green over a palette that is not AAA.

### Shop-Floor Machinist Mode — probing routines

> **Shop-Floor Machinist Mode (Role-Based UI):** A touch-optimized, high-contrast tablet view focusing on setup photos and probing routines

Setup photographs are built. Probing is not, and it is the harder half.

A probing routine is executable machine motion — a Renishaw or Haas macro
that drives a spindle-mounted probe at a surface. Emitting one means the
same chain executable NC goes through: post, verify, gate, human approval.
It cannot be a text box that prints G-code, and CANVAS holds no probe data
today: no probe in the tool crib vocabulary, no stylus length or ruby
diameter, no probing cycle in the CAM engine, and no record of whether the
machine has a probe at all.

The honest first step is the shop inventory — does this machine have a
probe, which one, what stylus — which is a metrology-device question, not a
toolpath one.

### View Environment must expose real functional controls for section-view fill and annotation visibility

> - annotation visibility ... - selected-feature contrast - section-view fill

**This entry was stale.** It was built and tested in an earlier pass and the list was never updated — found by re-checking the code before starting work on it rather than trusting the entry.

What is actually there: `sectionFillColor` drives the hatch in **both** section renderers (SectionSketch and FaceSection — wiring one and not the other would leave a control that works on bores and does nothing on faces), `sectionLineMode` drives the cut boundary through `sectionStroke`, with OFF dropping the boundary entirely rather than making it faint, and MEDIUM anchored to reproduce the widths the drawing already used. Annotation visibility is `annotationsVisible`, a boolean rather than an OFF member on `AnnotationSize` — a scale of zero is a sentinel that silently collapses any consumer that forgets to check it — with an On/Off control in the drawer and both on-model annotations (datum letters and measurement balloons) respecting it.

Tests in `tests/engines/view-preferences.test.ts` cover all of it, including that the section fill cannot repaint the locked datum and dimension blue.

### NC optimizer findings should include WORKHOLDING_LOAD_DIRECTION_REVIEW

> 9. Findings should include: AIR_CUTTING LOW_ENGAGEMENT HIGH_ENGAGEMENT CORNER_LOAD_SPIKE EXCESSIVE_RETRACT SLOW_LINKING_MOVE TOOL_REACH_REVIEW WORKHOLDING_LOAD_DIRECTION_REVIEW SEQUENCING_OPPORTUNITY UNKNOWN_CONTEXT

TOOL_REACH_REVIEW and SEQUENCING_OPPORTUNITY are now built. Reach compares each tool's deepest cutting segment against the crib record's stickout, sharing one rule (`reachesDepth` in `domain/shop.ts`) with the CAM engine rather than re-deriving it; a tool with no crib entry, or a crib entry with stickout and flute length at zero, reports INSUFFICIENT_DATA and names the missing measurement instead of guessing one. Sequencing reads M6 tool changes only, and prices nothing (`seconds: 0`) because no tool-change time is recorded anywhere — it reports the redundant loads and lets the machinist decide.

Building reach first required fixing the parser: a bare `T` word is a preselect, and the changer acts on M6, but `parse.ts` was stamping every subsequent segment with the newly-commanded tool. A `T1 M6 ... G1 Z-0.5 ... T2 ... G1 Z-2.0` program attributed the deep cut to T2 while T1 was still in the spindle — which would have made the reach finding blame the wrong tool. `commandedTool` and `tool` are now separate, and a program that cuts with no M6 at all carries a warning saying the commanded T word is being taken as the tool in the spindle.

WORKHOLDING_LOAD_DIRECTION_REVIEW is deliberately not built, and says so rather than being silently absent: the check needs a cutting-force vector and a jaw axis, and CANVAS records neither — the force model returns a magnitude, and no workholding record carries a clamping direction. It is declared in the analysis's new `checksSkipped` list, which the analyzer panel renders above the findings, so an operator reading a clean report can see which check did not run and why.

`src/lib/nc/analyze.ts` (reach and sequencing blocks, `checksSkipped`), `src/lib/domain/shop.ts:206` `reachesDepth`, `src/lib/nc/parse.ts` `spindleTool()`, `tests/engines/nc-findings.test.ts` (14 tests, including the preselect regression).

### The Run It Past CANVAS flow should let the user upload a tool list alongside the NC program

> 7. Design the UI flow: RUN IT PAST CANVAS → Upload NC / STEP / tool list / setup → Backplot → Cycle Time Analysis → ...

Built. The analyzer takes an optional CSV or tab-separated tool list beside the program, and reads tool number, description, diameter, flute count, flute length and stickout from a header row.

Four things it deliberately does not do, because each would be worse than the gap it closes:

- It does not create crib records. A CAM tool list describes one job's intended tooling, not the shop's record of what it owns and has measured. Entries are context for that one analysis and are discarded with it.
- It does not supply a chipload window, because no CAM export carries one. A tool known only from a list therefore gets geometry — a diameter for engagement, a stickout for reach — and no feed proposal. Inventing a window would put a feed in front of an operator with nothing behind it.
- It does not sniff units. The operator states inch or millimetre, and an attached list without that is refused: a 6 mm cutter read as 6 inch is a scrapped part, and no header convention separates the two.
- It does not read columns by position. Headers are matched whole against a synonym list; a header it cannot read is a refusal quoting the header it saw, and a column no synonym covers is reported as unread rather than dropped.

The crib wins where both have a record. The tool-mapping gate now has three answers rather than two: PASS for crib records, REVIEW for tools known only from the list — saying in the gate text that no feed proposal is coming for them — and INSUFFICIENT_DATA where a tool is in neither, which outranks the other two per principle 1.

This also exposed the reach check gating on stickout and flute length together: a list commonly carries one and not the other, and a 0.900″ stickout against a 1.500″ cut is a reach problem whether or not the flute length is known. Each figure is now checked on its own, the finding names the half that did not run, and a value from the list is attributed to the list rather than to the crib.

`src/lib/nc/tool-list.ts` (new), `src/app/api/parts/[id]/nc-analyze/route.ts`, `src/lib/nc/audit-gates.ts`, `src/lib/nc/analyze.ts`, `src/components/nc-analyzer.tsx`, `tests/engines/tool-list.test.ts` (16 tests).
