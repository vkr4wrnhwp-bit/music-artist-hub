import type { PartIntent } from "@/lib/domain/part-intent";
import { isCriticalApplication, missingEngineeringInput } from "@/lib/domain/part-intent";
import type { Feature, Stock } from "@/lib/domain/features";
import { maximumDepth, minimumInternalRadius } from "@/lib/domain/features";
import type { MachineProfile, Tool, WorkholdingDevice } from "@/lib/domain/shop";
import { canReach, checkEnvelope, fitsInternalCorner } from "@/lib/domain/shop";
import type { WorkholdingAssessment } from "./workholding";
import { assessCapability, measurementGeometry, worstCapability, type CapabilityResult, type Instrument } from "./inspection-capability";

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

export const SEVERITY: Record<GateStatus, number> = {
  PASS: 0,
  NOT_ATTEMPTED: 1,
  REVIEW: 2,
  MISSING: 3,
  FAIL: 4,
};

/**
 * Every gate this engine can emit.
 *
 * Declared as a closed list rather than left as a free string because
 * next-action.ts keys two tables off these ids — the order gates should be
 * resolved in, and where the operator goes to resolve each one. Both were
 * hand-written, and when the tool-loading gate was added neither was updated:
 * it sorted last among its peers and offered no link at all. A union means
 * the compiler asks for both entries the day a gate is added.
 */
export const READINESS_GATE_IDS = [
  "geometry",
  "material",
  "engineering",
  "machine",
  "reach",
  "corners",
  "tools",
  "tool-loading",
  "inspection-capability",
  "critical-review",
  "workholding",
  "tolerance",
  "inspection",
  "simulation",
  "nc",
  "approval",
] as const;
export type ReadinessGateId = (typeof READINESS_GATE_IDS)[number];

export interface ReadinessGate {
  id: ReadinessGateId;
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
  /**
   * Tool loading, PER SETUP.
   *
   * Per setup rather than per part, because `Setup.machineId` is per setup:
   * a part can be roughed on one machine and finished on another, and the
   * tools for setup 2 have no business being checked against setup 1's
   * changer. An earlier version of this gate checked every assigned tool
   * against one "primary" machine, which reported correctly-loaded tools as
   * missing the moment a part spanned two machines.
   *
   * `machineLabel: null` means that setup has no machine assigned — there is
   * nothing to check against, which is not the same as a failure.
   * `loadedToolNumbers: null` means the changer has not been mapped, which is
   * not the same as the tools being absent. Both are NOT_ATTEMPTED; only a
   * mapped changer that is genuinely missing a required tool is MISSING.
   */
  toolLoading?: {
    setupName: string;
    machineLabel: string | null;
    requiredToolNumbers: number[];
    loadedToolNumbers: number[] | null;
  }[];
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

  /* ---- Tooling loaded ----
   *
   * A separate gate from the one above, deliberately. "The crib contains this
   * cutter" and "this cutter is in the machine" are different questions, and
   * collapsing them lets a part read as ready with the tooling still on the
   * shelf. This is the last question before Cycle Start that CANVAS can
   * actually answer, so it is blocking.
   *
   * The distinction that matters: a tool the changer map does not list is a
   * real finding. A changer nobody has mapped is not — absence of evidence is
   * not evidence of absence, and failing a shop for not having adopted a
   * feature would be the gate lying in the other direction. That case is
   * NOT_ATTEMPTED, which keeps the part off READY_TO_RUN without claiming the
   * tooling is missing.
   */
  const loading = (input.toolLoading ?? []).filter((s) => s.requiredToolNumbers.length > 0);
  if (loading.length > 0) {
    const absentBySetup: { setupName: string; machineLabel: string; absent: number[] }[] = [];
    const unmapped: string[] = [];
    const unassigned: string[] = [];
    let checked = 0;

    for (const s of loading) {
      if (s.machineLabel === null) {
        unassigned.push(s.setupName);
        continue;
      }
      if (s.loadedToolNumbers === null || s.loadedToolNumbers.length === 0) {
        unmapped.push(`${s.setupName} (${s.machineLabel})`);
        continue;
      }
      const loaded = new Set(s.loadedToolNumbers);
      const absent = s.requiredToolNumbers.filter((n) => !loaded.has(n));
      checked += 1;
      if (absent.length > 0) absentBySetup.push({ setupName: s.setupName, machineLabel: s.machineLabel, absent });
    }

    const tnums = (ns: number[]) => ns.map((n) => `T${n}`).join(", ");

    if (absentBySetup.length > 0) {
      // A real finding outranks an unknown — the worst unresolved thing wins,
      // and a tool that is definitely not in the machine is worse than a
      // changer nobody has mapped.
      gates.push(
        gate(
          "tool-loading",
          "Tooling loaded",
          "MISSING",
          absentBySetup
            .map(
              (a) =>
                `${a.setupName}: ${tnums(a.absent)} ${a.absent.length === 1 ? "is" : "are"} not in the ${a.machineLabel} changer`,
            )
            .join("; ") + ".",
          true,
          absentBySetup.map((a) => `Load ${tnums(a.absent)} into the ${a.machineLabel} changer and record the pockets`),
        ),
      );
    } else if (unassigned.length > 0) {
      gates.push(
        gate(
          "tool-loading",
          "Tooling loaded",
          "NOT_ATTEMPTED",
          `${unassigned.join(", ")} ${unassigned.length === 1 ? "has" : "have"} no machine assigned, so there is no changer to check the tooling against.`,
          true,
          ["Assign a machine to every setup"],
        ),
      );
    } else if (unmapped.length > 0) {
      gates.push(
        gate(
          "tool-loading",
          "Tooling loaded",
          "NOT_ATTEMPTED",
          `The changer has not been mapped for ${unmapped.join(", ")}, so CANVAS cannot say whether this tooling is in the machine.`,
          true,
          ["Map the changer on the machine's carousel page"],
        ),
      );
    } else {
      const total = loading.reduce((n, s) => n + s.requiredToolNumbers.length, 0);
      gates.push(
        gate(
          "tool-loading",
          "Tooling loaded",
          "PASS",
          checked === 1
            ? `All ${total} tools this part needs are in the ${loading[0].machineLabel} changer.`
            : `All ${total} tools this part needs are loaded, across ${checked} setups.`,
          true,
          [],
        ),
      );
    }
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

  const { overall, blockingCount } = aggregate(gates);
  return { gates, overall, criticalApplication: critical, blockingCount, capability };
}

/**
 * The aggregation locked principle 1 is about: "the aggregate state is the
 * worst unresolved required gate. Never average a FAIL away."
 *
 * Lifted out of computeReadiness so it can be exercised directly. It could
 * not be before, and the gap showed: inverting SEVERITY so that FAIL ranked
 * as the LEAST severe status broke none of the readiness tests. That is
 * currently latent rather than live — every gate that can emit FAIL is also
 * marked blocking, so blockingFailures catches it first — but `worst` exists
 * precisely to survive someone adding a non-blocking FAIL later, and nothing
 * was checking that it would.
 */
export function aggregate(gates: ReadinessGate[]): {
  overall: ReadinessReport["overall"];
  blockingCount: number;
} {
  const blockingFailures = gates.filter((g) => g.blocking && g.status !== "PASS").length;
  const worst = gates.reduce<GateStatus>(
    (acc, g) => (SEVERITY[g.status] > SEVERITY[acc] ? g.status : acc),
    "PASS",
  );

  const overall =
    blockingFailures === 0 && worst !== "FAIL"
      ? "READY_TO_RUN"
      : blockingFailures > 0
        ? "NOT_READY_TO_RUN"
        : "REVIEW_REQUIRED";

  return { overall, blockingCount: blockingFailures };
}

/* `measurementGeometry` used to live here. It now lives in
   inspection-capability.ts beside `assessCapability`, because the workspace
   feature panel and the feature detail page each grew their own copy of it and
   the copies disagreed with this gate — the panel printed NOT CAPABLE on
   features the gate counted as verifiable. One classifier, one answer. */

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
  id: ReadinessGateId,
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
