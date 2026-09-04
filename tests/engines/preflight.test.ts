import { test } from "node:test";
import assert from "node:assert/strict";
import { buildPreflight } from "@/lib/engines/cam/preflight";
import { preflightPassed, type PostDefinition } from "@/lib/engines/cam/post";
import type { ManufacturingPackage } from "@/lib/package";

/**
 * The list that decides whether executable NC leaves the building.
 *
 * preflightPassed() was tested; the list it aggregates was not tested at all.
 * Every item here is required, so each one is individually a veto — and the
 * failure that matters on a veto list is an item that passes without having
 * checked anything.
 */

const POST = { id: "haas-ngc-dev", name: "Haas NGC (development)", certified: false } as unknown as PostDefinition;

const pkg = (over: Record<string, unknown> = {}): ManufacturingPackage =>
  ({
    primaryMachine: { manufacturer: "Haas", model: "VF-2" },
    revision: {
      units: "IN",
      stock: { x: 6, y: 4, z: 1 },
      features: [{ id: "f1", critical: true, inspectionMethod: "Bore gauge" }],
    },
    // One setup with one operation cutting f1, so the coverage item has a
    // complete package to look at. A fixture missing this reads as a part
    // whose only feature nothing cuts.
    setups: [{ id: "s1", operations: [{ id: "o1", label: "Bore f1", featureId: "f1" }] }],
    workholdingBySetup: { s1: { level: "SAFE" } },
    assignedTools: [{ stickout: 1.5 }],
    toolpaths: [{ isPlaceholder: false }],
    toolpathErrors: [],
    simulationRun: true,
    approved: true,
    ...over,
  }) as unknown as ManufacturingPackage;

const itemFor = (p: ManufacturingPackage, id: string) => buildPreflight(p, POST).find((i) => i.id === id)!;
const passes = (p: ManufacturingPackage) => preflightPassed(buildPreflight(p, POST));

/* ---------------- Nothing passes without having checked something ---------------- */

test("workholding is not verified when there are no setups to verify", () => {
  // `.every()` on an empty object is true, so a package with no setups passed
  // "Workholding verified" with the detail "No setups to evaluate". The
  // toolpath item was already fixed for this exact reason.
  const i = itemFor(pkg({ workholdingBySetup: {} }), "workholding");
  assert.equal(i.status, "FAIL");
  assert.match(i.detail, /nothing has been assessed/i);
});

test("tool lengths are not verified when no tools are assigned", () => {
  const i = itemFor(pkg({ assignedTools: [] }), "toollengths");
  assert.equal(i.status, "FAIL");
});

test("toolpaths are not generated when there are none", () => {
  const i = itemFor(pkg({ toolpaths: [] }), "toolpaths");
  assert.equal(i.status, "FAIL");
  assert.match(i.detail, /no operations to post/i);
});

test("a partly-generated toolpath set fails, and says what the program would skip", () => {
  // An operation with no engine is not omitted from the program — the post
  // writes it in as a comment. The program runs start to finish and never
  // cuts those features, and the operations that land there are BORE, TAP and
  // ADAPTIVE_2D: the bearing seats and the threads.
  const i = itemFor(pkg({ toolpaths: [{ isPlaceholder: false }, { isPlaceholder: true }, { isPlaceholder: true }] }), "toolpaths");
  assert.equal(i.status, "FAIL");
  assert.match(i.detail, /2 of 3/);
  assert.match(i.detail, /without cutting them/i);
});

/* ---------------- Every item is a veto ---------------- */

test("a complete package passes", () => {
  assert.equal(passes(pkg()), true);
});

test("each item on its own can stop the export", () => {
  const breakages: [string, Record<string, unknown>][] = [
    ["machine", { primaryMachine: null }],
    ["stock", { revision: { units: "IN", stock: null, features: [] } }],
    ["workholding", { workholdingBySetup: { s1: { level: "HIGH_RISK" } } }],
    ["tools", { assignedTools: [] }],
    ["toolpaths", { toolpaths: [] }],
    ["errors", { toolpathErrors: [{ reason: "no tool" }] }],
    ["simulation", { simulationRun: false }],
    ["approval", { approved: false }],
  ];
  for (const [id, over] of breakages) {
    const p = pkg(over);
    assert.equal(itemFor(p, id).status, "FAIL", `${id} did not fail`);
    assert.equal(passes(p), false, `the gate passed with ${id} failing`);
  }
});

test("no post processor selected stops the export", () => {
  const list = buildPreflight(pkg(), null);
  assert.equal(list.find((i) => i.id === "post")!.status, "FAIL");
  assert.equal(preflightPassed(list), false);
});

test("every item is required — there are no advisory entries on this list", () => {
  // An optional item on an export gate is an item somebody will learn to
  // ignore.
  for (const i of buildPreflight(pkg(), POST)) {
    assert.equal(i.required, true, `${i.id} is optional`);
  }
});

test("a workholding level short of likely-safe is not verified", () => {
  for (const level of ["REVIEW", "UNKNOWN", "HIGH_RISK"]) {
    assert.equal(itemFor(pkg({ workholdingBySetup: { s1: { level } } }), "workholding").status, "FAIL", level);
  }
  for (const level of ["SAFE", "LIKELY_SAFE"]) {
    assert.equal(itemFor(pkg({ workholdingBySetup: { s1: { level } } }), "workholding").status, "PASS", level);
  }
});

test("one unsafe setup among safe ones fails the whole item", () => {
  const i = itemFor(pkg({ workholdingBySetup: { s1: { level: "SAFE" }, s2: { level: "HIGH_RISK" } } }), "workholding");
  assert.equal(i.status, "FAIL");
  assert.match(i.detail, /HIGH_RISK/);
});

test("a critical feature with no inspection method stops the export", () => {
  const p = pkg({ revision: { units: "IN", stock: { x: 6, y: 4, z: 1 }, features: [{ id: "f1", critical: true }] } });
  assert.equal(itemFor(p, "criticaldims").status, "FAIL");
});

test("a part with no critical features does not need inspection methods", () => {
  // Vacuously true here is legitimately true: nothing critical is nothing to
  // inspect. Not every empty case is a false pass.
  const p = pkg({ revision: { units: "IN", stock: { x: 6, y: 4, z: 1 }, features: [{ id: "f1", critical: false }] } });
  assert.equal(itemFor(p, "criticaldims").status, "PASS");
});

/* ---------------- Every item explains itself ---------------- */

test("every item states a fact, not just a verdict", () => {
  for (const i of buildPreflight(pkg(), POST)) {
    assert.ok(i.label.length > 3, `${i.id} has no label`);
    assert.ok(i.detail.length > 3, `${i.id} states no detail`);
    assert.ok(!/undefined|NaN|\[object/.test(i.detail), `${i.id}: ${i.detail}`);
  }
});

test("a failing item's detail describes the failure, not the success", () => {
  // A green verdict beside a sentence describing six missing operations was
  // the original bug on this list. The detail and the status have to agree.
  const i = itemFor(pkg({ toolpaths: [{ isPlaceholder: false }, { isPlaceholder: true }] }), "toolpaths");
  assert.equal(i.status, "FAIL");
  assert.ok(!/all \d+ operations produced motion/i.test(i.detail), `a failing item reads as a pass: ${i.detail}`);
});

test("the list is deterministic and its ids are unique", () => {
  const a = buildPreflight(pkg(), POST);
  assert.deepEqual(a, buildPreflight(pkg(), POST));
  assert.equal(new Set(a.map((i) => i.id)).size, a.length);
});
