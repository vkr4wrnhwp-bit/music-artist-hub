import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { programDigest, proofState } from "@/lib/nc/proof";
import { evaluateReadiness } from "@/lib/engines/readiness";
import { emptyPartIntent } from "@/lib/domain/part-intent";

/**
 * PROOF-OUT
 *
 * Whether a program has ever cut a good part is the first thing anybody wants
 * to know about it, and nothing in the schema recorded it. A program proven on
 * the VF-2 last Tuesday and the same program never run were indistinguishable,
 * and no machinist treats them the same.
 *
 * The failure to guard against is a proof that outlives the program it was
 * about: re-post, and the record goes on vouching for text nobody has run.
 */

const CODE = "%\nO1000\nG20\nG1 X1.0 F20.\nM30\n%";
const RUN_AT = new Date("2026-08-20T09:00:00Z");

const proven = {
  provenAt: RUN_AT,
  provenByName: "R. Hale",
  provenMachineId: "m1",
  provenNote: "first article passed, 0.0002 over on the bore",
  provenDigest: programDigest(CODE),
};

test("a program nobody has run reads NEVER RUN", () => {
  const v = proofState(
    { provenAt: null, provenByName: null, provenMachineId: null, provenNote: null, provenDigest: null },
    CODE,
    "Haas VF-2",
  );
  assert.equal(v.state, "NEVER_RUN");
  // And it tells the machinist how to treat it rather than just labelling it.
  assert.match(v.detail, /single block, dry run above the part, hand on the feed hold/);
});

test("a proven program names who, when and where", () => {
  const v = proofState(proven, CODE, "Haas VF-2");
  assert.equal(v.state, "PROVEN");
  assert.match(v.detail, /Haas VF-2/);
  assert.match(v.detail, /2026-08-20/);
  assert.match(v.detail, /R\. Hale/);
  assert.match(v.detail, /first article passed/);
});

test("re-posting makes the proof stale by itself", () => {
  // The whole point of the digest. A proof is about specific bytes, and an
  // approval that survives the thing it approved is worse than none, because
  // somebody relies on it.
  const v = proofState(proven, CODE + "\n(REGENERATED)\n", "Haas VF-2");
  assert.equal(v.state, "STALE");
  assert.match(v.detail, /has changed since it was proven/);
  assert.match(v.detail, /Prove it again/);
});

test("a record with a date but no digest is not proven", () => {
  // A half-written record vouches for nothing. It must not read as PROVEN
  // just because a timestamp is present.
  const v = proofState({ ...proven, provenDigest: null }, CODE, "Haas VF-2");
  assert.equal(v.state, "NEVER_RUN");
});

/* ---------------- The gate ---------------- */

const gate = (proof?: { state: "NEVER_RUN" | "PROVEN" | "STALE"; detail: string }, ncGenerated = true) =>
  evaluateReadiness({
    intent: emptyPartIntent("Proof test"),
    stock: null,
    features: [],
    machine: null,
    tools: [],
    workholding: null,
    workholdingAssessment: null,
    hasInspectionPlan: false,
    simulationRun: false,
    ncGenerated,
    proof,
    operatorApproved: false,
  }).gates.find((g) => g.id === "proof")!;

test("the proof gate never blocks", () => {
  /*
   * Deliberate. A program that has never cut a part is the normal state of
   * every new program, and a gate that refused to release one would make first
   * articles impossible — which is to say it would be routed around inside a
   * week. It makes the distinction visible, not impossible.
   */
  for (const state of ["NEVER_RUN", "PROVEN", "STALE"] as const) {
    assert.equal(gate({ state, detail: "x" }).blocking, false, `${state} blocks`);
  }
  assert.equal(gate(undefined, false).blocking, false);
});

test("never-run and stale both read REVIEW, proven reads PASS", () => {
  assert.equal(gate({ state: "PROVEN", detail: "x" }).status, "PASS");
  assert.equal(gate({ state: "NEVER_RUN", detail: "x" }).status, "REVIEW");
  assert.equal(gate({ state: "STALE", detail: "x" }).status, "REVIEW");
});

test("a stale program is told to be proven again, not just flagged", () => {
  assert.ok(gate({ state: "STALE", detail: "x" }).actions.some((a) => /again/i.test(a)));
});

test("no program at all is NOT_ATTEMPTED rather than never-run", () => {
  // There is nothing to have run. Saying "this program has never cut a part"
  // about a program that does not exist is a true sentence describing the
  // wrong situation.
  assert.equal(gate(undefined, false).status, "NOT_ATTEMPTED");
});

/* ---------------- Routing ---------------- */

test("SHOW ME on the proof gate offers no link", () => {
  // It is resolved at the machine with a part in the vise. Before the id took
  // priority over the label, "Proven on the machine" substring-matched the
  // MACHINE gate and sent the operator to stock definition — a link to the one
  // screen with nothing to do with the blocker.
  const { showMeHrefFor } = require("@/lib/guide/show-me") as typeof import("@/lib/guide/show-me");
  assert.equal(showMeHrefFor("p1", "proof", "Proven on the machine"), null);
  // The machine gate itself still resolves.
  assert.ok(showMeHrefFor("p1", "machine", "Machine envelope"));
});

/* ---------------- The record ---------------- */

test("recording a run stores the digest of the code it was about", () => {
  const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
  const src = strip(readFileSync("src/app/(app)/parts/[id]/nc/actions.ts", "utf8"));
  assert.ok(/provenDigest: programDigest\(program\.code\)/.test(src), "the proof does not record which bytes it was about");
  assert.ok(/actorType: "HUMAN"/.test(src), "the run is not recorded as a human act");
  // A required sentence, not a checkbox: "first article passed, 0.0002 over on
  // the bore" is what the next person needs.
  assert.ok(/const clearing = note === ""/.test(src), "an empty note is not treated as withdrawing the record");
});
