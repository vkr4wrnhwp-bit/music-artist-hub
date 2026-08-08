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

import type { ReadinessReport, ReadinessGate } from "./readiness";
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
const RESOLUTION_ORDER = [
  "geometry",
  "material",
  "engineering",
  "machine",
  "reach",
  "corners",
  "tools",
  "inspection-capability",
  "workholding",
  "tolerance",
  "inspection",
  "simulation",
  "nc",
  "approval",
];

const GATE_ROUTE: Record<string, { href: (id: string) => string; label: string }> = {
  geometry: { href: (id) => `/parts/${id}`, label: "Part workspace" },
  material: { href: (id) => `/parts/${id}`, label: "Part workspace" },
  engineering: { href: (id) => `/parts/${id}/responsibility`, label: "Part responsibility" },
  machine: { href: () => `/machines`, label: "Machines" },
  reach: { href: (id) => `/parts/${id}/tooling`, label: "Tooling" },
  corners: { href: (id) => `/parts/${id}/tooling`, label: "Tooling" },
  tools: { href: (id) => `/parts/${id}/tooling`, label: "Tooling" },
  "inspection-capability": { href: () => `/metrology`, label: "Metrology" },
  workholding: { href: (id) => `/parts/${id}/setups`, label: "Setups" },
  tolerance: { href: (id) => `/parts/${id}/inspection`, label: "Inspection" },
  inspection: { href: (id) => `/parts/${id}/inspection`, label: "Inspection" },
  simulation: { href: (id) => `/parts/${id}/nc`, label: "NC output" },
  nc: { href: (id) => `/parts/${id}/nc`, label: "NC output" },
  approval: { href: (id) => `/parts/${id}/readiness`, label: "Readiness" },
};

function rank(gate: ReadinessGate): number {
  const i = RESOLUTION_ORDER.indexOf(gate.id);
  return i === -1 ? RESOLUTION_ORDER.length : i;
}

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
    if (i >= 0) actions[i] = replacement;
    else actions.push(replacement);
  }

  if (actions.length === 0 && readiness.overall === "READY_TO_RUN") {
    return [
      {
        action: "Run the first article and record what actually happened",
        reason:
          "Every gate passes. What CANVAS does not have yet is evidence from this part running on this machine — that is what turns a plan into shop knowledge.",
        href: `/parts/${partId}/nc`,
        linkLabel: "NC output",
        gateId: null,
        severity: "IMPROVEMENT",
      },
    ];
  }

  return actions.slice(0, limit);
}
