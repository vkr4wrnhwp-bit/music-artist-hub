/**
 * ROI / CAPACITY — deterministic arithmetic over ESTIMATED inputs.
 *
 * Every figure descends from the cycle-time estimate, so every figure is
 * ESTIMATED and says so. Assumptions ride along; nothing here implies a
 * guaranteed saving — recovered machine hours are capacity, and capacity
 * is only money if the shop fills it.
 */

export interface RoiInput {
  currentCycleMinutes: number;
  proposedCycleMinutes: number;
  batchQuantity: number;
  annualQuantity: number;
  /** $/hr from shop settings. Null = no dollar figure, not a default. */
  machineRatePerHour: number | null;
}

export interface RoiResult {
  savedSecondsPerPart: number;
  savedHoursPerBatch: number;
  annualMachineHoursRecovered: number;
  /** Null when no shop rate is configured — absent, never invented. */
  estimatedAnnualCapacityValue: number | null;
  assumptions: string[];
  estimated: true;
}

export function computeRoi(input: RoiInput): RoiResult {
  const savedMin = Math.max(0, input.currentCycleMinutes - input.proposedCycleMinutes);
  const batch = Math.max(1, Math.floor(input.batchQuantity));
  const annual = Math.max(0, Math.floor(input.annualQuantity));
  const savedHoursPerBatch = (savedMin * batch) / 60;
  const annualHours = (savedMin * annual) / 60;

  return {
    savedSecondsPerPart: Number((savedMin * 60).toFixed(1)),
    savedHoursPerBatch: Number(savedHoursPerBatch.toFixed(1)),
    annualMachineHoursRecovered: Number(annualHours.toFixed(1)),
    estimatedAnnualCapacityValue:
      input.machineRatePerHour !== null ? Number((annualHours * input.machineRatePerHour).toFixed(0)) : null,
    assumptions: [
      "Cycle figures are ESTIMATED from the same model as the analyzer — no acceleration model unless the machine records one.",
      "Recovered hours are capacity, not revenue; they are worth money only if the spindle time is refilled.",
      ...(input.machineRatePerHour === null
        ? ["No shop machine rate configured — no dollar figure is shown rather than assuming one."]
        : [`Valued at the shop's configured $${input.machineRatePerHour}/hr machine rate.`]),
    ],
    estimated: true,
  };
}
