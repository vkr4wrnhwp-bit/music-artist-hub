import type { GuideFlowDef } from "./engine";

/**
 * CANVAS GUIDE — flow definitions.
 *
 * One authored place for every flow. Steps complete from PROJECT STATE, so a
 * user who does the work manually (or arrives with it done) sees the truth,
 * not a stale checklist. Branching is the `applies` predicate reading the
 * same context.
 *
 * The MAKE_A_PART flow is the familiar CAM backbone mapped onto CANVAS:
 *
 *   CREATE/IMPORT → STOCK → SETUP/WORKHOLDING → OPERATIONS/TOOLPATHS →
 *   SIMULATE → VERIFY → APPROVE → EXPORT
 *
 * i.e. PART → HOLD → CUT → VERIFY → DELIVER.
 *
 * NOT IMPLEMENTED, NOT FAKED: there is no sketching in CANVAS today, so
 * DRAW_FROM_SCRATCH is not a flow (it would coach controls that do not
 * exist); there is no turning, so the turn flows are absent. When those
 * capabilities land, their flows are authored here.
 */

export const MAKE_A_PART: GuideFlowDef = {
  id: "MAKE_A_PART",
  title: "Make a part",
  steps: [
    {
      id: "features",
      title: "Give the part geometry",
      body: "CANVAS plans from features — holes, pockets, faces — not from a picture. Import a STEP file, describe the part, or accept the recognizer's proposals.",
      why: "Every downstream engine (workholding, toolpaths, inspection) reasons over features. A part with no features has nothing to plan, hold, cut or verify.",
      camHint: "This is your model geometry — what you would select chains and faces from in other CAM systems.",
      href: (ctx) => (ctx.pendingProposals > 0 ? `/parts/${ctx.partId}/proposals` : `/parts/${ctx.partId}`),
      done: (ctx) => ctx.featureCount > 0,
    },
    {
      id: "proposals",
      title: "Review the recognizer's proposals",
      body: "Recognized features are proposals, not geometry. Review each one and accept or reject it — nothing becomes the part until a named human says so.",
      why: "The recognizer's coordinates are exact but its classifications are heuristic. Accepting is the human decision that turns a suggestion into geometry the plan will cut.",
      href: (ctx) => `/parts/${ctx.partId}/proposals`,
      done: (ctx) => ctx.pendingProposals === 0,
      applies: (ctx) => ctx.pendingProposals > 0,
    },
    {
      id: "stock",
      title: "Define stock",
      body: "Enter what will actually be in the vise. The finished envelope is shown as reference — the allowance on top of it is your machining decision.",
      why: "Everything downstream plans from stock: workholding grips it, toolpaths start from its surfaces, cost counts it. Stock smaller than the finished part is refused because it cannot make the part.",
      camHint: "Stock setup — the same job it does in any CAM system's setup dialog.",
      recommended: "Envelope plus facing and edge allowance, in a size you actually stock.",
      href: (ctx) => `/parts/${ctx.partId}`,
      uiTarget: "define-stock",
      done: (ctx) => ctx.hasStock,
    },
    {
      id: "machine",
      title: "Confirm the machine",
      body: "CANVAS validates travel, spindle limits and posts against a real machine record — not a generic assumption.",
      why: "A toolpath that exceeds the machine's travels or spindle range is scrap waiting to happen. The machine record is what makes those checks possible.",
      href: () => `/machines`,
      done: (ctx) => ctx.hasMachine,
    },
    {
      id: "setup",
      title: "Create the setup and pick an approach",
      body: "The machinist screen scores complete approaches — setups, workholding, operation order — with the same engines that generate the toolpaths. Approving one writes the plan.",
      why: "Two machinists plan the same part differently, both defensibly. Comparing whole approaches beats assembling operations one at a time, and the risk numbers come from the workholding engine, not a habit.",
      camHint: "Setup + operation list in one decision — like accepting a full setup sheet rather than building op-by-op.",
      href: (ctx) => `/parts/${ctx.partId}/machinist`,
      uiTarget: "approve-approach",
      done: (ctx) => ctx.setupCount > 0,
    },
    {
      id: "workholding",
      title: "Resolve workholding",
      body: "The holding assessment must have enough evidence to call the setup safe — grip, projection, clamp force, positive stop. Soft jaws are one honest way to get there.",
      why: "A part that moves in the vise scraps itself and can hurt somebody. The holding model states its margin and its confidence; when it says REVIEW, the evidence is thin, not the part wrong.",
      href: (ctx) => `/parts/${ctx.partId}/setups`,
      done: (ctx) => ctx.workholdingAssessed,
      applies: (ctx) => ctx.setupCount > 0,
    },
    {
      id: "toolpaths",
      title: "Generate toolpaths",
      body: "Toolpaths come from the deterministic CAM engine — arithmetic over your features, tools and machine. An operation the engine cannot plan says so instead of guessing.",
      why: "An LLM never emits machine motion in CANVAS. The engine refuses what it cannot do safely (wrong tool, depth beyond flute, unfittable corner) — a refusal is information, not a failure.",
      camHint: "Tool → Geometry → Levels → Cutting → Linking live inside each operation's parameters here.",
      href: (ctx) => `/parts/${ctx.partId}`,
      done: (ctx) => ctx.toolpathCount > 0,
      applies: (ctx) => ctx.setupCount > 0,
    },
    {
      id: "simulate",
      title: "Simulate stock removal",
      body: "Watch the CUT view remove material move by move. It checks retract clearance and holder contact geometrically — label says GEOMETRIC SIMULATION because forces are not modelled.",
      why: "A collision found in simulation costs nothing. Recording a watched run is evidence the readiness gates read; skipping it leaves that gate honest and unresolved.",
      href: (ctx) => `/parts/${ctx.partId}`,
      uiTarget: "context-cut",
      done: (ctx) => ctx.simulationRecorded,
      applies: (ctx) => ctx.toolpathCount > 0,
    },
    {
      id: "verify",
      title: "Verify — datums, inspection, capability",
      body: "The VERIFY step asks one question: can your instruments actually prove the part is right? A ±0.0005\" bore is not verified by calipers, no matter how carefully they are read.",
      why: "Inspection capability is a property of the instruments the shop owns. It cannot be cleared by confirmation — the gate moves when the instrument does.",
      href: (ctx) => `/parts/${ctx.partId}/readiness`,
      done: (ctx) => !ctx.blockingGates.some((g) => /inspection|metrology/i.test(g.label)),
    },
    {
      id: "gates",
      title: "Clear the readiness gates",
      body: "Readiness is the worst unresolved required gate — never a percentage. Each failing gate names the evidence that would move it.",
      why: "Averaging would let a part with no inspection plan read as 90% ready. The worst gate is the honest answer to \"can I cut this yet\".",
      href: (ctx) => `/parts/${ctx.partId}/readiness`,
      done: (ctx) => ctx.blockingGates.length === 0,
      blockedBy: (ctx) =>
        ctx.blockingGates.length > 0
          ? {
              label: ctx.blockingGates[0].label,
              detail: ctx.blockingGates[0].detail,
              href: ctx.nextAction?.href ?? null,
            }
          : null,
    },
    {
      id: "deliver",
      title: "Deliver — post, review, approve, export",
      body: "Generate the program, read the verification report, and sign off. Export stays locked until every required gate passes — that is the point of the gates.",
      why: "The export mint re-checks the gates server-side at the moment of export. A program generated under a passing gate stops being exportable the moment a gate fails again.",
      camHint: "Post processing and NC output — the same final mile as any CAM system, with the gate check made explicit.",
      href: (ctx) => `/parts/${ctx.partId}/nc`,
      done: (ctx) => ctx.ncProgramExists && ctx.blockingGates.length === 0,
      applies: (ctx) => !ctx.training,
    },
  ],
};

/**
 * TURN_A_SHAFT — the same backbone spoken in the lathe's language, over the
 * turning workspace. Steps complete from the turning package state (the same
 * assembly the export mint gates on), mapped into GuideContext by the lathe
 * page: featureCount = profile segments, setupCount = workholding selected,
 * workholdingAssessed = grip evidence recorded, toolpathCount = engine-ok
 * toolpaths, blockingGates = the turning worst-gate readiness.
 */
export const TURN_A_SHAFT: GuideFlowDef = {
  id: "TURN_A_SHAFT",
  title: "Turn a shaft",
  steps: [
    {
      id: "profile",
      title: "Define the rotational profile",
      body: "A turned part is a profile revolved about the centerline: diameters and Z positions, front to back. Import it, plan it, or measure it on the bench with the reverse-engineering flow.",
      why: "X0 is the centerline and Z0 the datum face — every toolpath, hold analysis and inspection reads this one model. Diameters are diameters, never radii.",
      camHint: "This is the 2D profile you would sketch in a lathe CAM system — CANVAS keeps it as the single source of geometry.",
      href: (ctx) => `/lathe/${ctx.partId}`,
      done: (ctx) => ctx.featureCount > 0,
    },
    {
      id: "stock",
      title: "Confirm bar stock",
      body: "Stock is a bar: diameter and length, including facing and part-off allowance. A reverse-engineered part carries a SUGGESTED bar until you confirm what is actually on the rack.",
      why: "Bar economics (parts per bar, remnant, utilization) and every roughing pass start from this number. Stock that cannot make the part is refused, not shrunk.",
      href: (ctx) => `/lathe/${ctx.partId}`,
      done: (ctx) => ctx.hasStock,
    },
    {
      id: "lathe",
      title: "Pick the lathe",
      body: "Swing, between-centers length, spindle range and turret stations come from a real machine record.",
      why: "The CSS clamp, the RPM checks and the post all validate against this record — a generic lathe validates nothing.",
      href: () => `/lathe`,
      done: (ctx) => ctx.hasMachine,
    },
    {
      id: "hold",
      title: "Hold it — chuck, grip, evidence",
      body: "Pick the workholding and record the real numbers: grip length, stickout, the chuck's clamp force from the hydraulic setting. Soft jaws have their own drawer search and bore-in-place recipe.",
      why: "The grip analysis refuses to invent a clamp force. UNKNOWN is a verdict — the gate moves when the measurement is recorded, not when a warning is clicked away.",
      camHint: "Chuck setup — but the clamp force field is evidence, not a default.",
      href: (ctx) => `/lathe/${ctx.partId}`,
      done: (ctx) => ctx.setupCount > 0 && ctx.workholdingAssessed,
      blockedBy: (ctx) => {
        const g = ctx.blockingGates.find((x) => /grip|chuck|hold|workholding/i.test(x.label));
        return g ? { label: g.label, detail: g.detail, href: `/lathe/${ctx.partId}` } : null;
      },
    },
    {
      id: "toolpaths",
      title: "Generate the turning toolpaths",
      body: "Facing, roughing, finishing, grooving, threading, part-off — all from the deterministic turn engines. CSS is clamped by G50; a thread's feed IS its pitch and is never retimed.",
      why: "An LLM never emits machine motion. An operation the engine cannot plan (a groove narrower than the insert, a missing pitch) refuses by name instead of guessing.",
      href: (ctx) => `/lathe/${ctx.partId}`,
      done: (ctx) => ctx.toolpathCount > 0,
      applies: (ctx) => ctx.featureCount > 0,
    },
    {
      id: "watch",
      title: "Watch the stock come off",
      body: "The 3D playback replays the toolpaths against the radius envelope — scrub it, step the stock states operation by operation. It is a kinematic replay, labelled DEVELOPMENT: not a collision check.",
      why: "Seeing the remnant, the part-off moment and each operation's stock state catches planning mistakes the tables hide. Knowing what the view is NOT is part of reading it.",
      href: (ctx) => `/lathe/${ctx.partId}`,
      done: (ctx) => ctx.toolpathCount > 0, // watching leaves no record — the step teaches, the next gates
      applies: (ctx) => ctx.toolpathCount > 0,
    },
    {
      id: "verify",
      title: "Verify — can your instruments prove it?",
      body: "The bearing journal is +0.0000/\u22120.0005\" — a one-sided 0.0005\" band, and the gauge-maker's rule wants the instrument consuming no more than 10% of it. The seeded ±0.0002\" micrometer consumes 40%: what it reports is largely its own noise, and the gate fails until a tenths-reading instrument is on file.",
      why: "Inspection capability is a property of the instruments the shop owns. It cannot be cleared by confirmation, on a lathe or anywhere else.",
      href: (ctx) => `/lathe/${ctx.partId}`,
      done: (ctx) => !ctx.blockingGates.some((g) => /inspection|metrology/i.test(g.label)),
    },
    {
      id: "gates",
      title: "Clear the turning gates",
      body: "Turning readiness is the worst unresolved required gate — chuck grip, stickout, part-off, RPM limits, tooling, inspection. Each failing gate names the evidence that moves it.",
      why: "A shaft with nine passing gates and an unrecorded clamp force is not 90% ready; it is not ready.",
      href: (ctx) => `/lathe/${ctx.partId}`,
      done: (ctx) => ctx.blockingGates.length === 0,
      blockedBy: (ctx) =>
        ctx.blockingGates.length > 0
          ? { label: ctx.blockingGates[0].label, detail: ctx.blockingGates[0].detail, href: `/lathe/${ctx.partId}` }
          : null,
    },
    {
      id: "deliver",
      title: "Deliver — post, approve, export",
      body: "The development post emits the program (refusing an unclamped G96 outright), approval is a named human act, and the export mint re-runs every turning gate server-side. The file keeps its NOT FOR PRODUCTION USE header.",
      why: "An export authorization is permission to take bytes out of CANVAS, not a certification of the post. The gate check at the mint is what makes the button honest.",
      href: (ctx) => `/lathe/${ctx.partId}`,
      done: (ctx) => ctx.ncProgramExists && ctx.blockingGates.length === 0,
      applies: (ctx) => !ctx.training,
    },
  ],
};

/**
 * REVERSE_A_PART — the mill RE measurement session, guided. Steps complete
 * from the reconstruction plan the session page already builds (photos on
 * file, datums established, tasks measured, inferred nominals ruled on) —
 * the guide reads ctx.re, keeps no copy of the truth, and satisfies
 * nothing: a measurement exists when the instrument said so, not when a
 * card advanced.
 */
export const REVERSE_A_PART: GuideFlowDef = {
  id: "REVERSE_A_PART",
  title: "Reverse engineer a part",
  steps: [
    {
      id: "photos",
      title: "Photograph all six views",
      body: "Top, bottom, front, back, left, right — before anything is measured. The photo set is the record of what the part looked like when it arrived, wear and all.",
      why: "A dimension without its context photo is a number arguing with memory. When a reading looks wrong next week, the photograph is what settles it.",
      href: (ctx) => `/reverse-engineer/${ctx.re?.sessionId ?? ""}`,
      done: (ctx) => (ctx.re ? ctx.re.missingViews === 0 : false),
      applies: (ctx) => Boolean(ctx.re),
    },
    {
      id: "datums",
      title: "Establish the datum frame",
      body: "CANVAS proposes A/B/C with reasons across design, manufacturing and inspection systems. Accepting a datum is a human act — you know which face actually seats in service; the feature list does not.",
      why: "Every measurement after this is referenced to these. Re-measure a datum later and everything downstream needs re-checking — pick them first, deliberately.",
      href: (ctx) => `/reverse-engineer/${ctx.re?.sessionId ?? ""}`,
      done: (ctx) => (ctx.re ? ctx.re.datumsEstablished >= ctx.re.datumsRequired : false),
      applies: (ctx) => Boolean(ctx.re),
    },
    {
      id: "measure",
      title: "Measure in the order that constrains fastest",
      body: "The plan asks for dimensions datums-first, each naming the instrument to use and what the reading unlocks. Record what the instrument says — worn is worn.",
      why: "Measurement order is not cosmetic: a reading taken from an unestablished reference is a guess wearing a decimal point.",
      href: (ctx) => `/reverse-engineer/${ctx.re?.sessionId ?? ""}`,
      done: (ctx) => (ctx.re ? ctx.re.measurementsRequired > 0 && ctx.re.measurementsComplete >= ctx.re.measurementsRequired : false),
      applies: (ctx) => Boolean(ctx.re),
      blockedBy: (ctx) =>
        ctx.re && ctx.re.datumsEstablished < ctx.re.datumsRequired
          ? {
              label: "Datums not established",
              detail: `${ctx.re.datumsEstablished} of ${ctx.re.datumsRequired} datums accepted — measurements taken now have no home.`,
              href: `/reverse-engineer/${ctx.re.sessionId}`,
            }
          : null,
    },
    {
      id: "nominals",
      title: "Rule on the suggested nominals",
      body: "Readings that match a published standard wait for your decision: accept the nominal or keep the measurement. CANVAS never changes a dimension for you.",
      why: "1.5744\" on a worn seat probably means 40 mm — but 'probably' is a human's call to make, recorded with a name on it.",
      href: (ctx) => `/reverse-engineer/${ctx.re?.sessionId ?? ""}`,
      done: (ctx) => (ctx.re ? ctx.re.inferredAwaitingReview === 0 && ctx.re.measurementsComplete > 0 : false),
      applies: (ctx) => Boolean(ctx.re),
    },
    {
      id: "handoff",
      title: "Open the part workspace",
      body: "The reconstructed model now lives where every other part lives — features, workholding, toolpaths, gates. Reverse engineering ends where manufacturing begins.",
      why: "The measurement session is scaffolding. The part workspace is where the reconstruction gets held, cut and verified like anything else.",
      href: (ctx) => `/parts/${ctx.partId}`,
      done: (ctx) => ctx.featureCount > 0 && (ctx.re ? ctx.re.inferredAwaitingReview === 0 : false),
      applies: (ctx) => Boolean(ctx.re),
    },
  ],
};

/**
 * RUN_IT_PAST — the NC audit + optimizer, guided. Steps complete from
 * database facts (stored uploads, stored optimized revisions) and the
 * part's own context — the guide clears nothing: the audit gates and the
 * export mint hold their own lines regardless of what this card shows.
 */
export const RUN_IT_PAST: GuideFlowDef = {
  id: "RUN_IT_PAST",
  title: "Run a program past CANVAS",
  steps: [
    {
      id: "upload",
      title: "Upload the program",
      body: "Any Fanuc/Haas-style 3-axis program from your CAM system. CANVAS stores the original immutably — hash, filename, bytes — and every later derivation references that stored copy, never re-sent bytes.",
      why: "An audit without a fixed subject proves nothing. The stored hash is what makes 'nothing else changed' checkable instead of promised.",
      camHint: "Try the Load demo button first — it is deliberately imperfect: savings, a protected bore, and a review-only region.",
      href: (ctx) => `/parts/${ctx.partId}/nc-analyzer`,
      done: (ctx) => (ctx.nca?.uploads ?? 0) > 0,
      applies: (ctx) => Boolean(ctx.nca),
    },
    {
      id: "context",
      title: "Read the audit gates, add context",
      body: "The gate panel says what this analysis can honestly claim. No stock bound: air cutting cannot be proven. Unmapped tools: no load verdicts. Each gate names the evidence that moves it.",
      why: "Deeper context unlocks deeper claims — and the stages are each their worst gate, never a percentage. Stock alignment stays REVIEW by construction: CANVAS cannot see the vise.",
      href: (ctx) => `/parts/${ctx.partId}/nc-analyzer`,
      done: (ctx) => ctx.hasStock && ctx.hasMachine,
      applies: (ctx) => Boolean(ctx.nca),
    },
    {
      id: "findings",
      title: "Work the findings with Show Me",
      body: "Air cutting, retracts, rubbing feeds, engagement spikes, protected finish passes. Show Me frames the scene and the source block together — accept or reject each proposal individually; there is no accept-all.",
      why: "A finding is a place to look, not a change to make. Reductions are load control and claim zero savings; protected regions are never proposed in either direction.",
      href: (ctx) => `/parts/${ctx.partId}/nc-analyzer`,
      done: (ctx) => (ctx.nca?.optimized ?? 0) > 0,
      applies: (ctx) => Boolean(ctx.nca),
    },
    {
      id: "derived",
      title: "Generate and review the derived program",
      body: "Accepted proposals are re-derived server-side and applied as feed words only; the masked geometry diff must be byte-clean and the round-trip parse identical, or nothing is stored. The derived revision keeps its lineage to the stored original.",
      why: "The diff is the invariant — 'geometry never changes' is a mechanical check, not a promise. The derived program then faces the same pre-flight and mint as any other.",
      href: (ctx) => `/parts/${ctx.partId}/nc`,
      done: (ctx) => (ctx.nca?.optimized ?? 0) > 0 && ctx.blockingGates.length === 0,
      applies: (ctx) => Boolean(ctx.nca) && !ctx.training,
    },
  ],
};

export const GUIDE_FLOWS: Record<string, GuideFlowDef> = {
  MAKE_A_PART,
  TURN_A_SHAFT,
  REVERSE_A_PART,
  RUN_IT_PAST,
};

/** Flows that exist as concepts but whose functionality does not: named so
 * the UI can say DEVELOPMENT instead of pretending. */
export const DEVELOPMENT_FLOWS = [
  { id: "DRAW_FROM_SCRATCH", reason: "CANVAS has no sketching tools yet." },
];
