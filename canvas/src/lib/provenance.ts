/**
 * Provenance is a non-negotiable primitive in CANVAS.
 *
 * Manufacturing decisions are made from values of wildly different
 * trustworthiness — a spindle RPM off a manufacturer datasheet is not the same
 * kind of fact as an LLM's guess at a wall thickness from a photograph. Every
 * significant value carried through the system is wrapped so that the UI can
 * always answer "where did this come from, and how much should I trust it?"
 *
 * See /docs/MANUFACTURING_SAFETY.md.
 */

export const SOURCES = [
  "USER", // typed or confirmed by a human operator
  "MEASURED", // recorded through a metrology session
  "MANUFACTURER", // machine/tool/workholding vendor data
  "CALCULATED", // deterministic engine output (CAM, cost, geometry)
  "SIMULATION", // produced by a simulation run
  "AI_INFERENCE", // model inference — never treat as engineering truth
  "STANDARD", // published standard (bearing table, thread table, stock size)
  "DEFAULT", // system default that nobody has looked at yet
] as const;

export type Source = (typeof SOURCES)[number];

/** Ordered weakest → strongest. Used for gating, not for arithmetic. */
export const CONFIDENCE = ["UNKNOWN", "LOW", "MEDIUM", "HIGH", "VERIFIED"] as const;
export type Confidence = (typeof CONFIDENCE)[number];

export interface Provenanced<T> {
  value: T | null;
  source: Source;
  confidence: Confidence;
  /** True only once a human has explicitly signed off on this value. */
  confirmedByUser: boolean;
  /** Free-text rationale — shown in the provenance popover. */
  note?: string;
  /** Numeric model confidence, 0–1, only meaningful for AI_INFERENCE. */
  score?: number;
}

export function value<T>(
  v: T | null,
  source: Source,
  confidence: Confidence,
  extra: Partial<Omit<Provenanced<T>, "value" | "source" | "confidence">> = {},
): Provenanced<T> {
  return {
    value: v,
    source,
    confidence,
    confirmedByUser: extra.confirmedByUser ?? source === "USER",
    note: extra.note,
    score: extra.score,
  };
}

export const unknown = <T>(note?: string): Provenanced<T> =>
  value<T>(null, "DEFAULT", "UNKNOWN", { note });

export const userValue = <T>(v: T): Provenanced<T> =>
  value(v, "USER", "VERIFIED", { confirmedByUser: true });

export const measured = <T>(v: T, note?: string): Provenanced<T> =>
  value(v, "MEASURED", "HIGH", { note, confirmedByUser: true });

export const inferred = <T>(v: T, score: number, note?: string): Provenanced<T> =>
  value(v, "AI_INFERENCE", score >= 0.85 ? "MEDIUM" : "LOW", { score, note });

export const calculated = <T>(v: T, note?: string): Provenanced<T> =>
  value(v, "CALCULATED", "MEDIUM", { note });

export const manufacturerSpec = <T>(v: T, note?: string): Provenanced<T> =>
  value(v, "MANUFACTURER", "VERIFIED", { note, confirmedByUser: true });

/**
 * A value is safe to gate a manufacturing decision on only when a human has
 * confirmed it or it came from a source that is verifiable outside CANVAS.
 * AI inference NEVER satisfies this, at any score.
 */
export function isEngineeringGrade(p: Provenanced<unknown>): boolean {
  if (p.value === null || p.value === undefined) return false;
  if (p.source === "AI_INFERENCE") return p.confirmedByUser;
  return p.confirmedByUser || p.confidence === "VERIFIED" || p.confidence === "HIGH";
}

export const SOURCE_LABEL: Record<Source, string> = {
  USER: "User provided",
  MEASURED: "Measured",
  MANUFACTURER: "Manufacturer data",
  CALCULATED: "Calculated",
  SIMULATION: "Simulation result",
  AI_INFERENCE: "AI suggestion",
  STANDARD: "Published standard",
  DEFAULT: "System default",
};
