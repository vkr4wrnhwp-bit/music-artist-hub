import { test } from "node:test";
import assert from "node:assert/strict";
import { derivePlan, GOVERNING_DIMENSION, NEVER_DERIVABLE, METHOD_NOT_ASSIGNED } from "@/lib/engines/inspection-plan";
import { FEATURE_KINDS } from "@/lib/domain/features";
import { FEATURE_FIELDS } from "@/lib/domain/feature-input";
import type { Feature } from "@/lib/domain/features";

/**
 * The readiness gate said "Inspection plan — MISSING — Create an inspection
 * plan" and there was no `inspectionPlan.create` anywhere in the application.
 *
 * What these pin is the honesty of the derivation, not its convenience: a
 * derived plan may only contain characteristics taken from the part, and
 * everything it cannot derive has to be named rather than dropped.
 */

const feat = (over: Record<string, unknown>): Feature =>
  ({
    id: "f1",
    kind: "BORE",
    label: "⌀1.2500 bore",
    functionalRole: "BEARING_FIT",
    critical: false,
    diameter: 1.25,
    depth: 0.5,
    tolerance: { plus: 0.0005, minus: 0.0005 },
    ...over,
  }) as unknown as Feature;

/* ---------------- What gets on the sheet ---------------- */

test("a toleranced feature becomes a characteristic with its own nominal and band", () => {
  const { items } = derivePlan([feat({})]);
  assert.equal(items.length, 1);
  assert.equal(items[0].nominal, 1.25);
  assert.equal(items[0].plusTol, 0.0005);
  assert.equal(items[0].minusTol, 0.0005);
  assert.equal(items[0].featureId, "f1");
  // The label names which dimension it is, not just the feature.
  assert.match(items[0].label, /diameter/i);
});

test("geometry with no tolerance and no critical flag is not a characteristic", () => {
  // A row with no accept limits gives the inspector nothing to judge against.
  const { items, uncovered } = derivePlan([feat({ tolerance: undefined, critical: false })]);
  assert.equal(items.length, 0);
  assert.equal(uncovered.length, 0, "a plain geometric feature was reported as a gap");
});

test("the method comes from the feature, and an unassigned one says so", () => {
  const withMethod = derivePlan([feat({ inspectionMethod: "Bore gauge — consumes 40% of the tolerance band", inspectionDeviceType: "BORE_GAUGE" })]);
  assert.equal(withMethod.items[0].method, "Bore gauge — consumes 40% of the tolerance band");
  assert.equal(withMethod.items[0].deviceType, "BORE_GAUGE");

  // An inspector reading an instrument nobody chose is worse off than one
  // reading that the method is still open.
  const without = derivePlan([feat({})]);
  assert.equal(without.items[0].method, METHOD_NOT_ASSIGNED);
  assert.equal(without.items[0].deviceType, null);
});

test("sequence numbers run 1..n with no gaps where a feature was skipped", () => {
  const { items } = derivePlan([
    feat({ id: "a" }),
    feat({ id: "skipped", kind: "RECT_POCKET", label: "pocket", width: 1, length: 1, depth: 0.2 }),
    feat({ id: "b" }),
  ]);
  assert.deepEqual(
    items.map((i) => i.sequence),
    [1, 2],
  );
});

/* ---------------- What is refused, and named ---------------- */

test("a kind with more than one candidate dimension is refused, not guessed", () => {
  // THE DEFECT THIS PREVENTS. A pocket carries width, length and depth. "The
  // first number field" would silently pick one and print it as the
  // characteristic — a nominal that looks authoritative and describes the
  // wrong dimension.
  const { items, uncovered } = derivePlan([
    feat({ kind: "RECT_POCKET", label: "Relief pocket", width: 2, length: 1.5, depth: 0.1 }),
  ]);
  assert.equal(items.length, 0);
  assert.equal(uncovered.length, 1);
  assert.match(uncovered[0].reason, /no single governing dimension/);
  assert.equal(uncovered[0].label, "Relief pocket");
});

test("a feature whose governing dimension is missing gets no invented nominal", () => {
  const { items, uncovered } = derivePlan([feat({ diameter: undefined })]);
  assert.equal(items.length, 0);
  assert.match(uncovered[0].reason, /diameter is not recorded/);
});

test("a critical feature with no tolerance is named, not given a band", () => {
  // Somebody flagged it critical, so dropping it silently is wrong; inventing
  // limits for it is worse.
  const { items, uncovered } = derivePlan([feat({ critical: true, tolerance: undefined })]);
  assert.equal(items.length, 0);
  assert.equal(uncovered.length, 1);
  assert.match(uncovered[0].reason, /no tolerance/);
  assert.match(uncovered[0].reason, /State the tolerance/);
});

test("every uncovered characteristic carries a reason a machinist can act on", () => {
  const { uncovered } = derivePlan([
    feat({ id: "p", kind: "RECT_POCKET", label: "pocket", width: 1, length: 1, depth: 0.2 }),
    feat({ id: "n", diameter: undefined }),
    feat({ id: "c", critical: true, tolerance: undefined }),
  ]);
  assert.equal(uncovered.length, 3);
  for (const u of uncovered) {
    assert.ok(u.reason.length > 30, `"${u.label}" has no usable reason`);
    assert.ok(u.label, "an uncovered characteristic has no label");
  }
});

/* ---------------- The vocabulary cannot quietly fall behind ---------------- */

test("every feature kind has an explicit governing-dimension decision", () => {
  // Typed as an exhaustive Record so a new kind is a type error rather than a
  // silent `undefined` that reads as "no governing dimension" and drops the
  // feature off every derived plan without a word.
  for (const kind of FEATURE_KINDS) {
    assert.ok(kind in GOVERNING_DIMENSION, `${kind} has no governing-dimension decision`);
  }
});

test("a named governing dimension is a real field on that kind", () => {
  // A typo here would push every feature of that kind into "not recorded" and
  // read as missing data rather than as a bug.
  for (const kind of FEATURE_KINDS) {
    const governing = GOVERNING_DIMENSION[kind];
    if (!governing) continue;
    const fields = FEATURE_FIELDS[kind] ?? [];
    const field = fields.find((f) => f.name === governing);
    assert.ok(field, `${kind} governs on "${governing}", which is not one of its fields`);
    assert.equal(field!.type, "number", `${kind} governs on "${governing}", which is not a number`);
  }
});

test("what a derived plan never covers is stated, and is about relationships", () => {
  assert.ok(NEVER_DERIVABLE.length >= 3);
  const all = NEVER_DERIVABLE.join(" ").toLowerCase();
  for (const term of ["position", "flatness", "runout", "finish"]) {
    assert.ok(all.includes(term), `the never-derivable list does not mention ${term}`);
  }
});
