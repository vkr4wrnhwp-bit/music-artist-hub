import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { CHORD_TOLERANCE, arcGeometry, arcMove, arcSegments, flattenArcs, isArc, pathLength } from "@/lib/engines/cam/arc";
import { cycleTime } from "@/lib/engines/cam/engine";
import type { Move } from "@/lib/engines/cam/types";

/**
 * ARCS
 *
 * The defect this replaces, in one number: a Ø1.000" bore was walked as thirty
 * straight chords, and at the middle of each one the cutter sat 0.0027" inside
 * nominal. Five times the whole band on a ±0.0005" bearing seat, and a form
 * error rather than a size error — no offset dials it out.
 *
 * The two things that can go wrong now are worse than the thing they replace,
 * which is why they are tested hard: an I/J sign error puts the arc on the
 * other side of the part, and a direction error cuts the wrong way round.
 */

const cut = (x: number, y: number, z = 0, feed: number | null = 10): Move => ({ type: "CUT", x, y, z, feed });

/* ---------------- Geometry ---------------- */

test("I and J are the offsets from the arc start to the centre", () => {
  // The incremental convention every Fanuc-family control reads. Stored this
  // way so the post writes them out untouched — a conversion on the way out is
  // a sign error waiting to happen.
  const m = arcMove("ARC", { x: 1, y: 0 }, 0, 0, { x: -1, y: 0, z: 0 }, false, 10);
  assert.equal(m.i, -1);
  assert.equal(m.j, 0);
  assert.equal(m.cw, false);
  assert.ok(isArc(m));
});

test("a half turn sweeps pi, and its length is pi r", () => {
  const from = cut(1, 0);
  const m = arcMove("ARC", from, 0, 0, { x: -1, y: 0, z: 0 }, false, 10);
  const g = arcGeometry(from, m)!;
  assert.equal(g.radius, 1);
  assert.ok(Math.abs(g.sweep - Math.PI) < 1e-9, `sweep ${g.sweep}`);
  assert.ok(Math.abs(g.length - Math.PI) < 1e-9);
});

test("clockwise sweeps negative", () => {
  const from = cut(1, 0);
  const g = arcGeometry(from, arcMove("ARC", from, 0, 0, { x: -1, y: 0, z: 0 }, true, 10))!;
  assert.ok(g.sweep < 0, `clockwise arc swept ${g.sweep}`);
  assert.ok(Math.abs(Math.abs(g.sweep) - Math.PI) < 1e-9);
});

test("a helical arc is longer than its planar shadow", () => {
  const from = cut(1, 0, 0);
  const g = arcGeometry(from, arcMove("ARC", from, 0, 0, { x: -1, y: 0, z: -0.5 }, false, 10))!;
  assert.ok(Math.abs(g.length - Math.hypot(Math.PI, 0.5)) < 1e-9, `length ${g.length}`);
});

test("start and end coincident reads as a full circle", () => {
  // A control given I/J and no endpoint cuts a full circle. This reads one the
  // same way rather than as a zero-length move the simulator would skip.
  const from = cut(1, 0);
  const g = arcGeometry(from, { type: "ARC", x: 1, y: 0, z: 0, feed: 10, i: -1, j: 0, cw: false })!;
  assert.ok(Math.abs(g.sweep - 2 * Math.PI) < 1e-9);
});

test("a straight move is not an arc", () => {
  assert.equal(arcGeometry(cut(0, 0), cut(1, 1)), null);
  assert.equal(isArc(cut(1, 1)), false);
});

test("a degenerate arc with no radius is refused rather than divided by", () => {
  assert.equal(arcGeometry(cut(0, 0), { type: "ARC", x: 0, y: 0, z: 0, feed: 10, i: 0, j: 0, cw: false }), null);
});

/* ---------------- Flattening ---------------- */

test("segment count holds the stated chord tolerance", () => {
  for (const radius of [0.05, 0.25, 0.5, 1, 3]) {
    const n = arcSegments(radius, 2 * Math.PI);
    const sagitta = radius * (1 - Math.cos(Math.PI / n));
    assert.ok(
      sagitta <= CHORD_TOLERANCE + 1e-12,
      `r${radius} gave ${n} segments, sagitta ${sagitta.toFixed(6)} over ${CHORD_TOLERANCE}`,
    );
  }
});

test("the old chord count would have failed that tolerance by five times", () => {
  // What the engine used to emit for a 0.500" radius: max(24, 0.5*60) = 30.
  const sagitta = 0.5 * (1 - Math.cos(Math.PI / 30));
  assert.ok(sagitta > 0.002, `the historical error was ${sagitta}`);
  assert.ok(sagitta > CHORD_TOLERANCE * 5);
});

test("flattening lands exactly on the arc's endpoint", () => {
  // A path that does not close is a path the simulator and the control
  // disagree about, and the disagreement is invisible.
  const from = cut(1, 0);
  const m = arcMove("ARC", from, 0, 0, { x: -1, y: 0, z: -0.25 }, false, 10);
  const flat = flattenArcs([from, m]);
  const last = flat[flat.length - 1];
  assert.equal(last.x, -1);
  assert.equal(last.y, 0);
  assert.equal(last.z, -0.25);
});

test("every flattened point sits on the arc", () => {
  const from = cut(2, 0);
  const m = arcMove("ARC", from, 0, 0, { x: 0, y: 2, z: 0 }, false, 10);
  for (const p of flattenArcs([from, m]).slice(1)) {
    assert.ok(Math.abs(Math.hypot(p.x, p.y) - 2) < 1e-9, `point off the circle: ${p.x},${p.y}`);
  }
});

test("flattening carries the move type, so a lead-in stays a lead-in", () => {
  const from = cut(1, 0);
  const m = arcMove("LEAD_IN", from, 0, 0, { x: -1, y: 0, z: 0 }, false, 10);
  assert.ok(flattenArcs([from, m]).slice(1).every((s) => s.type === "LEAD_IN"));
});

test("straight moves pass through flattening untouched", () => {
  const moves = [cut(0, 0), cut(1, 0), { type: "RAPID" as const, x: 1, y: 1, z: 1, feed: null }];
  assert.deepEqual(flattenArcs(moves), moves);
});

/* ---------------- Length ---------------- */

test("path length measures an arc along the arc, not across its chord", () => {
  // The failure this prevents: a full bore ring measured as its diameter.
  // Every circular cut in the program shorter than it is, and the quoted
  // cycle time short with it.
  const from = cut(1, 0);
  const half = arcMove("ARC", from, 0, 0, { x: -1, y: 0, z: 0 }, false, 10);
  const { total, cutting } = pathLength([from, half]);
  assert.ok(Math.abs(total - Math.PI) < 1e-9, `measured ${total} for a half circle of radius 1`);
  assert.equal(cutting, total);
  // The chord would have been 2. The arc is π.
  assert.ok(total > 2);
});

test("cycle time bills an arc for the arc, not for its chord", () => {
  // This is the caller that a mutation slipped past: pathLength was tested and
  // cycleTime, which does the same arithmetic for the number a shop quotes
  // from, was not. A half circle of radius 1 at 10 in/min is π/10 minutes; the
  // chord would have said 2/10 — a third off, on every circular cut.
  const from = cut(1, 0);
  const half = arcMove("ARC", from, 0, 0, { x: -1, y: 0, z: 0 }, false, 10);
  const { minutes, cuttingDistance } = cycleTime([from, half], 600);
  assert.ok(Math.abs(cuttingDistance - Math.PI) < 1e-9, `cutting distance ${cuttingDistance}`);
  assert.ok(Math.abs(minutes - Math.PI / 10) < 1e-3, `minutes ${minutes}`);
});

test("rapids do not count as cutting distance", () => {
  const { cutting } = pathLength([cut(0, 0), { type: "RAPID", x: 5, y: 0, z: 0, feed: null }]);
  assert.equal(cutting, 0);
});

/* ---------------- What the generators now emit ---------------- */

test("a circle is emitted as two arcs, not one full-circle block", () => {
  // A G2 with I/J and no endpoint means "full circle" on Haas and Fanuc and
  // means something else or nothing elsewhere. Two halves are unambiguous
  // everywhere and cost one block.
  const src = readFileSync("src/lib/engines/cam/engine.ts", "utf8");
  const ring = /function ringMoves\([\s\S]{0,900}?\n}/.exec(src);
  assert.ok(ring, "ringMoves moved — this test cannot check it any more");
  const arcs = ring![0].match(/arcMove\(/g) ?? [];
  assert.equal(arcs.length, 2, "a circle is not two arcs");
});

test("no constant-radius circle in the engine is still walked in chords", () => {
  const src = readFileSync("src/lib/engines/cam/engine.ts", "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/\/\/.*$/gm, "");

  // The shape of the old defect, exactly: an angle stepped as a fraction of a
  // full turn. Four operations did this — pocket rings, profile corners, bore
  // helical interpolation and adaptive's ramp entry — and each one produced a
  // polygon where the drawing says circle.
  //
  // The ONE surviving site is the Archimedean spiral in adaptive clearing, and
  // it is not a circle: its radius grows every revolution, so no G2/G3 can
  // express it and every CAM system on the market chords it too. It is allowed
  // here by name, and the next test pins that its chord count comes from the
  // shared tolerance rather than from a guess.
  const fullTurnSteps = [...src.matchAll(/const a = \([^)]*\) \* Math\.PI \* 2;/g)];
  assert.equal(
    fullTurnSteps.length,
    1,
    `${fullTurnSteps.length} full-turn chord loops in the engine; only the spiral may remain`,
  );
  const spiral = /const segsPerRev[\s\S]{0,400}?const rad = Math\.min\(maxR/.exec(src);
  assert.ok(spiral, "the one permitted chord loop is no longer the spiral — check what it became");
});

test("the spiral's chord count comes from the shared tolerance, not a fixed number", () => {
  const src = readFileSync("src/lib/engines/cam/engine.ts", "utf8");
  // It was a flat 48 per revolution, which is a chord error that grows with
  // the pocket: fine on a half-inch pocket, 0.006" on a four-inch one.
  assert.ok(
    /const segsPerRev = arcSegments\(maxR, 2 \* Math\.PI\)/.test(src),
    "the spiral is back to a fixed chord count",
  );
});

/* ---------------- What reaches the control ---------------- */

const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
const post = strip(readFileSync("src/lib/engines/cam/post.ts", "utf8"));

test("the Fanuc family emits G2/G3 with I and J", () => {
  // I and J come from `ai`/`aj`, which resolve to the PROGRAMMED arc centre
  // where compensation is active and to the cutter centre otherwise. An arc's
  // centre offset is measured from where the program says the tool is.
  assert.ok(/\$\{mv\.cw \? "G2" : "G3"\} \$\{coords\} I\$\{n\(ai\)\} J\$\{n\(aj\)\}/.test(post), "no I/J arc block");
  assert.ok(/const ai = pg\?\.i \?\? mv\.i!;/.test(post), "the arc centre does not follow the programmed path");
  // R-word arcs are ambiguous over 180° — the control picks the minor arc and
  // the major one is unreachable. I/J is never ambiguous.
  assert.equal(/G2.*\bR\$\{/.test(post), false, "an R-word arc reached a post");
});

test("a dialect that cannot express a helix flattens it and says so", () => {
  // Guessing TNC or 840D helix syntax produces a program that does not cut the
  // shape. A longer program that cuts the right shape is the honest trade, and
  // the operator is told which one they are reading.
  for (const dialect of ["TNC HELIX SYNTAX NOT IMPLEMENTED", "TURN= HELIX NOT IMPLEMENTED"]) {
    assert.ok(post.includes(dialect), `${dialect} is not stated in the program`);
  }
  assert.ok(/FLATTENED TO \$\{CHORD_TOLERANCE\}IN CHORD/.test(post), "the flattening does not state its tolerance");
});

test("the simulator walks the flattened path", () => {
  // A height field is swept segment by segment. An arc read as its chord
  // removes a straight swath where the tool curves — leaving material the
  // program cuts, and missing the jaw the tool reaches on the way round.
  const sim = strip(readFileSync("src/lib/sim/stock-removal.ts", "utf8"));
  assert.ok(/const moves = flattenArcs\(op\.moves\)/.test(sim), "the simulator still treats arcs as chords");
});

test("one tessellation, so the simulator and the post cannot disagree", () => {
  const arc = readFileSync("src/lib/engines/cam/arc.ts", "utf8");
  for (const consumer of ["src/lib/sim/stock-removal.ts", "src/lib/engines/cam/post.ts", "src/components/viewport/scene.tsx"]) {
    const src = readFileSync(consumer, "utf8");
    assert.ok(/flattenArcs/.test(src), `${consumer} does not use the shared tessellation`);
  }
  assert.ok(/export function flattenArcs/.test(arc));
});

/* ------------------------------------------------------------------ */
/* Canned cycles                                                       */
/* ------------------------------------------------------------------ */

/**
 * Drilling used to go out as long-hand G1 plunges and retracts. It cuts, and it
 * is not what anybody expects to read at the control — and it gives up G83's
 * chip-break timing, the retract to R rather than to Z, and single-block
 * stepping through one cycle instead of forty lines.
 *
 * The thing that must not break: the cycle and the move list have to describe
 * the same motion. The simulator walks the moves and the machine runs the
 * cycle, so if those two disagree the simulation is proving a program that
 * will not run.
 */
test("the drill cycle and the moves agree about depth and the R plane", () => {
  const post = strip(readFileSync("src/lib/engines/cam/post.ts", "utf8"));
  const eng = strip(readFileSync("src/lib/engines/cam/engine.ts", "utf8"));

  // Both come from one `rPlane` in the generator, so there is no second number
  // to drift. The peck retract used to be topZ + 0.05 while the rapid came
  // down to clearanceZ — two planes for one operation.
  assert.ok(/const rPlane = req\.clearanceZ;/.test(eng), "the R plane is not a single value");
  // Scoped to the peck loop. `z: rPlane` also appears on the rapid down, so an
  // unscoped match here would pass while the retract between pecks went
  // somewhere else entirely — which is exactly what a mutation proved.
  const peckLoop = /while \(z > req\.finalZ \+ 1e-6\) \{[\s\S]*?\n  \}/.exec(eng);
  assert.ok(peckLoop, "the peck loop moved — this test cannot check it any more");
  assert.ok(
    /type: "RETRACT"[^}]*z: rPlane/.test(peckLoop![0]),
    "the retract between pecks no longer returns to the plane the cycle uses",
  );
  assert.ok(/r: rPlane,/.test(eng), "the cycle's R is not the move list's R");

  // And the post reads the descriptor rather than the moves.
  assert.equal(
    /Math\.min\(\.\.\.tp\.moves\.map/.test(post),
    false,
    "the post is pattern-matching a cycle out of the move list again",
  );
});

test("the Haas family emits G81, G83 and G84 and always closes with G80", () => {
  const post = strip(readFileSync("src/lib/engines/cam/post.ts", "utf8"));
  assert.ok(/G98 \$\{cy\.code\}/.test(post), "no canned cycle block");
  // G98 rather than G99: the tool returns to the initial level, which is what
  // clears a clamp on the way to the next hole.
  assert.ok(/lines\.push\("G80"\)/.test(post), "a cycle is left open");
});

test("G84 gets no M3, and a drill does", () => {
  // G84 owns the spindle — it reverses at the bottom. An M3 alongside it is a
  // broken tap. A drill needs the spindle started like anything else.
  const post = strip(readFileSync("src/lib/engines/cam/post.ts", "utf8"));
  assert.ok(/tap \? `S\$\{cy\.rpm\}` : `S\$\{cy\.rpm\} M3`/.test(post), "the spindle handling is not split by cycle");
});

test("no cycle leaves the spindle turning", () => {
  // The old special-cased tap branch was the one path out of this post that
  // ended a tool without an M5. G80 has cancelled the cycle by then, so the
  // spindle is back under normal control and stopping it is both safe and
  // what every other block here does.
  const post = strip(readFileSync("src/lib/engines/cam/post.ts", "utf8"));
  const block = /if \(tp\.cannedCycle\) \{[\s\S]*?continue;/.exec(post);
  assert.ok(block, "the canned-cycle block moved — this test cannot check it any more");
  assert.ok(/lines\.push\("M5"\);/.test(block![0]), "a canned cycle can end with the spindle running");
});

test("a control with no canned cycles drills as moves and says so", () => {
  // GRBL has no G81 or G83 at all — it faults on them. The same motion in more
  // blocks is correct; a cycle the control cannot run is not.
  const post = strip(readFileSync("src/lib/engines/cam/post.ts", "utf8"));
  assert.ok(/NOT AVAILABLE ON GRBL — DRILLED AS FEED MOVES/.test(post));
  for (const said of ["CYCLE 200/203 NOT IMPLEMENTED", "CYCLE81/83 NOT IMPLEMENTED"]) {
    assert.ok(post.includes(said), `${said} is not stated in the program`);
  }
});
