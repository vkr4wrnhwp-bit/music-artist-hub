/**
 * HOLDING MARGIN — CANVAS Holding Model v0.1
 *
 * Phase 1 judged workholding largely by grip depth against a scaled rule of
 * thumb. That is not how a part comes out of a vise.
 *
 * A 0.080" grip is not universally unsafe: 0.080" of a serrated jaw biting a
 * 6"-long block of 6061 under a light finishing pass is fine. A 0.250" grip is
 * not universally safe: 0.250" of smooth jaw on a 1"-wide slug taking a full
 * slot in 4140 will move. What decides it is the ratio between the load the cut
 * applies and the load the setup can resist, and neither of those is grip depth.
 *
 * So this model compares two forces:
 *
 *   RESISTING   friction from clamping force across both jaw faces, plus any
 *               positive mechanical stop (a soft-jaw step or a fixed stop is
 *               not friction — it is a shoulder, and it does not care about μ)
 *   APPLIED     the governing lateral load from the cutting force service,
 *               taken at peak rather than average
 *
 * The ratio is the holding margin. It is reported with the assumptions that
 * produced it, and the model refuses to produce it at all when clamping force
 * is unknown — which, in most shops, it is, because nobody torque-wrenches a
 * vise handle. That refusal is the honest answer, and it is accompanied by what
 * would have to be recorded to get a real one.
 *
 * CLASSIFICATION: DEVELOPMENT ANALYSIS.
 *
 * This model has not been validated against instrumented pull-off testing. It
 * is a defensible basis for comparing setups and for catching the setups that
 * are obviously wrong. It is not a certification that a part will stay in the
 * vise, and CANVAS does not present it as one.
 *
 * See /docs/MANUFACTURING_SAFETY.md.
 */

import type { CuttingForceEstimate } from "./cutting-force";
import { governingLateralLoad } from "./cutting-force";
import type { CalculationInput } from "./cutting-force";

export const HOLDING_MODEL_VERSION = "CANVAS Holding Model v0.1 (friction + positive stop)";

/* ------------------------------------------------------------------ */
/* Friction                                                            */
/* ------------------------------------------------------------------ */

export const JAW_SURFACES = ["SMOOTH", "SERRATED", "SOFT_MACHINED", "GRIP_INSERT", "UNKNOWN"] as const;
export type JawSurface = (typeof JAW_SURFACES)[number];

/**
 * Static friction coefficients for a dry, clean, machined interface. These are
 * conservative published ranges taken at the low end, because a film of coolant
 * on a jaw face is the normal condition rather than the exception.
 */
const FRICTION: Record<JawSurface, { mu: number; note: string }> = {
  SMOOTH: { mu: 0.15, note: "Smooth hardened jaws, dry: μ ≈ 0.15. Coolant film reduces this further." },
  SERRATED: { mu: 0.35, note: "Serrated jaws bite into the stock; μ ≈ 0.35 represents the mechanical interlock, not pure friction." },
  SOFT_MACHINED: { mu: 0.25, note: "Machined aluminium soft jaws conform to the part; μ ≈ 0.25." },
  GRIP_INSERT: { mu: 0.45, note: "Carbide grip inserts penetrate the surface; μ ≈ 0.45 with visible witness marks on the part." },
  UNKNOWN: { mu: 0.15, note: "Jaw surface not recorded — the smooth-jaw coefficient has been assumed as the conservative case." },
};

export const JAW_SURFACE_LABEL: Record<JawSurface, string> = {
  SMOOTH: "Smooth hardened",
  SERRATED: "Serrated",
  SOFT_MACHINED: "Machined soft jaws",
  GRIP_INSERT: "Carbide grip inserts",
  UNKNOWN: "Not recorded",
};

/* ------------------------------------------------------------------ */
/* Interface                                                           */
/* ------------------------------------------------------------------ */

export type MarginVerdict = "ADEQUATE" | "MARGINAL" | "INSUFFICIENT" | "INDETERMINATE";

export interface HoldingMarginInput {
  /** Clamping force the vise actually applies, lbf. */
  clampForce: number | null;
  jawSurface: JawSurface;
  /** Depth of stock held below the top of the jaws, inches. */
  gripDepth: number | null;
  /** Length of part in contact with the jaw face, inches. */
  gripLength: number | null;
  /** Jaw face height available, inches. */
  jawHeight: number | null;
  /**
   * True when the part seats against a machined step or a fixed stop that
   * opposes the cutting direction. This is load path, not friction.
   */
  hasPositiveStop: boolean;
  /** Shear area of that stop, in² — step depth × contact length. */
  stopContactArea?: number | null;
  /** Yield strength of the jaw material, psi — governs what the stop can take. */
  jawYieldStrength?: number | null;
  /** The cut being resisted. */
  force: CuttingForceEstimate;
  /** Direction the cutting load pushes the part, for the operator-facing text. */
  loadDirection?: string;
  /** Named operation this assessment belongs to. */
  operationLabel?: string;
  /**
   * Height of the cut above the top of the jaws, inches. The lateral load acts
   * here, not at the jaw line, so this is the lever arm that tries to roll the
   * part out of the vise.
   */
  cutHeightAboveJaws?: number | null;
}

export interface HoldingMargin {
  verdict: MarginVerdict;
  /** Resisting force ÷ applied force. Null when either is unknown. */
  margin: number | null;
  /** Total force the setup can resist before the part moves, lbf. */
  resistingForce: number | null;
  /** Portion of that from friction alone, lbf. */
  frictionComponent: number | null;
  /** Portion from a positive stop, lbf. */
  stopComponent: number | null;
  /** Governing lateral load from the cut, lbf. */
  appliedLoad: number | null;
  /** Contact area between part and jaws, in². */
  contactArea: number | null;
  /** Clamping pressure on that area, psi. */
  contactPressure: number | null;

  /** Which failure mode governs — the worse of the two. */
  governingMode: "SLIDING" | "TIPPING" | null;
  /** Margin against the part sliding in the jaws. */
  slidingMargin: number | null;
  /** Margin against the part rolling out of the jaws. */
  tippingMargin: number | null;
  /** Overturning moment applied by the cut, in-lbf. */
  appliedMoment: number | null;
  /** Moment the clamped grip can resist, in-lbf. */
  resistingMoment: number | null;

  /** Grip depth that would reach the target margin, inches. */
  recommendedGripDepth: number | null;
  /** Radial engagement that would reach it at the present grip, fraction of D. */
  recommendedRadialEngagement: number | null;

  method: string;
  inputs: CalculationInput[];
  assumptions: string[];
  missingInputs: string[];
  primaryRisk: string | null;
  recommendations: string[];
  /** Always true in v0.1 — this model is not validated against pull-off tests. */
  developmentAnalysis: true;
}

/**
 * Target margin. A factor of 2 on a peak load estimate carrying ±30% is not
 * generous; it is the minimum that survives the model being wrong in the
 * direction models are usually wrong.
 */
const TARGET_MARGIN = 2.0;
const MARGINAL_MARGIN = 1.3;

export function assessHoldingMargin(input: HoldingMarginInput): HoldingMargin {
  const missing: string[] = [];
  const assumptions: string[] = [];
  const recommendations: string[] = [];

  const applied = governingLateralLoad(input.force);
  if (applied === null) {
    missing.push(
      input.force.missingInputs.length > 0
        ? `Cutting load unknown — ${input.force.missingInputs.join("; ")}`
        : "Cutting load unknown",
    );
  }

  if (input.clampForce == null) {
    missing.push(
      "Clamping force not recorded for this vise — without it, friction cannot be quantified and the margin is a guess",
    );
  }
  if (input.gripDepth == null) missing.push("Grip depth not defined");
  if (input.gripLength == null) missing.push("Grip length not defined");

  const friction = FRICTION[input.jawSurface];
  if (input.jawSurface === "UNKNOWN") {
    missing.push("Jaw surface type not recorded");
  }

  const contactArea =
    input.gripDepth != null && input.gripLength != null
      ? Number((input.gripDepth * input.gripLength * 2).toFixed(4))
      : null;

  const indeterminate = (primaryRisk: string | null): HoldingMargin => ({
    verdict: "INDETERMINATE",
    margin: null,
    resistingForce: null,
    frictionComponent: null,
    stopComponent: null,
    appliedLoad: applied,
    contactArea,
    contactPressure: null,
    governingMode: null,
    slidingMargin: null,
    tippingMargin: null,
    appliedMoment: null,
    resistingMoment: null,
    recommendedGripDepth: null,
    recommendedRadialEngagement: null,
    method: HOLDING_MODEL_VERSION,
    inputs: baseInputs(input, contactArea, friction.mu),
    assumptions,
    missingInputs: missing,
    primaryRisk,
    recommendations: [
      input.clampForce == null
        ? "Record the clamping force for this vise. The manufacturer publishes it against handle torque; measuring it once with a clamp-force gauge is better."
        : "Complete the setup definition so the holding margin can be evaluated.",
      ...(applied === null ? ["Assign a roughing operation so the cutting load is defined."] : []),
    ],
    developmentAnalysis: true,
  });

  if (applied === null || input.clampForce == null || input.gripDepth == null || input.gripLength == null) {
    return indeterminate(
      applied !== null
        ? `Cut applies an estimated ${applied} lbf laterally, but what the setup can resist is not calculable from what is recorded.`
        : null,
    );
  }

  /* ---- Resisting force ---- */

  // A vise clamps the part between two faces. Both faces develop friction under
  // the same normal load, so the available friction is 2·μ·N.
  const frictionComponent = 2 * friction.mu * input.clampForce;
  assumptions.push(friction.note);
  assumptions.push("Friction developed on both jaw faces under the same clamping load.");
  assumptions.push("Dry, clean, deburred jaw and part surfaces.");

  let stopComponent = 0;
  if (input.hasPositiveStop) {
    // A machined step or fixed stop carries load in shear rather than by
    // friction, so μ is irrelevant to it. Bound it by the jaw material rather
    // than treating it as infinitely strong.
    const area = input.stopContactArea ?? (input.gripDepth * input.gripLength);
    const yieldStrength = input.jawYieldStrength ?? 35000; // 6061-T6 soft jaws
    // Shear yield ≈ 0.577 × tensile yield (von Mises), with a factor of 4 on
    // the jaw itself so the jaw is never the thing being designed to its limit.
    stopComponent = (0.577 * yieldStrength * area) / 4;
    assumptions.push(
      `Positive stop carries load in shear over ${area.toFixed(3)} in², bounded by a ${yieldStrength.toLocaleString()} psi jaw material at a factor of 4.`,
    );
    if (input.jawYieldStrength == null) {
      assumptions.push("Jaw material yield strength not recorded; 6061-T6 soft jaws assumed.");
    }
  }

  const resisting = frictionComponent + stopComponent;
  const slidingMargin = Number((resisting / Math.max(applied, 0.01)).toFixed(2));
  const contactPressure = contactArea && contactArea > 0 ? Number((input.clampForce / contactArea).toFixed(0)) : null;

  /* ---- Tipping ---- */

  // Friction does not depend on how deep the part sits in the jaws, so sliding
  // alone would rate a 0.080" grip and a 0.375" grip identically. It is not
  // sliding that makes a shallow grip dangerous — it is the moment.
  //
  // The lateral load acts at the height of the cut, above the jaw line, and
  // tries to roll the part out. That moment is resisted by the clamping
  // pressure redistributing across the gripped depth; the centre of pressure
  // can shift at most to the edge of the contact, so the resisting moment is
  // bounded by N · gripDepth / 2.
  let tippingMargin: number | null = null;
  let appliedMoment: number | null = null;
  let resistingMoment: number | null = null;

  const leverArm = input.cutHeightAboveJaws;
  if (leverArm != null && leverArm > 0) {
    appliedMoment = Number((applied * leverArm).toFixed(1));
    resistingMoment = Number(((input.clampForce * input.gripDepth) / 2).toFixed(1));
    tippingMargin = Number((resistingMoment / Math.max(appliedMoment, 0.01)).toFixed(2));
    assumptions.push(
      `Overturning resisted by the clamping load acting over the gripped depth; centre of pressure taken at half the grip, giving ${resistingMoment} in-lbf against ${appliedMoment} in-lbf applied at a ${leverArm.toFixed(3)}" lever arm.`,
    );
  } else {
    assumptions.push(
      "Height of the cut above the jaws not recorded, so the part has been checked against sliding only. A shallow grip fails by rolling out long before it fails by sliding.",
    );
  }

  /* ---- Verdict: the worse of the two failure modes governs ---- */

  const margin =
    tippingMargin === null ? slidingMargin : Number(Math.min(slidingMargin, tippingMargin).toFixed(2));
  const governingMode: "SLIDING" | "TIPPING" =
    tippingMargin !== null && tippingMargin < slidingMargin ? "TIPPING" : "SLIDING";

  const verdict: MarginVerdict =
    margin >= TARGET_MARGIN ? "ADEQUATE" : margin >= MARGINAL_MARGIN ? "MARGINAL" : "INSUFFICIENT";

  /* ---- What would fix it ---- */

  // Friction scales with clamping force, not with grip depth — so more grip
  // does not directly buy more holding. It buys contact area, which lets the
  // clamp be tightened without crushing the part, and it buys a deeper step.
  // Stating that honestly matters more than producing a number.
  let recommendedGrip: number | null = null;
  if (verdict !== "ADEQUATE" && governingMode === "TIPPING" && appliedMoment != null) {
    // Resisting moment is linear in grip depth, so this one is direct.
    recommendedGrip = Number(((2 * TARGET_MARGIN * appliedMoment) / input.clampForce).toFixed(3));
  } else if (verdict !== "ADEQUATE" && contactPressure != null) {
    const needed = (TARGET_MARGIN * applied - stopComponent) / (2 * friction.mu);
    const neededArea = needed / Math.max(contactPressure, 1);
    recommendedGrip = Number((neededArea / (2 * input.gripLength)).toFixed(3));
  }

  let recommendedEngagement: number | null = null;
  if (verdict !== "ADEQUATE" && input.force.ok && input.force.engagementAngle != null) {
    // Lateral load scales close to linearly with radial width at light
    // immersion, so scale the present engagement by the shortfall.
    const scale = margin / TARGET_MARGIN;
    const currentImmersion =
      input.force.inputs.find((i) => i.label === "Radial width (ae)")?.value.match(/\((\d+)%/)?.[1];
    if (currentImmersion) {
      recommendedEngagement = Number(((Number(currentImmersion) / 100) * scale).toFixed(3));
    }
  }

  if (verdict !== "ADEQUATE") {
    if (input.clampForce != null && !input.hasPositiveStop) {
      recommendations.push(
        "Machine soft jaws with a seat the part drops into. A positive step carries the cutting load in shear and does not depend on the coefficient of friction at all — it is the single largest change available here.",
      );
    }
    if (recommendedEngagement != null && recommendedEngagement > 0.02) {
      recommendations.push(
        `Reduce radial engagement on the governing pass to roughly ${(recommendedEngagement * 100).toFixed(0)}% of cutter diameter. Cycle time rises; the load falls close to proportionally.`,
      );
    }
    if (input.jawSurface === "SMOOTH") {
      recommendations.push(
        "Fit serrated jaws or grip inserts. Moving from smooth to serrated roughly doubles the friction available for the same clamping force.",
      );
    }
    if (recommendedGrip != null && input.gripDepth != null && recommendedGrip > input.gripDepth) {
      recommendations.push(
        `Increase grip to approximately ${recommendedGrip.toFixed(3)}" — not because friction scales with depth, but because the larger contact area allows the present clamping pressure to be maintained over more material.`,
      );
    }
    if (governingMode === "TIPPING") {
      recommendations.push(
        "Reduce the height of the cut above the jaws. Repositioning the part deeper, or using shorter parallels, shortens the lever arm directly and is usually free.",
      );
    }
    recommendations.push("Climb mill so the cutting load pushes the part into the fixed jaw rather than away from it.");
  }

  /* ---- Primary risk ---- */

  let primaryRisk: string | null = null;
  if (verdict !== "ADEQUATE") {
    const dir = input.loadDirection ? ` toward ${input.loadDirection}` : "";
    const op = input.operationLabel ? ` during ${input.operationLabel}` : "";
    primaryRisk =
      governingMode === "TIPPING"
        ? `Part rolling out of the jaws${dir}${op}. The cut applies ${applied} lbf at peak, ${leverArm?.toFixed(3)}" above the jaw line — ${appliedMoment} in-lbf of overturning against ${resistingMoment} in-lbf the grip can resist. Margin ${margin.toFixed(2)} against a target of ${TARGET_MARGIN.toFixed(1)}.`
        : `Part sliding in the jaws${dir}${op}. The cut applies an estimated ${applied} lbf at peak against ${resisting.toFixed(0)} lbf of resistance — a margin of ${margin.toFixed(2)} against a target of ${TARGET_MARGIN.toFixed(1)}.`;
  }

  if (input.force.uncertaintyPercent != null) {
    assumptions.push(
      `Applied load carries ±${input.force.uncertaintyPercent}% from the cutting model; the margin inherits that band.`,
    );
  }
  if (input.jawHeight != null && input.gripDepth > input.jawHeight) {
    assumptions.push(
      `Grip depth ${input.gripDepth.toFixed(3)}" exceeds the ${input.jawHeight.toFixed(3)}" jaw height — contact area has been capped at the jaw face.`,
    );
  }

  return {
    verdict,
    margin,
    resistingForce: Number(resisting.toFixed(0)),
    frictionComponent: Number(frictionComponent.toFixed(0)),
    stopComponent: Number(stopComponent.toFixed(0)),
    appliedLoad: applied,
    contactArea,
    contactPressure,
    governingMode,
    slidingMargin,
    tippingMargin,
    appliedMoment,
    resistingMoment,
    recommendedGripDepth: recommendedGrip,
    recommendedRadialEngagement: recommendedEngagement,
    method: HOLDING_MODEL_VERSION,
    inputs: baseInputs(input, contactArea, friction.mu),
    assumptions,
    missingInputs: missing,
    primaryRisk,
    recommendations,
    developmentAnalysis: true,
  };
}

function baseInputs(input: HoldingMarginInput, contactArea: number | null, mu: number): CalculationInput[] {
  const rows: CalculationInput[] = [
    { label: "Clamping force", value: input.clampForce == null ? "not recorded" : `${input.clampForce.toLocaleString()} lbf` },
    { label: "Jaw surface", value: `${JAW_SURFACE_LABEL[input.jawSurface]} (μ = ${mu.toFixed(2)})` },
    { label: "Grip depth", value: input.gripDepth == null ? "not defined" : `${input.gripDepth.toFixed(3)}"` },
    { label: "Grip length", value: input.gripLength == null ? "not defined" : `${input.gripLength.toFixed(3)}"` },
    { label: "Contact area", value: contactArea == null ? "not calculable" : `${contactArea.toFixed(3)} in² (both faces)` },
    { label: "Positive stop", value: input.hasPositiveStop ? "yes — machined seat or fixed stop" : "none" },
  ];
  if (input.force.ok) {
    rows.push({ label: "Cutting model", value: input.force.method });
  }
  return rows;
}

export const MARGIN_LABEL: Record<MarginVerdict, string> = {
  ADEQUATE: "Adequate",
  MARGINAL: "Marginal",
  INSUFFICIENT: "Insufficient",
  INDETERMINATE: "Indeterminate",
};
