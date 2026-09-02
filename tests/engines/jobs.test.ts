import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  JOB_STATUSES,
  NEXT_STATUS,
  canTransition,
  compareCycle,
  evaluateRelease,
  outcomeApplies,
  releaseSnapshot,
  validateOutcome,
  type JobStatus,
} from "@/lib/engines/jobs";
import { JOB_OUTCOMES, OUTCOME_CAUSES } from "@/lib/engines/network";
import type { ReadinessGate } from "@/lib/engines/readiness";

/**
 * The Jobs section described job outcomes as the most valuable data a shop
 * generates and then showed rows only the seed had written. Nothing could
 * create a Job or a JobOutcome, and the entry point the page named — "jobs
 * are created from a released part revision" — did not exist either, because
 * nothing anywhere set a revision to RELEASED.
 */

const gate = (id: string, status: ReadinessGate["status"], blocking: boolean): ReadinessGate => ({
  id, label: id, status, blocking, detail: `${id} detail`, actions: [],
} as ReadinessGate);

/* ---------------- Release ---------------- */

test("one unresolved blocking gate refuses the release, however many pass", () => {
  // Principle 1 on a second surface: the aggregate is the worst unresolved
  // required gate. Nine passes and one blocking failure is a refusal, not 90%.
  const gates = [
    ...Array.from({ length: 9 }, (_, i) => gate(`ok${i}`, "PASS", true)),
    gate("inspection", "FAIL", true),
  ];
  const v = evaluateRelease(gates);
  assert.equal(v.ok, false);
  assert.deepEqual(v.blockers.map((b) => b.id), ["inspection"]);
});

test("every non-PASS blocking status blocks, not only FAIL", () => {
  // MISSING and NOT_ATTEMPTED are not "nearly passing".
  for (const status of ["REVIEW", "MISSING", "FAIL", "NOT_ATTEMPTED"] as const) {
    assert.equal(evaluateRelease([gate("g", status, true)]).ok, false, `${status} did not block`);
  }
  assert.equal(evaluateRelease([gate("g", "PASS", true)]).ok, true);
});

test("a non-blocking gate that is short is a reservation, not a refusal", () => {
  const v = evaluateRelease([gate("blocking", "PASS", true), gate("nice-to-have", "REVIEW", false)]);
  assert.equal(v.ok, true);
  assert.deepEqual(v.reservations.map((r) => r.id), ["nice-to-have"]);
  assert.deepEqual(v.blockers, []);

  // And the two lists do not overlap: a blocking gate that is short is a
  // blocker, and reporting it a second time as a reservation would read as
  // something the shop may release over.
  const mixed = evaluateRelease([gate("hard", "MISSING", true), gate("soft", "REVIEW", false)]);
  assert.deepEqual(mixed.blockers.map((b) => b.id), ["hard"]);
  assert.deepEqual(mixed.reservations.map((r) => r.id), ["soft"]);
});

test("the blockers name themselves, so the refusal is actionable", () => {
  const v = evaluateRelease([gate("metrology", "MISSING", true)]);
  assert.equal(v.blockers[0].label, "metrology");
  assert.match(v.blockers[0].detail, /detail/);
});

test("the release snapshot records every gate, not just the failures", () => {
  // What a job outcome has to answer afterwards is what was known when the
  // shop said run it. A snapshot of only the problems cannot answer it.
  const gates = [gate("a", "PASS", true), gate("b", "REVIEW", false), gate("c", "MISSING", true)];
  const snap = releaseSnapshot(gates);
  assert.equal(snap.gates.length, 3, "the snapshot dropped gates");
  assert.deepEqual(snap.gates.map((g) => g.status), ["PASS", "REVIEW", "MISSING"]);
  assert.ok(snap.gates.every((g) => "blocking" in g && "status" in g && "label" in g));
  // The overall comes from readiness.ts's own aggregate, not a second copy of
  // the rule: one blocking gate short is NOT_READY_TO_RUN whatever else passes.
  assert.equal(snap.overall, "NOT_READY_TO_RUN");
  assert.equal(snap.blockingCount, 1);
});

/* ---------------- Lifecycle ---------------- */

test("a job cannot skip setup and running to reach complete", () => {
  // The actuals recorded against it would describe a setup and a run that
  // never happened.
  assert.equal(canTransition("PLANNED", "COMPLETE"), false);
  assert.equal(canTransition("PLANNED", "RUNNING"), false);
  assert.equal(canTransition("PLANNED", "SETUP"), true);
  assert.equal(canTransition("SETUP", "RUNNING"), true);
  assert.equal(canTransition("RUNNING", "COMPLETE"), true);
});

test("complete and cancelled are terminal", () => {
  // A finished job is the record of what happened; another run is another job.
  assert.deepEqual(NEXT_STATUS.COMPLETE, []);
  assert.deepEqual(NEXT_STATUS.CANCELLED, []);
  for (const to of JOB_STATUSES) {
    assert.equal(canTransition("COMPLETE", to), false, `COMPLETE → ${to} was allowed`);
    assert.equal(canTransition("CANCELLED", to), false, `CANCELLED → ${to} was allowed`);
  }
});

test("a status outside the vocabulary transitions nowhere", () => {
  assert.equal(canTransition("HALFWAY", "COMPLETE"), false);
  assert.equal(canTransition("PLANNED", "SHIPPED"), false);
});

test("every status is reachable and every transition is declared", () => {
  const declared = Object.keys(NEXT_STATUS) as JobStatus[];
  assert.deepEqual(declared.sort(), [...JOB_STATUSES].sort());
  for (const from of JOB_STATUSES) {
    for (const to of NEXT_STATUS[from]) {
      assert.ok((JOB_STATUSES as readonly string[]).includes(to), `${from} → ${to} is not a status`);
    }
  }
});

/* ---------------- Estimated against actual ---------------- */

test("a comparison needs both sides and is refused otherwise", () => {
  // A cycle time compared against a substituted estimate is a number that
  // looks like feedback and is not.
  assert.equal(compareCycle(null, 12), null);
  assert.equal(compareCycle(10, null), null);
  assert.equal(compareCycle(null, null), null);
  assert.equal(compareCycle(0, 12), null, "a zero estimate produced a ratio");
  assert.equal(compareCycle(10, -1), null);
});

test("the comparison is arithmetic, in both directions", () => {
  const over = compareCycle(10, 13)!;
  assert.equal(over.ratio, 1.3);
  assert.equal(over.deltaMinutes, 3);
  const under = compareCycle(10, 8)!;
  assert.equal(under.ratio, 0.8);
  assert.equal(under.deltaMinutes, -2);
});

/* ---------------- Outcomes ---------------- */

const ok = {
  code: "CHATTER",
  cause: "Excessive stickout",
  correctiveAction: "Shortened the stickout to 1.100 and re-cut",
  partsAffected: 2,
  operationId: null,
  toolNumber: 4,
  notes: "",
};

test("a well-formed failure outcome is accepted", () => {
  assert.deepEqual(validateOutcome(ok), []);
});

test("a cause outside the taxonomy is refused, never filed under OTHER", () => {
  // A mislabelled outcome is worse than a rejected one: everything downstream
  // that counts outcomes will count it as something it is not.
  const r = validateOutcome({ ...ok, cause: "it just sort of rattled" });
  assert.equal(r.length, 1);
  assert.equal(r[0].field, "cause");
  assert.match(r[0].reason, /not one of the causes/);
});

test("a cause valid for a different code is still refused", () => {
  // "Feed too high" belongs to TOOL_BREAK, not to PART_MOVED.
  const r = validateOutcome({ ...ok, code: "PART_MOVED", cause: "Feed too high" });
  assert.ok(r.some((x) => x.field === "cause"));
});

test("a failure with no corrective action is refused", () => {
  for (const action of ["", "fixed", "   ", "did stuff"]) {
    const r = validateOutcome({ ...ok, correctiveAction: action });
    assert.ok(r.some((x) => x.field === "correctiveAction"), `"${action}" was accepted`);
  }
});

test("SUCCESS needs no corrective action", () => {
  assert.deepEqual(validateOutcome({ ...ok, code: "SUCCESS", cause: "—", correctiveAction: "" }), []);
});

test("parts affected must be a whole number", () => {
  for (const n of [-1, 1.5, NaN]) {
    assert.ok(validateOutcome({ ...ok, partsAffected: n }).some((x) => x.field === "partsAffected"), `${n} accepted`);
  }
});

test("an unknown code is refused before anything else is checked", () => {
  const r = validateOutcome({ ...ok, code: "EXPLODED" });
  assert.equal(r.length, 1);
  assert.equal(r[0].field, "code");
});

test("every outcome code has causes declared for it", () => {
  // A code with no cause list would make every cause invalid and the outcome
  // unrecordable — a silent dead end in the form.
  for (const code of JOB_OUTCOMES) {
    assert.ok(OUTCOME_CAUSES[code]?.length > 0, `${code} has no causes`);
  }
});

/* ---------------- What an outcome may teach ---------------- */

const scope = { machine: "m1", material: "6061-T6", workholding: "v1", toolNumber: 4 };

test("an observation applies only where the whole scope matches", () => {
  assert.equal(outcomeApplies(scope, scope), true);
  assert.equal(outcomeApplies(scope, { ...scope, machine: "m2" }), false);
  assert.equal(outcomeApplies(scope, { ...scope, material: "17-4 PH" }), false);
  assert.equal(outcomeApplies(scope, { ...scope, workholding: "v2" }), false);
});

test("a null is a missing fact, not a wildcard, on either side", () => {
  // Principle 11. Treating an unrecorded machine as "matches anything" would
  // promote one shop's observation into a general claim.
  assert.equal(outcomeApplies({ ...scope, machine: null }, scope), false);
  assert.equal(outcomeApplies(scope, { ...scope, machine: null }), false);
  assert.equal(
    outcomeApplies({ machine: null, material: null, workholding: null, toolNumber: null },
      { machine: null, material: null, workholding: null, toolNumber: null }),
    false,
    "two unrecorded scopes matched each other",
  );
});

test("the tool number does not narrow the scope by itself", () => {
  // A vise that lets go is about the setup, not about which endmill was in
  // the spindle. The tool is carried for the reader, not for the match.
  assert.equal(outcomeApplies(scope, { ...scope, toolNumber: 9 }), true);
});

/* ---------------- The write path ---------------- */

const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
const actions = () => strip(readFileSync("src/app/(app)/jobs/actions.ts", "utf8"));
const release = () => strip(readFileSync("src/app/(app)/parts/[id]/release-actions.ts", "utf8"));

test("every job write re-resolves the row against the session's organisation", () => {
  const src = actions();
  const writes = [...src.matchAll(/db\.(job|jobOutcome)\.(create|update)/g)];
  assert.ok(writes.length >= 4, `expected the four write sites, found ${writes.length}`);
  // Each action reads the job scoped by organizationId before touching it.
  assert.equal((src.match(/organizationId: user\.organizationId/g) ?? []).length >= 4, true);
  assert.ok(!/organizationId:\s*String\(formData/.test(src), "an organisation was read from a form");
});

test("release refuses on the server, from gates it evaluates itself", () => {
  // A release decided on what the client happened to be showing is a release
  // decided on a stale page.
  const src = release();
  assert.match(src, /buildPackage\(user\.organizationId/);
  assert.match(src, /evaluateRelease\(pkg\.readiness\.gates\)/);
  assert.match(src, /if \(!verdict\.ok\) return;/);
  assert.ok(!/formData\.get\("(force|override|ignoreGates)"\)/.test(src), "release grew an override");
});

test("release writes a decision and never a gate", () => {
  const src = release();
  const writes = [...src.matchAll(/db\.(\w+)\.(create|update|updateMany|upsert|delete)/g)].map((m) => `${m[1]}.${m[2]}`);
  assert.deepEqual(writes, ["partRevision.update"], "release wrote something other than the revision");
  assert.ok(!/readiness|gate.*status.*PASS/i.test(src.replace(/pkg\.readiness\.gates/g, "")), "release touches a gate");
});

test("an actual is never seeded from an estimate", () => {
  // The comparison would then agree with itself, on every job, forever.
  const src = actions();
  // Not "does the identifier contain the word cycle" — does the actual take a
  // value from anywhere but the form.
  assert.match(src, /actualCycleMinutes: num\("actualCycleMinutes"\)/);
  assert.match(src, /actualSetupHours: num\("actualSetupHours"\)/);
  assert.ok(!/actualCycleMinutes:[^,\n]*\?\?[^,\n]*(estimated|snapshot|pkg\.)/i.test(src), "the actual falls back to an estimate");
  assert.match(src, /if \(raw === ""\) return null;/);
});

test("an outcome is validated server-side, not only narrowed by the form", () => {
  const src = actions();
  assert.match(src, /validateOutcome\(draft\)\.length > 0\) return;/);
});

test("the outcome's scope is captured at recording time, not looked up later", () => {
  const src = actions();
  assert.match(src, /machineId: setup\?\.machineId \?\? null/);
  assert.match(src, /materialName:/);
});

test("job outcomes are read back only within the organisation", () => {
  const src = strip(readFileSync("src/lib/job-knowledge.ts", "utf8"));
  assert.match(src, /job: \{ organizationId \}/);
  assert.match(src, /outcomeApplies\(/, "the scope rule is re-implemented rather than reused");
});
