import type { RotationalProfile } from "./geometry";
import type { TurnApprovalState } from "./approval";
import { validateProfile } from "./geometry";
import type { TurnAnalysis } from "./analysis";
import type { TurnInspectionVerdict } from "./derive";

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
  boringBar: TurnAnalysis | null; // null when the plan has no boring, or no bar is recorded
  /** The plan bores and the crib records no usable boring bar. */
  boringBarUnrecorded?: boolean;
  partOff: TurnAnalysis | null; // null when the plan has no cutoff
  toolsAssigned: number;
  toolsRequired: number;
  chuckRpmKnown: boolean;
  cssUsed: boolean;
  /** Verdict from turn/derive.ts — the mill's 10:1/4:1 rule, one home. */
  inspectionCapable: TurnInspectionVerdict | null; // null = not assessed
  postSelected: boolean;
  /**
   * Whether a human has approved THIS package.
   *
   * STALE means someone approved an earlier state of the part and something
   * approved has changed since — the profile, the plan, the lathe, the
   * workholding or the grip. It reopens the gate rather than passing it, which
   * is the whole reason the approval carries a digest. See turn/approval.ts.
   */
  approval: TurnApprovalState;
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
  } else if (input.boringBarUnrecorded) {
    // A plan that bores with no bar on file is not a plan without boring.
    g(
      "boring-bar",
      "Boring bar reach",
      // NOT_ATTEMPTED is this vocabulary's word for "could not be checked",
      // and it already blocks — see the aggregation below.
      "NOT_ATTEMPTED",
      "This plan bores, and no boring bar with a recorded diameter and stickout is in the crib. Length-to-diameter cannot be checked against a bar that is not on file.",
    );
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
  {
    // The mill's gauge-maker's rule, both ends: ≤10% of the band is
    // capable, ≤25% is marginal — usable with guard-banded accept limits,
    // and REVIEW rather than PASS says so — past that the reading is
    // largely the instrument's own noise. Turning used to pass at 25%.
    const v = input.inspectionCapable;
    const status: TurnGateStatus =
      v === null ? "NOT_ATTEMPTED" : v === "NOT_CAPABLE" ? "FAIL" : v === "MARGINAL" ? "REVIEW" : "PASS";
    const detail =
      v === null
        ? "Not assessed against the instrument library."
        : v === "NOT_REQUIRED"
          ? "No critical segment carries a tolerance band — nothing to verify, which is not the same as verified."
          : v === "CAPABLE"
            ? "Best instrument consumes no more than 10% of the tightest critical band."
            : v === "MARGINAL"
              ? "Best instrument consumes 10-25% of the tightest critical band. Guard-band the accept limits by the instrument's uncertainty, or use a more capable instrument."
              : "Instruments on hand cannot verify a required tolerance — what they report is largely their own noise. The gate moves when the instrument does.";
    g("inspection", "Inspection capability", status, detail);
  }
  g("post", "Post / NC", input.postSelected ? "PASS" : "FAIL", input.postSelected ? "Development lathe post selected." : "No post selected.");
  g(
    "approval",
    "Human approval",
    input.approval === "APPROVED" ? "PASS" : "NOT_ATTEMPTED",
    input.approval === "APPROVED"
      ? "Approved."
      : input.approval === "STALE"
        ? "This part was approved and has changed since — the profile, plan, lathe, workholding or grip is not the one that was reviewed. It needs approving again."
        : "Awaiting a named human.",
  );

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
