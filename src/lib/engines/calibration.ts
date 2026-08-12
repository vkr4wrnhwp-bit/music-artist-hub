/**
 * MACHINE CALIBRATION — shop-observed cycle times against CANVAS estimates.
 *
 * Methodology, stated: calibration is only claimed from MIN_SAMPLES or more
 * recorded cycles, and the factor is the MEDIAN of actual/estimated ratios —
 * a median because one interrupted cycle (door open, chip bird's nest,
 * operator lunch) must not poison the model. Below the threshold the
 * verdict is INSUFFICIENT CALIBRATION DATA, and one sample is an anecdote,
 * not a calibration.
 *
 * The factor is DISPLAY-ONLY in this phase: shown beside estimates as
 * shop-observed variance, never silently multiplied into them. Applying it
 * automatically comes only when the sample base and the spread justify it.
 * Calibration is SHOP_KNOWLEDGE — one machine's factor is never another
 * machine's truth.
 */

export const MIN_CALIBRATION_SAMPLES = 5;

export interface CalibrationSample {
  estimatedMinutes: number;
  actualMinutes: number;
}

export interface CalibrationSummary {
  samples: number;
  /** Median actual/estimated ratio. Null below the sample threshold. */
  medianFactor: number | null;
  /** Median signed variance in percent (+ = machine slower than estimate). */
  medianVariancePct: number | null;
  /** Spread: interquartile-ish range of ratios, when computable. */
  spreadPct: number | null;
  status: "CALIBRATED" | "INSUFFICIENT_DATA";
  statement: string;
}

export function summarizeCalibration(samples: CalibrationSample[]): CalibrationSummary {
  const ratios = samples
    .filter((s) => s.estimatedMinutes > 0 && s.actualMinutes > 0)
    .map((s) => s.actualMinutes / s.estimatedMinutes)
    .sort((a, b) => a - b);

  if (ratios.length < MIN_CALIBRATION_SAMPLES) {
    return {
      samples: ratios.length,
      medianFactor: null,
      medianVariancePct: null,
      spreadPct: null,
      status: "INSUFFICIENT_DATA",
      statement:
        ratios.length === 0
          ? "No recorded cycles. Record actual machine times to build calibration."
          : `${ratios.length} recorded cycle(s) — calibration is claimed from ${MIN_CALIBRATION_SAMPLES}. One sample is an anecdote, not a calibration.`,
    };
  }

  const median = ratios[Math.floor(ratios.length / 2)];
  const q1 = ratios[Math.floor(ratios.length * 0.25)];
  const q3 = ratios[Math.floor(ratios.length * 0.75)];
  const variancePct = (median - 1) * 100;

  return {
    samples: ratios.length,
    medianFactor: Number(median.toFixed(3)),
    medianVariancePct: Number(variancePct.toFixed(1)),
    spreadPct: Number(((q3 - q1) * 100).toFixed(1)),
    status: "CALIBRATED",
    statement: `Calibrated from ${ratios.length} recorded cycles: this machine runs ${Math.abs(variancePct).toFixed(1)}% ${variancePct >= 0 ? "slower" : "faster"} than the estimate (median). Shown beside estimates — not yet applied to them.`,
  };
}
