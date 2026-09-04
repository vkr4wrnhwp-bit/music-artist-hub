import { FEATURE_KINDS, type FeatureKind } from "@/lib/domain/features";
import type { MetrologyDevice } from "@/lib/domain/shop";

/**
 * "I HAVE THE PART AND A PHONE. WHERE DO I START?"
 *
 * The measurement plan already knew how to order work — datums first, envelope
 * before features, interfaces before cosmetic surfaces. What it could not do
 * was point. A machinist holding the part read a list of labels and had to
 * work out for themselves which lump of metal each one meant, and for a part
 * nobody has modelled yet there were no labels either, because the list is
 * built from features and there were none.
 *
 * A photograph closes both. A model can look at a picture of a part and say
 * "there is a bore here, four holes there, a step along that edge" — which is
 * pattern recognition, the thing it is actually good at, and it is not a
 * measurement.
 *
 * THE LINE, AND WHY IT IS STRUCTURAL
 *
 * The model supplies WHAT and WHERE. It never supplies HOW BIG. Not because it
 * would usually be wrong — because a plausible diameter is the single most
 * dangerous thing this application could produce, and it would arrive looking
 * exactly like a measured one.
 *
 * So there is nowhere to put one. `PhotoSighting` has a label, a kind, a point
 * on the image and the dimension a person must go and take. It has no size
 * field, no estimate, no range. The same trick as `clearableByConfirmation:
 * false`: the rule is enforced by the type rather than by everyone
 * remembering it.
 *
 * What comes out is a numbered order of work, each step pinned to the spot on
 * the photograph it is talking about, with the instrument this shop actually
 * owns that can take it. Every dimension in the finished model was measured by
 * a person. The model only ever pointed.
 */

/** One thing a model says it can see, and where. Never how big it is. */
export interface PhotoSighting {
  /** What it looks like, in the model's words. */
  label: string;
  kind: FeatureKind;
  /** Where on the image, 0-1 from the top-left. */
  x: number;
  y: number;
  /** The dimension a person has to go and take. */
  whatToMeasure: string;
  /** Anything about the view that makes this uncertain. */
  note?: string;
}

export interface PhotoRead {
  /** False when no vision model is connected. Then `sightings` is empty. */
  connected: boolean;
  sightings: PhotoSighting[];
  /** What the model could not see, and why. */
  note: string;
}

export interface GuidedStep {
  order: number;
  label: string;
  kind: FeatureKind;
  /** Where to point on the photo. */
  x: number;
  y: number;
  whatToMeasure: string;
  /** What to reach for, from what this shop owns. Null when nothing here can. */
  instrument: string | null;
  /** Why this one now. */
  why: string;
  /** Nothing after a blocking step is worth taking until it is done. */
  blocking: boolean;
  caution: string | null;
}

export interface GuidedPlan {
  steps: GuidedStep[];
  headline: string;
  /** Stated on the plan, every time. */
  caveats: string[];
  /** Steps this shop has no instrument for. */
  unmeasurable: string[];
}

/*
 * ORDER OF WORK.
 *
 * Datums first and blocking, because a bore is 2.000 FROM SOMETHING — until
 * that something is named the number is not reproducible, and every dimension
 * taken before it may have to be taken again. Then the envelope, because a
 * feature's position is meaningless if the block it sits in is the wrong size.
 * Then holes and bores, which are what the part is usually FOR. Cosmetic
 * surfaces last.
 *
 * This is the same order `reconstruction.ts` establishes for a modelled part.
 * It is repeated here as a rank per kind because a photograph has no features
 * to sort, only sightings.
 */
const RANK: Record<FeatureKind, number> = {
  FACE: 1,
  STEP: 2,
  OUTSIDE_CONTOUR: 2,
  BORE: 3,
  TAPPED_HOLE: 4,
  DRILLED_HOLE: 4,
  COUNTERBORE: 5,
  COUNTERSINK: 5,
  SLOT: 6,
  RECT_POCKET: 6,
  CIRC_POCKET: 6,
  BOSS: 7,
  FILLET: 8,
  CHAMFER: 8,
  ENGRAVING: 9,
};

/** What the shop reaches for, by what is being measured. */
function pickInstrument(kind: FeatureKind, devices: MetrologyDevice[]): string | null {
  const has = (t: string) => devices.find((d) => d.deviceType === t) ?? null;
  const order: Record<string, string[]> = {
    BORE: ["BORE_GAUGE", "INSIDE_MICROMETER", "CMM", "CALIPER"],
    DRILLED_HOLE: ["PIN_GAUGE", "BORE_GAUGE", "CALIPER"],
    TAPPED_HOLE: ["THREAD_GAUGE", "PIN_GAUGE"],
    COUNTERBORE: ["CALIPER", "DEPTH_MICROMETER"],
    COUNTERSINK: ["CALIPER"],
    FACE: ["MICROMETER", "HEIGHT_GAUGE", "CALIPER"],
    STEP: ["HEIGHT_GAUGE", "CALIPER", "MICROMETER"],
    OUTSIDE_CONTOUR: ["CALIPER", "HEIGHT_GAUGE", "CMM"],
  };
  for (const t of order[kind] ?? ["CALIPER", "CMM"]) {
    const d = has(t);
    if (d) return d.description;
  }
  return null;
}

/**
 * A sighting is not a fact about the part.
 *
 * It is a model's reading of one photograph — one angle, one lighting, one
 * side. The plan says so at the top rather than at the bottom, because a
 * machinist who takes the list as a description of the part will measure the
 * five things it lists and miss the sixth on the face they did not photograph.
 */
export function buildGuidedPlan(read: PhotoRead, devices: MetrologyDevice[], views: number): GuidedPlan {
  if (!read.connected) {
    return {
      steps: [],
      headline: "No vision model is connected, so nothing has been read from the photograph.",
      caveats: [read.note],
      unmeasurable: [],
    };
  }
  if (read.sightings.length === 0) {
    return { steps: [], headline: "Nothing recognisable in this photograph.", caveats: [read.note], unmeasurable: [] };
  }

  const sorted = read.sightings
    .slice()
    .sort((a, b) => (RANK[a.kind] ?? 9) - (RANK[b.kind] ?? 9) || a.label.localeCompare(b.label));

  const steps: GuidedStep[] = sorted.map((s, i) => {
    const instrument = pickInstrument(s.kind, devices);
    /*
     * The first step is the datum, and it blocks. Everything measured before
     * there is something to measure FROM is a number that may have to be taken
     * again — so the plan says stop rather than letting somebody work through
     * the list and find out at the end.
     */
    const blocking = i === 0;
    return {
      order: i + 1,
      label: s.label,
      kind: s.kind,
      x: s.x,
      y: s.y,
      whatToMeasure: s.whatToMeasure,
      instrument,
      why: blocking
        ? "Establish this first — it is what everything else is measured from. A dimension with no datum is not reproducible: the next person measures from a different edge and gets an answer that is equally defensible and different."
        : `${RANK[s.kind] <= 3 ? "The part's size before its details" : "After the sizes it sits inside"}.`,
      blocking,
      caution: s.note ?? null,
    };
  });

  const unmeasurable = steps.filter((s) => !s.instrument).map((s) => `${s.label} — ${s.whatToMeasure}`);

  const caveats = [
    "A model looked at a photograph and said what it thinks is there and roughly where. It did not measure anything, and it cannot: every dimension below is one you go and take.",
    `This is ${views === 1 ? "one view" : `${views} views`} of the part. Anything on a face that was not photographed is not on this list, and a list you can finish is not the same as a part you have described.`,
    "Nothing here becomes geometry until a reading is recorded against it.",
  ];
  if (read.note.trim()) caveats.push(read.note.trim());
  if (unmeasurable.length > 0) {
    caveats.push(
      `${unmeasurable.length} of these have no instrument in this shop's metrology library that can take them. They are listed and left unmeasured rather than dropped.`,
    );
  }

  return {
    steps,
    headline: `${steps.length} ${steps.length === 1 ? "thing" : "things"} to measure, in order. Start with ${steps[0].label}.`,
    caveats,
    unmeasurable,
  };
}

/** The next thing to do: the first step with no reading against it. */
export function nextStep(plan: GuidedPlan, done: number[]): GuidedStep | null {
  return plan.steps.find((s) => !done.includes(s.order)) ?? null;
}

/** Everything a sighting has to satisfy before it is shown to anybody. */
export function validSighting(s: unknown): s is PhotoSighting {
  if (typeof s !== "object" || s === null) return false;
  const v = s as Record<string, unknown>;
  return (
    typeof v.label === "string" &&
    v.label.trim().length > 0 &&
    typeof v.kind === "string" &&
    (FEATURE_KINDS as readonly string[]).includes(v.kind) &&
    typeof v.x === "number" &&
    Number.isFinite(v.x) &&
    v.x >= 0 &&
    v.x <= 1 &&
    typeof v.y === "number" &&
    Number.isFinite(v.y) &&
    v.y >= 0 &&
    v.y <= 1 &&
    typeof v.whatToMeasure === "string" &&
    v.whatToMeasure.trim().length > 0
  );
}
