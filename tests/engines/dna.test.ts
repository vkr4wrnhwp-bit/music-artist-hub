import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { DNA_EVENT_KINDS, DNA_KIND_LABEL, buildDnaTimeline, dnaCoverage, type DnaInput } from "@/lib/engines/dna";

/**
 * "Attach history to a PartRevision. Show timeline: initial release, bore
 * nominal changed, soft jaws added, chatter observed, inspection passed,
 * workholding failure corrected, process revised."
 *
 * The ManufacturingDNA model was keyed to Part, had no event shape, no
 * provenance and no write site outside the seed; the UI was a four-column
 * table. The design decision here is that the timeline is DERIVED — every
 * event points at a record somebody's action created — because a
 * hand-maintained one can claim an event that never happened.
 */

const D = (s: string) => new Date(s);

const EMPTY: DnaInput = {
  revision: { id: "rev1", revision: "A", createdAt: D("2026-01-01T09:00:00Z"), releasedAt: null, releasedBy: null },
  audit: [], approvals: [], simulations: [], jobs: [], outcomes: [], inspections: [], disagreements: [], findingResolutions: [],
};

test("an untouched revision still has the one event that is true of it", () => {
  const t = buildDnaTimeline(EMPTY);
  assert.equal(t.length, 1);
  assert.equal(t[0].kind, "REVISION_CREATED");
  assert.equal(t[0].source, "PART_REVISION");
});

test("nothing is invented for a revision nothing has happened to", () => {
  // The failure this guards is a timeline that fills itself with plausible
  // milestones a part "would have" passed.
  const t = buildDnaTimeline(EMPTY);
  assert.ok(!t.some((e) => e.kind === "RELEASED"), "an unreleased revision reported a release");
  assert.ok(!t.some((e) => e.kind === "APPROVED"));
  assert.ok(!t.some((e) => e.kind === "JOB_RAISED"));
});

test("every event points at the record it was read from", () => {
  const t = buildDnaTimeline({
    ...EMPTY,
    revision: { ...EMPTY.revision, releasedAt: D("2026-02-01T10:00:00Z"), releasedBy: "Demo Operator" },
    audit: [{ id: "a1", entityType: "Feature", entityId: "f1", action: "UPDATE", field: "diameter", oldValue: "1.5000", newValue: "1.5748", actorType: "HUMAN", reason: null, createdAt: D("2026-01-10T10:00:00Z"), userName: "Machinist" }],
    outcomes: [{ id: "o1", jobNumber: "J-1", code: "CHATTER", cause: "Excessive stickout", correctiveAction: "Shortened the stickout", partsAffected: 2, recordedAt: D("2026-03-01T10:00:00Z"), recordedBy: "Machinist" }],
  });
  for (const e of t) {
    assert.ok(e.sourceId.length > 0, `${e.kind} has no source record`);
    assert.ok(e.at instanceof Date && Number.isFinite(e.at.getTime()), `${e.kind} has no usable timestamp`);
  }
});

test("the events the brief names all come out of real records", () => {
  const t = buildDnaTimeline({
    revision: { id: "rev1", revision: "A", createdAt: D("2026-01-01T09:00:00Z"), releasedAt: D("2026-02-01T09:00:00Z"), releasedBy: "Demo Operator" },
    audit: [
      { id: "a1", entityType: "Feature", entityId: "f1", action: "UPDATE", field: "diameter", oldValue: "1.5000", newValue: "1.5748", actorType: "HUMAN", reason: null, createdAt: D("2026-01-10T10:00:00Z"), userName: "Machinist" },
      { id: "a2", entityType: "Setup", entityId: "s1", action: "UPDATE", field: "geometry", oldValue: "grip 0.25 (planned)", newValue: "grip 0.40 (measured)", actorType: "HUMAN", reason: "Recorded the setup as actually built.", createdAt: D("2026-01-12T10:00:00Z"), userName: "Machinist" },
    ],
    approvals: [{ id: "ap1", scope: "MANUFACTURING_PACKAGE", statement: "Approved", approvedAt: D("2026-01-31T10:00:00Z"), revokedAt: null, userName: "Lead" }],
    simulations: [{ id: "sim1", runAt: D("2026-01-20T10:00:00Z"), collisionChecked: false, setupName: "Setup 1" }],
    jobs: [{ id: "j1", jobNumber: "J-1", quantity: 25, status: "COMPLETE", createdAt: D("2026-02-02T10:00:00Z"), completedAt: D("2026-02-10T10:00:00Z"), actualCycleMinutes: 12, scrapCount: 1 }],
    outcomes: [
      { id: "o1", jobNumber: "J-1", code: "CHATTER", cause: "Excessive stickout", correctiveAction: "Shortened the stickout", partsAffected: 2, recordedAt: D("2026-02-05T10:00:00Z"), recordedBy: "Machinist" },
      { id: "o2", jobNumber: "J-1", code: "WORKHOLDING_FAILURE", cause: "Jaw wear", correctiveAction: "Replaced the jaws", partsAffected: 1, recordedAt: D("2026-02-06T10:00:00Z"), recordedBy: "Machinist" },
    ],
    inspections: [{ id: "i1", label: "40 mm bore", measured: 1.5749, pass: true, measuredAt: D("2026-02-11T10:00:00Z"), inspector: "QA" }],
    disagreements: [{ id: "d1", subjectType: "PROCESS", canvasPosition: "Two setups", reasoning: "One is enough on the 4th axis", status: "ACCEPTED_AS_KNOWLEDGE", createdAt: D("2026-01-25T10:00:00Z"), userName: "Machinist" }],
    findingResolutions: [{ id: "fr1", findingTitle: "Tool cannot reach depth", status: "ACTIONED", note: "Longer tool", actorType: "HUMAN", actorName: "Machinist", recordedAt: D("2026-01-28T10:00:00Z") }],
  });
  const kinds = new Set(t.map((e) => e.kind));
  for (const expected of ["RELEASED", "GEOMETRY_CHANGED", "SETUP_RECORDED", "OUTCOME_OBSERVED", "INSPECTION_RECORDED", "DISAGREEMENT_RAISED", "APPROVED"]) {
    assert.ok(kinds.has(expected as never), `${expected} does not appear`);
  }
  // "chatter observed" and "workholding failure corrected" are both outcomes,
  // and the corrective action is carried, not dropped.
  const wh = t.find((e) => e.title.includes("workholding failure"))!;
  assert.match(wh.detail, /Replaced the jaws/);
});

test("newest first, and stable when two events share an instant", () => {
  const at = D("2026-01-05T10:00:00Z");
  const t = buildDnaTimeline({
    ...EMPTY,
    audit: [
      { id: "a1", entityType: "Feature", entityId: "f1", action: "CREATE", field: null, oldValue: null, newValue: null, actorType: "HUMAN", reason: "first", createdAt: at, userName: "A" },
      { id: "a2", entityType: "Feature", entityId: "f2", action: "CREATE", field: null, oldValue: null, newValue: null, actorType: "HUMAN", reason: "second", createdAt: at, userName: "A" },
    ],
  });
  const times = t.map((e) => e.at.getTime());
  assert.deepEqual([...times].sort((a, b) => b - a), times, "the timeline is not newest first");
  const tied = t.filter((e) => e.at.getTime() === at.getTime());
  assert.deepEqual(tied.map((e) => e.sourceId), ["a1", "a2"], "tied events swapped order");
});

test("an actor type is read from the record, never assumed", () => {
  // Principle 13's discipline on a read surface: an unrecorded actor is a
  // missing fact, not a human by default.
  const t = buildDnaTimeline({
    ...EMPTY,
    audit: [{ id: "a1", entityType: "Feature", entityId: "f1", action: "CREATE", field: null, oldValue: null, newValue: null, actorType: "AI", reason: "accepted a suggestion", createdAt: D("2026-01-02T10:00:00Z"), userName: null }],
    outcomes: [{ id: "o1", jobNumber: "J-1", code: "SUCCESS", cause: "—", correctiveAction: "—", partsAffected: 25, recordedAt: D("2026-01-03T10:00:00Z"), recordedBy: null }],
  });
  assert.equal(t.find((e) => e.sourceId === "a1")!.actor.type, "AI", "a recorded AI actor was not carried through");
  assert.equal(t.find((e) => e.sourceId === "o1")!.actor.type, null, "an unrecorded actor was assumed");
  assert.equal(t.find((e) => e.kind === "REVISION_CREATED")!.actor.type, null);
});

test("an actor type outside the vocabulary is not carried through", () => {
  const t = buildDnaTimeline({
    ...EMPTY,
    audit: [{ id: "a1", entityType: "Feature", entityId: "f1", action: "CREATE", field: null, oldValue: null, newValue: null, actorType: "ROBOT", reason: null, createdAt: D("2026-01-02T10:00:00Z"), userName: null }],
  });
  assert.equal(t.find((e) => e.sourceId === "a1")!.actor.type, null);
});

test("an audit entry on something else does not become a timeline event", () => {
  // The audit log is organisation-wide. Only entities under this revision are
  // events in its history.
  const t = buildDnaTimeline({
    ...EMPTY,
    audit: [{ id: "a1", entityType: "Machine", entityId: "m1", action: "UPDATE", field: "maxFeed", oldValue: "400", newValue: "500", actorType: "HUMAN", reason: null, createdAt: D("2026-01-02T10:00:00Z"), userName: "A" }],
  });
  assert.equal(t.length, 1, "an unrelated audit entry became history");
});

test("a simulation says whether the fixture was modelled", () => {
  const off = buildDnaTimeline({ ...EMPTY, simulations: [{ id: "s1", runAt: D("2026-01-02T10:00:00Z"), collisionChecked: false, setupName: "Setup 1" }] });
  assert.match(off.find((e) => e.kind === "SIMULATION_RUN")!.detail, /fixture was not modelled/);
  const on = buildDnaTimeline({ ...EMPTY, simulations: [{ id: "s1", runAt: D("2026-01-02T10:00:00Z"), collisionChecked: true, setupName: "Setup 1" }] });
  assert.match(on.find((e) => e.kind === "SIMULATION_RUN")!.detail, /parametric jaw model/);
});

test("a job that never completed reports no completion", () => {
  const t = buildDnaTimeline({ ...EMPTY, jobs: [{ id: "j1", jobNumber: "J-1", quantity: 5, status: "RUNNING", createdAt: D("2026-01-02T10:00:00Z"), completedAt: null, actualCycleMinutes: null, scrapCount: 0 }] });
  assert.equal(t.filter((e) => e.kind === "JOB_COMPLETED").length, 0);
  assert.equal(t.filter((e) => e.kind === "JOB_RAISED").length, 1);
});

test("an unrecorded cycle time says so rather than reading as zero", () => {
  const t = buildDnaTimeline({ ...EMPTY, jobs: [{ id: "j1", jobNumber: "J-1", quantity: 5, status: "COMPLETE", createdAt: D("2026-01-02T10:00:00Z"), completedAt: D("2026-01-09T10:00:00Z"), actualCycleMinutes: null, scrapCount: 0 }] });
  assert.match(t.find((e) => e.kind === "JOB_COMPLETED")!.detail, /no actual cycle recorded/);
});

test("every event kind has a label", () => {
  for (const k of DNA_EVENT_KINDS) assert.ok(DNA_KIND_LABEL[k], `${k} has no label`);
  assert.deepEqual(Object.keys(DNA_KIND_LABEL).sort(), [...DNA_EVENT_KINDS].sort());
});

test("coverage names the sources that had nothing in them", () => {
  // A short history means little has happened, not that little was checked,
  // and the page has to be able to say which.
  const c = dnaCoverage(EMPTY);
  assert.ok(c.length >= 8);
  assert.ok(c.every((x) => !x.present));
  const withJobs = dnaCoverage({ ...EMPTY, jobs: [{ id: "j1", jobNumber: "J-1", quantity: 1, status: "PLANNED", createdAt: D("2026-01-02T10:00:00Z"), completedAt: null, actualCycleMinutes: null, scrapCount: 0 }] });
  assert.equal(withJobs.find((x) => x.source === "JOB")!.present, true);
});

/* ---- derived, not authored ---- */

const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");

test("the timeline has no write path at all", () => {
  // The moment it can be typed into it can claim an event that never
  // happened, which is the whole reason it is derived.
  const engine = strip(readFileSync("src/lib/engines/dna.ts", "utf8"));
  assert.ok(!/db\./.test(engine), "the engine reaches the database");
  const page = strip(readFileSync("src/app/(app)/parts/[id]/history/page.tsx", "utf8"));
  assert.ok(!/db\.\w+\.(create|update|delete|upsert)/.test(page), "the history page writes something");
  assert.ok(!/"use server"/.test(page), "the history page grew an action");
});

test("no model is consulted to summarise history", () => {
  const engine = readFileSync("src/lib/engines/dna.ts", "utf8");
  assert.ok(!/from "@\/lib\/ai\//.test(engine), "the timeline consults a model");
});

test("a completed job writes the manufacturing record", () => {
  // /intelligence has always said "each completed job writes an immutable
  // snapshot" and nothing ever wrote one.
  const src = strip(readFileSync("src/app/(app)/jobs/actions.ts", "utf8"));
  assert.match(src, /if \(to === "COMPLETE"\)/);
  assert.match(src, /db\.manufacturingDNA\.create/);
  assert.match(src, /geometrySource: s\.geometrySource/, "the snapshot does not record whether the setup was measured");
  assert.match(src, /costActual: null/, "a cost was derived rather than left unrecorded");
});


test("a job raised before the date was recorded contributes no raised event", () => {
  // Putting it on the timeline at the moment the column appeared would be a
  // date nothing observed. The completion, which IS recorded, still appears.
  const t = buildDnaTimeline({
    ...EMPTY,
    jobs: [{ id: "j1", jobNumber: "J-old", quantity: 5, status: "COMPLETE", createdAt: null, completedAt: D("2026-01-09T10:00:00Z"), actualCycleMinutes: 9, scrapCount: 0 }],
  });
  assert.equal(t.filter((e) => e.kind === "JOB_RAISED").length, 0);
  assert.equal(t.filter((e) => e.kind === "JOB_COMPLETED").length, 1);
});

test("the job creation date is written, not left to a database default", () => {
  // SQLite cannot ADD COLUMN NOT NULL with a non-constant default, so the
  // column is nullable and the action states the time.
  const src = readFileSync("src/app/(app)/jobs/actions.ts", "utf8");
  assert.match(src, /createdAt: new Date\(\)/);
});

test("both migration trees add the column the same way", () => {
  const sqlite = readFileSync("prisma/migrations/20260902160000_job_created_at/migration.sql", "utf8");
  const pg = readFileSync("prisma/migrations-postgres/20260902160010_job_created_at/migration.sql", "utf8");
  // The comments explain why there is no NOT NULL and no DEFAULT, so they are
  // stripped before the statement itself is checked.
  const statements = (sql: string) => sql.split("\n").filter((l) => !l.trim().startsWith("--")).join("\n");
  for (const [name, raw] of [["sqlite", sqlite], ["postgres", pg]] as const) {
    const sql = statements(raw);
    assert.match(sql, /ADD COLUMN "createdAt"/, `${name} does not add the column`);
    assert.ok(!/NOT NULL/.test(sql), `${name} adds it NOT NULL — SQLite cannot, and existing rows would need a fabricated date`);
    assert.ok(!/DEFAULT/.test(sql), `${name} backfills existing rows with a date nothing observed`);
  }
});


test("the manufacturing record survives a snapshot written in another shape", () => {
  // Caught in the browser: the seeded row stores {setups: 2, machine, tools}
  // — setups is a COUNT, not an array — and reading it as today's shape threw
  // and took the whole page down. A stored blob is whatever was written when
  // the job completed, which may be older than the code reading it.
  const src = readFileSync("src/app/(app)/intelligence/page.tsx", "utf8");
  assert.match(src, /catch \{\s*return \{\};/, "a malformed snapshot is not caught");
  assert.match(src, /Array\.isArray\(snap\.setups\)/, "setups is read as an array without checking");
  assert.ok(
    !/snap\.setups \?\? \[\]/.test(src),
    "an unreadable snapshot is coerced to an empty array, which reads as 'no setups' rather than 'not recorded'",
  );
  assert.match(src, /not recorded/, "an unreadable field is guessed at rather than reported");
});

test("a zero cycle estimate is no estimate, not an estimate of zero", () => {
  // cycleMinutes reads 0 when no toolpath was generated. Printing "0.0"
  // beside a real actual invites a comparison against nothing.
  const src = readFileSync("src/app/(app)/intelligence/page.tsx", "utf8");
  assert.match(src, /estimatedRaw != null && estimatedRaw > 0 \? estimatedRaw : null/);
  assert.match(src, /"no estimate"/);
});
