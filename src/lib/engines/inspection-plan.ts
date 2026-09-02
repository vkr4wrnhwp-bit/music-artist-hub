import { FEATURE_FIELDS } from "@/lib/domain/feature-input";
import type { Feature, FeatureKind } from "@/lib/domain/features";

/**
 * DERIVING A FIRST-ARTICLE PLAN FROM THE PART
 *
 * The readiness gate said "Inspection plan — MISSING — Create an inspection
 * plan" and there was no `inspectionPlan.create` anywhere in the application.
 * The empty state told a shop to make one before the first article ran and
 * gave them nothing to make it with.
 *
 * WHAT THIS DERIVES, AND WHAT IT CANNOT
 *
 * A plan item is a characteristic: a nominal, a tolerance band, and the
 * instrument that will read it. All three can be taken honestly from a feature
 * that CANVAS already holds — the nominal from its governing dimension, the
 * band from its own tolerance, the instrument from the method assigned on the
 * feature.
 *
 * What cannot be derived is anything that lives BETWEEN features. Hole-to-hole
 * spacing, true position, flatness, parallelism, runout and overall envelope
 * are relationships, not features, and CANVAS holds no relationships. The
 * seeded demo plan contains "Dowel hole spacing — 4.000 ±0.001", which is
 * exactly such a dimension and exactly what this cannot produce.
 *
 * So a derived plan is a starting point and says so. It is not represented as
 * a complete inspection plan, because a shop that believed it was would ship a
 * part whose position callouts nobody checked.
 */

/**
 * The dimension a feature's tolerance is about.
 *
 * Declared explicitly per kind rather than inferred from field order. A
 * pocket carries a width, a length and a depth, and "the first number field"
 * would silently pick one of the three and print it as the characteristic —
 * a nominal that looks authoritative and describes the wrong dimension.
 *
 * `null` means this kind has no single governing dimension, and it is left out
 * of the derived plan with the reason stated rather than given a guess.
 */
export const GOVERNING_DIMENSION: Record<FeatureKind, string | null> = {
  FACE: "depth",
  BORE: "diameter",
  DRILLED_HOLE: "diameter",
  TAPPED_HOLE: "diameter",
  COUNTERBORE: "diameter",
  CIRC_POCKET: "diameter",
  COUNTERSINK: "diameter",
  BOSS: "diameter",
  // A radius is a single dimension and it is the one a fillet is toleranced on.
  FILLET: "radius",

  // No single governing dimension. Each of these carries two or more that a
  // tolerance could equally be about, and picking one would print a nominal
  // that looks authoritative and describes the wrong dimension.
  RECT_POCKET: null, // width, length and depth
  SLOT: null, // width, depth and the two end points that set its length
  OUTSIDE_CONTOUR: null, // width, length and corner radius
  CHAMFER: null, // width and angle
  STEP: null, // width and depth
  ENGRAVING: null, // a height and a string; not a characteristic with limits
};

export interface DerivedItem {
  featureId: string;
  label: string;
  nominal: number;
  plusTol: number;
  minusTol: number;
  method: string;
  deviceType: string | null;
  sequence: number;
}

/** A characteristic that could not be derived, and the reason in plain words. */
export interface UncoveredCharacteristic {
  featureId: string | null;
  label: string;
  reason: string;
}

export interface DerivedPlan {
  items: DerivedItem[];
  uncovered: UncoveredCharacteristic[];
}

/** Text stored when the shop has not said how a characteristic will be read. */
export const METHOD_NOT_ASSIGNED = "No method assigned";

/**
 * Everything on this revision that carries a tolerance or is flagged critical.
 *
 * A feature with neither is not a characteristic: it is geometry, and putting
 * it on a first-article report gives the inspector a row with no accept limits
 * to judge against.
 */
export function derivePlan(features: Feature[]): DerivedPlan {
  const items: DerivedItem[] = [];
  const uncovered: UncoveredCharacteristic[] = [];

  const characteristics = features.filter((f) => f.tolerance != null || f.critical);

  for (const f of characteristics) {
    const governing = GOVERNING_DIMENSION[f.kind as FeatureKind];
    if (!governing) {
      uncovered.push({
        featureId: f.id,
        label: f.label,
        reason: `A ${f.kind.replace(/_/g, " ").toLowerCase()} has no single governing dimension — it carries several, and CANVAS will not pick one and print it as the characteristic. Add the rows this feature needs by hand.`,
      });
      continue;
    }

    const raw = (f as unknown as Record<string, unknown>)[governing];
    const nominal = typeof raw === "number" && Number.isFinite(raw) ? raw : null;
    if (nominal == null) {
      uncovered.push({
        featureId: f.id,
        label: f.label,
        reason: `Its ${governing} is not recorded, so there is no nominal to inspect against.`,
      });
      continue;
    }

    // A critical feature with no tolerance gets no band invented for it. It is
    // still worth listing — somebody flagged it critical — so it is named here
    // rather than dropped, and the shop states the limits.
    if (!f.tolerance) {
      uncovered.push({
        featureId: f.id,
        label: f.label,
        reason: `Flagged critical but carries no tolerance, so there are no accept limits to inspect against. State the tolerance on the feature.`,
      });
      continue;
    }

    const field = (FEATURE_FIELDS[f.kind as FeatureKind] ?? []).find((x) => x.name === governing);
    items.push({
      featureId: f.id,
      label: `${f.label} — ${(field?.label ?? governing).toLowerCase()}`,
      nominal,
      plusTol: f.tolerance.plus,
      minusTol: f.tolerance.minus,
      // Taken from the method assigned on the feature. Where none is assigned
      // the row says so: an inspector reading "Calipers" that nobody chose is
      // worse off than one reading that the method is still open.
      method: f.inspectionMethod ?? METHOD_NOT_ASSIGNED,
      deviceType: f.inspectionDeviceType ?? null,
      sequence: 0,
    });
  }

  // Sequenced after filtering, so the numbers a machinist reads off the sheet
  // are 1..n with no gaps where a feature was skipped.
  items.forEach((it, i) => {
    it.sequence = i + 1;
  });

  return { items, uncovered };
}

/**
 * What a derived plan does not cover, stated the same way every time.
 *
 * Kept beside the derivation because the list is a property of what CANVAS
 * models, not of any one part: nothing here is a feature, so no part will ever
 * derive them.
 */
export const NEVER_DERIVABLE = [
  "Position, spacing and hole-to-hole distances — these are relationships between features, and CANVAS holds features",
  "Form and orientation callouts: flatness, parallelism, perpendicularity, runout",
  "Overall envelope dimensions taken across the part rather than on one feature",
  "Surface finish, thread class and anything verified by gauge rather than by reading a number",
];
