import { test } from "node:test";
import assert from "node:assert/strict";
import { POSTS, type PostContext } from "@/lib/engines/cam/post";
import { buildPreflight } from "@/lib/engines/cam/preflight";
import type { ManufacturingPackage } from "@/lib/package";

/**
 * THE UNITS WORD WAS THE ONLY UNITS-AWARE LINE IN THE PIPELINE.
 *
 * Every engine in CANVAS computes in inches. Geometry is converted INTO
 * inches on import — nc/parse.ts and nc/tool-list.ts both divide by 25.4 on
 * the way in — and nothing converts on the way out. The post then chose G20
 * or G21 from the revision's units field and emitted the same numbers either
 * way.
 *
 * So a metric revision posted `G21` followed by `X6.` — and X6 under G21 is
 * six MILLIMETRES. The part comes off the machine at 1/25.4 scale, every
 * number on the setup sheet reads correctly, and the pre-flight item called
 * "Units confirmed" passed, because it was checking that the field held one
 * of its two legal values.
 *
 * Converting properly has to reach every coordinate, every arc centre, every
 * feed, the safe and clearance planes, the tool table in the header and the
 * travel check in verifyNc. A conversion that misses one of those is worse
 * than none, because it looks converted. Until it exists, both the gate and
 * the post refuse — the same posture the engines take for a missing input.
 */

const pkg = (units: "IN" | "MM"): ManufacturingPackage =>
  ({
    primaryMachine: { manufacturer: "Haas", model: "VF-2" },
    revision: { units, stock: { x: 6, y: 4, z: 1 }, features: [] },
    setups: [{ id: "s1", operations: [] }],
    postValidation: { state: "VALIDATED", detail: "proven", record: null },
    workholdingBySetup: { s1: { level: "SAFE" } },
    assignedTools: [{ stickout: 1.5 }],
    toolpaths: [{ isPlaceholder: false }],
    toolpathErrors: [],
    simulationRun: true,
    approved: true,
  }) as unknown as ManufacturingPackage;

const unitsItem = (units: "IN" | "MM") =>
  buildPreflight(pkg(units), POSTS[0]).find((i) => i.id === "units")!;

test("the units gate passes inches and fails millimetres, with the reason", () => {
  const inch = unitsItem("IN");
  assert.equal(inch.status, "PASS");
  assert.match(inch.detail, /G20/);

  const mm = unitsItem("MM");
  assert.equal(mm.status, "FAIL", "a metric revision passed the units gate");
  assert.match(mm.detail, /1\/25\.4|millimetre/i);
  assert.ok(mm.required, "the units gate must be required — it decides the scale of the part");
});

test("the gate is not satisfied by the field merely holding a legal value", () => {
  // The original condition was `units === "IN" || units === "MM"`, which is
  // true for every value the type permits. A gate that cannot fail is not a
  // gate, and this one was named "Units confirmed".
  const both = (["IN", "MM"] as const).map((u) => unitsItem(u).status);
  assert.notDeepEqual(both, ["PASS", "PASS"], "the units gate passes for every legal value");
});

test("every post refuses a metric revision rather than emitting inch numbers under G21", () => {
  // The gate refuses first. This is the backstop, beside the G41 D0 and
  // arc-compensation refusals, for the same reason those exist: a post that
  // any caller can hand a package does not get to assume the gate ran.
  const ctx = (units: "IN" | "MM") =>
    ({
      programNumber: "1234", programName: "P", partName: "P", revision: "A",
      machine: { manufacturer: "Haas", model: "VF-2", controller: "HAAS", travelsX: 30, travelsY: 16, travelsZ: 20 },
      units, workOffset: "G54", safeZ: 1, toolTable: [], origins: [],
      generatedAtIso: "2026-09-04",
    }) as unknown as PostContext;

  for (const post of POSTS) {
    assert.throws(
      () => post.emit([], ctx("MM")),
      /millimetre|1\/25\.4/i,
      `${post.id} emitted a program for a metric revision`,
    );
    // And inches still post — the refusal must not have taken everything with it.
    assert.doesNotThrow(() => post.emit([], ctx("IN")), `${post.id} refuses inches`);
  }
});
