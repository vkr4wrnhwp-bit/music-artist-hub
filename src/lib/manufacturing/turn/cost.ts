import type { RotationalProfile } from "./geometry";
import { overallLength } from "./geometry";
import type { CostAssumptions } from "@/lib/engines/cost";
import { DEFAULT_ASSUMPTIONS } from "@/lib/engines/cost";

/**
 * TURNING COST — bar economics derived from the rotational model.
 *
 * The generic cost engine (engines/cost.ts) already does the arithmetic
 * honestly: every line carries its basis. What turning changes is where
 * the assumptions COME FROM. Bar work has real structure a mill blank
 * does not:
 *
 * - the part-off kerf is consumed per part, and its width is a recorded
 *   property of the parting tool — where no parting tool is recorded the
 *   parts-per-bar figure is not computed, rather than guessed;
 * - the chuck remnant is the piece of every bar you cannot use; the grip
 *   length is recorded on the setup, the spindle-side margin is a stated
 *   assumption;
 * - utilization is COMPUTED from parts-per-bar, not assumed;
 * - cycle minutes come from the generated toolpaths, and setup hours are
 *   built from what the setup actually needs — including boring soft jaws
 *   when the recorded jaw set is not at the grip diameter yet.
 *
 * Everything else (rates, margins, scrap) stays a visible shop assumption.
 */

export const STANDARD_BAR_LENGTH_IN = 144; // 12 ft — the stated assumption
export const SPINDLE_REMNANT_MARGIN = 1.0; // beyond the grip, stated below

export interface TurnCostInput {
  profile: RotationalProfile;
  /** From the generated toolpaths — the real number, not an estimate. */
  cycleMinutes: number;
  /** Recorded parting tool width. Null = no parting tool recorded. */
  partOffKerf: number | null;
  gripLength: number | null;
  /** True when the setup's soft jaws still need boring for this grip. */
  softJawsNeedBoring: boolean;
  tailstock: boolean;
  materialCostPerPound?: number;
  materialDensity?: number;
}

export interface BarEconomics {
  barLengthIn: number;
  partLengthWithKerf: number | null;
  remnant: number | null;
  partsPerBar: number | null;
  /** Computed purchased→part utilization, not assumed. Null when not computable. */
  utilization: number | null;
  notes: string[];
  missingInputs: string[];
}

export function computeBarEconomics(input: TurnCostInput): BarEconomics {
  const notes: string[] = [];
  const missingInputs: string[] = [];
  const partLen = Math.max(overallLength(input.profile), input.profile.stockLength);

  let remnant: number | null = null;
  if (input.gripLength !== null && input.gripLength > 0) {
    remnant = Number((input.gripLength + SPINDLE_REMNANT_MARGIN).toFixed(2));
    notes.push(`Remnant = ${input.gripLength.toFixed(2)}" recorded grip + ${SPINDLE_REMNANT_MARGIN.toFixed(1)}" spindle-side margin (assumption, stated).`);
  } else {
    missingInputs.push("Grip length is not recorded — the bar remnant, and with it parts-per-bar, is not computed.");
  }

  let partWithKerf: number | null = null;
  if (input.partOffKerf !== null && input.partOffKerf > 0) {
    partWithKerf = Number((partLen + input.partOffKerf).toFixed(3));
    notes.push(`Each part consumes ${partLen.toFixed(2)}" + ${input.partOffKerf.toFixed(3)}" part-off kerf from the recorded parting tool.`);
  } else {
    missingInputs.push("No parting tool width is recorded — the kerf per part, and with it parts-per-bar, is not computed.");
  }

  let partsPerBar: number | null = null;
  let utilization: number | null = null;
  if (remnant !== null && partWithKerf !== null) {
    partsPerBar = Math.max(0, Math.floor((STANDARD_BAR_LENGTH_IN - remnant) / partWithKerf));
    if (partsPerBar > 0) {
      // Fraction of the purchased bar that becomes blanks (part + kerf).
      // The kerf itself is already in the per-part stock volume, so this
      // factor amortises only the remnant and the end drop — no double count.
      utilization = Number(((partsPerBar * partWithKerf) / STANDARD_BAR_LENGTH_IN).toFixed(3));
      notes.push(`${partsPerBar} parts per ${STANDARD_BAR_LENGTH_IN / 12} ft bar; the remnant and end drop spread ${(100 - utilization * 100).toFixed(1)}% of the bar across the lot. Computed, not assumed.`);
    } else {
      notes.push("The part is longer than a standard bar less the remnant — bar-feed economics do not apply.");
    }
  }

  return { barLengthIn: STANDARD_BAR_LENGTH_IN, partLengthWithKerf: partWithKerf, remnant, partsPerBar, utilization, notes, missingInputs };
}

export interface TurnAssumptionSet {
  assumptions: CostAssumptions;
  bar: BarEconomics;
  /** Where each turning-derived assumption came from. */
  basis: string[];
}

export function deriveTurnCostAssumptions(input: TurnCostInput): TurnAssumptionSet {
  const bar = computeBarEconomics(input);
  const basis: string[] = [];

  const partLen = Math.max(overallLength(input.profile), input.profile.stockLength);
  const d = input.profile.stockDiameter;
  const stockVolumePerPart = Number(((Math.PI / 4) * d * d * (bar.partLengthWithKerf ?? partLen)).toFixed(3));
  basis.push(`Stock volume = π/4 × ⌀${d.toFixed(3)}² × ${(bar.partLengthWithKerf ?? partLen).toFixed(2)}" ${bar.partLengthWithKerf ? "(incl. kerf)" : "(kerf unrecorded — volume excludes it)"}.`);

  // Setup built from what the setup needs, each adder named.
  let setupHours = 0.75;
  basis.push("Setup baseline 0.75 hr: chuck job, prove first part.");
  if (input.softJawsNeedBoring) {
    setupHours += 0.6;
    basis.push("+0.60 hr: the recorded soft jaw set is not at this grip diameter — boring jaws is part of this setup (see the soft jaws page).");
  }
  if (input.tailstock) {
    setupHours += 0.15;
    basis.push("+0.15 hr: tailstock engagement and center alignment.");
  }

  const utilization = bar.utilization ?? DEFAULT_ASSUMPTIONS.materialUtilization;
  if (bar.utilization === null) {
    basis.push(`Utilization falls back to the shop default ${(DEFAULT_ASSUMPTIONS.materialUtilization * 100).toFixed(0)}% — it could not be computed (see missing inputs).`);
  }

  basis.push(`Cycle ${input.cycleMinutes.toFixed(2)} min from the generated turning toolpaths — not an estimate typed into a field.`);

  return {
    assumptions: {
      ...DEFAULT_ASSUMPTIONS,
      materialCostPerPound: input.materialCostPerPound ?? DEFAULT_ASSUMPTIONS.materialCostPerPound,
      materialDensity: input.materialDensity ?? DEFAULT_ASSUMPTIONS.materialDensity,
      stockVolumePerPart,
      materialUtilization: utilization,
      setupHours: Number(setupHours.toFixed(2)),
      cycleMinutes: input.cycleMinutes,
    },
    bar,
    basis,
  };
}
