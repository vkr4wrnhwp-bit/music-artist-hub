import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { generateToolpath, deriveCuttingParameters, type CuttableContext } from "@/lib/engines/cam/engine";
import type { MachiningContext, OperationRequest } from "@/lib/engines/cam/types";
import type { Feature, Stock } from "@/lib/domain/features";
import type { Tool } from "@/lib/domain/shop";

/**
 * FINISH PASSES
 *
 * `stockToLeave` was the only thing that distinguished a finish pass from a
 * roughing one, which made it a roughing pass with a different number in it:
 * the same mid-range chipload, the same stepdown, the same depth ladder. So an
 * operation the planner labelled "Finish outside profile" cut the final wall
 * at roughing feeds, with a witness line at every depth step — on the ±0.0005"
 * features the inspection engine reasons so carefully about.
 */

const stock: Stock = { form: "RECTANGULAR", x: 8, y: 6, z: 1, material: "Aluminum 6061" };

const mill = (over: Partial<Tool> = {}) =>
  ({
    id: "t2", toolNumber: 2, toolClass: "FLAT_END_MILL", description: "1/2 3FL", diameter: 0.5,
    cornerRadius: 0, flutes: 3, material: "CARBIDE", fluteLength: 1, overallLength: 3, stickout: 1.5,
    holder: "CAT40 ER32", holderNoseDiameter: 1.5, maxRPM: 8100, recommendedMaterials: [],
    chiploadMin: 0.001, chiploadMax: 0.005, sfmMin: 400, sfmMax: 1000, coolant: "FLOOD", lifeRemaining: 1,
    condition: "GOOD", regrindCount: 0, ...over,
  }) as unknown as Tool;

const ctx = (tool = mill()): MachiningContext => ({
  tool, materialSfmMin: 600, materialSfmMax: 1000, materialName: "Aluminum 6061",
  rapidRate: 1000, maxSpindleRPM: 8100, maxFeed: 500,
});

const contour = {
  id: "f1", kind: "OUTSIDE_CONTOUR", label: "Outside profile", functionalRole: "NONE", critical: false,
  width: 5, length: 3, cornerRadius: 0.375, depth: 0.5,
} as unknown as Feature;

const req = (pass: "ROUGH" | "FINISH", depth = 0.5): OperationRequest => ({
  id: "op", type: "CONTOUR_2D", label: "profile", featureId: "f1", toolId: "t2", setupId: "s",
  pass, topZ: 0, finalZ: -depth, clearanceZ: 0.1, retractZ: 1,
});

const run = (pass: "ROUGH" | "FINISH", depth = 0.5, tool = mill()) => {
  const r = generateToolpath(req(pass, depth), contour, ctx(tool), stock);
  assert.ok(r.ok, "the contour did not generate");
  if (!r.ok) throw new Error("unreachable");
  return r.toolpath;
};

/* ---------------- Parameters follow the operation, not its type ---------------- */

test("a finish pass takes the finishing chipload, a roughing pass does not", () => {
  // It used to be `type === "CHAMFER" || type === "ENGRAVE"`, so an operation
  // labelled "Finish outside profile" got mid-range roughing chipload.
  assert.equal(run("FINISH").parameters.chipload, 0.001);
  assert.equal(run("ROUGH").parameters.chipload, 0.003);
});

test("a finish pass leaves nothing behind", () => {
  assert.equal(run("FINISH").parameters.stockToLeave, 0);
  assert.ok(run("ROUGH").parameters.stockToLeave > 0);
});

test("the finishing flag reaches deriveCuttingParameters from the request", () => {
  const src = readFileSync("src/lib/engines/cam/engine.ts", "utf8");
  assert.ok(
    /const finishing = req\.pass === "FINISH" \|\| req\.type === "CHAMFER" \|\| req\.type === "ENGRAVE";/.test(src),
    "finishing is inferred from the operation type again",
  );
});

test("an operation with no pass reads as roughing", () => {
  // Absent means ROUGH. Every operation planned before the column existed has
  // no value, and a missing value must not change what an approved plan cuts.
  const r = generateToolpath({ ...req("ROUGH"), pass: undefined }, contour, ctx(), stock);
  assert.ok(r.ok);
  if (!r.ok) return;
  assert.equal(r.toolpath.parameters.chipload, 0.003);
});

/* ---------------- Full depth, and the honest fallback ---------------- */

const depthSteps = (tp: ReturnType<typeof run>) =>
  new Set(tp.moves.filter((m) => m.feed !== null).map((m) => m.z.toFixed(4))).size;

test("a finish pass runs the full depth in one go", () => {
  // Every depth step leaves a witness line: a visible band where the cutter
  // re-entered, and a place the wall sits proud or shy by however the tool
  // deflected on that step.
  const finish = run("FINISH", 0.5, mill({ fluteLength: 1 }));
  assert.equal(depthSteps(finish), 1, "the finish pass stepped down");
  // The roughing pass on the same wall does step, at stepdown = D/2.
  assert.ok(depthSteps(run("ROUGH", 0.5)) > 1, "the roughing pass no longer steps down");
});

test("a wall deeper than the flute steps down, and the program says why", () => {
  // Past the flute length the shank is rubbing the wall, which is not a
  // finishing strategy. A machinist who ordered a finish pass and got a
  // stepped one has to be told which he has.
  const deep = run("FINISH", 0.9, mill({ fluteLength: 0.4 }));
  assert.ok(depthSteps(deep) > 1, "a finish pass ran past the flute length in one pass");
  assert.ok(
    deep.warnings.some((w) => /witness line at each step/i.test(w) && /flute/i.test(w)),
    deep.warnings.join(" | "),
  );
});

test("a full-depth finish pass warns about nothing", () => {
  assert.deepEqual(run("FINISH", 0.5, mill({ fluteLength: 1 })).warnings, []);
});

/* ---------------- The plan ---------------- */

const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
const planner = strip(readFileSync("src/lib/engines/machinist.ts", "utf8"));

test("a toleranced wall gets its own pass under every approach", () => {
  /*
   * This used to depend on the approach: only BEST_FINISH split rough from
   * finish, so a toleranced profile planned under any other heading got
   * roughing feeds on its final wall. The approach decides how hard to push,
   * not whether a toleranced surface is finished — that is a property of the
   * feature.
   */
  assert.ok(
    /const needsFinish = separateFinish \|\| f\.critical \|\| Boolean\(f\.tolerance\);/.test(planner),
    "whether a wall is finished depends on the approach again",
  );
});

test("a toleranced wall with no tool to finish it is named, not silently roughed", () => {
  assert.ok(
    /concerns\.push\([\s\S]{0,200}?no tool in the crib can finish it/.test(planner),
    "a missing finishing tool passes without a word",
  );
});

test("the planned pass survives into the operation and out to the engine", () => {
  // Three hops, and a break in any of them silently turns every finish pass
  // back into a roughing pass.
  const page = strip(readFileSync("src/app/(app)/parts/[id]/machinist/page.tsx", "utf8"));
  assert.ok(/pass: o\.pass \?\? "ROUGH"/.test(page), "the plan's pass is not stored on the operation");
  const pkg = strip(readFileSync("src/lib/package.ts", "utf8"));
  assert.ok(/pass: op\.pass === "FINISH" \? "FINISH" : "ROUGH"/.test(pkg), "the stored pass never reaches the engine");
  const review = strip(readFileSync("src/lib/machinist-review.ts", "utf8"));
  assert.ok(/pass: op\.pass \?\? "ROUGH"/.test(review), "the approach comparison prices finishing at roughing feeds");
});

test("the setup sheet tells the machinist which pass is which", () => {
  const sheet = strip(readFileSync("src/lib/setup-sheet.ts", "utf8"));
  assert.ok(/pass: op\.pass === "FINISH" \? "FINISH" : "ROUGH"/.test(sheet), "the sheet does not carry the pass");
});

/* ---------------- Not a behaviour change where none was wanted ---------------- */

test("deriveCuttingParameters still honours explicit overrides", () => {
  // The planner sets stepover per approach; finishing must not overrule what
  // somebody asked for by name.
  const p = deriveCuttingParameters(ctx() as CuttableContext, { stepover: 0.33 }, true);
  assert.equal(p.stepover, 0.33);
});
