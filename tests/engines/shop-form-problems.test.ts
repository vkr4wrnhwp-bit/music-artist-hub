import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { FormReader, FormRejected, rejectionQuery } from "@/lib/shop-form";

/**
 * Cross-field rules were being recorded by calling `text()` with a made-up
 * field name and the message as the label. It works — `text()` pushes a
 * problem for a field that is not there — but it formats the problem as
 * "<label> is required", so the operator was told:
 *
 *   "Uncertainty ±0.0001 is below half the 0.001 resolution, which no
 *    instrument achieves is required"
 *
 * Found by reading the redirect a real form produced, not by a test. Nothing
 * asserted the wording of a refusal.
 */

const fd = (o: Record<string, string>) => {
  const f = new FormData();
  for (const [k, v] of Object.entries(o)) f.append(k, v);
  return f;
};

test("a cross-field problem is stated as written, with nothing appended", () => {
  const f = new FormReader(fd({}));
  f.problem("Through-layer strength is above the in-plane figure.");
  try {
    f.done();
    assert.fail("done() did not reject");
  } catch (err) {
    assert.ok(err instanceof FormRejected);
    assert.deepEqual(err.problems, ["Through-layer strength is above the in-plane figure."]);
    assert.ok(!/is required/.test(err.problems[0]), "the message still has 'is required' glued onto it");
  }
});

test("a genuinely missing field still reads as required", () => {
  // The other half of the distinction: `text()` keeps its own wording.
  const f = new FormReader(fd({}));
  f.text("name", "Name");
  try {
    f.done();
    assert.fail("done() did not reject");
  } catch (err) {
    assert.deepEqual((err as FormRejected).problems, ["Name is required"]);
  }
});

test("problems reach the form as a readable query, in order", () => {
  const f = new FormReader(fd({}));
  f.problem("First thing.");
  f.problem("Second thing.");
  try {
    f.done();
  } catch (err) {
    const q = rejectionQuery(err);
    assert.match(decodeURIComponent(q), /First thing\. · Second thing\./);
  }
});

test("no action smuggles a message through a fake field name any more", () => {
  // The idiom was copied three times before it was noticed. A guard is
  // cheaper than noticing it a fourth time.
  const files = [
    "src/app/(app)/metrology/actions.ts",
    "src/app/(app)/printing/actions.ts",
  ];
  for (const file of files) {
    const src = readFileSync(file, "utf8").replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
    assert.ok(
      !/f\.text\(\s*["'`]__/.test(src),
      `${file} still records a cross-field problem through text() with a fake field name`,
    );
  }
});
