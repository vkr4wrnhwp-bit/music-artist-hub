import { aggregate, type ReadinessGate } from "./readiness";
import { JOB_OUTCOMES, OUTCOME_CAUSES, type JobOutcomeCode } from "./network";

/**
 * JOBS — what actually happened, recorded so it can teach
 *
 * A job outcome is the most valuable data a shop generates and the one most
 * often lost. The Jobs page said so and then showed demo rows: nothing in the
 * application could create a Job or a JobOutcome, and the entry point it named
 * — "jobs are created from a released part revision" — did not exist either,
 * because nothing anywhere set a revision to RELEASED.
 *
 * This file is the deterministic half: what may be released, what a job may do
 * next, and what a finished job is allowed to claim. No model calls, no
 * defaults substituted for numbers nobody recorded.
 */

/* ------------------------------------------------------------------ */
/* Release                                                             */
/* ------------------------------------------------------------------ */

export interface ReleaseGate {
  id: string;
  label: string;
  status: string;
  detail: string;
}

export interface ReleaseVerdict {
  /** True when nothing hard-refuses. Acknowledgements are still required. */
  ok: boolean;
  /**
   * Blocking gates with no evidence behind them — MISSING, NOT_ATTEMPTED or
   * FAIL. These refuse the release outright and cannot be acknowledged away.
   */
  blockers: ReleaseGate[];
  /**
   * Blocking gates at REVIEW: the evidence exists and a judgement is required.
   * Each must be acknowledged INDIVIDUALLY before the release goes through,
   * and the acknowledgement is recorded against the gate.
   */
  acknowledgeable: ReleaseGate[];
  /** Non-blocking gates short of PASS. Recorded with the release, not gating it. */
  reservations: { id: string; label: string; status: string }[];
}

/**
 * Whether a revision may be released to the floor.
 *
 * Releasing is not the same question as readiness, and conflating them is what
 * made this unreachable. `aggregate()` answers "is this verified ready to run",
 * and for a blocking gate at REVIEW the honest answer is no — the simulation
 * gate, for instance, has no PASS branch at all, because a geometric
 * visualisation is not verified stock removal and must never claim to be.
 * That answer does not change here and readiness still reports it.
 *
 * Release answers a different question: did a named human take responsibility
 * for running it anyway. So the two kinds of shortfall are separated:
 *
 *   - MISSING / NOT_ATTEMPTED / FAIL on a blocking gate is a refusal. There is
 *     no evidence to exercise judgement over, and principle 2 says a click
 *     does not substitute for evidence that does not exist. No override.
 *   - REVIEW on a blocking gate is where the evidence exists and a machinist's
 *     judgement is the missing input. That is acknowledged per gate, by name,
 *     and recorded — principle 11: the override records evidence and clears
 *     nothing. The gate is still REVIEW after the release, and readiness still
 *     reports the part as not ready to run.
 */
export function evaluateRelease(gates: ReadinessGate[]): ReleaseVerdict {
  const g = (x: ReadinessGate): ReleaseGate => ({ id: x.id, label: x.label, status: x.status, detail: x.detail });
  const blockers = gates.filter((x) => x.blocking && x.status !== "PASS" && x.status !== "REVIEW").map(g);
  const acknowledgeable = gates.filter((x) => x.blocking && x.status === "REVIEW").map(g);
  const reservations = gates
    .filter((x) => !x.blocking && x.status !== "PASS")
    .map((x) => ({ id: x.id, label: x.label, status: x.status }));
  return { ok: blockers.length === 0, blockers, acknowledgeable, reservations };
}

/**
 * Whether the acknowledgements supplied cover every gate that needs one.
 *
 * Every id must be present. A blanket "I accept the above" would make one
 * click stand for several separate engineering judgements, which is the shape
 * of exactly the problem this whole split exists to avoid.
 */
export function acknowledgementsSatisfied(verdict: ReleaseVerdict, acknowledged: string[]): boolean {
  if (!verdict.ok) return false;
  const given = new Set(acknowledged);
  return verdict.acknowledgeable.every((a) => given.has(a.id));
}

/** The readiness picture at the moment of release, stored with the revision. */
export function releaseSnapshot(gates: ReadinessGate[], acknowledged: string[] = []) {
  const { overall, blockingCount } = aggregate(gates);
  return {
    overall,
    blockingCount,
    gates: gates.map((g) => ({
      id: g.id,
      label: g.label,
      status: g.status,
      blocking: g.blocking,
      // Which blocking REVIEW gates a human took responsibility for. The gate
      // itself is unchanged — this records who decided, not a new status.
      acknowledged: acknowledged.includes(g.id),
    })),
  };
}

/* ------------------------------------------------------------------ */
/* Job lifecycle                                                       */
/* ------------------------------------------------------------------ */

export const JOB_STATUSES = ["PLANNED", "SETUP", "RUNNING", "COMPLETE", "CANCELLED"] as const;
export type JobStatus = (typeof JOB_STATUSES)[number];

export const JOB_STATUS_LABEL: Record<JobStatus, string> = {
  PLANNED: "Planned",
  SETUP: "In setup",
  RUNNING: "Running",
  COMPLETE: "Complete",
  CANCELLED: "Cancelled",
};

/**
 * What a job may do next. A closed table rather than a free status field: a
 * job that jumps from PLANNED to COMPLETE has no setup and no run behind it,
 * and the actuals recorded against it would be describing nothing.
 *
 * COMPLETE and CANCELLED are terminal. A finished job is the shop's record of
 * what happened and is not reopened — a further run is a further job.
 */
export const NEXT_STATUS: Record<JobStatus, JobStatus[]> = {
  PLANNED: ["SETUP", "CANCELLED"],
  SETUP: ["RUNNING", "CANCELLED"],
  RUNNING: ["COMPLETE", "CANCELLED"],
  COMPLETE: [],
  CANCELLED: [],
};

export function canTransition(from: string, to: string): boolean {
  if (!(JOB_STATUSES as readonly string[]).includes(from)) return false;
  if (!(JOB_STATUSES as readonly string[]).includes(to)) return false;
  return NEXT_STATUS[from as JobStatus].includes(to as JobStatus);
}

/* ------------------------------------------------------------------ */
/* Estimated against actual                                            */
/* ------------------------------------------------------------------ */

export interface CycleComparison {
  estimatedMinutes: number;
  actualMinutes: number;
  /** actual / estimated. Above 1 means the job took longer than planned. */
  ratio: number;
  /** Signed difference in minutes, actual minus estimated. */
  deltaMinutes: number;
}

/**
 * The comparison the Jobs page exists to make.
 *
 * Returns null when either side is missing, and the caller says which is
 * missing. A comparison against a substituted estimate is a number that looks
 * like feedback and is not.
 */
export function compareCycle(estimatedMinutes: number | null, actualMinutes: number | null): CycleComparison | null {
  if (estimatedMinutes == null || actualMinutes == null) return null;
  if (estimatedMinutes <= 0 || actualMinutes < 0) return null;
  return {
    estimatedMinutes,
    actualMinutes,
    ratio: actualMinutes / estimatedMinutes,
    deltaMinutes: actualMinutes - estimatedMinutes,
  };
}

/* ------------------------------------------------------------------ */
/* Outcome validation                                                  */
/* ------------------------------------------------------------------ */

export interface OutcomeDraft {
  code: string;
  cause: string;
  correctiveAction: string;
  partsAffected: number;
  operationId: string | null;
  toolNumber: number | null;
  notes: string;
}

export type OutcomeRefusal = { field: string; reason: string };

/**
 * What a recorded outcome must carry to be worth having.
 *
 * The cause comes from the taxonomy in network.ts, not from free text: an
 * outcome whose cause is somebody's sentence cannot be counted across jobs,
 * and counting across jobs is the entire reason to record it. A cause that is
 * not in the list for its code is refused rather than filed under OTHER —
 * a mislabelled outcome is worse than a rejected one, because it will be
 * counted as something it is not.
 */
export function validateOutcome(draft: OutcomeDraft): OutcomeRefusal[] {
  const refusals: OutcomeRefusal[] = [];
  if (!(JOB_OUTCOMES as readonly string[]).includes(draft.code)) {
    refusals.push({ field: "code", reason: `"${draft.code}" is not a recorded outcome.` });
    return refusals;
  }
  const code = draft.code as JobOutcomeCode;
  const causes = OUTCOME_CAUSES[code];
  if (!causes.includes(draft.cause)) {
    refusals.push({
      field: "cause",
      reason: `"${draft.cause}" is not one of the causes recorded for ${code}. Pick one, or record the outcome as OTHER.`,
    });
  }
  if (code !== "SUCCESS") {
    if (draft.correctiveAction.trim().length < 10) {
      refusals.push({
        field: "correctiveAction",
        reason: "Say what was done about it. A failure with no corrective action teaches the next person nothing.",
      });
    }
    if (!Number.isInteger(draft.partsAffected) || draft.partsAffected < 0) {
      refusals.push({ field: "partsAffected", reason: "Parts affected must be a whole number, zero or more." });
    }
  }
  return refusals;
}

/* ------------------------------------------------------------------ */
/* What an outcome is allowed to teach                                 */
/* ------------------------------------------------------------------ */

export interface OutcomeScope {
  machine: string | null;
  material: string | null;
  workholding: string | null;
  toolNumber: number | null;
}

/**
 * Principle 11: shop knowledge is scoped to the shop, machine, tool and
 * material it was observed on, and is never promoted into a published
 * engineering fact.
 *
 * So an outcome teaches only where every part of its scope matches. One shop
 * chattering a 6061 pocket on a worn machine is not evidence about 17-4 on
 * somebody else's. `null` on either side does not match: an unrecorded
 * machine is not a wildcard, it is a missing fact.
 */
export function outcomeApplies(observed: OutcomeScope, here: OutcomeScope): boolean {
  const same = (a: string | number | null, b: string | number | null) => a != null && b != null && a === b;
  if (!same(observed.machine, here.machine)) return false;
  if (!same(observed.material, here.material)) return false;
  if (!same(observed.workholding, here.workholding)) return false;
  return true;
}
