import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { postValidationState, type PostValidationRecord } from "@/lib/engines/post-validation";
import { evaluateReadiness } from "@/lib/engines/readiness";
import { emptyPartIntent } from "@/lib/domain/part-intent";

/**
 * POST VALIDATION
 *
 * `PostDefinition.certified` is typed as the literal `false` — the same trick
 * as `clearableByConfirmation` — and that was correct and also a dead end.
 * There was no path OUT: no record of a post having been validated, against
 * which machine and which control software, by whom, with what evidence. Every
 * post was permanently DEVELOPMENT, which is honest right up until it becomes
 * the label nobody reads.
 */

const rec = (over: Partial<PostValidationRecord> = {}): PostValidationRecord => ({
  postId: "haas-ngc-dev",
  machineId: "m1",
  controlVersion: "100.22.000.1130",
  validatedByName: "R. Hale",
  validatedAt: new Date("2026-08-01T10:00:00Z"),
  evidence: "Cut air above the part, single blocked the whole program, first article to print",
  revokedAt: null,
  ...over,
});

const labels = { post: "Haas NGC (development)", machine: "Haas VF-2" };
const state = (records: PostValidationRecord[], control: string | null = "100.22.000.1130") =>
  postValidationState(records, "haas-ngc-dev", "m1", control, labels);

test("a post proven on this machine at this control version is validated", () => {
  const v = state([rec()]);
  assert.equal(v.state, "VALIDATED");
  assert.match(v.detail, /Haas VF-2/);
  assert.match(v.detail, /R\. Hale/);
  assert.match(v.detail, /single blocked/);
});

test("a post nobody has proven here is not validated", () => {
  const v = state([]);
  assert.equal(v.state, "NONE");
  assert.match(v.detail, /never been validated/);
  assert.match(v.detail, /nobody has watched run/);
});

test("a proof on another machine does not carry over", () => {
  // Different travels, different changer, possibly a different control
  // generation. A post proven on the VF-2 says nothing about the VF-4.
  assert.equal(state([rec({ machineId: "m2" })]).state, "NONE");
});

test("a proof of another post does not carry over", () => {
  assert.equal(state([rec({ postId: "fanuc-dev" })]).state, "NONE");
});

test("a control software update supersedes the proof rather than inheriting it", () => {
  /*
   * The single case this field exists for. A control update can change how a
   * canned cycle retracts or how look-ahead handles short blocks, which is
   * exactly what a post validation is about.
   */
  const v = state([rec()], "100.23.000.2000");
  assert.equal(v.state, "SUPERSEDED");
  assert.match(v.detail, /validated at control 100\.22\.000\.1130/);
  assert.match(v.detail, /now running 100\.23\.000\.2000/);
  assert.match(v.detail, /Prove it again/);
});

test("a machine with no control version recorded cannot match a proof", () => {
  // Treating "unknown equals unknown" as a match would let a proof taken
  // before a software update stand after it, which is the case the field is
  // for. The message says which half is missing.
  const v = state([rec()], null);
  assert.equal(v.state, "SUPERSEDED");
  assert.match(v.detail, /no control version recorded/);
});

test("a blank control version on both sides is not a match", () => {
  /*
   * The half of the rule a mutation slipped past. "Unknown equals unknown" is
   * the reading that lets a proof taken before a software update stand after
   * it — and it is reachable the moment a record arrives with a blank version
   * from anywhere other than the form, which refuses one.
   */
  const v = state([rec({ controlVersion: "   " })], null);
  assert.equal(v.state, "SUPERSEDED", "a proof with no version matched a machine with no version");
  const w = state([rec({ controlVersion: "" })], "");
  assert.equal(w.state, "SUPERSEDED");
});

test("a withdrawn proof stops counting", () => {
  assert.equal(state([rec({ revokedAt: new Date("2026-08-20T00:00:00Z") })]).state, "NONE");
});

test("the newest live proof wins", () => {
  const v = state([
    rec({ validatedAt: new Date("2026-07-01T00:00:00Z"), evidence: "older" }),
    rec({ validatedAt: new Date("2026-08-15T00:00:00Z"), evidence: "newer" }),
  ]);
  assert.equal(v.state, "VALIDATED");
  assert.match(v.detail, /newer/);
});

test("no post or no machine says which is missing rather than failing vaguely", () => {
  assert.match(postValidationState([], null, "m1", "1.0", labels).detail, /No post processor is selected/);
  assert.match(postValidationState([], "haas-ngc-dev", null, "1.0", labels).detail, /only ever proven on a named machine/);
});

/* ---------------- The gate ---------------- */

const gate = (postValidation?: { state: "VALIDATED" | "SUPERSEDED" | "NONE"; detail: string }) =>
  evaluateReadiness({
    intent: emptyPartIntent("Post validation test"),
    stock: null,
    features: [],
    machine: null,
    tools: [],
    workholding: null,
    workholdingAssessment: null,
    hasInspectionPlan: false,
    simulationRun: false,
    ncGenerated: false,
    postValidation,
    operatorApproved: false,
  }).gates.find((g) => g.id === "post-validation")!;

test("the post-validation gate blocks", () => {
  // Unlike proof-out, which is the normal state of a new program, an unproven
  // post is a program nobody has watched run on this machine at all.
  assert.equal(gate({ state: "NONE", detail: "x" }).blocking, true);
  assert.equal(gate({ state: "NONE", detail: "x" }).status, "MISSING");
  assert.equal(gate({ state: "SUPERSEDED", detail: "x" }).status, "REVIEW");
  assert.equal(gate({ state: "VALIDATED", detail: "x" }).status, "PASS");
});

/* ---------------- The export gate reads the same record ---------------- */

const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");

test("the export pre-flight refuses an unproven post, and the item is required", () => {
  const pre = strip(readFileSync("src/lib/engines/cam/preflight.ts", "utf8"));
  assert.ok(/item\(\s*"postvalidation",/.test(pre), "the export gate has no post-validation item");
  assert.ok(
    /pkg\.postValidation\.state === "VALIDATED" \|\| pkg\.postValidation\.foreign === true,\s*pkg\.postValidation\.detail,\s*true,/.test(pre),
    "the export gate does not read the validation record, or the item is advisory",
  );
  // A program CANVAS did not write passes by abstention rather than approval:
  // validating a CANVAS post says nothing about a file Mastercam wrote, and a
  // gate that claimed otherwise would be asking for evidence about the wrong
  // artifact — the kind that gets cleared to make it go away.
  assert.ok(/foreign === true/.test(pre), "an uploaded program is judged against a CANVAS post's validation");
});

test("readiness and the pre-flight read one verdict, computed once", () => {
  // Two calls to postValidationState could drift; the package computes it
  // before readiness and hands the same object to both.
  const pkg = strip(readFileSync("src/lib/package.ts", "utf8"));
  assert.equal((pkg.match(/postValidationState\(/g) ?? []).length, 1, "the verdict is computed more than once");
  assert.ok(/postValidation,\n/.test(pkg), "the verdict is not passed to readiness");
});

/* ---------------- Recording one ---------------- */

test("a validation needs evidence, and takes the control version from the machine", () => {
  const src = strip(readFileSync("src/app/(app)/machines/validation-actions.ts", "utf8"));
  // No evidence, no validation. This is the gate that releases executable NC —
  // the one place in the system where a click would be least defensible.
  assert.ok(/if \(evidence === ""\) return;/.test(src), "a validation can be recorded with no evidence");
  // Taken from the machine record, not typed on the form, so a proof cannot be
  // recorded against a version the machine does not claim to be running.
  assert.ok(/const controlVersion = \(machine\.controlVersion \?\? ""\)\.trim\(\)/.test(src));
  assert.ok(/if \(controlVersion === ""\) return;/.test(src), "a validation can be recorded against no version");
  assert.ok(/actorType: "HUMAN"/.test(src));
});

test("withdrawing a validation revokes it rather than deleting it", () => {
  // A program exported last month under a validation later withdrawn is
  // something a shop needs to be able to find.
  const src = strip(readFileSync("src/app/(app)/machines/validation-actions.ts", "utf8"));
  assert.ok(/data: \{ revokedAt: new Date\(\), revokedReason: reason \}/.test(src));
  assert.equal(/postValidation\.delete/.test(src), false, "a validation is deleted rather than revoked");
  assert.ok(/if \(reason === ""\) return;/.test(src), "a validation can be withdrawn with no reason");
});

test("certified stays a literal false on every post", () => {
  // Certification is not a property of the code, and this is what stops
  // anybody re-adding a boolean somewhere and calling it certified.
  const post = readFileSync("src/lib/engines/cam/post.ts", "utf8");
  assert.ok(/certified: false;/.test(post), "PostDefinition.certified is no longer the literal false");
  assert.equal(/certified: true/.test(post), false, "a post claims to be certified");
});

test("a program CANVAS did not write abstains rather than failing", () => {
  const { foreignProgram } = require("@/lib/engines/post-validation") as typeof import("@/lib/engines/post-validation");
  const v = foreignProgram({ machine: "Haas VF-2" });
  assert.equal(v.foreign, true);
  assert.match(v.detail, /not written by a CANVAS post/);
  assert.match(v.detail, /Whoever produced it is who vouches/);
  // And the readiness gate stops blocking on it, because there is nothing to
  // prove about an artifact this check does not describe.
  const g = gate(v);
  assert.equal(g.blocking, false);
  assert.equal(g.status, "NOT_ATTEMPTED");
});
