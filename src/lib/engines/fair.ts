import type { Feature, Tolerance } from "@/lib/domain/features";
import { featureSummary, fmtTol } from "@/lib/domain/features";
import type { PartIntent } from "@/lib/domain/part-intent";

/**
 * AS9102 FIRST ARTICLE INSPECTION REPORT — deterministic assembly
 *
 * This engine fills AS9102 Forms 1–3 from records CANVAS actually holds. It
 * is a report generator, not an inspection: nothing here measures anything,
 * and no field is ever padded with a plausible value. A requirement the shop
 * has not recorded renders as REQUIRED — NOT ON FILE, because a FAIR with a
 * quietly invented certificate number is worse than an incomplete one — it
 * is the incomplete one that gets caught at audit.
 *
 * Two rules with teeth:
 *
 * 1. Only INSPECTION-mode measurement sessions feed Form 3. The demo shop's
 *    reverse-engineering readings were taken from the worn original
 *    component; presenting those as first-article results would be
 *    fabricating an inspection. The session mode is the evidence boundary.
 *
 * 2. Conformance is decided only when the arithmetic actually decides it:
 *    a recorded result, a stated tolerance, a single unambiguous nominal,
 *    and an instrument whose uncertainty can carry the verdict. Everything
 *    else is CANNOT_DETERMINE with the reason stated. A measurement inside
 *    the limits by less than its own uncertainty does not conform — it is
 *    unresolved, per the gauge maker's rule already used in
 *    inspection-capability.ts.
 */

export type FairField =
  | { state: "ON_FILE"; value: string }
  | { state: "NOT_ON_FILE"; requirement: string };

const onFile = (value: string): FairField => ({ state: "ON_FILE", value });
const missing = (requirement: string): FairField => ({ state: "NOT_ON_FILE", requirement });

export interface FairForm1 {
  fairNumber: string;
  partNumber: FairField;
  partName: FairField;
  revision: FairField;
  drawingNumber: FairField;
  drawingRevision: FairField;
  organization: FairField;
  serialNumber: FairField;
  purchaseOrder: FairField;
  supplierCode: FairField;
  detailOrAssembly: "DETAIL";
  fullOrPartial: "FULL";
  preparedBy: FairField;
}

export interface FairForm2Row {
  kind: "MATERIAL" | "SPECIAL_PROCESS" | "FUNCTIONAL_TEST";
  name: FairField;
  specification: FairField;
  supplier: FairField;
  certificateNumber: FairField;
}

export type ConformanceVerdict =
  | { verdict: "CONFORMS" }
  | { verdict: "NONCONFORMS"; departure: number; nonconformanceDoc: FairField }
  | { verdict: "CANNOT_DETERMINE"; reason: string };

export interface FairCharacteristic {
  charNumber: number;
  location: string;
  designator: "CRITICAL" | "";
  requirement: string;
  tolerance: string;
  result:
    | {
        state: "MEASURED";
        value: number;
        uncertainty: number;
        instrument: string;
        measuredAt: string;
        repeatCount: number;
      }
    | { state: "NOT_MEASURED" };
  conformance: ConformanceVerdict;
  inspectionMethod: FairField;
}

export interface FairReport {
  form1: FairForm1;
  form2: FairForm2Row[];
  form3: FairCharacteristic[];
  summary: {
    characteristics: number;
    measured: number;
    conforming: number;
    nonconforming: number;
    undetermined: number;
    fieldsNotOnFile: number;
  };
  generatedAtIso: string;
}

export interface FairInput {
  organizationName: string;
  partNumber: string | null;
  partName: string;
  revision: string;
  intent: PartIntent;
  features: Feature[];
  drawings: { title: string; sheetNumber: string | null }[];
  /** INSPECTION-mode measurements only. The caller enforces the session
   *  filter; this engine additionally refuses anything not so marked. */
  inspectionMeasurements: {
    featureId: string | null;
    sessionMode: string;
    value: number;
    uncertainty: number;
    instrument: string | null;
    measuredAt: string;
    repeatCount: number;
  }[];
  generatedAtIso: string;
  preparedBy: string | null;
}

export function buildFair(input: FairInput): FairReport {
  const form1: FairForm1 = {
    fairNumber: `FAIR-${input.partNumber ?? input.partName.replace(/\s+/g, "-").toUpperCase()}-${input.revision}`,
    partNumber: input.partNumber ? onFile(input.partNumber) : missing("Part number"),
    partName: onFile(input.partName),
    revision: onFile(input.revision),
    drawingNumber: input.drawings[0]
      ? onFile(input.drawings[0].sheetNumber ?? input.drawings[0].title)
      : missing("Drawing number — no drawing on file for this revision"),
    drawingRevision: input.drawings[0]
      ? onFile(input.revision)
      : missing("Drawing revision"),
    organization: onFile(input.organizationName),
    serialNumber: missing("Serial / lot number of the inspected article"),
    purchaseOrder: missing("Customer purchase order number"),
    supplierCode: missing("Customer-assigned supplier code"),
    detailOrAssembly: "DETAIL",
    fullOrPartial: "FULL",
    preparedBy: input.preparedBy ? onFile(input.preparedBy) : missing("Preparer identity"),
  };

  /* ---- Form 2 — material, processes, tests ---- */

  const matVal = input.intent.material.value;
  const condition = input.intent.materialCondition.value;
  const form2: FairForm2Row[] = [
    {
      kind: "MATERIAL",
      name: matVal && matVal.trim() !== ""
        ? onFile(condition ? `${matVal} · ${condition}` : matVal)
        : missing("Raw material identification"),
      specification: missing("Material specification (e.g. AMS/ASTM) — not recorded"),
      supplier: missing("Raw material supplier"),
      certificateNumber: missing("Material certification / test report number — no cert on file"),
    },
    // CANVAS has no special-process or functional-test records. The rows
    // exist so their absence is a visible statement, not a missing section.
    {
      kind: "SPECIAL_PROCESS",
      name: missing("Special processes (plating, heat treat, NDT) — none recorded; state 'none required' only on engineering authority"),
      specification: missing("Process specification"),
      supplier: missing("Process source"),
      certificateNumber: missing("Process certification number"),
    },
    {
      kind: "FUNCTIONAL_TEST",
      name: missing("Functional test procedures — none recorded"),
      specification: missing("Test specification"),
      supplier: missing("Test facility"),
      certificateNumber: missing("Acceptance report number"),
    },
  ];

  /* ---- Form 3 — characteristic accountability ---- */

  const measurable = input.features.filter((f) => f.tolerance || f.critical || f.inspectionMethod);
  const form3: FairCharacteristic[] = measurable.map((f, i) => {
    const m = input.inspectionMeasurements
      .filter((r) => r.featureId === f.id && r.sessionMode === "INSPECTION")
      .sort((a, b) => b.measuredAt.localeCompare(a.measuredAt))[0];

    const result: FairCharacteristic["result"] = m
      ? {
          state: "MEASURED",
          value: m.value,
          uncertainty: m.uncertainty,
          instrument: m.instrument ?? "instrument not recorded",
          measuredAt: m.measuredAt,
          repeatCount: m.repeatCount,
        }
      : { state: "NOT_MEASURED" };

    return {
      charNumber: i + 1,
      location: f.label,
      designator: f.critical ? "CRITICAL" : "",
      requirement: featureSummary(f),
      tolerance: f.tolerance ? fmtTol(f.tolerance) : "No tolerance stated",
      result,
      conformance: assessConformance(f, m),
      inspectionMethod: f.inspectionMethod
        ? onFile(f.inspectionMethod)
        : missing("Inspection method not assigned"),
    };
  });

  const verdicts = form3.map((c) => c.conformance.verdict);
  const fieldsNotOnFile =
    countMissing(form1) + form2.reduce((s, r) => s + countMissing(r), 0) +
    form3.filter((c) => c.inspectionMethod.state === "NOT_ON_FILE").length;

  return {
    form1,
    form2,
    form3,
    summary: {
      characteristics: form3.length,
      measured: form3.filter((c) => c.result.state === "MEASURED").length,
      conforming: verdicts.filter((v) => v === "CONFORMS").length,
      nonconforming: verdicts.filter((v) => v === "NONCONFORMS").length,
      undetermined: verdicts.filter((v) => v === "CANNOT_DETERMINE").length,
      fieldsNotOnFile,
    },
    generatedAtIso: input.generatedAtIso,
  };
}

/**
 * The single unambiguous nominal for a feature, where one exists. A diameter
 * is one; a pocket's width-and-length is two, and picking one silently would
 * assign a conformance verdict to the wrong dimension.
 */
function nominalOf(feature: Feature): number | null {
  if ("diameter" in feature && typeof feature.diameter === "number") return feature.diameter;
  return null;
}

/**
 * THE conformance rule. The FAIR report and the live inspection session both
 * call this — a session screen that disagreed with the report it feeds would
 * be the measurementGeometry bug all over again. One rule, one home.
 */
export function assessConformance(
  feature: Feature,
  m: { value: number; uncertainty: number } | undefined,
): ConformanceVerdict {
  if (!m) return { verdict: "CANNOT_DETERMINE", reason: "No first-article measurement recorded" };
  if (!feature.tolerance) return { verdict: "CANNOT_DETERMINE", reason: "No tolerance stated on the characteristic" };

  const nominal = nominalOf(feature);
  if (nominal === null) {
    return {
      verdict: "CANNOT_DETERMINE",
      reason: "Characteristic has no single nominal dimension — assess against the drawing manually",
    };
  }

  const tol: Tolerance = feature.tolerance;
  const band = tol.plus + tol.minus;
  // 4:1 test — an instrument whose uncertainty spans more than a quarter of
  // the band cannot carry a conformance decision on it.
  if (m.uncertainty * 2 > band / 4) {
    return {
      verdict: "CANNOT_DETERMINE",
      reason: `Instrument uncertainty ±${m.uncertainty.toFixed(4)}" cannot verify a ${band.toFixed(4)}" band (4:1 rule)`,
    };
  }

  const hi = nominal + tol.plus;
  const lo = nominal - tol.minus;
  if (m.value > hi || m.value < lo) {
    return {
      verdict: "NONCONFORMS",
      departure: m.value > hi ? m.value - hi : m.value - lo,
      nonconformanceDoc: missing("Nonconformance record — none on file in CANVAS"),
    };
  }
  // Inside the limits by less than the measurement's own uncertainty is not
  // a pass — the true value may be outside.
  if (m.value + m.uncertainty > hi || m.value - m.uncertainty < lo) {
    return {
      verdict: "CANNOT_DETERMINE",
      reason: `Result is within ${Math.min(hi - m.value, m.value - lo).toFixed(4)}" of a limit — less than the ±${m.uncertainty.toFixed(4)}" uncertainty. Re-measure with a more capable instrument.`,
    };
  }
  return { verdict: "CONFORMS" };
}

function countMissing(obj: object): number {
  return Object.values(obj).filter(
    (v) => typeof v === "object" && v !== null && (v as FairField).state === "NOT_ON_FILE",
  ).length;
}
