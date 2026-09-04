import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

/**
 * CORRECTING STOCK
 *
 * `defineStock` used to return early whenever stock already existed — define,
 * never redefine. A 2.000 blank entered as 0.200 was permanent, and every
 * downstream engine (holding margin, tool reach, cycle time, material removed)
 * went on planning from the wrong number with no way back short of a new part.
 *
 * Correction is now allowed, and it takes down what was concluded from the old
 * blank: the approval is revoked and the simulation cleared. These guards exist
 * because nothing else exercises this action — it is a server action inside a
 * page component, and a regression here is silent.
 */

const stripComments = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
const src = stripComments(readFileSync("src/app/(app)/parts/[id]/page.tsx", "utf8"));

test("stock is no longer write-once", () => {
  assert.ok(
    !/if \(fresh\.revision\.stock\) return;/.test(src),
    "defineStock still refuses to redefine stock, so a mistyped blank is permanent",
  );
});

test("a stock correction revokes the approval given on the old blank", () => {
  assert.ok(
    /db\.approval\.updateMany\(\{[\s\S]{0,200}revokedAt: null[\s\S]{0,120}revokedAt: new Date\(\)/.test(src),
    "stock can be changed while an approval of the previous blank still stands",
  );
});

test("a stock correction clears the simulation run against the old blank", () => {
  assert.ok(
    /db\.simulation\.deleteMany\(\{[\s\S]{0,160}partRevisionId: fresh\.revision\.revisionId/.test(src),
    "a simulation of a cut that will not happen survives the stock it was run against",
  );
});

test("neither consequence fires when stock is first defined", () => {
  // `previous` is null on the define path. Revoking an approval that cannot
  // exist is harmless; the guard is here so the two blocks stay inside it if
  // the action is rearranged.
  assert.ok(
    /if \(previous\) \{[\s\S]*db\.approval\.updateMany[\s\S]*db\.simulation\.deleteMany[\s\S]*\n {4}\}/.test(src),
    "the invalidation is not scoped to a correction",
  );
});

test("re-posting identical stock changes nothing", () => {
  assert.ok(
    /if \(previous && describe\(previous\) === describe\(stock\)\) return;/.test(src),
    "saving the same numbers again would revoke an approval and delete a simulation for no change",
  );
});

test("the correction is offered on the part page, not just in the action", () => {
  const raw = readFileSync("src/app/(app)/parts/[id]/page.tsx", "utf8");
  assert.ok(/Correct stock/.test(raw), "there is no control that reaches the corrected path");
});
