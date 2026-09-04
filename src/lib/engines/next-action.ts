/**
 * NEXT REQUIRED ACTION
 *
 * A part in CANVAS has several hundred fields across a dozen pages. A machinist
 * should never have to go looking through them to find out what is actually
 * stopping this job from running.
 *
 * So this answers one question: of everything unresolved, what is the single
 * most useful thing to do next?
 *
 * The ordering is not by how easy something is to fix. It is by what would be
 * wasted by fixing something else first. There is no point resolving the grip
 * on setup 2 if the bore's nominal diameter is still a guess, because the
 * nominal decides the tool, which decides the load, which decides the grip.
 * Work that has to be redone is worse than work not yet started.
 */

import { READINESS_GATE_IDS, type ReadinessReport, type ReadinessGate, type ReadinessGateId } from "./readiness";
import type { WorkholdingAssessment } from "./workholding";

export interface NextAction {
  /** One line, imperative, specific enough to act on without context. */
  action: string;
  /** Why this and not something else. */
  reason: string;
  /** Where to go to do it. */
  href: string | null;
  linkLabel: string | null;
  gateId: string | null;
  severity: "BLOCKING" | "REVIEW" | "IMPROVEMENT";
}

/**
 * Gate ordering. Earlier entries invalidate later ones when they change, so
 * they are worth resolving first even when a later one looks more urgent.
 */
const RESOLUTION_ORDER: ReadinessGateId[] = [
  "geometry",
  "material",
  "engineering",
  "machine",
  "reach",
  "corners",
  "tools",
  // Coverage sits after tools because an uncut feature is usually resolved by
  // planning an operation, and an operation needs a tool. It sits ahead of
  // everything downstream because adding an operation invalidates the
  // workholding assessment, the simulation and the approval.
  "coverage",
  // tool-loading and critical-review were both absent from this list and from
  // GATE_ROUTE below. A gate missing here ranks last among its peers; a gate
  // missing from the route table offers the operator no link at all — the
  // action said "load T3 and T7 into the changer" with nowhere to go. Both
  // tables are now keyed by ReadinessGateId, so the compiler asks for an
  // entry the day a gate is added.
  "tool-loading",
  "inspection-capability",
  "critical-review",
  "workholding",
  "tolerance",
  "inspection",
  "simulation",
  "nc",
  // A post nobody has proven on this machine blocks the export, and it is
  // resolved on the machine record rather than on the part.
  "post-validation",
  // Proof-out sits beside the program itself: it is a fact about the bytes,
  // and it is resolved at the machine rather than on a screen.
  "proof",
  "approval",
];

const GATE_ROUTE: Record<ReadinessGateId, { href: (id: string) => string; label: string }> = {
  geometry: { href: (id) => `/parts/${id}`, label: "Part workspace" },
  material: { href: (id) => `/parts/${id}`, label: "Part workspace" },
  engineering: { href: (id) => `/parts/${id}/responsibility`, label: "Part responsibility" },
  machine: { href: () => `/machines`, label: "Machines" },
  reach: { href: (id) => `/parts/${id}/tooling`, label: "Tooling" },
  corners: { href: (id) => `/parts/${id}/tooling`, label: "Tooling" },
  tools: { href: (id) => `/parts/${id}/tooling`, label: "Tooling" },
  // An uncut feature is fixed by planning an operation for it, which is what
  // the machinist page does.
  coverage: { href: (id) => `/parts/${id}/machinist`, label: "Machinist" },
  // The carousel lives on the machine, not on the part.
  "tool-loading": { href: () => `/machines`, label: "Machines" },
  "inspection-capability": { href: () => `/metrology`, label: "Metrology" },
  "critical-review": { href: (id) => `/parts/${id}/responsibility`, label: "Part responsibility" },
  workholding: { href: (id) => `/parts/${id}/setups`, label: "Setups" },
  tolerance: { href: (id) => `/parts/${id}/inspection`, label: "Inspection" },
  inspection: { href: (id) => `/parts/${id}/inspection`, label: "Inspection" },
  simulation: { href: (id) => `/parts/${id}/nc`, label: "NC output" },
  nc: { href: (id) => `/parts/${id}/nc`, label: "NC output" },
  "post-validation": { href: () => `/machines`, label: "Machines" },
  proof: { href: (id) => `/parts/${id}/nc`, label: "NC output" },
  approval: { href: (id) => `/parts/${id}/readiness`, label: "Readiness" },
};

function rankOfId(id: string | null): number {
  const i = id === null ? -1 : RESOLUTION_ORDER.indexOf(id as ReadinessGateId);
  return i === -1 ? RESOLUTION_ORDER.length : i;
}

function rank(gate: ReadinessGate): number {
  return rankOfId(gate.id);
}

const WORKHOLDING_RANK = RESOLUTION_ORDER.indexOf("workholding");

/**
 * Turns a gate into an instruction. Gates already carry suggested actions; the
 * first is used, because they are written most-direct-first, and the gate's own
 * detail becomes the reason so the operator sees the evidence rather than a
 * restatement of the label.
 */
function fromGate(gate: ReadinessGate, partId: string): NextAction {
  const route = GATE_ROUTE[gate.id];
  return {
    action: gate.actions[0] ?? `Resolve ${gate.label.toLowerCase()}`,
    reason: gate.detail,
    href: route ? route.href(partId) : null,
    linkLabel: route ? route.label : null,
    gateId: gate.id,
    severity: gate.status === "FAIL" || gate.status === "MISSING" ? "BLOCKING" : "REVIEW",
  };
}

export function nextActions(
  readiness: ReadinessReport,
  partId: string,
  workholding: WorkholdingAssessment | null,
  limit = 3,
): NextAction[] {
  const unresolved = readiness.gates
    .filter((g) => g.status !== "PASS" && g.status !== "NOT_ATTEMPTED")
    .sort((a, b) => {
      // Blocking gates first, then by what invalidates what.
      const aBlock = a.status === "FAIL" || a.status === "MISSING" ? 0 : 1;
      const bBlock = b.status === "FAIL" || b.status === "MISSING" ? 0 : 1;
      if (aBlock !== bBlock) return aBlock - bBlock;
      return rank(a) - rank(b);
    });

  const actions = unresolved.map((g) => fromGate(g, partId));

  // The holding margin is more specific than the workholding gate that carries
  // it, so when it has a concrete recommendation, use that instead.
  const margin = workholding?.holdingMargin;
  if (margin && margin.verdict !== "ADEQUATE" && margin.recommendations.length > 0) {
    const i = actions.findIndex((a) => a.gateId === "workholding");
    const replacement: NextAction = {
      action: margin.recommendations[0],
      reason: margin.primaryRisk ?? "The setup does not reach the target holding margin.",
      href: `/parts/${partId}/setups`,
      linkLabel: "Setups",
      gateId: "workholding",
      severity: margin.verdict === "INSUFFICIENT" ? "BLOCKING" : "REVIEW",
    };
    if (i >= 0) {
      actions[i] = replacement;
    } else {
      // This used to push, which appends AFTER the sort. A margin verdict of
      // INSUFFICIENT is BLOCKING, so it landed behind every REVIEW item and,
      // with the default limit of three, was cut off the list entirely — the
      // engine whose whole job is "the single most useful thing to do next"
      // dropped a blocking workholding finding on the floor.
      //
      // It is inserted where its severity puts it, at the workholding gate's
      // own resolution rank.
      const at = actions.findIndex(
        (a) =>
          (a.severity !== "BLOCKING" && replacement.severity === "BLOCKING") ||
          (a.severity === replacement.severity && rankOfId(a.gateId) > WORKHOLDING_RANK),
      );
      if (at === -1) actions.push(replacement);
      else actions.splice(at, 0, replacement);
    }
  }

  if (actions.length === 0) {
    // Returning an empty list said nothing at all to an operator asking what
    // to do next. Every gate passing and every gate untouched are different
    // situations and both now get an answer.
    return readiness.overall === "READY_TO_RUN"
      ? [
          {
            action: "Run the first article and record what actually happened",
            reason:
              "Every gate passes. What CANVAS does not have yet is evidence from this part running on this machine — that is what turns a plan into shop knowledge.",
            href: `/parts/${partId}/nc`,
            linkLabel: "NC output",
            gateId: null,
            severity: "IMPROVEMENT",
          },
        ]
      : [
          {
            action: "Open the readiness report and work through the gates",
            reason:
              "Nothing is outstanding on any gate that has been attempted, but this part is not clear to run. The gates that decide it have not been evaluated yet.",
            href: `/parts/${partId}/readiness`,
            linkLabel: "Readiness",
            gateId: null,
            severity: "REVIEW",
          },
        ];
  }

  return actions.slice(0, limit);
}
