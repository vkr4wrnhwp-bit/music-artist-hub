/**
 * WORKSPACE PANEL DATA
 *
 * The serialisable shapes the server hands to the workspace client tree.
 *
 * Every field here corresponds to something CANVAS actually stores or actually
 * computes, and the names say which. There is deliberately no `status`,
 * `progress`, `elapsed`, `confidence` or `pass` on any of these types — not
 * because they were forgotten, but because nothing in the data model produces
 * them, and a field that exists is a field a component will eventually fill in.
 *
 * If you are about to add one, check `prisma/schema.prisma` first. If the
 * column is not there, the value is not a fact.
 */

/** A metrology instrument the shop owns. From `MetrologyDevice`. */
export interface InstrumentInfo {
  description: string;
  deviceType: string;
  rangeMin: number | null;
  rangeMax: number | null;
  resolution: number;
  uncertainty: number;
  calibrated: boolean;
  /** ISO date, or null when no certificate date is recorded. */
  calibrationDue: string | null;
}

/** Output of `assessCapability()` — the gate no click can clear. */
export interface CapabilityInfo {
  verdict: string;
  label: string;
  reason: string;
  toleranceBand: number | null;
  consumedFraction: number | null;
  requiredUncertainty: number | null;
  bestInstrument: InstrumentInfo | null;
}

/**
 * A recorded measurement. `Measurement` stores a scalar, its uncertainty and
 * how many readings went into it — there are no coordinates, so nothing here
 * can place a probe point in the scene.
 */
export interface MeasurementInfo {
  id: string;
  label: string;
  value: number;
  units: string;
  uncertainty: number;
  repeatCount: number;
  /** PENDING | ACCEPTED_NOMINAL | KEPT_MEASURED | INVESTIGATING */
  resolution: string;
  /** Instrument description, or null when the reading was recorded without one. */
  instrument: string | null;
  operator: string | null;
  sessionId: string;
  sessionName: string;
  recordedAt: string;
  /** What the reading was taken from. Null on every seeded row — the UI does not set it yet. */
  datumLetter: string | null;
}

/** One line of the inspection plan. From `InspectionItem`. */
export interface InspectionItemInfo {
  label: string;
  nominal: number;
  plusTol: number;
  minusTol: number;
  method: string;
  deviceType: string | null;
}

/** An established or proposed datum. From `Datum`. */
export interface DatumInfo {
  letter: string;
  system: string;
  description: string;
  geometryType: string;
  accepted: boolean;
  featureId: string | null;
}

/**
 * Verification state for the INSPECTION view mode, computed server-side by
 * the same conformance rule the FAIR generator uses (`assessConformance`) on
 * the latest INSPECTION-session measurement. NOT_MEASURED and
 * CANNOT_DETERMINE are distinct states, not absences.
 */
export interface VerifyInfo {
  state: "CONFORMS" | "NONCONFORMS" | "NOT_MEASURED" | "CANNOT_DETERMINE";
  /** Why, when the state is not a clean pass/fail. */
  reason: string | null;
  /**
   * Signed departure beyond the violated LIMIT — not from nominal. Positive is
   * above the upper limit, negative below the lower. NONCONFORMS only.
   */
  departure: number | null;
  /**
   * The exact inputs `assessConformance` was given, carried so a UI can show
   * the reading, its nominal and its limits beside the verdict without
   * recomputing any of them.
   *
   * This exists because recomputation drifts. `compare()` in dimension.ts
   * resolves a nominal through `primaryDimension`, which accepts depth, radius
   * and width where the conformance engine accepts a diameter and nothing
   * else — so on a FACE it returns a confident deviation and band for a
   * feature the engine refuses to assess. `InspectionItem.nominal` is a third
   * number again, and on the seeded plan it frequently describes a different
   * characteristic than the feature it hangs off. One verdict beside a nominal
   * from a different source is how an inspector reads a bore result off a
   * drill size.
   *
   * Null whenever no inspection reading exists — NOT_MEASURED has nothing to
   * carry.
   */
  evidence: VerifyEvidence | null;
}

/** The measured reading and the limits it was judged against. All inches. */
export interface VerifyEvidence {
  /** `resolvedValue ?? measuredValue` — the same field the FAIR report reads. */
  value: number;
  /**
   * True when `value` is a resolved value rather than the raw reading — a
   * human accepted a nominal in place of what the instrument said. The two
   * are different claims and the panel labels them differently.
   */
  valueWasResolved: boolean;
  uncertainty: number;
  /**
   * The engine's nominal: the feature's diameter, or null when it has none.
   * Null means the engine returned CANNOT_DETERMINE for want of a nominal, and
   * a UI must not substitute a depth or a width to fill the gap.
   */
  nominal: number | null;
  /**
   * Limits from `feature.tolerance`, asymmetric by construction. Null when
   * there is no nominal to anchor them to EVEN IF a tolerance is stated —
   * which is why `tolerancePlus`/`toleranceMinus` travel separately. Printing
   * "no limits" for a characteristic whose drawing states ±0.002 is a lie
   * about the drawing, not a statement about the engine.
   */
  lo: number | null;
  hi: number | null;
  tolerancePlus: number | null;
  toleranceMinus: number | null;
  /** The device that took the reading. Not necessarily the best one on hand. */
  instrument: string | null;
  recordedAt: string;
  sessionName: string;
}

/** Everything the feature panel needs about one feature, precomputed server-side. */
export interface FeatureDetail {
  capability: CapabilityInfo | null;
  measurements: MeasurementInfo[];
  inspectionItem: InspectionItemInfo | null;
  verify: VerifyInfo;
}

/* ------------------------------------------------------------------ */
/* Operation runway                                                    */
/* ------------------------------------------------------------------ */

/**
 * One planned operation.
 *
 * There is no execution state on this type. `Operation` has no status column,
 * `OperationState` has no write sites, and there is no machine connection — so
 * COMPLETE / ACTIVE / NEXT / PENDING cannot be represented here honestly. What
 * IS real is the sequence, the tool, the feature, whether the deterministic CAM
 * engine produced a toolpath, and how long that toolpath takes.
 */
export interface RunwayOperation {
  id: string;
  setupId: string;
  sequence: number;
  label: string;
  type: string;
  toolNumber: number | null;
  toolDescription: string | null;
  featureId: string | null;
  featureLabel: string | null;
  /** Cycle time from the generated toolpath. Null when no toolpath exists. */
  cycleMinutes: number | null;
  moveCount: number | null;
  /** The CAM engine has no implementation for this operation type. */
  isPlaceholder: boolean;
  /** Why a toolpath could not be generated, verbatim from the engine. */
  error: string | null;
  warnings: string[];
}

export interface RunwaySetup {
  id: string;
  name: string;
  sequence: number;
  machine: string | null;
  workholding: string | null;
  /** SAFE | LIKELY_SAFE | REVIEW | HIGH_RISK | UNKNOWN */
  riskLevel: string | null;
  riskLabel: string | null;
  gripDepth: number | null;
  hasPositiveStop: boolean;
}

export interface RunwayData {
  setups: RunwaySetup[];
  operations: RunwayOperation[];
  /** Sum of generated toolpath cycle times. Excludes placeholder operations. */
  cycleMinutes: number;
  placeholderCount: number;
  workholding: {
    worstLevel: string | null;
    worstLabel: string | null;
    device: string | null;
    gripDepth: number | null;
    hasPositiveStop: boolean;
    /** The holding model is not validated against physical testing. */
    developmentAnalysis: boolean;
  };
  inspection: {
    hasPlan: boolean;
    itemCount: number;
    /** `InspectionResult` rows. There is no write path yet, so this is 0. */
    resultCount: number;
    measurementCount: number;
    pendingResolutionCount: number;
    criticalFeatureCount: number;
  };
  material: {
    name: string | null;
    condition: string | null;
    stockForm: string | null;
    stockSize: string | null;
    stockCondition: string | null;
  };
}

/** The single next action, from `nextActions()`. */
export interface NextActionInfo {
  action: string;
  reason: string;
  href: string | null;
  linkLabel: string | null;
  severity: "BLOCKING" | "REVIEW" | "IMPROVEMENT";
}
