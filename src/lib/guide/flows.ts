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

export const GUIDE_FLOWS: Record<string, GuideFlowDef> = {
  MAKE_A_PART,
};

/** Flows that exist as concepts but whose functionality does not: named so
 * the UI can say DEVELOPMENT instead of pretending. */
export const DEVELOPMENT_FLOWS = [
  { id: "DRAW_FROM_SCRATCH", reason: "CANVAS has no sketching tools yet." },
  { id: "CREATE_TURN_SETUP", reason: "Turning is not implemented." },
  { id: "REVERSE_ENGINEER_GUIDE", reason: "The RE measurement session exists; its guided flow is not authored yet." },
];
