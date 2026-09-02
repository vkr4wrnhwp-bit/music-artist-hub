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

## NEVER STARTED

### Build a Feature Specimen View: selecting a feature isolates and enlarges it, allows rotation, shows dimension lines and nominal vs measured, with GEOMETRY / FUNCTION / MEASURE / MACHINE / INSPECT / HISTORY tabs

> When user selects a feature: - isolate the feature visually - enlarge it - allow rotation - show dimension line - show nominal vs measured - show mating component if available - show tabs:   GEOMETRY   FUNCTION   MEASURE

Nothing renders a specimen view. The only trace is a `specimenMode` boolean and a SPECIMEN action in the interaction reducer with zero consumers — selecting a feature opens the ordinary side panel, and the feature detail page is a form (mating component, fit, verifiability), not an isolated rotatable feature with tabs.

`src/components/workspace/interaction.tsx:55 declares `specimenMode`; `grep -rn "specimenMode\|setSpecimen" src --include=*.tsx --include=*.ts | grep -v interaction.tsx` returns nothing. `grep -ril specimen src` matches only interaction.tsx and two docs.`

### Copilot structured mutations — the copilot should be able to propose a structured change and drive the scene, not only emit text

> 18. COPILOT STRUCTURED MUTATIONS

The copilot's reply contract is `{reply, references, needs}` — text plus two string lists. There is no proposed-mutation channel, nothing applies a copilot suggestion, and the client renders `references` as a comma-joined line of plain text rather than something that selects geometry or changes context. Structured proposals exist elsewhere (AIRecommendation → accept on /proposals) but the copilot cannot write one.

`src/lib/ai/provider.ts:47-53 (copilotReplySchema); src/app/api/copilot/route.ts only persists ConversationMessage rows; src/components/workspace/copilot.tsx:126 renders references as `m.references.map(r => r.label).join(", ")`.`

### When the mating component is a bearing, allow the bearing number to be supplied by uploading a photo, not only by typing it

> Bearing number? Allow: TYPE NUMBER UPLOAD PHOTO UNKNOWN

The mating panel offers a free-text "Designation, if known" field and UNKNOWN as a mating component, but there is no photo upload on the feature page at all — a machinist holding a bearing whose stamp is easier to photograph than to read has no path in.

`src/app/(app)/parts/[id]/features/[fid]/page.tsx:244-287 (radio row + text input only); `grep -n -i "photo\|upload\|file" src/app/(app)/parts/[id]/features/[fid]/page.tsx` returns nothing.`


## DEFERRED BY ME

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

The Quoting page renders, but nothing in the codebase ever writes a Quote or a CostEstimate — not the app, not the seed. The page is a read-only view over two tables that are always empty, and it tells the user to "Open a part's Cost panel to produce one, then attach it to a quote" while the part Cost page performs no writes at all and there is no attach-to-quote UI. Unlike Network and Shop intelligence, Quoting is not marked `shell: true` in the nav, so it presents as a working section.

``grep -rn 'quote.create|costEstimate.create|db.quote\.' src --include=*.ts --include=*.tsx` -> only the read at src/app/(app)/quoting/page.tsx:11; costEstimate only at src/app/(app)/quoting/page.tsx:16; `grep -n 'quote|costEstimate' prisma/seed.ts` -> nothing; src/app/(app)/parts/[id]/cost/page.tsx has no "use server" `

### JOBS as a full Phase 1 section — job outcomes recorded so they can feed the workholding and process models

> JOBS QUOTING NETWORK Build shell only in Phase 1.

Jobs is read-only over demo-seed data. No code path creates a Job or a JobOutcome outside prisma/seed.ts, so a real shop can never record what held, what chattered or what scrapped — which is what the page's own copy says the section is for. The stated entry point does not exist either: both the Jobs page and the home dashboard say "Jobs are created from a released part revision", but nothing anywhere sets a revision's status to RELEASED. The home page's CANVAS-intelligence insights that derive from job outcomes are therefore also unreachable for a real shop.

``grep -rn 'db.job\.|job.create|jobOutcome.create' src` -> only reads at src/app/(app)/jobs/page.tsx:9 and src/app/(app)/page.tsx:18; db.job.create exists only at prisma/seed.ts:648 and db.jobOutcome.create at prisma/seed.ts:665; `grep -rn 'RELEASED' src` -> only two StatusChip comparisons (src/app/(app)/parts/[id]/page`

### Manufacturing DNA: attach history to a PartRevision and show a timeline of events (initial release, bore nominal changed, soft jaws added, chatter observed, inspection passed, workholding failure corrected, process revised) with provenance labels

> Create: MANUFACTURING DNA Attach history to a PartRevision. Show timeline: - initial release - bore nominal changed - soft jaws added - chatter observed - inspection passed - workholding failure corrected - process revis

The `ManufacturingDNA` model exists and is read in one place, but it is keyed to `Part` (not `PartRevision`), has no event/timeline shape, carries no provenance labels, and has no write site anywhere in `src/` — the only row in existence is created by the seed. The UI is a four-column table (Part / Rev / Actual cost / Recorded) on /intelligence, not a timeline.

`prisma/schema.prisma:935-950 (`partId`, `snapshotJson`, no event type, no provenance); only write is prisma/seed.ts:677; only read is src/app/(app)/intelligence/page.tsx:22 rendered as a table at line 72. `grep -rn "manufacturingDNA" src/app src/lib src/components` returns one hit.`

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

### Create structured, persisted entities for the review package — ImportedModel, ImportedNCProgram, ImportedToolList, ImportedSetup, ReviewFinding, FindingSeverity, FindingEvidence, FindingResolution

> Create structured entities for: ImportedModel ImportedNCProgram ImportedToolList ImportedSetup ReviewFinding FindingSeverity FindingEvidence FindingResolution Do not make review findings only chat text.

`ReviewFinding`, `FindingEvidence` and `Severity` exist as TypeScript interfaces only — findings are recomputed on every page load and never persisted, so a finding cannot be tracked, assigned or closed. `FindingResolution` has no trace at all: there is no way to resolve or acknowledge a finding. None of ImportedModel / ImportedToolList / ImportedSetup exist as models (only NCProgram with origin UPLOADED covers part of ImportedNCProgram).

`src/lib/engines/review.ts:35-63 (TS interfaces, no Prisma model); `grep -rn "FindingResolution\|ImportedModel\|ImportedToolList\|ImportedSetup" src prisma docs` returns nothing; prisma/schema.prisma model list has no ReviewFinding.`

### During guided measurement, highlight the target feature in the uploaded image and the 3D reconstruction

> Highlight the target feature in the uploaded image and 3D reconstruction.

The Reference panel always shows `photos[0]` — the first uploaded photo — regardless of which measurement is being requested, with no highlight, marker or crop on the target feature and no 3D reconstruction beside it. The view labels captured at upload (TOP/BOTTOM/FRONT/…) are never used to pick the right image, even though photo-set.tsx's own comment says they exist for exactly that purpose.

`src/components/reverse/guided-measurement.tsx:220-221 render `photos[0].url` / `photos[0].view` unconditionally; src/components/reverse/photo-set.tsx:6-10 states views are labelled "so the guided measurement step can show the operator the right image".`

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

Stock removal, rapid-into-stock and holder-vs-stock contact were built; fixture collision was not. The engine states it itself: "The fixture is not modelled in the CUT view yet; collision checks cover stock and holder-vs-stock only. Vise collision belongs to the HOLD geometry integration." The two `CollisionEvent` kinds are RAPID_INTO_STOCK and HOLDER_CONTACT only — there is no vise/jaw/fixture geometry in the sim at all (`grep -n 'fixture|vise' src/components/viewport/sim-view.tsx` returns nothing). Worse, the header comment claims the result "is listed as unchecked", but nothing lists it: the run action writes `collisionChecked: true` on every Simulation row, and the schema comment says that flag "exists so no consumer can mistake a visualisation for a verification". The NC pre-flight's `simulation` item then passes on that run.

`src/lib/sim/stock-removal.ts:28-30 and the CollisionEvent union at :61-64; src/app/(app)/parts/[id]/page.tsx:164 sets `collisionChecked: true`; `grep -n 'unchecked' src/lib/sim/stock-removal.ts` hits only the comment, never a result field`

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

### Shop-Floor Machinist Mode focused on setup photos and probing routines

> **Shop-Floor Machinist Mode (Role-Based UI):** A touch-optimized, high-contrast tablet view focusing on setup photos, tool projection, probing routines, and digital sign-offs.

Two of the four named focuses landed (tool projection/stickout at :270 and :306, digital sign-off at :375-421, 48px touch targets). The other two did not. Setup photos: the tablet page renders no image at all — `grep -ni 'img|Image|asset|photo'` over the file returns nothing — even though `Asset.kind` already carries a PHOTO value in the schema. Probing routines: section 3 shows generic Z0/parallels advice and states outright "A stored probing routine with per-feature expected values does not exist for this setup"; there is no probing-routine model anywhere (schema has only two `probe Boolean` capability flags on machines).

``grep -ni 'img|Image|asset|photo' 'src/app/(app)/parts/[id]/tablet/page.tsx'` returns nothing; src/app/(app)/parts/[id]/tablet/page.tsx:343; prisma/schema.prisma has no probing-routine model (`grep -ni probe` hits only lines 157 and 1482, both capability booleans)`

### View Environment must expose real functional controls for section-view fill and annotation visibility

> - annotation visibility ... - selected-feature contrast - section-view fill

`sectionFillColor` and `sectionLineMode` are declared on the ViewEnvironment interface and given defaults, but nothing reads them — no renderer, no drawer control — which is exactly the failure the same brief prohibits ('It must NOT merely update a label, button state, local variable, or inactive UI control'). There is also no 3D section view for them to act on: the display modes are Shaded / Wireframe / Ghost, and the 2D section sketch panel draws with its own fixed hatch and CSS tokens. Annotation visibility is likewise absent — the drawer offers annotation SIZE (Compact/Standard/Large) with no off state, unlike datum lines which do have an OFF mode.

`src/lib/view-environment.ts:59 `sectionFillColor: string;` and :75 `sectionLineMode: LineMode;`; `grep -rn "sectionFillColor\|sectionLineMode" src/ --include=*.ts --include=*.tsx` returns only those declarations plus the two default assignments (:90, :112) — zero consumers. Drawer colour list is Background/Floor/Grid/S`

### NC optimizer findings should include TOOL_REACH_REVIEW, WORKHOLDING_LOAD_DIRECTION_REVIEW and SEQUENCING_OPPORTUNITY

> 9. Findings should include: AIR_CUTTING LOW_ENGAGEMENT HIGH_ENGAGEMENT CORNER_LOAD_SPIKE EXCESSIVE_RETRACT SLOW_LINKING_MOVE TOOL_REACH_REVIEW WORKHOLDING_LOAD_DIRECTION_REVIEW SEQUENCING_OPPORTUNITY UNKNOWN_CONTEXT

Four of the ten kinds exist as findings (AIR_CUTTING, EXCESSIVE_RETRACT, SLOW_LINKING_MOVE, UNKNOWN_CONTEXT); low/high engagement and corner spikes are covered in substance by the load bands and REDUCE proposals. But three have no implementation anywhere: TOOL_REACH_REVIEW (the analyzer never compares programmed cut depth against the crib tool's flute length or stickout, although the CAM engine does exactly that at engine.ts:743), WORKHOLDING_LOAD_DIRECTION_REVIEW (no cut-direction-vs-holding check runs on an uploaded program), and SEQUENCING_OPPORTUNITY (the sequencing engine only ever runs on CANVAS-planned operations, never on a parsed NC file). The plan document still lists all ten as the intended set, so this was scoped and then not built.

`src/lib/nc/analyze.ts:28 `kind: "AIR_CUTTING" | "EXCESSIVE_RETRACT" | "SLOW_LINKING_MOVE" | "UNKNOWN_CONTEXT";`. `grep -rn "TOOL_REACH_REVIEW\|WORKHOLDING_LOAD_DIRECTION_REVIEW\|SEQUENCING_OPPORTUNITY" src/` returns nothing. docs/LOAD_AWARE_NC_OPTIMIZER.md:141-150 and :101 still promise them ("Load-direction-vs-holding`

### The Run It Past CANVAS flow should let the user upload a tool list alongside the NC program

> 7. Design the UI flow: RUN IT PAST CANVAS → Upload NC / STEP / tool list / setup → Backplot → Cycle Time Analysis → ...

The NC program upload, backplot, cycle-time analysis, load map, proposals, original-vs-optimized, review and gated export all landed. The tool-list upload did not: the analyzer accepts only a program file, and tool context is resolved solely by matching T numbers against the shop's existing crib records. A program whose tools are not already in the crib gets no load verdict and no proposals, and the audit gate tells the operator to go create the tool records by hand instead of attaching the tool list they already have from their CAM system. The optimizer's own design doc still describes this as part of the flow.

`src/components/nc-analyzer.tsx:161 `accept=".nc,.txt,.tap,.ngc,.prg"` is the only file input; `grep -rni "tool list\|toolList\|import tools\|csv" src/app/api src/components` returns nothing. Tools come from `getTools(user.organizationId)` at src/app/api/parts/[id]/nc-analyze/route.ts:39. Unmatched tools land in the too`
