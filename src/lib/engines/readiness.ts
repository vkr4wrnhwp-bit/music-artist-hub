import type { PartIntent } from "@/lib/domain/part-intent";
import { isCriticalApplication, missingEngineeringInput } from "@/lib/domain/part-intent";
import type { Feature, Stock } from "@/lib/domain/features";
import { maximumDepth, minimumInternalRadius } from "@/lib/domain/features";
import type { MachineProfile, Tool, WorkholdingDevice } from "@/lib/domain/shop";
import { canReach, checkEnvelope, fitsInternalCorner } from "@/lib/domain/shop";
import type { WorkholdingAssessment } from "./workholding";
import { assessCapability, worstCapability, type CapabilityResult, type Instrument, type MeasurementGeometry } from "./inspection-capability";

/**
 * MANUFACTURING READINESS
 *
 * Not a percentage. A percentage invites the operator to feel 87% confident
 * about a part that is missing an inspection plan entirely. This is a gate
 * list: each item passes, needs review, is missing, or has not been attempted,
 * and the aggregate status is the worst item — never an average.
 */

export const GATE_STATUS = ["PASS", "REVIEW", "MISSING", "FAIL", "NOT_ATTEMPTED"] as const;
export type GateStatus = (typeof GATE_STATUS)[number];

const SEVERITY: Record<GateStatus, number> = {
  PASS: 0,
  NOT_ATTEMPTED: 1,
  REVIEW: 2,
  MISSING: 3,
  FAIL: 4,
};

export interface ReadinessGate {
  id: string;
  label: string;
  status: GateStatus;
  detail: string;
  /** Critical gates block NC export regardless of anything else. */
  blocking: boolean;
  actions: string[];
}

export interface ReadinessReport {
  gates: ReadinessGate[];
  /** READY_TO_RUN only when every blocking gate passes and nothing is FAIL. */
  overall: "READY_TO_RUN" | "NOT_READY_TO_RUN" | "REVIEW_REQUIRED";
  criticalApplication: boolean;
  blockingCount: number;
  /** Per-feature measurement capability, surfaced so the UI can explain it. */
  capability: CapabilityResult[];
}

export interface ReadinessInput {
  intent: PartIntent;
  stock: Stock | null;
  features: Feature[];
  machine: MachineProfile | null;
  tools: Tool[];
  workholding: WorkholdingDevice | null;
  workholdingAssessment: WorkholdingAssessment | null;
  hasInspectionPlan: boolean;
  /** Metrology the shop actually owns. Drives the inspection capability gate. */
  instruments?: Instrument[];
  simulationRun: boolean;
  ncGenerated: boolean;
  operatorApproved: boolean;
}

export function evaluateReadiness(input: ReadinessInput): ReadinessReport {
  const gates: ReadinessGate[] = [];
  const critical = isCriticalApplication(input.intent);

  /* ---- Geometry ---- */
  gates.push(
    input.features.length === 0
      ? gate("geometry", "Geometry", "MISSING", "No features are defined on this part.", true, ["Add features to the part"])
      : gate("geometry", "Geometry", "PASS", `${input.features.length} features defined.`, true, []),
  );

  /* ---- Machine envelope ---- */
  if (!input.machine) {
    gates.push(
      gate("machine", "Machine envelope", "MISSING", "No machine is selected, so travel and spindle limits cannot be validated.", true, [
        "Select a machine for this setup",
      ]),
    );
  } else if (!input.stock) {
    gates.push(gate("machine", "Machine envelope", "MISSING", "Stock is not defined.", true, ["Define stock dimensions"]));
  } else {
    const fixtureH = input.workholding?.fixtureHeight ?? 0;
    const check = checkEnvelope(input.machine, input.stock, fixtureH, 6);
    gates.push(
      check.fits
        ? gate(
            "machine",
            "Machine envelope",
            "PASS",
            `Fits ${input.machine.manufacturer} ${input.machine.model} with ${check.clearanceZ.toFixed(2)}" Z clearance over the fixture stack.`,
            true,
            [],
          )
        : gate("machine", "Machine envelope", "FAIL", check.reasons.join("; "), true, [
            "Select a larger machine",
            "Reduce stock size",
            "Use lower-profile workholding",
          ]),
    );
  }

  /* ---- Tool availability ---- */
  if (input.tools.length === 0) {
    gates.push(gate("tools", "Tool availability", "MISSING", "No tools are assigned to this part.", true, ["Assign tools from the tool crib"]));
  } else {
    gates.push(gate("tools", "Tool availability", "PASS", `${input.tools.length} tools assigned from the crib.`, true, []));
  }

  /* ---- Tool reach ---- */
  if (input.stock && input.tools.length > 0) {
    const depth = maximumDepth(input.features, input.stock);
    const shortest = input.tools.filter((t) => !canReach(t, depth));
    gates.push(
      shortest.length === 0
        ? gate("reach", "Tool reach", "PASS", `All assigned tools reach the ${depth.toFixed(3)}" maximum depth.`, true, [])
        : gate(
            "reach",
            "Tool reach",
            "REVIEW",
            `${shortest.map((t) => t.description).join(", ")} cannot reach ${depth.toFixed(3)}".`,
            true,
            ["Increase stickout", "Select longer-reach tooling", "Split into two setups"],
          ),
    );
  } else {
    gates.push(gate("reach", "Tool reach", "NOT_ATTEMPTED", "Requires stock and assigned tooling.", true, []));
  }

  /* ---- Internal corner feasibility ---- */
  const minR = minimumInternalRadius(input.features);
  if (minR !== null && input.tools.length > 0) {
    const smallest = input.tools.reduce((a, b) => (a.diameter < b.diameter ? a : b));
    gates.push(
      fitsInternalCorner(smallest, minR)
        ? gate("corners", "Internal corner access", "PASS", `Smallest tool ⌀${smallest.diameter.toFixed(4)}" fits the R${minR.toFixed(4)} minimum corner.`, false, [])
        : gate(
            "corners",
            "Internal corner access",
            "FAIL",
            `Smallest assigned tool ⌀${smallest.diameter.toFixed(4)}" cannot produce the R${minR.toFixed(4)} internal corner.`,
            true,
            [`Add a ⌀${(minR * 2).toFixed(4)}" or smaller tool`, "Increase the corner radius"],
          ),
    );
  }

  /* ---- Material ---- */
  const mat = input.intent.material;
  gates.push(
    mat.value == null
      ? gate("material", "Material", "MISSING", "Material is not specified.", true, ["Specify material and condition"])
      : mat.confirmedByUser
        ? gate("material", "Material", "PASS", `${mat.value} — confirmed.`, true, [])
        : gate("material", "Material", "REVIEW", `${mat.value} — inferred, not confirmed by a human.`, true, ["Confirm the material"]),
  );

  /* ---- Workholding ---- */
  if (!input.workholding || !input.workholdingAssessment) {
    gates.push(
      gate("workholding", "Workholding", "MISSING", "Workholding is not defined, so setup stability and fixture clearance cannot be evaluated.", true, [
        "Define workholding for this setup",
      ]),
    );
  } else {
    const a = input.workholdingAssessment;
    const status: GateStatus =
      a.level === "SAFE" || a.level === "LIKELY_SAFE" ? "PASS" : a.level === "UNKNOWN" ? "MISSING" : a.level === "REVIEW" ? "REVIEW" : "FAIL";
    gates.push(
      gate("workholding", "Workholding", status, workholdingDetail(a), true, a.factors.flatMap((f) => f.suggestions).slice(0, 3)),
    );
  }

  /* ---- Critical tolerance strategy ---- */
  const criticalFeatures = input.features.filter((f) => f.critical);
  const withoutStrategy = criticalFeatures.filter((f) => !f.inspectionMethod);
  gates.push(
    criticalFeatures.length === 0
      ? gate("tolerance", "Critical tolerance strategy", "NOT_ATTEMPTED", "No features are flagged critical.", false, [])
      : withoutStrategy.length === 0
        ? gate("tolerance", "Critical tolerance strategy", "PASS", `All ${criticalFeatures.length} critical features have an inspection method.`, critical, [])
        : gate(
            "tolerance",
            "Critical tolerance strategy",
            "REVIEW",
            `${withoutStrategy.length} of ${criticalFeatures.length} critical features have no inspection method assigned.`,
            critical,
            ["Assign an inspection method to each critical feature"],
          ),
  );

  /* ---- Inspection capability ---- */

  // A tolerance nobody can measure is not a tolerance. This gate is decided by
  // the instruments in the drawer, which is why it cannot be cleared by
  // acknowledging it: clicking Confirm does not buy a bore gauge.
  const instruments = input.instruments ?? [];
  const capability: CapabilityResult[] = input.features
    .filter((f) => f.tolerance != null || f.critical)
    .map((f) =>
      assessCapability(
        {
          featureId: f.id,
          featureLabel: f.label,
          geometry: measurementGeometry(f),
          nominal: "diameter" in f ? f.diameter : null,
          toleranceBand: f.tolerance ? f.tolerance.plus + f.tolerance.minus : null,
          critical: f.critical,
        },
        instruments,
      ),
    );

  const worstCap = worstCapability(capability);
  const incapable = capability.filter((c) => c.verdict === "NOT_CAPABLE" || c.verdict === "NO_INSTRUMENT");
  const marginal = capability.filter((c) => c.verdict === "MARGINAL");

  gates.push(
    capability.length === 0
      ? gate("inspection-capability", "Inspection capability", "NOT_ATTEMPTED", "No toleranced features to verify.", false, [])
      : instruments.length === 0
        ? gate(
            "inspection-capability",
            "Inspection capability",
            "MISSING",
            "No metrology equipment is recorded, so no toleranced dimension on this part can be shown to be verifiable.",
            true,
            ["Record the shop's measuring equipment, with resolution and uncertainty"],
          )
        : incapable.length > 0
          ? gate(
              "inspection-capability",
              "Inspection capability",
              "FAIL",
              `${incapable.length} toleranced ${incapable.length === 1 ? "feature cannot" : "features cannot"} be verified with the instruments on hand. ${incapable[0].reason}`,
              true,
              incapable[0].recommendations,
            )
          : marginal.length > 0
            ? gate(
                "inspection-capability",
                "Inspection capability",
                "REVIEW",
                `${marginal.length} ${marginal.length === 1 ? "measurement consumes" : "measurements consume"} more than 10% of the tolerance band. ${marginal[0].reason}`,
                false,
                marginal[0].recommendations,
              )
            : gate(
                "inspection-capability",
                "Inspection capability",
                "PASS",
                `Every toleranced feature can be measured within 10% of its band by equipment on hand.`,
                true,
                [],
              ),
  );

  /* ---- Inspection plan ---- */
  gates.push(
    input.hasInspectionPlan
      ? gate("inspection", "Inspection plan", "PASS", "Inspection plan is defined.", critical, [])
      : gate("inspection", "Inspection plan", "MISSING", "No inspection plan exists for this revision.", critical, ["Create an inspection plan"]),
  );

  /* ---- Engineering input ---- */
  const gaps = missingEngineeringInput(input.intent);
  gates.push(
    gaps.length === 0
      ? gate("engineering", "Engineering input", "PASS", "Required intake fields are complete.", true, [])
      : gate("engineering", "Engineering input", "MISSING", `${gaps.length} required inputs outstanding: ${gaps.slice(0, 3).join(", ")}${gaps.length > 3 ? "…" : ""}`, true, [
          "Complete the Part Responsibility Profile",
        ]),
  );

  /* ---- Simulation ---- */
  gates.push(
    input.simulationRun
      ? gate("simulation", "Simulation", "REVIEW", "Development visualisation completed. This is not verified stock removal or collision checking.", true, [
          "Verify on the machine with a dry run above the part",
        ])
      : gate("simulation", "Simulation", "NOT_ATTEMPTED", "Simulation has not been run.", true, ["Run the development simulation"]),
  );

  /* ---- NC ---- */
  gates.push(
    input.ncGenerated
      ? gate("nc", "NC post", "REVIEW", "Development post output generated. Not certified for production.", true, ["Review the program line by line"])
      : gate("nc", "NC post", "NOT_ATTEMPTED", "No NC program has been generated.", false, []),
  );

  /* ---- Operator approval — always the last gate ---- */
  gates.push(
    input.operatorApproved
      ? gate("approval", "Operator approval", "PASS", "A human has approved this manufacturing package.", true, [])
      : gate("approval", "Operator approval", "MISSING", "No human has approved this package.", true, ["Review and approve"]),
  );

  /* ---- Critical application requires a human, always ---- */
  if (critical) {
    gates.push(
      gate(
        "critical-review",
        "Critical application review",
        input.operatorApproved ? "REVIEW" : "MISSING",
        "This component is load bearing or safety critical. CANVAS assists with manufacturing planning; it does not certify component safety.",
        true,
        ["Obtain engineering validation", "Confirm material certification and traceability requirements"],
      ),
    );
  }

  const blocking = gates.filter((g) => g.blocking);
  const worst = gates.reduce((acc, g) => (SEVERITY[g.status] > SEVERITY[acc] ? g.status : acc), "PASS" as GateStatus);
  const blockingFailures = blocking.filter((g) => g.status !== "PASS").length;

  const overall =
    blockingFailures === 0 && worst !== "FAIL"
      ? "READY_TO_RUN"
      : blockingFailures > 0
        ? "NOT_READY_TO_RUN"
        : "REVIEW_REQUIRED";

  return { gates, overall, criticalApplication: critical, blockingCount: blockingFailures, capability };
}

/**
 * Which family of instrument a feature needs. A bore and a boss of the same
 * size are not measured with the same tool, and a position is not measured with
 * either of them.
 */
function measurementGeometry(f: Feature): MeasurementGeometry {
  switch (f.kind) {
    case "DRILLED_HOLE":
    case "TAPPED_HOLE":
    case "BORE":
    case "CIRC_POCKET":
    case "RECT_POCKET":
    case "SLOT":
      return f.functionalRole === "DOWEL_HOLE" || f.functionalRole === "MOUNTING_HOLE" ? "POSITION" : "INTERNAL";
    default:
      return "EXTERNAL";
  }
}

function workholdingDetail(a: WorkholdingAssessment): string {
  const parts: string[] = [];
  if (a.gripDepth != null) parts.push(`Grip ${a.gripDepth.toFixed(3)}"`);
  if (a.engagementPercent != null) parts.push(`${a.engagementPercent}% jaw engagement`);
  if (a.estimatedCuttingForce != null) parts.push(`~${a.estimatedCuttingForce} lbf estimated cutting load`);
  const worst = a.factors.find((f) => f.level === "HIGH_RISK" || f.level === "REVIEW");
  if (worst) parts.push(worst.reason);
  return parts.join(" · ") || "Not evaluated.";
}

const gate = (
  id: string,
  label: string,
  status: GateStatus,
  detail: string,
  blocking: boolean,
  actions: string[],
): ReadinessGate => ({ id, label, status, detail, blocking, actions });

export const GATE_LABEL: Record<GateStatus, string> = {
  PASS: "Pass",
  REVIEW: "Review",
  MISSING: "Missing",
  FAIL: "Fail",
  NOT_ATTEMPTED: "Not attempted",
};
