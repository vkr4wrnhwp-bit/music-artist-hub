/**
 * RECONSTRUCTION PLAN
 *
 * "I have the part. I need another one."
 *
 * Photographs do not produce geometry. They produce a list of things somebody
 * has to go and measure, and the useful thing software can do is work out what
 * that list is, put it in an order that does not waste anybody's afternoon,
 * and be honest that the list is the deliverable rather than pretending the
 * photographs were.
 *
 * TWO PRINCIPLES DECIDE THE ORDER
 *
 * Datums first. A bore is 2.000 *from something*. Until that something is
 * named, the number is not reproducible — the next person measures from a
 * different edge and gets an answer that is equally defensible and different.
 * Every dimension measured before the datum is settled may have to be measured
 * again, so datums are not merely first, they are blocking.
 *
 * Then by what invalidates what. Overall envelope before features, because a
 * feature position is meaningless if the envelope it sits in is wrong.
 * Interfaces before cosmetic surfaces, because an interface decides the
 * tolerance and the tolerance decides the instrument.
 *
 * WHAT THIS DELIBERATELY DOES NOT DO
 *
 * It does not derive geometry from the photographs. CANVAS has no vision model
 * wired up, and inferring a wall thickness from a photograph and presenting it
 * as a dimension would be the single most dangerous thing this application
 * could do. The photographs are evidence for a human reading the plan, and the
 * plan says what a human must go and measure.
 */

import type { Feature } from "@/lib/domain/features";

export const DATUM_SYSTEMS = ["DESIGN", "MANUFACTURING", "INSPECTION"] as const;
export type DatumSystem = (typeof DATUM_SYSTEMS)[number];

export const DATUM_SYSTEM_LABEL: Record<DatumSystem, string> = {
  DESIGN: "Design datum",
  MANUFACTURING: "Manufacturing datum",
  INSPECTION: "Inspection datum",
};

export const DATUM_SYSTEM_QUESTION: Record<DatumSystem, string> = {
  DESIGN: "What is the part's function referenced to?",
  MANUFACTURING: "What is the part located from in the fixture?",
  INSPECTION: "What is it set up on to be measured?",
};

export type DatumGeometry = "PLANE" | "AXIS" | "POINT";

/** Degrees of freedom each datum type removes — the reason three are needed. */
const CONSTRAINS: Record<DatumGeometry, number> = { PLANE: 3, AXIS: 2, POINT: 1 };

export interface DatumProposal {
  letter: string;
  system: DatumSystem;
  featureId: string | null;
  description: string;
  geometryType: DatumGeometry;
  reason: string;
}

export interface MeasurementTask {
  id: string;
  order: number;
  label: string;
  featureId: string | null;
  /** Which datum this dimension must be taken from. */
  datumLetter: string | null;
  context: "BORE" | "SHAFT" | "HOLE" | "THREAD" | "THICKNESS" | "GENERAL";
  instruction: string;
  /** Why this one matters, in terms of what it unlocks. */
  unlocks: string;
  /** Total tolerance band this dimension is expected to carry, if known. */
  expectedBand: number | null;
  blocking: boolean;
  complete: boolean;
}

export interface ReconstructionPlan {
  /** Photographs still wanted before the plan can be considered evidenced. */
  missingViews: string[];
  photosOnFile: number;
  /** Datums that must be established, across all three systems. */
  datumProposals: DatumProposal[];
  datumsEstablished: number;
  datumsRequired: number;
  /** Ordered work list. */
  tasks: MeasurementTask[];
  measurementsRequired: number;
  measurementsComplete: number;
  /** Readings matched to a standard that a human has not ruled on yet. */
  inferredAwaitingReview: number;
  /** One-line statement of what the plan amounts to. */
  headline: string;
  /** What blocks progress right now. */
  blockedBy: string[];
}

const REQUIRED_VIEWS = ["TOP", "BOTTOM", "FRONT", "BACK", "LEFT", "RIGHT"];

export interface ReconstructionInput {
  features: Feature[];
  /** viewLabel values already uploaded. */
  uploadedViews: string[];
  /** Datums already accepted, keyed system:letter. */
  establishedDatums: { system: string; letter: string }[];
  /** Measurement labels already recorded. */
  completedLabels: string[];
  inferredAwaitingReview: number;
}

/**
 * Proposes a datum reference frame.
 *
 * The proposal is a starting point and says why, because the machinist looking
 * at the part knows things the feature list does not — which face is actually
 * the mounting face, which bore actually carries the load. The reason is
 * carried through so they can disagree with the reasoning rather than only
 * with the conclusion.
 */
export function proposeDatums(features: Feature[]): DatumProposal[] {
  const proposals: DatumProposal[] = [];

  const faces = features.filter((f) => f.kind === "FACE" || f.functionalRole === "DATUM_FACE");
  const bores = features.filter((f) => f.kind === "BORE" || f.functionalRole === "BEARING_SEAT");
  const dowels = features.filter((f) => f.functionalRole === "DOWEL_HOLE");
  const holes = features.filter((f) => f.kind === "DRILLED_HOLE" || f.kind === "TAPPED_HOLE");

  /* ---- A: a plane. Three degrees of freedom in one go. ---- */
  const primary = faces[0] ?? null;
  proposals.push({
    letter: "A",
    system: "DESIGN",
    featureId: primary?.id ?? null,
    description: primary ? primary.label : "Primary mounting face",
    geometryType: "PLANE",
    reason: primary
      ? `${primary.label} is the largest stable functional surface on the part. A plane constrains three degrees of freedom at once, which is why the primary datum is almost always a face rather than a hole.`
      : "No face is identified yet. The primary datum should be the surface the part actually seats on in service — it constrains three degrees of freedom on its own.",
  });

  /* ---- B: an axis. Two more. ---- */
  const secondary = bores[0] ?? null;
  proposals.push({
    letter: "B",
    system: "DESIGN",
    featureId: secondary?.id ?? null,
    description: secondary ? `${secondary.label} centreline` : "Principal bore centreline",
    geometryType: "AXIS",
    reason: secondary
      ? `${secondary.label} is the feature the part exists to locate. Referencing to its centreline rather than to an outside edge means the dimension that matters is measured directly instead of being accumulated through the casting.`
      : "The secondary datum should be whatever the part exists to locate — usually the principal bore, referenced on its centreline.",
  });

  /* ---- C: a point. The last rotational freedom. ---- */
  const tertiary = dowels[0] ?? holes[0] ?? null;
  proposals.push({
    letter: "C",
    system: "DESIGN",
    featureId: tertiary?.id ?? null,
    description: tertiary ? `${tertiary.label} centre` : "Clocking feature centre",
    geometryType: "POINT",
    reason: tertiary
      ? `${tertiary.label} fixes rotation about datum B. Without a third datum the part is free to spin about the bore and every angular position on it is undefined.`
      : "A third datum is needed to fix rotation about B. A dowel hole is the usual choice because it is the feature that clocks the part in assembly.",
  });

  /* ---- Manufacturing and inspection, where they differ ---- */

  proposals.push({
    letter: "A",
    system: "MANUFACTURING",
    featureId: primary?.id ?? null,
    description: primary ? `${primary.label} — seated on parallels` : "Face seated in the vise",
    geometryType: "PLANE",
    reason:
      "The manufacturing datum is what the part is located from in the fixture, which is frequently not the design datum — the design datum is often the face machined last, and it cannot locate the setup that creates it. Where the two differ, the difference stacks into every dimension.",
  });

  proposals.push({
    letter: "A",
    system: "INSPECTION",
    featureId: primary?.id ?? null,
    description: primary ? `${primary.label} — on the surface plate` : "Face on the surface plate",
    geometryType: "PLANE",
    reason:
      "The inspection datum is what the part is set up on to be measured. If it differs from the manufacturing datum, a part can be made correctly and measured as wrong, or the reverse — which is the most expensive kind of argument a shop can have with a customer.",
  });

  return proposals;
}

/**
 * Builds the measurement work list.
 *
 * Every entry names an instrument context and states what it unlocks, because
 * "measure the bore" is an instruction and "measure the bore, because it
 * decides the tool, the finishing pass and the inspection method" is a reason
 * to do it now rather than after lunch.
 */
export function buildTasks(features: Feature[], datumsReady: boolean, completed: string[]): MeasurementTask[] {
  const tasks: MeasurementTask[] = [];
  // Completion is matched by label, and labels are not unique — two bores on
  // a casting are frequently both called "Bore". A Set marked every one of
  // them complete as soon as any one was measured, which on a reverse
  // engineering job reports an unmeasured feature as measured. Counting
  // occurrences means one recorded measurement satisfies one task.
  const remaining = new Map<string, number>();
  for (const c of completed) {
    const key = c.toLowerCase();
    remaining.set(key, (remaining.get(key) ?? 0) + 1);
  }
  const takeCompletion = (label: string): boolean => {
    const key = label.toLowerCase();
    const left = remaining.get(key) ?? 0;
    if (left <= 0) return false;
    remaining.set(key, left - 1);
    return true;
  };

  let order = 0;

  const push = (t: Omit<MeasurementTask, "order" | "complete" | "id">) => {
    order += 1;
    tasks.push({
      ...t,
      id: `task-${order}`,
      order,
      complete: takeCompletion(t.label),
    });
  };

  /* ---- Envelope. Everything else sits inside it. ---- */
  for (const axis of ["X", "Y", "Z"] as const) {
    push({
      label: `Overall ${axis}`,
      featureId: null,
      datumLetter: axis === "Z" ? "A" : null,
      context: "GENERAL",
      instruction:
        axis === "Z"
          ? "Measure overall thickness from datum A at three separated positions. A casting is rarely parallel, and the variation is the number you need."
          : `Measure the overall ${axis} envelope at both ends. If the two disagree, the part is tapered and that is worth knowing before anything is referenced to it.`,
      unlocks: "Stock size, machine envelope check, and the reference frame every feature position sits inside.",
      expectedBand: null,
      blocking: true,
    });
  }

  /* ---- Interfaces before everything else ---- */
  const interfaces = features.filter(
    (f) =>
      f.functionalRole === "BEARING_SEAT" ||
      f.functionalRole === "PRESS_FIT" ||
      f.functionalRole === "SLIP_FIT" ||
      f.functionalRole === "SEAL_SURFACE" ||
      f.critical,
  );

  for (const f of interfaces) {
    const isBore = "diameter" in f;
    push({
      label: f.label,
      featureId: f.id,
      datumLetter: datumsReady ? "B" : null,
      context: isBore ? "BORE" : "GENERAL",
      instruction: isBore
        ? "Measure at two positions approximately 90° apart, and at two depths. One reading cannot distinguish a round bore from an oval one, and an oval bore is the reason the bearing was replaced."
        : "Measure across the interface at three separated positions.",
      unlocks:
        "The functional intent behind this dimension — which decides the nominal, the fit class, the finishing operation and the instrument that has to verify it.",
      expectedBand: f.tolerance ? f.tolerance.plus + f.tolerance.minus : null,
      blocking: true,
    });
  }

  /* ---- Positions, which only mean anything against a datum ---- */
  const positioned = features.filter(
    (f) => (f.kind === "DRILLED_HOLE" || f.kind === "TAPPED_HOLE") && !interfaces.includes(f),
  );

  if (positioned.length > 0) {
    push({
      label: `Hole pattern position (${positioned.length} holes)`,
      featureId: positioned[0].id,
      // Was hardcoded "C" regardless of whether C existed yet, so the plan
      // instructed a measurement from a datum nobody had established — the
      // exact error the instruction below warns about.
      datumLetter: datumsReady ? "C" : null,
      context: "HOLE",
      instruction:
        "Measure hole centres from datum C on a surface plate, not from the part edges. Edge-referenced hole positions are the classic reverse-engineering error: they reproduce the original's edge condition rather than its intent.",
      unlocks: "Whether the pattern is a standard bolt circle or spacing, which is usually what it turns out to be.",
      expectedBand: null,
      blocking: false,
    });
  }

  /* ---- Remaining features ---- */
  for (const f of features) {
    if (interfaces.includes(f) || positioned.includes(f)) continue;
    if (f.kind === "FACE" || f.kind === "OUTSIDE_CONTOUR") continue;
    push({
      label: f.label,
      featureId: f.id,
      datumLetter: null,
      context: "diameter" in f ? "HOLE" : "GENERAL",
      instruction: "Measure the feature size and its position from the established datums.",
      unlocks: "Completes the feature definition so the operation can be planned.",
      expectedBand: f.tolerance ? f.tolerance.plus + f.tolerance.minus : null,
      blocking: false,
    });
  }

  return tasks;
}

export function buildReconstructionPlan(input: ReconstructionInput): ReconstructionPlan {
  const uploaded = new Set(input.uploadedViews.map((v) => v.toUpperCase()));
  const missingViews = REQUIRED_VIEWS.filter((v) => !uploaded.has(v));

  const datumProposals = proposeDatums(input.features);
  const established = new Set(input.establishedDatums.map((d) => `${d.system}:${d.letter}`));
  const datumsEstablished = datumProposals.filter((d) => established.has(`${d.system}:${d.letter}`)).length;

  // The design frame is what blocks measurement. The manufacturing and
  // inspection datums matter for stack-up and can be settled later.
  const designDatums = datumProposals.filter((d) => d.system === "DESIGN");
  const designReady = designDatums.every((d) => established.has(`DESIGN:${d.letter}`));

  const tasks = buildTasks(input.features, designReady, input.completedLabels);
  const complete = tasks.filter((t) => t.complete).length;

  const blockedBy: string[] = [];
  if (missingViews.length === REQUIRED_VIEWS.length) {
    blockedBy.push("None of the six required views uploaded — the part has not been photographed yet");
  } else if (missingViews.length > 0) {
    blockedBy.push(
      `${missingViews.length} of the six required views still missing — ${missingViews.map((v) => v.toLowerCase()).join(", ")}`,
    );
  }
  if (!designReady) {
    const outstanding = designDatums.filter((d) => !established.has(`DESIGN:${d.letter}`));
    blockedBy.push(
      `Design datum ${outstanding.map((d) => d.letter).join(", ")} not established — dimensions taken before the reference frame is settled may have to be taken again`,
    );
  }
  if (input.inferredAwaitingReview > 0) {
    blockedBy.push(
      `${input.inferredAwaitingReview} reading${input.inferredAwaitingReview === 1 ? "" : "s"} matched to a standard and awaiting a human decision`,
    );
  }

  // This counted the PROPOSED frame, which is always a plane, an axis and a
  // point — 3 + 2 + 1 — so it printed "constrains 6 of 6 degrees of freedom"
  // on every part in the app, including one with no features and no datums
  // established. A constant presented as an analysis result is worse than no
  // result: it reads as a completeness claim about a part nobody has measured.
  // What is actually worth knowing is how much of the frame is settled, so it
  // counts established datums only.
  const constrained = designDatums
    .filter((d) => established.has(`DESIGN:${d.letter}`))
    .reduce((sum, d) => sum + CONSTRAINS[d.geometryType], 0);

  const headline =
    `${tasks.length} measurements required, ${datumProposals.length} datum relationships to establish` +
    (input.inferredAwaitingReview > 0
      ? `, ${input.inferredAwaitingReview} inferred ${input.inferredAwaitingReview === 1 ? "feature requires" : "features require"} review.`
      : ".") +
    ` The established design frame constrains ${constrained} of 6 degrees of freedom.`;

  return {
    missingViews,
    photosOnFile: input.uploadedViews.length,
    datumProposals,
    datumsEstablished,
    datumsRequired: datumProposals.length,
    tasks,
    measurementsRequired: tasks.length,
    measurementsComplete: complete,
    inferredAwaitingReview: input.inferredAwaitingReview,
    headline,
    blockedBy,
  };
}

/** The single next thing to measure, or null when the list is done. */
export function nextTask(plan: ReconstructionPlan): MeasurementTask | null {
  return plan.tasks.find((t) => !t.complete && t.blocking) ?? plan.tasks.find((t) => !t.complete) ?? null;
}
