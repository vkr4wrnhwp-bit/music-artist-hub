import type { ActorType } from "@/lib/audit";

/**
 * MANUFACTURING DNA — the history a part revision already has
 *
 * The brief asks for a timeline attached to a PartRevision: initial release,
 * bore nominal changed, soft jaws added, chatter observed, inspection passed,
 * workholding failure corrected, process revised — with provenance labels.
 *
 * The `ManufacturingDNA` model was keyed to `Part`, had no event shape, no
 * provenance, and no write site outside the seed. The UI was a four-column
 * table on /intelligence.
 *
 * This is DERIVED, not authored, and that is the whole design. Every event
 * below already exists as a record somebody's action created: an audit entry,
 * an approval, a job outcome, an inspection result, a disagreement. A
 * hand-maintained timeline can be typed into, goes stale the moment somebody
 * forgets, and can claim an event that never happened. A derived one cannot —
 * if it says the bore nominal changed on the 14th, an audit row says so.
 *
 * Which is also why every event carries where it came from and who did it.
 * The actor type is read from the record that states it, and where a record
 * does not state one it is null — "not recorded" — never assumed to be a
 * human. Nothing here is inferred by a model.
 */

export const DNA_EVENT_KINDS = [
  "REVISION_CREATED",
  "GEOMETRY_CHANGED",
  "RESPONSIBILITY_STATED",
  "SETUP_RECORDED",
  "SIMULATION_RUN",
  "APPROVED",
  "RELEASED",
  "JOB_RAISED",
  "JOB_COMPLETED",
  "OUTCOME_OBSERVED",
  "INSPECTION_RECORDED",
  "DISAGREEMENT_RAISED",
  "FINDING_ANSWERED",
] as const;
export type DnaEventKind = (typeof DNA_EVENT_KINDS)[number];

/** Where an event came from. Named so a reader can go and check it. */
export const DNA_SOURCES = [
  "PART_REVISION",
  "AUDIT_LOG",
  "APPROVAL",
  "SIMULATION",
  "JOB",
  "JOB_OUTCOME",
  "INSPECTION_RESULT",
  "DISAGREEMENT",
  "FINDING_RESOLUTION",
] as const;
export type DnaSource = (typeof DNA_SOURCES)[number];

export interface DnaEvent {
  at: Date;
  kind: DnaEventKind;
  title: string;
  detail: string;
  /** The record this was read from, so the claim is checkable. */
  source: DnaSource;
  sourceId: string;
  /**
   * Who did it. `type` is null where the underlying record does not state
   * one — an unrecorded actor is a missing fact, not a human by default.
   */
  actor: { name: string | null; type: ActorType | null };
}

export const DNA_KIND_LABEL: Record<DnaEventKind, string> = {
  REVISION_CREATED: "Revision created",
  GEOMETRY_CHANGED: "Geometry changed",
  RESPONSIBILITY_STATED: "Responsibility stated",
  SETUP_RECORDED: "Setup recorded",
  SIMULATION_RUN: "Simulation run",
  APPROVED: "Approved",
  RELEASED: "Released to the floor",
  JOB_RAISED: "Job raised",
  JOB_COMPLETED: "Job completed",
  OUTCOME_OBSERVED: "Outcome observed",
  INSPECTION_RECORDED: "Inspection recorded",
  DISAGREEMENT_RAISED: "Disagreement raised",
  FINDING_ANSWERED: "Review finding answered",
};

export interface DnaInput {
  revision: { id: string; revision: string; createdAt: Date; releasedAt: Date | null; releasedBy: string | null };
  /** Audit entries for this revision and anything under it. */
  audit: {
    id: string;
    entityType: string;
    entityId: string;
    action: string;
    field: string | null;
    oldValue: string | null;
    newValue: string | null;
    actorType: string;
    reason: string | null;
    createdAt: Date;
    userName: string | null;
  }[];
  approvals: { id: string; scope: string; statement: string; approvedAt: Date; revokedAt: Date | null; userName: string | null }[];
  simulations: { id: string; runAt: Date; collisionChecked: boolean; setupName: string }[];
  /** `createdAt` is null for jobs raised before it was recorded. */
  jobs: { id: string; jobNumber: string; quantity: number; status: string; createdAt: Date | null; completedAt: Date | null; actualCycleMinutes: number | null; scrapCount: number }[];
  outcomes: { id: string; jobNumber: string; code: string; cause: string; correctiveAction: string; partsAffected: number; recordedAt: Date; recordedBy: string | null }[];
  inspections: { id: string; label: string; measured: number; pass: boolean; measuredAt: Date; inspector: string | null }[];
  disagreements: { id: string; subjectType: string; canvasPosition: string; reasoning: string; status: string; createdAt: Date; userName: string | null }[];
  findingResolutions: { id: string; findingTitle: string; status: string; note: string; actorType: string; actorName: string; recordedAt: Date }[];
}

/** Reads an actor type off a record that states one; never guesses. */
function statedActor(value: string | null | undefined): ActorType | null {
  return value === "HUMAN" || value === "AI" || value === "SYSTEM" ? value : null;
}

/**
 * Assembles the timeline, newest first.
 *
 * Deterministic and total: every event in the output points at a record in the
 * input. Nothing is summarised by a model and nothing is added because it
 * "probably" happened.
 */
export function buildDnaTimeline(input: DnaInput): DnaEvent[] {
  const events: DnaEvent[] = [];

  events.push({
    at: input.revision.createdAt,
    kind: "REVISION_CREATED",
    title: `Revision ${input.revision.revision} created`,
    detail: "The revision this history belongs to.",
    source: "PART_REVISION",
    sourceId: input.revision.id,
    actor: { name: null, type: null },
  });

  if (input.revision.releasedAt) {
    events.push({
      at: input.revision.releasedAt,
      kind: "RELEASED",
      title: `Revision ${input.revision.revision} released to the floor`,
      detail:
        "Jobs can be raised against it. Releasing cleared no gate — readiness reports what it reports, and the picture at that moment is stored with the revision.",
      source: "PART_REVISION",
      sourceId: input.revision.id,
      actor: { name: input.revision.releasedBy, type: input.revision.releasedBy ? "HUMAN" : null },
    });
  }

  for (const a of input.audit) {
    const kind: DnaEventKind | null =
      a.entityType === "Feature"
        ? "GEOMETRY_CHANGED"
        : a.entityType === "Setup"
          ? "SETUP_RECORDED"
          : a.entityType === "PartResponsibilityProfile"
            ? "RESPONSIBILITY_STATED"
            : null;
    if (!kind) continue;
    events.push({
      at: a.createdAt,
      kind,
      title:
        kind === "GEOMETRY_CHANGED"
          ? `${a.action === "CREATE" ? "Feature added" : a.action === "DELETE" ? "Feature removed" : "Feature changed"}`
          : kind === "SETUP_RECORDED"
            ? "Setup geometry recorded"
            : "Responsibility stated",
      detail:
        a.reason ??
        (a.field && (a.oldValue || a.newValue)
          ? `${a.field}: ${a.oldValue ?? "not recorded"} → ${a.newValue ?? "not recorded"}`
          : `${a.action.toLowerCase()} on ${a.entityType}`),
      source: "AUDIT_LOG",
      sourceId: a.id,
      actor: { name: a.userName, type: statedActor(a.actorType) },
    });
  }

  for (const ap of input.approvals) {
    events.push({
      at: ap.approvedAt,
      kind: "APPROVED",
      title: ap.revokedAt ? "Approval later revoked" : `Approved — ${ap.scope.toLowerCase().replace(/_/g, " ")}`,
      detail: ap.statement,
      source: "APPROVAL",
      sourceId: ap.id,
      actor: { name: ap.userName, type: ap.userName ? "HUMAN" : null },
    });
  }

  for (const s of input.simulations) {
    events.push({
      at: s.runAt,
      kind: "SIMULATION_RUN",
      title: `Simulation run on ${s.setupName}`,
      detail: s.collisionChecked
        ? "Geometric simulation, with the cutter checked against a parametric jaw model. Not verified stock removal."
        : "Geometric simulation. The fixture was not modelled, so the cutter was not checked against the jaws.",
      source: "SIMULATION",
      sourceId: s.id,
      // A simulation is run by a person pressing play, but the row records no
      // user, so the actor is the system that produced it.
      actor: { name: null, type: "SYSTEM" },
    });
  }

  for (const j of input.jobs) {
    // A job raised before this was recorded contributes no "raised" event.
    // Putting it on the timeline at the moment the column appeared would be a
    // date nothing observed.
    if (j.createdAt) events.push({
      at: j.createdAt,
      kind: "JOB_RAISED",
      title: `Job ${j.jobNumber} raised`,
      detail: `Quantity ${j.quantity}.`,
      source: "JOB",
      sourceId: j.id,
      actor: { name: null, type: null },
    });
    if (j.completedAt) {
      events.push({
        at: j.completedAt,
        kind: "JOB_COMPLETED",
        title: `Job ${j.jobNumber} completed`,
        detail: [
          j.actualCycleMinutes != null ? `${j.actualCycleMinutes} min actual cycle` : "no actual cycle recorded",
          `${j.scrapCount} scrapped`,
        ].join(" · "),
        source: "JOB",
        sourceId: j.id,
        actor: { name: null, type: null },
      });
    }
  }

  for (const o of input.outcomes) {
    events.push({
      at: o.recordedAt,
      kind: "OUTCOME_OBSERVED",
      title: `${o.code.toLowerCase().replace(/_/g, " ")} on job ${o.jobNumber}`,
      detail:
        o.code === "SUCCESS"
          ? `${o.partsAffected} parts.`
          : `Cause: ${o.cause}. Then: ${o.correctiveAction}. ${o.partsAffected} parts affected.`,
      source: "JOB_OUTCOME",
      sourceId: o.id,
      actor: { name: o.recordedBy, type: o.recordedBy ? "HUMAN" : null },
    });
  }

  for (const i of input.inspections) {
    events.push({
      at: i.measuredAt,
      kind: "INSPECTION_RECORDED",
      title: `${i.label} ${i.pass ? "passed" : "failed"} inspection`,
      detail: `Measured ${i.measured}.`,
      source: "INSPECTION_RESULT",
      sourceId: i.id,
      actor: { name: i.inspector, type: i.inspector ? "HUMAN" : null },
    });
  }

  for (const d of input.disagreements) {
    events.push({
      at: d.createdAt,
      kind: "DISAGREEMENT_RAISED",
      title: `Disagreed with CANVAS on ${d.subjectType.toLowerCase().replace(/_/g, " ")}`,
      detail: `CANVAS said: ${d.canvasPosition} — the shop said: ${d.reasoning} (${d.status.toLowerCase().replace(/_/g, " ")})`,
      source: "DISAGREEMENT",
      sourceId: d.id,
      actor: { name: d.userName, type: d.userName ? "HUMAN" : null },
    });
  }

  for (const f of input.findingResolutions) {
    events.push({
      at: f.recordedAt,
      kind: "FINDING_ANSWERED",
      title: `Review finding answered — ${f.findingTitle}`,
      detail: `${f.status.toLowerCase()}: ${f.note}`,
      source: "FINDING_RESOLUTION",
      sourceId: f.id,
      actor: { name: f.actorName, type: statedActor(f.actorType) },
    });
  }

  // Newest first, and stable: two events at the same instant keep the order
  // their sources were read in rather than swapping between page loads.
  return events
    .map((e, i) => ({ e, i }))
    .sort((a, b) => b.e.at.getTime() - a.e.at.getTime() || a.i - b.i)
    .map(({ e }) => e);
}

/** What the timeline could not draw on, so an empty history reads correctly. */
export function dnaCoverage(input: DnaInput): { source: DnaSource; present: boolean }[] {
  return [
    { source: "AUDIT_LOG", present: input.audit.length > 0 },
    { source: "APPROVAL", present: input.approvals.length > 0 },
    { source: "SIMULATION", present: input.simulations.length > 0 },
    { source: "JOB", present: input.jobs.length > 0 },
    { source: "JOB_OUTCOME", present: input.outcomes.length > 0 },
    { source: "INSPECTION_RESULT", present: input.inspections.length > 0 },
    { source: "DISAGREEMENT", present: input.disagreements.length > 0 },
    { source: "FINDING_RESOLUTION", present: input.findingResolutions.length > 0 },
  ];
}
