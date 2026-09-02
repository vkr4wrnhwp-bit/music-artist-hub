import { FEATURE_KINDS, type FeatureKind } from "./features";

/**
 * WHAT EACH FEATURE KIND ACTUALLY NEEDS
 *
 * `Feature.parametersJson` was a free record. The only path into it was
 * accepting an AI proposal, whose schema types the parameters as
 * `Record<string, number | string | boolean>` — so a proposal missing a
 * diameter wrote a feature with no diameter, and every engine downstream met
 * `undefined` where it expected a number. There was no hand-entry path at all:
 * the empty state said "add features" and no control existed.
 *
 * This is the one description of a feature's parameters. The manual form
 * renders from it and the accept-a-proposal path validates against it, so a
 * feature cannot enter the system through either door in a shape the renderers
 * and engines cannot read.
 *
 * It describes shape only. What the feature is FOR — functional role,
 * tolerance, mating component — is asked separately, because a dimension
 * without its responsibility is a number, and the two are deliberately not
 * collected in one breath.
 */

export type FieldType = "number" | "boolean" | "text" | "choice";

export interface FeatureField {
  name: string;
  label: string;
  type: FieldType;
  /** Shown after the input. Inches unless stated. */
  unit?: string;
  /**
   * Smallest accepted value. Absent means any finite number — a centre
   * coordinate is legitimately negative, and a corner radius is legitimately
   * zero, so neither can share a rule with a diameter.
   */
  min?: number;
  /** True when the field must be present. Optional fields may be omitted. */
  required: boolean;
  choices?: readonly string[];
  hint?: string;
}

const XY: FeatureField[] = [
  { name: "centerX", label: "Centre X", type: "number", unit: "in", required: true, hint: "From program zero at the stock centre." },
  { name: "centerY", label: "Centre Y", type: "number", unit: "in", required: true },
];
/** Z of the feature's mouth. 0 is the top face; a recessed feature is negative. */
const TOP: FeatureField = { name: "top", label: "Mouth Z", type: "number", unit: "in", required: true, hint: "0 is the top of the stock. Cuts run negative." };
const DEPTH: FeatureField = { name: "depth", label: "Depth", type: "number", unit: "in", min: 0.0001, required: true };
const DIAMETER: FeatureField = { name: "diameter", label: "Diameter", type: "number", unit: "in", min: 0.0001, required: true };
const THROUGH: FeatureField = { name: "through", label: "Through the part", type: "boolean", required: false };

export const FEATURE_FIELDS: Record<FeatureKind, FeatureField[]> = {
  FACE: [DEPTH],
  RECT_POCKET: [
    ...XY,
    { name: "width", label: "Width, X", type: "number", unit: "in", min: 0.0001, required: true },
    { name: "length", label: "Length, Y", type: "number", unit: "in", min: 0.0001, required: true },
    DEPTH,
    { name: "cornerRadius", label: "Corner radius", type: "number", unit: "in", min: 0, required: true, hint: "Zero means a sharp corner no endmill can cut." },
    { name: "bottomRadius", label: "Bottom radius", type: "number", unit: "in", min: 0, required: true },
    TOP,
  ],
  CIRC_POCKET: [...XY, DIAMETER, DEPTH, { name: "bottomRadius", label: "Bottom radius", type: "number", unit: "in", min: 0, required: true }, TOP, THROUGH],
  BORE: [...XY, DIAMETER, DEPTH, { name: "bottomRadius", label: "Bottom radius", type: "number", unit: "in", min: 0, required: true }, TOP, THROUGH],
  SLOT: [
    { name: "startX", label: "Start X", type: "number", unit: "in", required: true },
    { name: "startY", label: "Start Y", type: "number", unit: "in", required: true },
    { name: "endX", label: "End X", type: "number", unit: "in", required: true },
    { name: "endY", label: "End Y", type: "number", unit: "in", required: true },
    { name: "width", label: "Width", type: "number", unit: "in", min: 0.0001, required: true },
    DEPTH,
    TOP,
  ],
  DRILLED_HOLE: [...XY, DIAMETER, DEPTH, TOP, THROUGH],
  TAPPED_HOLE: [
    ...XY, DIAMETER, DEPTH, TOP, THROUGH,
    { name: "thread", label: "Thread", type: "text", required: true, hint: 'As it is called out, e.g. "1/4-20 UNC" or "M6x1.0".' },
  ],
  COUNTERBORE: [
    ...XY, DIAMETER, DEPTH, TOP, THROUGH,
    { name: "headDiameter", label: "Counterbore ⌀", type: "number", unit: "in", min: 0.0001, required: true },
    { name: "headDepth", label: "Counterbore depth", type: "number", unit: "in", min: 0.0001, required: true },
  ],
  COUNTERSINK: [
    ...XY, DIAMETER, DEPTH, TOP, THROUGH,
    { name: "headDiameter", label: "Countersink ⌀", type: "number", unit: "in", min: 0.0001, required: true },
    { name: "countersinkAngle", label: "Included angle", type: "number", unit: "°", min: 1, required: true },
  ],
  CHAMFER: [
    { name: "width", label: "Chamfer width", type: "number", unit: "in", min: 0.0001, required: true },
    { name: "angle", label: "Angle", type: "number", unit: "°", min: 1, required: true },
    { name: "applyTo", label: "Applies to", type: "choice", required: true, choices: ["OUTSIDE_TOP", "OUTSIDE_BOTTOM", "HOLES", "POCKET"] },
  ],
  FILLET: [
    { name: "radius", label: "Radius", type: "number", unit: "in", min: 0.0001, required: true },
    { name: "applyTo", label: "Applies to", type: "choice", required: true, choices: ["OUTSIDE_VERTICAL", "POCKET_CORNERS"] },
  ],
  OUTSIDE_CONTOUR: [
    { name: "width", label: "Finished width, X", type: "number", unit: "in", min: 0.0001, required: true },
    { name: "length", label: "Finished length, Y", type: "number", unit: "in", min: 0.0001, required: true },
    { name: "cornerRadius", label: "Corner radius", type: "number", unit: "in", min: 0, required: true },
    DEPTH,
  ],
  ENGRAVING: [
    { name: "text", label: "Text", type: "text", required: true },
    ...XY,
    { name: "height", label: "Character height", type: "number", unit: "in", min: 0.0001, required: true },
    DEPTH,
    TOP,
  ],
  BOSS: [...XY, DIAMETER, { name: "height", label: "Height", type: "number", unit: "in", min: 0.0001, required: true }],
  STEP: [
    { name: "side", label: "Side", type: "choice", required: true, choices: ["XMIN", "XMAX", "YMIN", "YMAX"] },
    { name: "width", label: "Width", type: "number", unit: "in", min: 0.0001, required: true },
    DEPTH,
  ],
};

export type ParamValue = number | string | boolean;
export type FeatureRefusal = { field: string; reason: string };

/**
 * Validates a parameter set against its kind.
 *
 * Refusals name the field and say what is wrong with it. Nothing is defaulted:
 * a missing depth is a refusal, not a zero, because a zero-depth pocket is a
 * feature that removes no material and every engine downstream would treat it
 * as real.
 */
export function validateFeatureParameters(
  kind: string,
  params: Record<string, unknown>,
): FeatureRefusal[] {
  if (!(FEATURE_KINDS as readonly string[]).includes(kind)) {
    return [{ field: "kind", reason: `"${kind}" is not a feature kind CANVAS knows.` }];
  }
  const fields = FEATURE_FIELDS[kind as FeatureKind];
  const refusals: FeatureRefusal[] = [];

  for (const f of fields) {
    const raw = params[f.name];
    const absent = raw === undefined || raw === null || raw === "";
    if (absent) {
      if (f.required) refusals.push({ field: f.name, reason: `${f.label} is required and was not given.` });
      continue;
    }
    if (f.type === "number") {
      const v = typeof raw === "number" ? raw : Number(raw);
      if (!Number.isFinite(v)) {
        refusals.push({ field: f.name, reason: `${f.label} is not a number.` });
      } else if (f.min !== undefined && v < f.min) {
        refusals.push({
          field: f.name,
          reason:
            f.min > 0
              ? `${f.label} must be greater than zero. A feature with no ${f.label.toLowerCase()} removes no material and every engine downstream would treat it as real.`
              : `${f.label} cannot be negative.`,
        });
      }
    } else if (f.type === "boolean") {
      if (typeof raw !== "boolean") refusals.push({ field: f.name, reason: `${f.label} must be yes or no.` });
    } else if (f.type === "choice") {
      if (!f.choices?.includes(String(raw))) {
        refusals.push({ field: f.name, reason: `${f.label} must be one of ${f.choices?.join(", ")}.` });
      }
    } else if (f.type === "text") {
      if (String(raw).trim() === "") refusals.push({ field: f.name, reason: `${f.label} is required and was not given.` });
    }
  }

  return refusals;
}

/** Coerces a validated parameter set into the types the domain models expect. */
export function coerceFeatureParameters(kind: FeatureKind, params: Record<string, unknown>): Record<string, ParamValue> {
  const out: Record<string, ParamValue> = {};
  for (const f of FEATURE_FIELDS[kind]) {
    const raw = params[f.name];
    if (raw === undefined || raw === null || raw === "") {
      // An absent optional boolean is false, which is what the domain models
      // mean by it. Nothing else is filled in.
      if (f.type === "boolean" && !f.required) out[f.name] = false;
      continue;
    }
    if (f.type === "number") out[f.name] = typeof raw === "number" ? raw : Number(raw);
    else if (f.type === "boolean") out[f.name] = Boolean(raw);
    else out[f.name] = String(raw).trim();
  }
  return out;
}
