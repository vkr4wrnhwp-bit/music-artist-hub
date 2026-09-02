import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { JAW_SURFACES } from "@/lib/engines/holding-margin";

/**
 * Grip depth, projection, machine and workholding could only be written by the
 * approach generator. A machinist who planned 0.250" of grip and set 0.400"
 * had no way to say so — while the holding margin, the jaw-clearance check,
 * the fixture model in the simulator and the release snapshot were all
 * computed from the number they could not correct.
 */

const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
const action = () => strip(readFileSync("src/app/(app)/parts/[id]/setups/setup-actions.ts", "utf8"));
const form = () => strip(readFileSync("src/components/setup-geometry.tsx", "utf8"));
const page = () => strip(readFileSync("src/app/(app)/parts/[id]/setups/page.tsx", "utf8"));
const machinist = () => strip(readFileSync("src/app/(app)/parts/[id]/machinist/page.tsx", "utf8"));

test("a blank field is stored as null, never as zero and never as the plan", () => {
  // A zero grip depth is a measurement nobody took; the plan's value is not
  // what the machinist set. The engine already handles a missing input by
  // naming it.
  const src = action();
  assert.match(src, /if \(raw === ""\) return null;/);
  assert.ok(!/\?\?\s*0\b/.test(src), "a field falls back to zero");
  assert.ok(!/\?\?\s*(owned|planned|setup)\./.test(src), "a field falls back to the stored plan value");
});

test("a negative measurement is refused rather than stored", () => {
  const src = action();
  assert.match(src, /Number\.isFinite\(v\) && v >= 0/);
});

test("saving marks the geometry measured, with who and when", () => {
  const src = action();
  assert.match(src, /geometrySource: "MEASURED"/);
  assert.match(src, /geometryRecordedBy: user\.name \?\? user\.email/);
  assert.match(src, /geometryRecordedAt: new Date\(\)/);
});

test("the plan generator marks its own output as planned", () => {
  // Without this every setup would read as measured the moment the column
  // existed, which is the fabrication the column exists to prevent.
  assert.match(machinist(), /geometrySource: "PLANNED"/);
});

test("machine and workholding are verified to belong to this shop", () => {
  // Setup carries no organizationId of its own, so an id posted in a form is
  // one another shop's session could name.
  const src = action();
  assert.match(src, /db\.machine\.findFirst\(\{ where: \{ id: machineIdRaw, organizationId: user\.organizationId \}/);
  assert.match(src, /db\.workholdingDevice\.findFirst\(\{ where: \{ id: workholdingIdRaw, organizationId: user\.organizationId \}/);
  assert.match(src, /partRevision: \{ part: \{ id: partId, organizationId: user\.organizationId \} \}/);
});

test("an unrecognised jaw axis or surface is cleared, not filed", () => {
  // A stored value is one the workholding engine and the fixture model will
  // trust. "diagonal" placing a modelled vise somewhere is worse than null.
  const src = action();
  assert.match(src, /jawAxisRaw === "X" \|\| jawAxisRaw === "Y" \? jawAxisRaw : null/);
  assert.match(src, /JAW_SURFACES as readonly string\[\]\)\.includes\(jawSurfaceRaw\)/);
});

test("the jaw surface options are the vocabulary the margin engine reads", () => {
  // A label in the form that the engine does not know would silently fall
  // back to UNKNOWN and change the friction coefficient without saying so.
  const src = form();
  assert.match(src, /JAW_SURFACES\.map/);
  assert.match(src, /JAW_SURFACE_LABEL\[j\]/);
  assert.ok(JAW_SURFACES.includes("UNKNOWN"), "UNKNOWN left the vocabulary — the form's default is now invalid");
});

test("the form says which kind of number the margin was computed from", () => {
  // The arithmetic is identical for a planned and a measured grip; what it is
  // entitled to claim is not.
  const src = form();
  assert.match(src, /Planned, not measured/);
  assert.match(src, /describes a\s*\n?\s*setup nobody has built yet/);
  assert.match(src, /Not recorded/);
});

test("the margin readout carries the same caveat, where the number is claimed", () => {
  // Putting it only inside a collapsed form would hide it from the person
  // reading the figure.
  const src = page();
  assert.match(src, /geometrySource !== "MEASURED"/);
  assert.match(src, /describes a setup nobody has confirmed building/);
});

test("recording the setup writes no gate and no readiness state", () => {
  const src = action();
  const writes = [...src.matchAll(/db\.(\w+)\.(create|update|updateMany|upsert|delete|deleteMany)\b/g)].map((m) => `${m[1]}.${m[2]}`);
  assert.deepEqual(writes, ["setup.update"], "recording the setup wrote something other than the setup");
});

test("the actor is stated, never inferred", () => {
  assert.match(action(), /actorType: "HUMAN"/);
});
