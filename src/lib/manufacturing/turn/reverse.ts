import type { ProfileSegment, RotationalProfile } from "./geometry";

/**
 * TURNING REVERSE ENGINEERING — a shaft measured on the bench, step by step.
 *
 * A rotational part is the friendliest thing in the shop to reverse
 * engineer: set it datum-face-down (or chuck-end-left on V-blocks) and it
 * is a sequence of diameters and lengths read front to back. This engine
 * turns those readings into a RotationalProfile with MEASURED provenance —
 * and nothing else. It never rounds a reading to a nominal (the nominal
 * engine SUGGESTS and a human rules), never invents a tolerance, and the
 * stock it proposes is labelled a suggestion until a human confirms it.
 *
 * Measurement order is the guided part: work from the datum face toward
 * the far end, one step at a time, because every Z position downstream is
 * referenced to that face. Re-measure the face and everything after it is
 * suspect — the mill RE flow says the same thing, and it is just as true
 * on a lathe.
 */

export interface TurnReading {
  /** Measured diameter, inches — a diameter, never a radius. */
  diameter: number;
  /** Axial length of this step from where the previous one ended. */
  length: number;
  /** Instrument uncertainty, from the metrology device record. Null = unrecorded. */
  uncertainty: number | null;
  instrument: string | null;
  /** Thread designation exactly as read from the gauge, e.g. "3/4-16 UNF". */
  thread?: string | null;
  internal?: boolean;
  /**
   * How the human ruled on the nominal suggestion for this reading.
   * NOMINAL = accepted a suggested standard value (resolvedDiameter holds it);
   * MEASURED = keep the reading as-is. Absent = not ruled on yet.
   */
  resolution?: "NOMINAL" | "MEASURED" | null;
  resolvedDiameter?: number | null;
}

/** Common cold-finished bar diameters, inches. A stock SUGGESTION list, not a claim. */
const BAR_STOCK = [0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1.0, 1.125, 1.25, 1.375, 1.5, 1.625, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.5, 4.0];
/** Cleanup so a bar with mill scale still cleans to the largest measured diameter. */
const CLEANUP = 1 / 16;
/** Facing + part-off allowance on length. */
const LENGTH_ALLOWANCE = 0.25;

export interface AssembledProfile {
  profile: RotationalProfile | null;
  issues: string[];
  /** Why the stock came out the way it did — a suggestion until confirmed. */
  stockNote: string | null;
}

export function assembleMeasuredProfile(readings: TurnReading[]): AssembledProfile {
  const issues: string[] = [];
  if (readings.length === 0) {
    return { profile: null, issues: ["No measurements recorded yet — start at the datum face."], stockNote: null };
  }

  let z = 0;
  const segments: ProfileSegment[] = [];
  readings.forEach((r, i) => {
    if (r.diameter <= 0 || r.length <= 0) {
      issues.push(`Step ${i + 1}: diameter and length must both be positive — reading skipped.`);
      return;
    }
    if (r.uncertainty === null) {
      issues.push(`Step ${i + 1} was recorded without an instrument — its uncertainty is unknown, and nominal matching is weaker for it.`);
    }
    const dia = r.resolution === "NOMINAL" && r.resolvedDiameter != null ? r.resolvedDiameter : r.diameter;
    segments.push({
      id: `m${i + 1}`,
      kind: r.thread ? "THREAD" : "CYLINDER",
      label: r.thread ? `Thread ${r.thread}` : `Step ${i + 1} ⌀${dia.toFixed(4)}`,
      zStart: Number(z.toFixed(4)),
      zEnd: Number((z + r.length).toFixed(4)),
      diameterStart: dia,
      diameterEnd: dia,
      internal: r.internal ?? false,
      thread: r.thread ?? undefined,
      functionalRole: r.thread ? "THREAD_EXTERNAL" : "NONE",
      critical: false,
      // A reading stays MEASURED until a human rules; accepting a nominal is
      // a USER act and the segment says so.
      source: r.resolution === "NOMINAL" ? "USER" : "MEASURED",
      confirmedByUser: r.resolution != null,
    });
    z += r.length;
  });

  if (segments.length === 0) return { profile: null, issues, stockNote: null };

  const maxDia = Math.max(...segments.filter((s) => !s.internal).map((s) => s.diameterStart));
  const bar = BAR_STOCK.find((b) => b >= maxDia + CLEANUP - 1e-9) ?? Number((Math.ceil((maxDia + CLEANUP) * 4) / 4).toFixed(3));
  const stockLength = Number((z + LENGTH_ALLOWANCE).toFixed(3));

  return {
    profile: {
      units: "IN",
      zZeroReference: "measured datum face",
      stockDiameter: bar,
      stockLength,
      barStock: true,
      segments,
    },
    issues,
    stockNote: `Stock ⌀${bar.toFixed(3)} × ${stockLength.toFixed(2)}" is a SUGGESTION: the next standard bar over the largest measured ⌀${maxDia.toFixed(4)} plus ${CLEANUP.toFixed(4)}" cleanup, with ${LENGTH_ALLOWANCE.toFixed(2)}" facing and part-off allowance. Confirm against what is actually on the rack before planning.`,
  };
}

/* ------------------------------------------------------------------ */
/* The guided part: what to measure next, and with what                */
/* ------------------------------------------------------------------ */

export interface TurnTask {
  step: number;
  instruction: string;
  instrumentHint: string;
  why: string;
}

export function nextTurnTask(readings: TurnReading[]): TurnTask {
  if (readings.length === 0) {
    return {
      step: 1,
      instruction: "Choose the datum face — the face the part locates from in service — and set the part on it. Measure the FIRST diameter behind that face and its length.",
      instrumentHint: "Micrometer on the diameter; caliper or depth micrometer on the length.",
      why: "Every Z position on a turned part is referenced to one face. Pick it first and every later reading has a home; pick it last and every reading moves.",
    };
  }
  const z = readings.reduce((t, r) => t + r.length, 0);
  return {
    step: readings.length + 1,
    instruction: `Measure the next step working away from the datum face: the diameter starting at Z${z.toFixed(3)} and how far it runs. If it is threaded, read the designation off a thread gauge — do not measure a thread OD with a micrometer and call it the size.`,
    instrumentHint: "Micrometer for the diameter; caliper/depth micrometer for the length; pitch gauge + ring gauge or wire method for threads.",
    why: "Steps are recorded front to back so each Z lands where the previous one ended. Skipping around loses the running dimension.",
  };
}
