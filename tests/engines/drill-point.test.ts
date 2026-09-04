import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { BREAKOUT_CLEARANCE, drillPoint } from "@/lib/engines/cam/drill-point";
import { planApproach } from "@/lib/engines/machinist";
import type { Feature, Stock } from "@/lib/domain/features";
import type { MachineProfile, Tool } from "@/lib/domain/shop";

/**
 * A DRILL DOES NOT MAKE A HOLE AS DEEP AS IT GOES.
 *
 * `depthOf` returns `stock.z` for a feature marked `through`, and the drill
 * operation went to exactly that Z. A twist drill is ground to a point: the
 * full diameter is reached a point-length behind the tip, so a ⌀0.201″ jobber
 * drill at 118° reaches full diameter 0.060″ up from where its tip stopped.
 * Every through hole on the part came off the machine with a cone still in the
 * bottom of it — finished-looking on the plan, on the setup sheet and in the
 * program, and short on the first part.
 *
 * Found while fixing the hole-pattern defect, which is the second time in this
 * area that reading the code for one thing has turned up another.
 */

const tool = (over: Partial<Tool> = {}): Tool =>
  ({
    id: "d201", toolNumber: 6, toolClass: "DRILL", description: '#7 (0.201") carbide drill',
    diameter: 0.201, cornerRadius: 0, flutes: 2, material: "CARBIDE", fluteLength: 1.5,
    overallLength: 3, stickout: 1.9, holder: "CAT40", holderNoseDiameter: 1.5, maxRPM: 8100,
    recommendedMaterials: [], chiploadMin: 0.003, chiploadMax: 0.006, sfmMin: 250, sfmMax: 400,
    coolant: "FLOOD", lifeRemaining: 1, condition: "GOOD", regrindCount: 0,
    pointAngle: 118, tipDiameter: 0, ...over,
  }) as unknown as Tool;

/* ---------------- The point ---------------- */

test("the point stands off the tip by half the diameter over the tangent of half the angle", () => {
  // ⌀0.201 at 118°: 0.1005 / tan 59° = 0.0604. Not a rounding error — it is
  // the difference between a hole and a blind hole with a cone in it.
  const p = drillPoint(tool());
  assert.ok(!("error" in p));
  assert.equal(Number(p.pointLength.toFixed(4)), 0.0604);
  assert.equal(Number(p.breakthrough.toFixed(4)), Number((0.0604 + BREAKOUT_CLEARANCE).toFixed(4)));
});

test("a split point is a shorter point, and the number follows the grind", () => {
  // 135° is the other common grind and it is a quarter shorter on the same
  // drill, which is exactly why guessing between them is not available.
  const jobber = drillPoint(tool({ pointAngle: 118 }));
  const split = drillPoint(tool({ pointAngle: 135 }));
  assert.ok(!("error" in jobber) && !("error" in split));
  assert.equal(Number(split.pointLength.toFixed(4)), 0.0416);
  assert.ok(split.pointLength < jobber.pointLength * 0.8, "135° came out within 20% of 118°");
});

test("a flat-bottom tool has no point", () => {
  const p = drillPoint(tool({ pointAngle: 180 }));
  assert.ok(!("error" in p));
  assert.equal(p.pointLength, 0);
  assert.equal(p.breakthrough, BREAKOUT_CLEARANCE);
});

test("no point angle recorded is a refusal that names the field", () => {
  const p = drillPoint(tool({ pointAngle: undefined }));
  assert.ok("error" in p);
  assert.match(p.error.reason, /no point angle recorded/);
  assert.match(p.error.reason, /118° and 135° differ by a quarter of that length/);
  assert.ok(p.error.recommendations.some((r) => /118° is the jobber grind/.test(r)));
});

test("an angle a drill point cannot have is refused rather than used", () => {
  // The most likely way to get one is somebody entering half the angle.
  assert.ok("error" in drillPoint(tool({ pointAngle: 0 })));
  assert.ok("error" in drillPoint(tool({ pointAngle: 200 })));
  const p = drillPoint(tool({ pointAngle: 190 }));
  assert.ok("error" in p);
  assert.match(p.error.reason, /not an angle a drill point can have/);
  assert.ok(p.error.recommendations.some((r) => /the full angle, not half of it/.test(r)));
  // 180 is a flat-bottom tool, not a bad angle.
  assert.equal("error" in drillPoint(tool({ pointAngle: 180 })), false);
});

/* ---------------- What the plan does with it ---------------- */

const MACHINE = { id: "m", name: "VF-2", maxSpindlePower: 20, maxRPM: 8100, toolCapacity: 20 } as unknown as MachineProfile;

const hole = (over: Record<string, unknown> = {}): Feature =>
  ({
    id: "h1", kind: "DRILLED_HOLE", label: "thru hole", diameter: 0.201, depth: 0.5, through: true,
    centerX: 0, centerY: 0, functionalRole: "CLEARANCE", critical: false, ...over,
  }) as unknown as Feature;

const plan = (features: Feature[], stockZ = 0.75, crib: Tool[] = [tool()]) =>
  planApproach("MINIMUM_SETUPS", {
    stock: { form: "RECTANGULAR", x: 6, y: 4, z: stockZ, material: "Aluminum 6061" } as Stock,
    features, machine: MACHINE, tools: crib, workholding: null, finishedHeight: stockZ * 0.9,
  });

const drills = (features: Feature[], stockZ = 0.75, crib: Tool[] = [tool()]) =>
  plan(features, stockZ, crib).setups.flatMap((s) => s.operations).filter((o) => o.toolId === "d201");

test("a through hole is drilled past the material by the point and the break", () => {
  const ops = drills([hole()]);
  assert.equal(ops.length, 1);
  // 0.750 of material, plus the 0.0604 point on a ⌀0.201 drill at 118°, plus
  // 0.020 to break the burr. Written out rather than recomputed from the same
  // constants the planner used, so a change to any of them shows up here.
  assert.equal(Number(ops[0].finalZ.toFixed(4)), -0.8304);
  // The old behaviour, which left the cone in the bottom of every one.
  assert.notEqual(Number(ops[0].finalZ.toFixed(4)), -0.75);
});

test("a blind hole is drilled to its recorded depth and no further", () => {
  /*
   * A drawing's blind depth is measured to the SHOULDER — the full-diameter
   * part of the hole — and adding a breakthrough to it would drill through the
   * bottom of a pocket that has to stay closed.
   */
  const ops = drills([hole({ through: false, depth: 0.4 })]);
  assert.equal(ops.length, 1);
  assert.equal(ops[0].finalZ, -0.4);
});

test("a shorter point drills a shorter hole", () => {
  const a = drills([hole()], 0.75, [tool({ pointAngle: 118 })])[0];
  const b = drills([hole()], 0.75, [tool({ pointAngle: 135 })])[0];
  assert.ok(b.finalZ > a.finalZ, "the 135° drill went as deep as the 118°");
  assert.equal(Number((a.finalZ - b.finalZ).toFixed(4)), Number((0.0416 - 0.0604).toFixed(4)));
});

test("a through hole whose drill has no point angle is a concern, not a short hole", () => {
  // Silently drilling to the stock thickness is the defect. Refusing is the
  // only other honest answer, because there is no safe direction to guess in.
  const p = plan([hole()], 0.75, [tool({ pointAngle: undefined })]);
  assert.equal(p.setups.flatMap((s) => s.operations).filter((o) => o.toolId === "d201").length, 0);
  assert.ok(p.concerns.some((c) => /thru hole: .*no point angle recorded/.test(c)), `got [${p.concerns.join(" | ")}]`);
});

test("the peck decision is the material, not the drilled depth", () => {
  /*
   * What packs a flute is how much hole the chips have to climb out of. The
   * point-length overrun is mostly the point leaving the far side, so counting
   * it would peck a hole that does not need it — 0.804 in material is exactly
   * 4:1 on a ⌀0.201 drill, and 0.884 to the tip is 4.4:1.
   */
  const ops = drills([hole()], 0.804);
  assert.equal(ops.length, 1);
  assert.equal(ops[0].type, "DRILL", "the breakthrough tipped the hole into a peck cycle");
  assert.match(ops[0].rationale, /4\.0:1 depth to diameter/);

  // And material that genuinely is past 4:1 still pecks.
  assert.equal(drills([hole()], 0.9)[0].type, "PECK_DRILL");
});

test("the operation says how far past the material it goes and why", () => {
  // The Z alone reads as an error to anybody checking the plan against the
  // drawing, and the clearance under the part is a setup decision.
  const op = drills([hole()])[0];
  assert.match(op.rationale, /Through hole: the tip runs to Z-0\.8304/);
  assert.match(op.rationale, /0\.750" of material plus the drill's 0\.0604" point and 0\.020"/);
  assert.match(op.rationale, /The part needs that much clearance under it/);

  // A blind hole says nothing about breakthrough, because there is none.
  assert.equal(/Through hole/.test(drills([hole({ through: false, depth: 0.4 })])[0].rationale), false);
});

/* ---------------- The shape that caused it ---------------- */

const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");

test("nothing plans a through hole straight to the stock thickness", () => {
  const planner = strip(readFileSync("src/lib/engines/machinist.ts", "utf8"));
  assert.ok(/drillPoint\(match\)/.test(planner), "the planner no longer asks for the drill's point");
  assert.ok(/finalZ: tipZ,/.test(planner), "the drill operation is back to the material depth");
  assert.ok(
    /const ratio = holeDepth \/ match\.diameter;/.test(planner),
    "the peck ratio is no longer the material depth",
  );
});
