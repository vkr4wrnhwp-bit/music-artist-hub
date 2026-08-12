/**
 * TURNING ANALYSES — grip, stickout, boring-bar reach, part-off.
 *
 * The verdict vocabulary is PASS | REVIEW | FAIL | UNKNOWN, and UNKNOWN is a
 * real answer: where an input is missing (clamp force, chuck RPM limit) the
 * analysis names it and stops, because a guessed clamp force is worse than
 * none. All of these are DEVELOPMENT ANALYSIS — none has been validated
 * against physical testing — and each result carries that flag
 * non-optionally, the same pattern as the mill holding-margin model.
 */

export type TurnVerdict = "PASS" | "REVIEW" | "FAIL" | "UNKNOWN";

export interface TurnAnalysis {
  verdict: TurnVerdict;
  detail: string;
  recommendations: string[];
  missingInputs: string[];
  assumptions: string[];
  developmentAnalysis: true;
}

/* ---------------- Chuck grip ---------------- */

export function assessChuckGrip(input: {
  gripDiameter: number;
  gripLength: number;
  jawMaterial: "HARD" | "SOFT_MACHINED" | null;
  serrated: boolean | null;
  clampForceLbf: number | null;
  stickout: number;
  chuckMaxRpm: number | null;
  programmedMaxRpm: number | null;
}): TurnAnalysis {
  const missing: string[] = [];
  const recs: string[] = [];
  if (input.clampForceLbf === null) missing.push("Clamp force not recorded — the chuck's actual hydraulic setting, not the catalogue maximum.");
  if (input.chuckMaxRpm === null) missing.push("Chuck RPM limit not recorded.");

  const gripRatio = input.gripLength / Math.max(1e-6, input.gripDiameter);
  const stickRatio = input.stickout / Math.max(1e-6, input.gripDiameter);

  if (input.programmedMaxRpm !== null && input.chuckMaxRpm !== null && input.programmedMaxRpm > input.chuckMaxRpm) {
    return dev("FAIL", `Programmed maximum ${input.programmedMaxRpm} RPM exceeds the chuck's ${input.chuckMaxRpm} RPM limit. Centrifugal force unloads the jaws as speed rises.`, ["Lower the G50 clamp below the chuck limit"], missing);
  }
  if (gripRatio < 0.25) {
    recs.push("Increase grip length", "Machine soft jaws for full-contact grip");
    return dev("REVIEW", `Grip length is ${(gripRatio).toFixed(2)}× the grip diameter — a shallow bite for the recorded stickout.`, recs, missing);
  }
  if (missing.length > 0) {
    return dev("UNKNOWN", "Grip geometry looks workable, but the missing inputs below keep this from being a verdict. Record them; do not assume them.", recs, missing);
  }
  if (stickRatio > 4) {
    recs.push("Add tailstock support", "Reduce stickout");
    return dev("REVIEW", `Stickout is ${stickRatio.toFixed(1)}× the grip diameter with chuck-only support.`, recs, missing);
  }
  return dev("PASS", `Grip ${input.gripLength.toFixed(2)}" on Ø${input.gripDiameter.toFixed(3)}", clamp force and RPM limits recorded and consistent.`, recs, missing);
}

/* ---------------- Stickout / deflection ---------------- */

export function assessStickout(input: {
  unsupportedLength: number;
  diameter: number;
  tailstock: boolean;
}): TurnAnalysis & { ldRatio: number } {
  const ld = input.unsupportedLength / Math.max(1e-6, input.diameter);
  const base = {
    ldRatio: Number(ld.toFixed(1)),
    missingInputs: ["Cutting force not estimated — deflection is judged on L/D guideline only."],
    assumptions: ["Shop guideline: chuck-only work above 4:1 L/D wants support; above 8:1 it needs it."],
    developmentAnalysis: true as const,
  };
  if (input.tailstock) {
    return { ...base, verdict: ld > 12 ? "REVIEW" : "PASS", detail: `L/D ${ld.toFixed(1)}:1 with tailstock support.`, recommendations: ld > 12 ? ["Consider a steady rest for the mid-span"] : [] };
  }
  if (ld > 8) return { ...base, verdict: "FAIL", detail: `L/D ${ld.toFixed(1)}:1 unsupported. The part will push away and chatter before it cuts to size.`, recommendations: ["Add tailstock (needs a center-drilled end)", "Reduce stickout", "Support with a steady rest"] };
  if (ld > 4) return { ...base, verdict: "REVIEW", detail: `L/D ${ld.toFixed(1)}:1 unsupported — workable with light cuts, marginal for roughing.`, recommendations: ["Add tailstock", "Reduce cutting load", "Rough closer to the chuck first"] };
  return { ...base, verdict: "PASS", detail: `L/D ${ld.toFixed(1)}:1 unsupported — within the chuck-only guideline.`, recommendations: [] };
}

/* ---------------- Boring bar reach ---------------- */

export function assessBoringBar(input: {
  barDiameter: number;
  stickout: number;
  boreDepth: number;
  barMaterial: "STEEL" | "CARBIDE" | null;
}): TurnAnalysis & { ldRatio: number } {
  const ld = input.stickout / Math.max(1e-6, input.barDiameter);
  const limit = input.barMaterial === "CARBIDE" ? 6 : 4;
  const missing = input.barMaterial === null ? ["Bar material not recorded — steel guideline (4×D) assumed, carbide reaches 6×D."] : [];
  const base = {
    ldRatio: Number(ld.toFixed(1)),
    missingInputs: missing,
    assumptions: [`Guideline: ${limit}×D for a ${input.barMaterial ?? "steel (assumed)"} bar.`],
    developmentAnalysis: true as const,
  };
  if (input.stickout < input.boreDepth) {
    return { ...base, verdict: "FAIL", detail: `Bar stickout ${input.stickout.toFixed(2)}" cannot reach the ${input.boreDepth.toFixed(2)}" bore depth.`, recommendations: ["Longer bar", "Bore from both ends", "Different setup"] };
  }
  if (ld > limit * 1.5) return { ...base, verdict: "FAIL", detail: `${ld.toFixed(1)}×D stickout against a ${limit}×D guideline.`, recommendations: ["Larger-diameter bar", "Shorter stickout", "Damped bar", "Lower DOC and feed"] };
  if (ld > limit) return { ...base, verdict: "REVIEW", detail: `${ld.toFixed(1)}×D stickout against a ${limit}×D guideline — expect chatter at finishing tolerances.`, recommendations: ["Larger bar", "Shorter stickout", "Lower DOC", "Damped bar"] };
  return { ...base, verdict: "PASS", detail: `${ld.toFixed(1)}×D stickout within the ${limit}×D guideline.`, recommendations: [] };
}

/* ---------------- Part-off stability ---------------- */

export function assessPartOff(input: {
  cutoffZ: number;
  cutoffDiameter: number;
  distanceFromChuck: number;
  toolWidth: number | null;
  hasPartsCatcher: boolean;
  hasSubSpindle: boolean;
  tailstockActive: boolean;
}): TurnAnalysis {
  const missing: string[] = [];
  const recs: string[] = [];
  if (input.toolWidth === null) missing.push("Cutoff insert width not recorded.");
  if (input.tailstockActive) {
    return dev("FAIL", "Part-off with the tailstock engaged pinches the blade at separation.", ["Retract the tailstock before the cutoff", "Part off in a later operation"], missing);
  }
  const overhang = input.distanceFromChuck / Math.max(1e-6, input.cutoffDiameter);
  if (!input.hasPartsCatcher && !input.hasSubSpindle) {
    recs.push("Fit the parts catcher", "Catch by hand only with the spindle low and guards considered", "Accept the drop and the resulting face ding, stated");
  }
  if (overhang > 4) {
    recs.unshift("Move the cutoff closer to the chuck", "Support the free end");
    return dev("REVIEW", `Cutoff ${input.distanceFromChuck.toFixed(2)}" from the jaws on Ø${input.cutoffDiameter.toFixed(3)}" (${overhang.toFixed(1)}×D overhang). The far side is unsupported at separation.`, recs, missing);
  }
  const catchNote = input.hasPartsCatcher || input.hasSubSpindle ? "drop is managed" : "nothing manages the drop — the finished part falls";
  return dev(
    input.hasPartsCatcher || input.hasSubSpindle ? "PASS" : "REVIEW",
    `Cutoff at ${overhang.toFixed(1)}×D overhang; ${catchNote}.`,
    recs,
    missing,
  );
}

function dev(verdict: TurnVerdict, detail: string, recommendations: string[], missingInputs: string[]): TurnAnalysis {
  return { verdict, detail, recommendations, missingInputs, assumptions: [], developmentAnalysis: true };
}
