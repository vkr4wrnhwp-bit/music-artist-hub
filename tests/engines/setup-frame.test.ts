import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  DEFAULT_FRAME,
  frameSentence,
  isIdentity,
  reversesArcs,
  setupFrame,
  toProgram,
  toProgramMove,
  toProgramToolpath,
  type SetupFrame,
} from "@/lib/engines/cam/setup-frame";
import type { Move, Toolpath } from "@/lib/engines/cam/types";
import type { Feature, Stock } from "@/lib/domain/features";
import type { MachineProfile, Tool } from "@/lib/domain/shop";
import { planApproach } from "@/lib/engines/machinist";

/**
 * THE SETUP'S COORDINATE FRAME
 *
 * `Setup` carried `orientation` — the string "TOP" or "BOTTOM" — and a work
 * offset, and nothing else. Feature coordinates were program coordinates by
 * assumption: no origin, no rotation, no statement of how the part sits.
 *
 * For the first setup on a centred part that assumption is true, which is why
 * it survived. For the second it is not. Turn a part over and every X on it
 * moves to the other side of the machine, and nothing in the system knew — a
 * program that is dimensionally perfect and mirrored, which measures correct on
 * every individual feature and scraps the part.
 */

const frame = (over: Partial<SetupFrame> = {}): SetupFrame => ({ ...DEFAULT_FRAME, ...over });

/* ---------------- Reading a setup ---------------- */

test("a setup the way it was modelled is the identity, and so is one that records nothing", () => {
  // Every setup planned before these columns existed means exactly this, so
  // nothing already in the system moves.
  const f = setupFrame({ orientation: "TOP" });
  assert.ok(!("error" in f));
  assert.ok(isIdentity(f));
  assert.deepEqual(f, DEFAULT_FRAME);
});

test("bottom up with no flip axis is refused, because the two answers are two parts", () => {
  /*
   * "BOTTOM" cannot say which way the part was turned. Rolled about X mirrors
   * every Y, pitched about Y mirrors every X. Both put the bottom face up.
   */
  const f = setupFrame({ orientation: "BOTTOM" });
  assert.ok("error" in f);
  assert.match(f.error.reason, /does not record which axis it was turned about/);
  assert.match(f.error.reason, /two different parts/);
  assert.ok(f.error.recommendations.some((r) => /X if you rolled it front to back/.test(r)));
});

test("a flip axis on a setup that is not turned over is refused rather than silently winning", () => {
  // Either reading mirrors the program, so there is no safe way to pick one.
  const f = setupFrame({ orientation: "TOP", flipAxis: "Y" });
  assert.ok("error" in f);
  assert.match(f.error.reason, /One of the two is wrong/);
});

test("an index a vise does not produce is refused", () => {
  // A quarter turn is what a vise does. An angle between them needs a fixture
  // that locates the part at it, and none is modelled.
  for (const q of [-1, 4, 1.5]) {
    const f = setupFrame({ orientation: "TOP", quarterTurns: q });
    assert.ok("error" in f, `${q} quarter turns was accepted`);
  }
  assert.ok(!("error" in setupFrame({ orientation: "TOP", quarterTurns: 3 })));
});

/* ---------------- The transform ---------------- */

test("turning a part over about Y sends every X to the other side", () => {
  // The defect this exists for: a hole at X+2.2500 in the model is at X−2.2500
  // once the part is flipped, and the program drilled it where the model said.
  const f = frame({ flipAxis: "Y" });
  assert.deepEqual(toProgram(f, 2.25, -1.375), { x: -2.25, y: -1.375 });
  // Rolled about X instead, the same hole moves the other way.
  assert.deepEqual(toProgram(frame({ flipAxis: "X" }), 2.25, -1.375), { x: 2.25, y: 1.375 });
});

test("a quarter turn is counter-clockwise about Z", () => {
  assert.deepEqual(toProgram(frame({ quarterTurns: 1 }), 1, 0), { x: 0, y: 1 });
  assert.deepEqual(toProgram(frame({ quarterTurns: 2 }), 1, 0), { x: -1, y: 0 });
  assert.deepEqual(toProgram(frame({ quarterTurns: 3 }), 1, 0), { x: 0, y: -1 });
  // Mirroring zero produces negative zero, which reads as "X-0.0000" wherever
  // a coordinate is formatted without guarding for it.
  assert.ok(Object.is(toProgram(frame({ flipAxis: "Y" }), 0, 1).x, 0), "a mirrored zero came back as -0");
});

test("the origin is subtracted after the part is turned and indexed", () => {
  // Zero at the lower-left corner of a 6 × 4 stock, part the way it was
  // modelled: every coordinate moves by half the stock.
  const f = frame({ originX: -3, originY: -2 });
  assert.deepEqual(toProgram(f, 0, 0), { x: 3, y: 2 });
  assert.deepEqual(toProgram(f, -3, -2), { x: 0, y: 0 });
});

test("a flip and an index compose in that order", () => {
  // Turned over about Y, then indexed a quarter turn: (2, 1) mirrors to
  // (−2, 1) and rotates to (−1, −2).
  assert.deepEqual(toProgram(frame({ flipAxis: "Y", quarterTurns: 1 }), 2, 1), { x: -1, y: -2 });
});

test("the identity frame is a no-op, exactly", () => {
  for (const [x, y] of [[0, 0], [2.25, -1.375], [-1, 3]] as const) {
    assert.deepEqual(toProgram(DEFAULT_FRAME, x, y), { x, y });
  }
});

/* ---------------- Arcs ---------------- */

const arc = (over: Partial<Move> = {}): Move =>
  ({ type: "CUT", x: 1, y: 0, z: -0.1, feed: 20, i: -1, j: 0, cw: false, ...over }) as Move;

test("turning a part over reverses every arc, because the plane is seen from the other side", () => {
  /*
   * The full 3×3 of a turnover is a proper rotation — the part is not mirrored
   * — but in the XY plane the machine works in, its determinant is −1. A G3 on
   * the top face is a G2 on the bottom, and a G3 left as a G3 cuts the other
   * side of the line.
   */
  assert.equal(reversesArcs(frame({ flipAxis: "Y" })), true);
  assert.equal(reversesArcs(frame({ flipAxis: "X" })), true);
  // A quarter turn is an ordinary rotation and leaves it alone.
  assert.equal(reversesArcs(frame({ quarterTurns: 1 })), false);

  const m = toProgramMove(frame({ flipAxis: "Y" }), arc());
  assert.equal(m.cw, true, "the arc kept its direction through a turnover");
  assert.deepEqual({ x: m.x, y: m.y }, { x: -1, y: 0 });
  // i and j are the offset from the move's start to the centre — a vector, so
  // it takes the turn without the origin.
  assert.deepEqual({ i: m.i, j: m.j }, { i: 1, j: 0 });
});

test("an arc's centre offset ignores the origin, and the end point does not", () => {
  const f = frame({ originX: -3, originY: -2 });
  const m = toProgramMove(f, arc());
  assert.deepEqual({ x: m.x, y: m.y }, { x: 4, y: 2 });
  assert.deepEqual({ i: m.i, j: m.j }, { i: -1, j: 0 }, "the arc centre moved with the origin");
});

test("a straight move keeps no arc words", () => {
  const m = toProgramMove(frame({ flipAxis: "Y" }), { type: "CUT", x: 1, y: 2, z: 0, feed: 10 } as Move);
  assert.equal(m.i, undefined);
  assert.equal(m.cw, undefined);
});

/* ---------------- A whole toolpath ---------------- */

const toolpath = (over: Partial<Toolpath> = {}): Toolpath =>
  ({
    operationId: "op1", type: "DRILL", toolId: "t6", toolNumber: 6,
    moves: [
      { type: "RAPID", x: 2.25, y: -1.375, z: 0.1, feed: null },
      { type: "PLUNGE", x: 2.25, y: -1.375, z: -0.5, feed: 20 },
    ],
    parameters: { rpm: 3000, feed: 20, coolant: "FLOOD" },
    cycleTimeMinutes: 0.1, materialRemoved: 0.01, cuttingDistance: 0.6, warnings: [], isPlaceholder: false,
    cannedCycle: { code: "G81", x: 2.25, y: -1.375, z: -0.5, r: 0.1, feed: 20, rpm: 3000 },
    ...over,
  }) as unknown as Toolpath;

test("the canned cycle is transformed with the moves, not left behind", () => {
  /*
   * The descriptor is what the control actually executes. Transforming the
   * move list and not the cycle would drill the pattern in one place and
   * simulate it in another — and the reconciler, which compares the two, would
   * be the only thing that noticed.
   */
  const tp = toProgramToolpath(frame({ flipAxis: "Y" }), toolpath());
  assert.equal(tp.cannedCycle!.x, -2.25);
  assert.equal(tp.cannedCycle!.y, -1.375);
  assert.equal(tp.moves[0].x, -2.25);
  // Z and the R plane are the setup's own and are not turned.
  assert.equal(tp.cannedCycle!.z, -0.5);
  assert.equal(tp.cannedCycle!.r, 0.1);
});

test("an identity frame returns the toolpath it was given", () => {
  const tp = toolpath();
  assert.equal(toProgramToolpath(DEFAULT_FRAME, tp), tp);
});

/* ---------------- What a machinist reads ---------------- */

const STOCK = { form: "RECTANGULAR", x: 6, y: 4, z: 0.75, material: "Aluminum 6061" } as Stock;

test("the sentence names the turn, the index and where zero is", () => {
  const plain = frameSentence(DEFAULT_FRAME, STOCK);
  assert.match(plain.sentence, /X0 Y0 AT THE CENTRE OF THE STOCK/);
  assert.equal(/TURNED OVER/.test(plain.sentence), false);

  const flipped = frameSentence(frame({ flipAxis: "Y", quarterTurns: 1, originX: -3, originY: -2 }), STOCK);
  assert.match(flipped.sentence, /TURNED OVER ABOUT Y/);
  assert.match(flipped.sentence, /EVERY X ON THE MODEL IS ON THE OTHER SIDE OF THE MACHINE/);
  assert.match(flipped.sentence, /INDEXED 90° COUNTER-CLOCKWISE/);
  assert.match(flipped.sentence, /X-3\.0000 Y-2\.0000 FROM THE CENTRE OF THE STOCK/);
  // The prose form says the same thing to a screen rather than a control.
  assert.match(flipped.prose, /turned over about Y/);
  assert.match(flipped.prose, /6\.000 × 4\.000 × 0\.750/);
});

test("rolling about X names the axis that actually moves", () => {
  // The whole point of recording the axis is that the two mirror different
  // coordinates, so the sentence has to name the right one.
  assert.match(frameSentence(frame({ flipAxis: "X" }), STOCK).prose, /every Y on the model/);
  assert.match(frameSentence(frame({ flipAxis: "Y" }), STOCK).prose, /every X on the model/);
});

/* ---------------- The plan says which way it flips ---------------- */

test("a planned second setup states the axis it is turned about", () => {
  /*
   * The planner is the thing that decides there will be a flip, so it is the
   * thing that has to say which one. A plan that leaves it blank produces a
   * setup nothing can generate motion for — honest, and useless, and it would
   * happen on every two-setup part in the system.
   */
  const plan = planApproach("MINIMUM_SETUPS", {
    stock: { form: "RECTANGULAR", x: 6, y: 4, z: 0.75, material: "Aluminum 6061" } as Stock,
    features: [
      {
        id: "c1", kind: "OUTSIDE_CONTOUR", label: "Outside profile", width: 5.5, length: 3.5,
        cornerRadius: 0.25, depth: 0.625, functionalRole: "NONE", critical: false,
      } as unknown as Feature,
    ],
    machine: { id: "m", name: "VF-2", maxSpindlePower: 20, maxRPM: 8100, toolCapacity: 20 } as unknown as MachineProfile,
    tools: [
      {
        id: "em", toolNumber: 2, toolClass: "FLAT_END_MILL", description: '1/2" end mill', diameter: 0.5,
        cornerRadius: 0, flutes: 3, material: "CARBIDE", fluteLength: 1.5, overallLength: 4, stickout: 2.5,
        holder: "CAT40", holderNoseDiameter: 1.5, maxRPM: 8000, recommendedMaterials: [],
        chiploadMin: 0.001, chiploadMax: 0.006, sfmMin: 300, sfmMax: 900, coolant: "FLOOD",
        lifeRemaining: 1, condition: "GOOD", regrindCount: 0,
      } as unknown as Tool,
    ],
    workholding: null,
    finishedHeight: 0.65,
  });

  const flipped = plan.setups.filter((s) => s.orientation === "BOTTOM");
  assert.ok(flipped.length > 0, "the plan has no second setup to check");
  for (const s of flipped) {
    assert.ok(s.flipAxis, `${s.name} does not say which axis it is turned about`);
    // And the frame engine accepts what the planner wrote, rather than the two
    // agreeing in shape and disagreeing in vocabulary.
    const f = setupFrame({ orientation: s.orientation, flipAxis: s.flipAxis });
    assert.ok(!("error" in f), `the frame engine rejects the plan's own flip axis`);
    assert.equal(f.flipAxis, s.flipAxis);
    // The datum note says why that axis and not the other one.
    assert.match(s.datumNote, /fixed jaw/);
  }
  // A first setup is the way the part was modelled and says so by saying
  // nothing, which is what the identity frame is.
  for (const s of plan.setups.filter((x) => x.orientation === "TOP")) assert.equal(s.flipAxis, null);
});

/* ---------------- The package refuses rather than mirroring ---------------- */

const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");

test("a setup with no readable frame produces no motion at all", () => {
  /*
   * The alternative is a program that is dimensionally perfect and mirrored,
   * which measures correct on every individual feature and is scrap. That is
   * the one failure worth refusing outright rather than warning about.
   */
  const src = strip(readFileSync("src/lib/package.ts", "utf8"));
  assert.ok(/const frame = setupFrame\(setup\);/.test(src), "the package no longer reads the setup's frame");
  assert.ok(
    /if \("error" in frame\) \{[\s\S]{0,600}?continue;/.test(src),
    "a setup whose frame cannot be read still produces toolpaths",
  );
  assert.ok(/frameErrorsBySetup\[setup\.id\] = frame\.error;/.test(src), "the refusal is not recorded");
  assert.ok(/toolpathErrors\.push\(\{[\s\S]{0,200}?frame\.error\.reason/.test(src), "the operations are not told why");
});

test("approving a plan stores the frame it planned", () => {
  /*
   * The planner saying which way it flips buys nothing if the write drops it.
   * A plan approved without its flip axis produces a setup that generates no
   * motion, on every two-setup part, with the reason pointing at a field the
   * planner had already filled in.
   */
  const src = strip(readFileSync("src/app/(app)/parts/[id]/machinist/page.tsx", "utf8"));
  const write = /await db\.setup\.create\(\{[\s\S]*?\n      \}\);/.exec(src);
  assert.ok(write, "the setup write moved — this test cannot check it any more");
  assert.ok(/orientation: s\.orientation,/.test(write[0]), "the window is not the setup write");
  assert.ok(/flipAxis: s\.flipAxis,/.test(write[0]), "approving a plan drops the axis it planned to flip about");
});

test("the printed sheet carries the turn as its own line", () => {
  // The prose form was never rendered on the sheet, so a turn stated only
  // there reached nobody at the machine.
  const src = strip(readFileSync("src/app/(app)/parts/[id]/setups/[sid]/sheet/page.tsx", "utf8"));
  assert.ok(/sheet\.origin\.turned/.test(src), "the sheet does not print which way the part was turned");
});

test("the setup form stores only a frame the engine will act on", () => {
  /*
   * Same rule as the jaw axis: a stored value is one the frame engine acts on,
   * so an unrecognised one is cleared rather than filed. And program zero can
   * sit either side of the stock centre — the grip fields reject negatives,
   * and running the origin through the same parser would turn "X0 at the
   * lower-left corner" into "X0 at the centre" silently.
   */
  const src = strip(readFileSync("src/app/(app)/parts/[id]/setups/setup-actions.ts", "utf8"));
  assert.ok(
    /flipAxis: flipAxisRaw === "X" \|\| flipAxisRaw === "Y" \? flipAxisRaw : null,/.test(src),
    "any string can be stored as a flip axis",
  );
  assert.ok(
    /quarterTurns: quarterTurns === null \|\| quarterTurns > 3 \? null : Math\.round\(quarterTurns\),/.test(src),
    "an index outside 0-3 can be stored",
  );
  assert.ok(/originX: signed\(formData, "originX"\)/.test(src), "the origin is parsed by the unsigned reader");
  assert.ok(/originY: signed\(formData, "originY"\)/.test(src));
  assert.ok(/Number\.isFinite\(v\) \? v : null/.test(src), "the signed reader does not exist");
});

test("the transform is applied once, where the toolpath is produced", () => {
  // Two places transforming would be two chances to transform twice, and a
  // path in half-program coordinates is not visibly wrong anywhere.
  const src = strip(readFileSync("src/lib/package.ts", "utf8"));
  assert.equal((src.match(/toProgramToolpath\(/g) ?? []).length, 1);
  assert.ok(/toolpaths\.push\(toProgramToolpath\(frame, result\.toolpath\)\)/.test(src));
});
