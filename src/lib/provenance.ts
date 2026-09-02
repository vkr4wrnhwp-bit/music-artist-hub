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
  /** Free-text rationale — shown in the provenance panel. */
  note?: string;
  /** Numeric model confidence, 0–1, only meaningful for AI_INFERENCE. */
  score?: number;

  /*
   * The rest of the chain of custody principle 4 names: "where relevant,
   * timestamp, instrument, method and uncertainty".
   *
   * All optional, and all left UNSET unless a write site actually recorded
   * them. Defaulting `recordedAt` to now, or `recordedBy` to whoever happens
   * to be looking at the screen, would fabricate a chain of custody for a
   * value nobody stamped — which is worse than admitting there isn't one.
   */

  /** How the value was arrived at. "Part responsibility interview", "ISO 286". */
  method?: string;
  /** ISO 8601. When it was recorded, not when it was read. */
  recordedAt?: string;
  /**
   * Who recorded it, as a display-name SNAPSHOT rather than a user id. The
   * intent is stored as a JSON document, so a snapshot survives the user row
   * the way a disagreement's captured position survives a recompute.
   */
  recordedBy?: string;
  /** The instrument, where a reading came from one. */
  instrument?: string;
  /** Measurement uncertainty, in the value's own units. */
  uncertainty?: number;
  /** Which version of a deterministic engine produced it. */
  calculationVersion?: string;
}

export function value<T>(
  v: T | null,
  source: Source,
  confidence: Confidence,
  extra: Partial<Omit<Provenanced<T>, "value" | "source" | "confidence">> = {},
): Provenanced<T> {
  // Spread `extra` rather than picking two fields out of it: the picked-field
  // form silently dropped everything else a caller passed, so a write site
  // that recorded a method or a timestamp had it discarded on the way in.
  return {
    ...extra,
    value: v,
    source,
    confidence,
    confirmedByUser: extra.confirmedByUser ?? source === "USER",
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

export const calculated = <T>(v: T, note?: string, method?: string): Provenanced<T> =>
  value(v, "CALCULATED", "MEDIUM", { note, method });

export const manufacturerSpec = <T>(v: T, note?: string): Provenanced<T> =>
  value(v, "MANUFACTURER", "VERIFIED", { note, confirmedByUser: true });

/**
 * Can this source stand on its own, or does it need a human?
 *
 * True means the value is checkable outside CANVAS — against the operator
 * who typed it, an instrument, a vendor datasheet, a published standard.
 * False means it is CANVAS talking to itself: a model's guess, a
 * simulation, a derived number, a default nobody has looked at. Those
 * become engineering grade only when a named human signs off.
 *
 * Keyed by Source so a new entry in the vocabulary has to be decided here
 * rather than inheriting whatever the last branch happened to do.
 */
const VERIFIABLE_OUTSIDE_CANVAS: Record<Source, boolean> = {
  USER: true,
  MEASURED: true,
  MANUFACTURER: true,
  STANDARD: true,
  // Locked principle 3. Never true, at any score.
  AI_INFERENCE: false,
  // A simulation is not a measurement, and a derived number is not evidence
  // about the world — both are only as good as what went into them.
  SIMULATION: false,
  CALCULATED: false,
  // "A system default that nobody has looked at yet" cannot certify
  // anything, whatever confidence a caller attaches to it.
  DEFAULT: false,
};

/**
 * A value is safe to gate a manufacturing decision on only when a human has
 * confirmed it or it came from a source that is verifiable outside CANVAS.
 * AI inference NEVER satisfies this, at any score.
 */
export function isEngineeringGrade(p: Provenanced<unknown>): boolean {
  if (p.value === null || p.value === undefined) return false;
  if (p.confirmedByUser) return true;
  if (!VERIFIABLE_OUTSIDE_CANVAS[p.source]) return false;
  return p.confidence === "VERIFIED" || p.confidence === "HIGH";
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

/* ------------------------------------------------------------------ */
/* The provenance panel                                                */
/* ------------------------------------------------------------------ */

export interface ProvenanceRow {
  label: string;
  /** Null means NOT RECORDED. The UI must say so rather than omit the row. */
  value: string | null;
}

/**
 * The full chain of custody behind a value, as rows.
 *
 * FIXED LENGTH, deliberately. Every row is returned for every value, with an
 * explicit null where nothing was recorded, so the panel cannot quietly drop
 * a field it has no answer for. "Instrument — not recorded" is a fact a
 * machinist can act on; a missing row is one they will not notice.
 *
 * The last row is the one that matters most and is the reason this is a
 * function rather than markup: whether the value can satisfy a required gate
 * is answered by calling `isEngineeringGrade`, never by re-deriving the rule
 * here. That rule lives in one place.
 */
export function provenanceDetail(p: Provenanced<unknown>): ProvenanceRow[] {
  const has = (v: string | null | undefined) => (v && v.length > 0 ? v : null);
  return [
    { label: "Source", value: SOURCE_LABEL[p.source] },
    { label: "Confidence", value: p.confidence.toLowerCase() },
    { label: "Confirmed by a human", value: p.confirmedByUser ? "Yes" : "No" },
    { label: "Basis", value: has(p.note) },
    { label: "Method", value: has(p.method) },
    { label: "Calculation version", value: has(p.calculationVersion) },
    { label: "Recorded", value: has(p.recordedAt) },
    { label: "Recorded by", value: has(p.recordedBy) },
    { label: "Instrument", value: has(p.instrument) },
    {
      label: "Uncertainty",
      value: p.uncertainty === undefined || p.uncertainty === null ? null : `±${p.uncertainty}`,
    },
    {
      // Only for a model's own output. A score on a measured value would be
      // a number with no meaning behind it.
      label: "Model score",
      value: p.source === "AI_INFERENCE" && p.score !== undefined ? p.score.toFixed(2) : null,
    },
    {
      label: "Can satisfy a required gate",
      value: isEngineeringGrade(p) ? "Yes" : "No",
    },
  ];
}

/**
 * A value a named human signed off, at a stated time, by a stated method.
 *
 * Write sites were hand-rolling `userValue(x)`, which records that a human
 * provided it and nothing about who or when. This is the shape a chain of
 * custody actually needs.
 */
export const confirmedBy = <T>(v: T, by: string, at: Date, method: string): Provenanced<T> =>
  value(v, "USER", "VERIFIED", {
    confirmedByUser: true,
    recordedBy: by,
    recordedAt: at.toISOString(),
    method,
  });
