import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  emptyPartIntent,
  missingEngineeringInput,
  reconcileIntentWithStock,
} from "@/lib/domain/part-intent";
import type { Stock } from "@/lib/domain/features";

/**
 * "Complete the Part Responsibility Profile — this doesn't fix the issue when
 * you fill everything out."
 *
 * It did not, and could not. The Engineering-input gate requires material,
 * stock, finished envelope, quantity and general tolerance of every part.
 * Material and stock were written once at intake and never again — a machinist
 * who defined stock on the part page wrote `stockJson` while the gate read
 * `intent.stock`, and nothing joined them. The other three had no editor
 * anywhere in the application. So the gate reported them missing, recommended
 * the profile page, and the profile page did not ask. Round and round.
 */

const STOCK: Stock = { form: "RECTANGULAR", x: 4.25, y: 3.25, z: 0.625, material: "Aluminum 6061" };

test("defining stock answers the intent's stock and material questions", () => {
  const before = emptyPartIntent("TEST");
  assert.equal(before.stock.value, null);
  assert.equal(before.material.value, null);

  const after = reconcileIntentWithStock(before, STOCK);
  assert.deepEqual(after.stock.value, STOCK);
  assert.equal(after.material.value, "Aluminum 6061");
});

test("the derived values carry honest provenance — the human typed them", () => {
  const after = reconcileIntentWithStock(emptyPartIntent("TEST"), STOCK);
  for (const field of [after.stock, after.material]) {
    assert.equal(field.source, "USER", "derived from a human's own stock definition, not calculated or assumed");
    assert.equal(field.confirmedByUser, true);
    assert.ok(field.note, "a derived value must say where it came from");
  }
});

test("an answer already in the intent is not overwritten by the billet", () => {
  // A later, more specific statement outranks the material the stock happens
  // to be cut from.
  const intent = emptyPartIntent("TEST");
  intent.material = { value: "Aluminum 7075-T651", source: "USER", confidence: "VERIFIED", confirmedByUser: true };
  const after = reconcileIntentWithStock(intent, STOCK);
  assert.equal(after.material.value, "Aluminum 7075-T651");
});

test("no stock changes nothing", () => {
  const intent = emptyPartIntent("TEST");
  const after = reconcileIntentWithStock(intent, null);
  assert.equal(after.stock.value, null);
  assert.equal(after.material.value, null);
});

test("stock with no material named leaves material unanswered", () => {
  const after = reconcileIntentWithStock(emptyPartIntent("TEST"), { ...STOCK, material: "" });
  assert.deepEqual(after.stock.value, { ...STOCK, material: "" });
  assert.equal(after.material.value, null, "an empty material string must not read as an answer");
});

test("the loop closes: stock plus the profile's fields clears the baseline", () => {
  let intent = reconcileIntentWithStock(emptyPartIntent("TEST"), STOCK);
  // Still short exactly the three the profile now asks for.
  assert.deepEqual(
    missingEngineeringInput(intent).filter((m) => m !== "Failure consequence not assessed"),
    ["Finished envelope", "Quantity", "General tolerance"],
  );

  intent = {
    ...intent,
    finishedEnvelope: { value: { x: 4, y: 3, z: 0.5 }, source: "USER", confidence: "VERIFIED", confirmedByUser: true },
    quantity: { value: 25, source: "USER", confidence: "VERIFIED", confirmedByUser: true },
    generalTolerance: { value: 0.005, source: "USER", confidence: "VERIFIED", confirmedByUser: true },
    failureConsequence: { value: "LOW", source: "USER", confidence: "VERIFIED", confirmedByUser: true },
  };
  assert.deepEqual(missingEngineeringInput(intent), [], "the gate still cannot be cleared by filling everything in");
});

/* ---- the page the gate sends you to must ask for what the gate wants ---- */

test("the profile asks for every baseline input the gate requires", () => {
  const page = readFileSync("src/app/(app)/parts/[id]/responsibility/page.tsx", "utf8");
  for (const field of ["quantity", "generalTolerance"]) {
    assert.ok(new RegExp(`name="${field}"`).test(page), `the profile does not ask for ${field}`);
  }
  // The three envelope inputs are generated from one template, so the literal
  // names never appear; pin the template and the axes it walks.
  assert.ok(
    /name=\{`envelope\$\{axis\.toUpperCase\(\)\}`\}/.test(page),
    "the profile does not ask for the finished envelope",
  );
  assert.ok(
    /\(\["x", "y", "z"\] as const\)\.map\(\(axis\)/.test(page),
    "the finished envelope is not asked for on all three axes",
  );
});

test("the load path reconciles, so the gate and the part page cannot disagree", () => {
  const data = readFileSync("src/lib/data.ts", "utf8");
  assert.ok(
    /reconcileIntentWithStock\(/.test(data),
    "stock and intent are still parsed independently — define stock and the gate still says stock is undefined",
  );
});

test("a blank field leaves the gate open rather than writing a number", () => {
  const page = readFileSync("src/app/(app)/parts/[id]/responsibility/page.tsx", "utf8");
  // The dangerous failure is an empty input becoming 0: a quantity of zero or
  // a general tolerance of zero would clear the gate with a value nobody gave.
  assert.ok(/quantity >= 1/.test(page), "an empty or zero quantity can be stored as an answer");
  assert.ok(/generalTolerance > 0/.test(page), "a zero general tolerance can be stored as an answer");
  assert.ok(
    /envelope\.every\(\(n\) => n !== null/.test(page),
    "a partly-filled finished envelope can be stored — two axes is not a smaller envelope, it is an unanswered question",
  );
});
