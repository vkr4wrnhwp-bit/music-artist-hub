/**
 * CUTTING FORCE — CANVAS Cutting Model v0.2 (Kienzle specific-force)
 *
 * This is a deterministic engineering service. No part of it consults a
 * language model, and nothing downstream is permitted to invent a force value
 * when this module declines to produce one.
 *
 * The model is Kienzle, which is the standard published specific-cutting-force
 * formulation and is chosen here specifically because it is traceable: the
 * material coefficients come from published machining data rather than from
 * anything CANVAS made up, and every result carries the inputs and assumptions
 * that produced it so a machinist can disagree with the arithmetic rather than
 * with a bare number.
 *
 *   kc(h) = kc1.1 · h^(-mc)              specific cutting force at chip thickness h
 *   Fc    = kc(h) · ap · h               tangential force on one engaged tooth
 *   hm    = 360·ae·fz / (π·D·φs)         average chip thickness over the arc
 *   zc    = z · φs / 360                 teeth engaged at any instant
 *
 * WHAT THIS MODEL IS NOT
 *
 * It is a rigid-body estimate of steady-state orthogonal cutting. It does not
 * model tool deflection, built-up edge, chip packing, re-cutting, entry shock,
 * runout, or any dynamic (chatter) behaviour. Interrupted cuts and plunging
 * entries produce peaks well above what this returns. Treat the output as a
 * defensible basis for ranking and sizing decisions, not as a certified load.
 *
 * See /docs/MANUFACTURING_SAFETY.md.
 */

import type { Confidence } from "@/lib/provenance";

export const CUTTING_MODEL_VERSION = "CANVAS Cutting Model v0.2 (Kienzle)";

/* ------------------------------------------------------------------ */
/* Material coefficients                                               */
/* ------------------------------------------------------------------ */

/**
 * Published Kienzle coefficients. kc1.1 is the specific cutting force at a
 * 1 mm × 1 mm chip, in N/mm²; mc is the chip-thickness exponent.
 *
 * These are representative values for the family, not certified values for a
 * specific heat or supplier. A shop that has measured its own material should
 * override them, and the result records which coefficient set was used.
 */
export interface MaterialCuttingData {
  key: string;
  label: string;
  /** Specific cutting force at h = 1 mm, N/mm². */
  kc11: number;
  /** Chip thickness exponent, dimensionless. */
  mc: number;
  /**
   * Radial (perpendicular) force as a fraction of tangential. Tougher and more
   * work-hardening materials push the tool away harder for the same tangential
   * load, which is what actually tries to move the part in the vise.
   */
  radialRatio: number;
  note?: string;
}

export const MATERIAL_CUTTING_DATA: MaterialCuttingData[] = [
  { key: "ALUMINIUM_WROUGHT", label: "Wrought aluminium (6061, 7075)", kc11: 800, mc: 0.23, radialRatio: 0.35 },
  { key: "ALUMINIUM_CAST", label: "Cast aluminium", kc11: 600, mc: 0.25, radialRatio: 0.35 },
  { key: "BRASS", label: "Brass", kc11: 800, mc: 0.2, radialRatio: 0.3 },
  { key: "BRONZE", label: "Bronze", kc11: 1200, mc: 0.25, radialRatio: 0.35 },
  { key: "COPPER", label: "Copper", kc11: 1000, mc: 0.25, radialRatio: 0.4 },
  { key: "STEEL_LOW_CARBON", label: "Low carbon steel (1018, A36)", kc11: 1780, mc: 0.25, radialRatio: 0.45 },
  { key: "STEEL_ALLOY", label: "Alloy steel (4140, 4340)", kc11: 2100, mc: 0.26, radialRatio: 0.45 },
  { key: "STEEL_TOOL", label: "Tool steel (A2, D2, O1)", kc11: 2500, mc: 0.26, radialRatio: 0.5 },
  { key: "STAINLESS_AUSTENITIC", label: "Austenitic stainless (304, 316)", kc11: 2350, mc: 0.21, radialRatio: 0.55, note: "Work hardens rapidly; dwelling raises force sharply." },
  { key: "STAINLESS_PH", label: "Precipitation hardening stainless (17-4)", kc11: 2400, mc: 0.24, radialRatio: 0.5 },
  { key: "CAST_IRON", label: "Grey cast iron", kc11: 1160, mc: 0.26, radialRatio: 0.35 },
  { key: "TITANIUM", label: "Titanium (Ti-6Al-4V)", kc11: 1400, mc: 0.23, radialRatio: 0.6, note: "Low modulus and poor conductivity; force is not the limiting factor, heat is." },
  { key: "NICKEL_ALLOY", label: "Nickel alloy (Inconel 718)", kc11: 2700, mc: 0.24, radialRatio: 0.6 },
  { key: "PLASTIC", label: "Engineering plastic", kc11: 200, mc: 0.2, radialRatio: 0.3 },
];

const BY_KEY = new Map(MATERIAL_CUTTING_DATA.map((m) => [m.key, m]));

/**
 * Resolves a shop material record onto a coefficient set. Returns null rather
 * than guessing — an unrecognised material must surface as a missing input,
 * because silently substituting aluminium for Inconel is exactly the failure
 * this whole module exists to prevent.
 */
export function materialCuttingData(family: string | null | undefined): MaterialCuttingData | null {
  if (!family) return null;
  const key = family.toUpperCase().replace(/[\s-]+/g, "_");
  if (BY_KEY.has(key)) return BY_KEY.get(key)!;

  // Accept the coarser family names the material library uses.
  const aliases: Record<string, string> = {
    ALUMINIUM: "ALUMINIUM_WROUGHT",
    ALUMINUM: "ALUMINIUM_WROUGHT",
    STEEL: "STEEL_LOW_CARBON",
    STAINLESS: "STAINLESS_AUSTENITIC",
    STAINLESS_STEEL: "STAINLESS_AUSTENITIC",
    IRON: "CAST_IRON",
    NICKEL: "NICKEL_ALLOY",
    PLASTICS: "PLASTIC",
    POLYMER: "PLASTIC",
  };
  const aliased = aliases[key];
  return aliased ? (BY_KEY.get(aliased) ?? null) : null;
}

/* ------------------------------------------------------------------ */
/* Tool condition                                                      */
/* ------------------------------------------------------------------ */

export const TOOL_CONDITIONS = ["NEW", "GOOD", "WORN", "REGRIND", "UNKNOWN"] as const;
export type ToolCondition = (typeof TOOL_CONDITIONS)[number];

/**
 * A dull tool does not cut, it ploughs. Edge rounding raises specific cutting
 * force substantially, and it is the single most common reason a setup that
 * calculated fine throws a part on the eightieth piece.
 */
const CONDITION_FACTOR: Record<ToolCondition, number> = {
  NEW: 1.0,
  GOOD: 1.1,
  WORN: 1.4,
  REGRIND: 1.2,
  UNKNOWN: 1.25,
};

const CONDITION_NOTE: Record<ToolCondition, string> = {
  NEW: "New edge — no wear allowance applied.",
  GOOD: "Serviceable edge — 10% wear allowance applied.",
  WORN: "Worn edge — 40% wear allowance applied. A dull tool ploughs rather than cuts.",
  REGRIND: "Reground edge — 20% allowance for edge geometry departing from new.",
  UNKNOWN: "Tool condition not recorded — 25% allowance applied on the assumption of a part-worn edge.",
};

/* ------------------------------------------------------------------ */
/* Interface                                                           */
/* ------------------------------------------------------------------ */

export interface CuttingForceInput {
  /** Material family key, resolved against MATERIAL_CUTTING_DATA. */
  materialFamily: string | null;
  /** Cutter diameter, inches. */
  toolDiameter: number | null;
  flutes: number | null;
  /** Axial depth of cut, inches. */
  axialDepth: number | null;
  /** Radial width of cut, inches. */
  radialWidth: number | null;
  /** Feed per tooth, inches. */
  chipload: number | null;
  /** Spindle speed, rev/min. */
  rpm: number | null;
  toolCondition: ToolCondition;
  /** Helix angle, degrees. Drives how much of the load is thrown up the Z axis. */
  helixAngle?: number | null;
  /** Overrides the material table when a shop has measured its own stock. */
  overrideKc11?: number | null;
}

export interface CalculationInput {
  label: string;
  value: string;
}

export interface CuttingForceEstimate {
  ok: boolean;
  /** Average tangential (cutting) force over the engagement arc, lbf. */
  tangential: number | null;
  /** Average radial force — the component that tries to move the part, lbf. */
  radial: number | null;
  /** Axial force along the spindle, lbf. */
  axial: number | null;
  /** Resultant of the three components, lbf. */
  resultant: number | null;
  /**
   * Peak tangential force at maximum instantaneous chip thickness. This is what
   * the workholding actually has to survive, not the average.
   */
  peakTangential: number | null;
  /** Spindle power at the cut, hp. */
  spindlePower: number | null;
  /** Metal removal rate, in³/min. */
  materialRemovalRate: number | null;
  /** Table feed, in/min. */
  feedRate: number | null;
  /** Average chip thickness, inches. */
  averageChipThickness: number | null;
  /** Radial engagement arc, degrees. */
  engagementAngle: number | null;

  method: string;
  materialData: MaterialCuttingData | null;
  inputs: CalculationInput[];
  assumptions: string[];
  /** Symmetric uncertainty band on the reported forces, percent. */
  uncertaintyPercent: number | null;
  confidence: Confidence;
  /** Inputs the model required and did not receive. */
  missingInputs: string[];
  /** Conditions the model is being asked to cover that it does not cover well. */
  cautions: string[];
}

const N_TO_LBF = 0.224809;
const MM_PER_IN = 25.4;

/* ------------------------------------------------------------------ */
/* The calculation                                                     */
/* ------------------------------------------------------------------ */

export function estimateCuttingForce(input: CuttingForceInput): CuttingForceEstimate {
  const missing: string[] = [];
  const cautions: string[] = [];

  const material = input.overrideKc11
    ? { key: "SHOP_MEASURED", label: "Shop-measured coefficient", kc11: input.overrideKc11, mc: 0.25, radialRatio: 0.45 }
    : materialCuttingData(input.materialFamily);

  if (!material) {
    missing.push(
      input.materialFamily
        ? `No cutting coefficients on file for material family "${input.materialFamily}"`
        : "Material not assigned — cutting force cannot be estimated",
    );
  }
  if (input.toolDiameter == null || input.toolDiameter <= 0) missing.push("Tool diameter unknown");
  if (input.flutes == null || input.flutes <= 0) missing.push("Flute count unknown");
  if (input.axialDepth == null || input.axialDepth <= 0) missing.push("Axial depth of cut not defined");
  if (input.radialWidth == null || input.radialWidth <= 0) missing.push("Radial width of cut not defined");
  if (input.chipload == null || input.chipload <= 0) missing.push("Chip load (feed per tooth) not defined");
  if (input.rpm == null || input.rpm <= 0) missing.push("Spindle speed not defined");

  const empty = (): CuttingForceEstimate => ({
    ok: false,
    tangential: null,
    radial: null,
    axial: null,
    resultant: null,
    peakTangential: null,
    spindlePower: null,
    materialRemovalRate: null,
    feedRate: null,
    averageChipThickness: null,
    engagementAngle: null,
    method: CUTTING_MODEL_VERSION,
    materialData: material,
    inputs: [],
    assumptions: [],
    uncertaintyPercent: null,
    confidence: "UNKNOWN",
    missingInputs: missing,
    cautions,
  });

  if (missing.length > 0 || !material) return empty();

  const D = input.toolDiameter!;
  const z = input.flutes!;
  const ap = input.axialDepth!;
  const ae = Math.min(input.radialWidth!, D);
  const fz = input.chipload!;
  const rpm = input.rpm!;

  if (input.radialWidth! > D) {
    cautions.push(
      `Radial width ${input.radialWidth!.toFixed(3)}" exceeds the ${D.toFixed(3)}" cutter diameter. The cut has been treated as a full slot; a wider trench is more than one pass.`,
    );
  }

  /* ---- Engagement geometry ---- */

  // Arc of contact. Full immersion (slotting) is 180°.
  const immersion = Math.min(1, ae / D);
  const phiRad = Math.acos(Math.max(-1, Math.min(1, 1 - 2 * immersion)));
  const phiDeg = (phiRad * 180) / Math.PI;

  // Average chip thickness across the arc, and the peak at maximum immersion.
  const hmIn = (360 * ae * fz) / (Math.PI * D * Math.max(phiDeg, 1e-6));
  const hMaxIn = fz * Math.sin(Math.min(phiRad, Math.PI / 2));
  const hmMm = hmIn * MM_PER_IN;
  const hMaxMm = Math.max(hMaxIn * MM_PER_IN, 1e-4);

  if (hmIn < 0.0008) {
    cautions.push(
      `Average chip thickness is ${hmIn.toFixed(5)}" — below roughly 0.001" the edge burnishes rather than cuts, force rises instead of falling, and this model reads low.`,
    );
  }

  /* ---- Kienzle ---- */

  const conditionFactor = CONDITION_FACTOR[input.toolCondition];
  const kcAvg = material.kc11 * Math.pow(Math.max(hmMm, 1e-4), -material.mc) * conditionFactor;
  const kcPeak = material.kc11 * Math.pow(hMaxMm, -material.mc) * conditionFactor;

  // Teeth engaged at any instant. Below one, the cut is intermittent — every
  // tooth enters and leaves, and the average understates what the part feels.
  const teethEngaged = (z * phiDeg) / 360;
  if (teethEngaged < 1) {
    cautions.push(
      `Only ${teethEngaged.toFixed(2)} of a tooth is in the cut at any instant. The cut is interrupted, so peak load rather than average load governs the workholding.`,
    );
  }

  const apMm = ap * MM_PER_IN;

  // Fc = kc · b · h, summed over the teeth in cut.
  const tangentialN = kcAvg * apMm * hmMm * Math.max(teethEngaged, 0);

  // The worst instant is one tooth at maximum chip thickness while the rest of
  // the teeth in the cut carry their average share. Taking a single tooth alone
  // understates a slotting cut, where two or three teeth are engaged at once;
  // taking every tooth at maximum overstates it, because they cannot all be at
  // maximum immersion simultaneously.
  const teethAtPeak = Math.max(1, Math.ceil(teethEngaged));
  const perToothAverageN = teethEngaged > 0 ? tangentialN / teethEngaged : 0;
  const peakTangentialN = kcPeak * apMm * hMaxMm + (teethAtPeak - 1) * perToothAverageN;

  const radialN = tangentialN * material.radialRatio;

  // Axial component from the helix. A right-hand helix in a conventional
  // orientation pulls the part upward, which is why helix matters to a vise.
  const helix = input.helixAngle ?? 30;
  const axialN = tangentialN * Math.tan((helix * Math.PI) / 180) * 0.5;

  const resultantN = Math.sqrt(tangentialN ** 2 + radialN ** 2 + axialN ** 2);

  /* ---- Derived process values ---- */

  const feedRate = rpm * z * fz; // in/min
  const mrr = ae * ap * feedRate; // in³/min
  const surfaceSpeed = (Math.PI * D * rpm) / 12; // sfm
  // Pc = Fc · vc, converted from lbf·ft/min to hp.
  const spindlePower = (tangentialN * N_TO_LBF * surfaceSpeed) / 33000;

  /* ---- Uncertainty ---- */

  // Baseline model uncertainty for a steady-state rigid-body estimate against
  // measured data is around 25%. Everything that departs from the model's
  // assumptions widens it, and the band is reported rather than buried.
  let uncertainty = 25;
  const assumptions: string[] = [
    "Rigid tool, holder, spindle and fixture — no deflection modelled.",
    "Sharp, correctly-seated cutter running with no runout.",
    "Steady-state engagement — entry shock and exit burr loads are not modelled.",
    "Chips fully evacuated; no re-cutting.",
    `Radial force taken as ${(material.radialRatio * 100).toFixed(0)}% of tangential for ${material.label.toLowerCase()}.`,
    `Axial force from a ${helix.toFixed(0)}° helix, taken as half the tangential-times-tangent product.`,
    CONDITION_NOTE[input.toolCondition],
  ];

  if (input.toolCondition === "UNKNOWN") uncertainty += 10;
  if (input.toolCondition === "WORN") uncertainty += 10;
  if (input.helixAngle == null) {
    uncertainty += 5;
    assumptions.push("Helix angle not recorded on the tool; 30° assumed.");
  }
  if (teethEngaged < 1) uncertainty += 10;
  if (hmIn < 0.0008) uncertainty += 15;
  if (input.overrideKc11) {
    uncertainty -= 5;
    assumptions.push("Specific cutting force overridden with a shop-measured coefficient.");
  }
  if (material.note) assumptions.push(material.note);

  uncertainty = Math.max(15, Math.min(70, uncertainty));

  // Confidence never exceeds MEDIUM. This is a calculation from a published
  // model against representative coefficients — it is not a measurement, and
  // labelling it HIGH would let it satisfy gates it has no business satisfying.
  const confidence: Confidence = uncertainty <= 30 ? "MEDIUM" : uncertainty <= 45 ? "LOW" : "UNKNOWN";

  const lbf = (n: number) => Number((n * N_TO_LBF).toFixed(1));

  return {
    ok: true,
    tangential: lbf(tangentialN),
    radial: lbf(radialN),
    axial: lbf(axialN),
    resultant: lbf(resultantN),
    peakTangential: lbf(peakTangentialN),
    spindlePower: Number(spindlePower.toFixed(2)),
    materialRemovalRate: Number(mrr.toFixed(2)),
    feedRate: Number(feedRate.toFixed(1)),
    averageChipThickness: Number(hmIn.toFixed(5)),
    engagementAngle: Number(phiDeg.toFixed(1)),
    method: CUTTING_MODEL_VERSION,
    materialData: material,
    inputs: [
      { label: "Material", value: material.label },
      { label: "kc₁.₁", value: `${material.kc11} N/mm²` },
      { label: "mc", value: material.mc.toFixed(2) },
      { label: "Cutter", value: `${D.toFixed(4)}" ${z}-flute` },
      { label: "Axial depth (ap)", value: `${ap.toFixed(4)}"` },
      { label: "Radial width (ae)", value: `${ae.toFixed(4)}" (${(immersion * 100).toFixed(0)}% of D)` },
      { label: "Chip load (fz)", value: `${fz.toFixed(4)}"/tooth` },
      { label: "Spindle speed", value: `${Math.round(rpm)} rpm (${Math.round(surfaceSpeed)} sfm)` },
      { label: "Feed rate", value: `${feedRate.toFixed(1)} in/min` },
      { label: "Tool condition", value: input.toolCondition.toLowerCase() },
      { label: "Engagement arc", value: `${phiDeg.toFixed(1)}° (${teethEngaged.toFixed(2)} teeth in cut)` },
      { label: "Average chip thickness", value: `${hmIn.toFixed(5)}"` },
    ],
    assumptions,
    uncertaintyPercent: uncertainty,
    confidence,
    missingInputs: [],
    cautions,
  };
}

/**
 * The load the workholding has to resist. Deliberately the peak rather than the
 * average, and deliberately including the radial component, because what throws
 * a part is the worst instant of the cut and not its mean.
 */
export function governingLateralLoad(e: CuttingForceEstimate): number | null {
  if (!e.ok || e.tangential === null || e.radial === null || e.peakTangential === null) return null;
  const peakRatio = e.peakTangential / Math.max(e.tangential, 0.01);
  const peakRadial = e.radial * peakRatio;
  return Number(Math.sqrt(e.peakTangential ** 2 + peakRadial ** 2).toFixed(1));
}
