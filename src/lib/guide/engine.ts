/**
 * CANVAS GUIDE — the engine.
 *
 * A deliberately small, PURE state machine. It reads a snapshot of real
 * project state (GuideContext) and a session (which step is active, what the
 * user has visited); it returns what to show. It has no write access to any
 * manufacturing table, which is not a convention but the architecture:
 * nothing in this module can clear a gate, apply a mutation, alter
 * provenance, or unlock NC export, because nothing in this module can write
 * anything at all. Guide progress and manufacturing readiness are separate
 * systems that happen to look at the same part.
 *
 * BACK ONE STEP is a pop of the session's actual visited-step history —
 * never `order - 1`, never browser history. Branches are followed backwards
 * exactly as the user travelled them. Popping history changes which card is
 * shown; it cannot change project state, by construction.
 *
 * Step completion is a property of PROJECT STATE (`done(ctx)`), not of
 * clicking "next": a step the user completed manually, or that was already
 * satisfied before the flow started, reads as complete. This is the rule
 * that stops Guide completion from ever being mistaken for evidence — the
 * evidence is in the project, and the Guide only reports it.
 */

export type GuideMode = "OFF" | "ASSIST" | "TEACH";

export const GUIDE_MODES: GuideMode[] = ["OFF", "ASSIST", "TEACH"];

export type ExperienceProfile =
  | "NEW_TO_CNC"
  | "MACHINIST_NEW_TO_CAM"
  | "CAM_USER_NEW_TO_CANVAS"
  | "FUSION_USER"
  | "MASTERCAM_USER"
  | "EXPERIENCED";

export const PROFILE_LABEL: Record<ExperienceProfile, string> = {
  NEW_TO_CNC: "New to CNC and CAM",
  MACHINIST_NEW_TO_CAM: "Machinist — new to CAM",
  CAM_USER_NEW_TO_CANVAS: "CAM user — new to CANVAS",
  FUSION_USER: "Fusion user",
  MASTERCAM_USER: "Mastercam user",
  EXPERIENCED: "Experienced CAM programmer",
};

/** Profile → default mode. Configures depth, never restricts capability. */
export const PROFILE_DEFAULT_MODE: Record<ExperienceProfile, GuideMode> = {
  NEW_TO_CNC: "TEACH",
  MACHINIST_NEW_TO_CAM: "TEACH",
  CAM_USER_NEW_TO_CANVAS: "ASSIST",
  FUSION_USER: "ASSIST",
  MASTERCAM_USER: "ASSIST",
  EXPERIENCED: "ASSIST",
};

/**
 * The real project state a flow branches on. Assembled server-side from the
 * same package the workspace renders — the Guide never keeps its own copy of
 * manufacturing truth.
 */
export interface GuideContext {
  partId: string;
  hasStock: boolean;
  hasMachine: boolean;
  hasMaterial: boolean;
  featureCount: number;
  pendingProposals: number;
  setupCount: number;
  workholdingAssessed: boolean;
  toolpathCount: number;
  simulationRecorded: boolean;
  approvalExists: boolean;
  ncProgramExists: boolean;
  /** Blocking readiness gates, verbatim from the readiness engine. */
  blockingGates: { id: string; label: string; detail: string }[];
  /** Head of the real nextActions() queue, when one exists. */
  nextAction: { action: string; href: string | null } | null;
  training: boolean;
  /** NC analyzer snapshot — present only on Run It Past CANVAS pages. */
  nca?: {
    uploads: number;
    optimized: number;
  };
  /** Reverse-engineering session snapshot — present only on RE pages. */
  re?: {
    sessionId: string;
    photosOnFile: number;
    missingViews: number;
    datumsEstablished: number;
    datumsRequired: number;
    measurementsComplete: number;
    measurementsRequired: number;
    inferredAwaitingReview: number;
  };
}

export type StepStatus = "NOT_STARTED" | "ACTIVE" | "COMPLETED" | "SKIPPED" | "DEFERRED" | "BLOCKED";

export interface GuideStepDef {
  id: string;
  title: string;
  /** One or two sentences, machinist voice. The lecture goes under WHY. */
  body: string;
  why: string;
  /** Familiar-CAM terminology hint, shown when the preference is on. */
  camHint?: string;
  recommended?: string;
  /** Route the step's work happens on (SHOW ME / DO IT WITH ME navigate here). */
  href?: (ctx: GuideContext) => string;
  /** data-guide-target id of the real control, for the coach mark. */
  uiTarget?: string;
  /** Completion is read from project state — never from a click. */
  done: (ctx: GuideContext) => boolean;
  /**
   * A real manufacturing blocker that must take priority over the lesson.
   * Returning a gate makes the step BLOCKED and the card teaches the gate.
   * The Guide can only report it; resolving it takes real evidence.
   */
  blockedBy?: (ctx: GuideContext) => { label: string; detail: string; href: string | null } | null;
  /** Branch: skip this step entirely in the current context. */
  applies?: (ctx: GuideContext) => boolean;
}

export interface GuideFlowDef {
  id: string;
  title: string;
  steps: GuideStepDef[];
}

export interface GuideSession {
  flowId: string;
  /** The actual visited path, in order. BACK ONE STEP pops this. */
  history: string[];
  /** Steps the user explicitly skipped/deferred (they stay incomplete). */
  skipped: string[];
  active: string | null;
  startedAtIso: string;
  pausedAtIso: string | null;
}

/* ------------------------------------------------------------------ */
/* Session operations — every one returns a NEW session object.        */
/* ------------------------------------------------------------------ */

export function startSession(flow: GuideFlowDef, ctx: GuideContext, nowIso: string): GuideSession {
  const first = firstIncomplete(flow, ctx, []);
  return {
    flowId: flow.id,
    history: first ? [first] : [],
    skipped: [],
    active: first,
    startedAtIso: nowIso,
    pausedAtIso: null,
  };
}

/** The next applicable, incomplete, unskipped step after the active one. */
export function advance(flow: GuideFlowDef, session: GuideSession, ctx: GuideContext): GuideSession {
  const next = firstIncomplete(flow, ctx, session.skipped, session.active);
  if (!next) return { ...session, active: null };
  return { ...session, active: next, history: [...session.history, next] };
}

/**
 * BACK ONE STEP — pop the visited history. Pure: no project state is read,
 * none can be written. Disabled (returns the same session) at the first step.
 */
export function back(session: GuideSession): GuideSession {
  if (session.history.length < 2) return session;
  const history = session.history.slice(0, -1);
  return { ...session, history, active: history[history.length - 1] };
}

export function canGoBack(session: GuideSession): boolean {
  return session.history.length >= 2;
}

export function skip(flow: GuideFlowDef, session: GuideSession, ctx: GuideContext): GuideSession {
  if (!session.active) return session;
  const skipped = session.skipped.includes(session.active) ? session.skipped : [...session.skipped, session.active];
  return advance(flow, { ...session, skipped }, ctx);
}

export function pause(session: GuideSession, nowIso: string): GuideSession {
  return { ...session, pausedAtIso: nowIso };
}

export function resume(session: GuideSession): GuideSession {
  return { ...session, pausedAtIso: null };
}

/* ------------------------------------------------------------------ */
/* Reading the machine                                                 */
/* ------------------------------------------------------------------ */

export interface StepView {
  step: GuideStepDef;
  index: number;
  ofTotal: number;
  status: StepStatus;
  blocked: { label: string; detail: string; href: string | null } | null;
}

/** The card to render for the active step, with blocker priority applied. */
export function currentStep(flow: GuideFlowDef, session: GuideSession, ctx: GuideContext): StepView | null {
  if (!session.active) return null;
  const applicable = applicableSteps(flow, ctx);
  const step = applicable.find((s) => s.id === session.active) ?? flow.steps.find((s) => s.id === session.active);
  if (!step) return null;
  const blocked = step.blockedBy?.(ctx) ?? null;
  const status: StepStatus = blocked ? "BLOCKED" : step.done(ctx) ? "COMPLETED" : "ACTIVE";
  return {
    step,
    index: Math.max(0, applicable.findIndex((s) => s.id === step.id)) + 1,
    ofTotal: applicable.length,
    status,
    blocked,
  };
}

export function flowProgress(flow: GuideFlowDef, session: GuideSession, ctx: GuideContext) {
  const applicable = applicableSteps(flow, ctx);
  return {
    completed: applicable.filter((s) => s.done(ctx)).length,
    skipped: session.skipped.filter((id) => applicable.some((s) => s.id === id && !s.done(ctx))).length,
    total: applicable.length,
    finished: applicable.every((s) => s.done(ctx) || session.skipped.includes(s.id)),
  };
}

function applicableSteps(flow: GuideFlowDef, ctx: GuideContext): GuideStepDef[] {
  return flow.steps.filter((s) => s.applies?.(ctx) ?? true);
}

function firstIncomplete(
  flow: GuideFlowDef,
  ctx: GuideContext,
  skipped: string[],
  after?: string | null,
): string | null {
  const steps = applicableSteps(flow, ctx);
  const start = after ? steps.findIndex((s) => s.id === after) + 1 : 0;
  for (let i = Math.max(0, start); i < steps.length; i++) {
    if (!steps[i].done(ctx) && !skipped.includes(steps[i].id)) return steps[i].id;
  }
  // Wrap: an earlier step may have become incomplete (state changed) or the
  // user may re-enter after skipping ahead.
  for (let i = 0; i < steps.length; i++) {
    if (!steps[i].done(ctx) && !skipped.includes(steps[i].id)) return steps[i].id;
  }
  return null;
}
