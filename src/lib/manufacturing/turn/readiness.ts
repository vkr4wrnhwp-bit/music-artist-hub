import type { RotationalProfile } from "./geometry";
import { validateProfile } from "./geometry";
import type { TurnAnalysis } from "./analysis";

/**
 * TURNING READINESS — the same law as milling: gates, and the aggregate is
 * the worst unresolved required gate. Never a percentage, never an average.
 * The aggregation function is worst-case by construction; if arithmetic
 * appears here, stop.
 */

export type TurnGateStatus = "PASS" | "REVIEW" | "FAIL" | "NOT_ATTEMPTED";

export interface TurnGate {
  id: string;
  label: string;
  status: TurnGateStatus;
  detail: string;
  blocking: boolean;
}

export interface TurnReadinessInput {
  profile: RotationalProfile | null;
  materialKnown: boolean;
  latheSelected: boolean;
  workholdingSelected: boolean;
  grip: TurnAnalysis | null;
  stickout: TurnAnalysis | null;
  boringBar: TurnAnalysis | null; // null when the plan has no boring
  partOff: TurnAnalysis | null; // null when the plan has no cutoff
  toolsAssigned: number;
  toolsRequired: number;
  chuckRpmKnown: boolean;
  cssUsed: boolean;
  inspectionCapable: boolean | null; // null = not assessed
  postSelected: boolean;
  humanApproved: boolean;
}

const fromAnalysis = (a: TurnAnalysis | null, na: string): { status: TurnGateStatus; detail: string } => {
  if (a === null) return { status: "NOT_ATTEMPTED", detail: na };
  if (a.verdict === "PASS") return { status: "PASS", detail: a.detail };
  if (a.verdict === "FAIL") return { status: "FAIL", detail: a.detail };
  if (a.verdict === "UNKNOWN") return { status: "FAIL", detail: `${a.detail} Missing: ${a.missingInputs.join(" ")}` };
  return { status: "REVIEW", detail: a.detail };
};

export function evaluateTurnReadiness(input: TurnReadinessInput): {
  gates: TurnGate[];
  overall: "READY_TO_RUN" | "REVIEW_REQUIRED" | "NOT_READY_TO_RUN";
} {
  const gates: TurnGate[] = [];
  const g = (id: string, label: string, status: TurnGateStatus, detail: string, blocking = true) =>
    gates.push({ id, label, status, detail, blocking });

  if (!input.profile) {
    g("geometry", "Rotational geometry", "FAIL", "No profile defined.");
  } else {
    const problems = validateProfile(input.profile);
    g("geometry", "Rotational geometry", problems.length === 0 ? "PASS" : "FAIL", problems.length === 0 ? `${input.profile.segments.length} segments validated.` : problems.join(" "));
  }
  g("material", "Material", input.materialKnown ? "PASS" : "FAIL", input.materialKnown ? "Material recorded." : "Material not specified.");
  g("machine", "Lathe machine", input.latheSelected ? "PASS" : "FAIL", input.latheSelected ? "Lathe selected." : "No lathe selected.");
  g("workholding", "Chuck / workholding", input.workholdingSelected ? "PASS" : "FAIL", input.workholdingSelected ? "Workholding assigned." : "No workholding assigned.");

  const grip = fromAnalysis(input.grip, "Grip not assessed.");
  g("grip", "Grip", grip.status, grip.detail);
  const stick = fromAnalysis(input.stickout, "Stickout not assessed.");
  g("stickout", "Stickout / deflection", stick.status, stick.detail);
  if (input.boringBar !== null) {
    const bb = fromAnalysis(input.boringBar, "");
    g("boring-bar", "Boring bar reach", bb.status, bb.detail);
  }
  if (input.partOff !== null) {
    const po = fromAnalysis(input.partOff, "");
    g("part-off", "Part-off stability", po.status, po.detail);
  }

  g(
    "tooling",
    "Tooling",
    input.toolsAssigned >= input.toolsRequired && input.toolsRequired > 0 ? "PASS" : "FAIL",
    `${input.toolsAssigned} of ${input.toolsRequired} required stations assigned.`,
  );
  g(
    "rpm",
    "Spindle / RPM limit",
    input.cssUsed && !input.chuckRpmKnown ? "REVIEW" : "PASS",
    input.cssUsed && !input.chuckRpmKnown
      ? "CSS is programmed but the chuck's RPM limit is not recorded — G50 cannot be sized honestly."
      : input.cssUsed
        ? "CSS with a recorded chuck limit."
        : "Fixed RPM programming.",
  );
  g(
    "inspection",
    "Inspection capability",
    input.inspectionCapable === null ? "NOT_ATTEMPTED" : input.inspectionCapable ? "PASS" : "FAIL",
    input.inspectionCapable === null
      ? "Not assessed against the instrument library."
      : input.inspectionCapable
        ? "Instruments cover the tolerances."
        : "Instruments on hand cannot verify a required tolerance. The gate moves when the instrument does.",
  );
  g("post", "Post / NC", input.postSelected ? "PASS" : "FAIL", input.postSelected ? "Development lathe post selected." : "No post selected.");
  g("approval", "Human approval", input.humanApproved ? "PASS" : "NOT_ATTEMPTED", input.humanApproved ? "Approved." : "Awaiting a named human.");

  // Worst-gate, by construction: any blocking FAIL/NOT_ATTEMPTED → NOT
  // READY; any REVIEW → REVIEW REQUIRED; else ready.
  const blocking = gates.filter((x) => x.blocking);
  const overall = blocking.some((x) => x.status === "FAIL" || x.status === "NOT_ATTEMPTED")
    ? "NOT_READY_TO_RUN"
    : blocking.some((x) => x.status === "REVIEW")
      ? "REVIEW_REQUIRED"
      : "READY_TO_RUN";
  return { gates, overall };
}
