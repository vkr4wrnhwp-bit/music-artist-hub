import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { POSITION_TOLERANCE, reconcilePostedProgram } from "@/lib/nc/reconcile";
import { arcMove } from "@/lib/engines/cam/arc";
import type { Move, Toolpath } from "@/lib/engines/cam/types";

/**
 * DOES THE PROGRAM CUT THE PATH THAT WAS APPROVED?
 *
 * Everything upstream verifies the toolpath. The post sits downstream of every
 * one of those proofs and nothing read what came out of it, so a dropped
 * retract, a reversed arc or a canned cycle whose R plane does not match the
 * moves it replaced would all produce a program that looks like the plan and
 * does not cut like it.
 *
 * Every test here plants one of those failures in the PROGRAM TEXT and asks
 * whether it is caught. A test that only feeds it matching input proves the
 * function returns true.
 */

const tp = (toolNumber: number, moves: Move[]): Toolpath =>
  ({
    operationId: `op${toolNumber}`,
    type: "CONTOUR_2D",
    toolId: `t${toolNumber}`,
    toolNumber,
    moves,
    parameters: { rpm: 5000, feed: 20 },
    cycleTimeMinutes: 1,
    materialRemoved: 1,
    cuttingDistance: 1,
    warnings: [],
    isPlaceholder: false,
  }) as unknown as Toolpath;

const square: Move[] = [
  { type: "RAPID", x: 0, y: 0, z: 0.1, feed: null },
  { type: "PLUNGE", x: 0, y: 0, z: -0.1, feed: 5 },
  { type: "CUT", x: 1, y: 0, z: -0.1, feed: 20 },
  { type: "CUT", x: 1, y: 1, z: -0.1, feed: 20 },
  { type: "CUT", x: 0, y: 1, z: -0.1, feed: 20 },
  { type: "CUT", x: 0, y: 0, z: -0.1, feed: 20 },
];

const squareProgram = `%
O1000 (TEST)
G20
G17 G40 G49 G80 G90
T1 M6
S5000 M3
G54 G0 X0.0000 Y0.0000
G43 H1 Z1.000
G0 X0.0000 Y0.0000 Z0.100
G1 X0.0000 Y0.0000 Z-0.100 F5.
G1 X1.0000 Y0.0000 Z-0.100 F20.
G1 X1.0000 Y1.0000 Z-0.100
G1 X0.0000 Y1.0000 Z-0.100
G1 X0.0000 Y0.0000 Z-0.100
M5
M30
%`;

/* ---------------- The program that matches ---------------- */

test("a program that traces the plan verifies", () => {
  const r = reconcilePostedProgram(squareProgram, [tp(1, square)]);
  assert.equal(r.verified, true, r.detail);
  assert.equal(r.tools.length, 1);
  assert.ok(r.tools[0].maxDeviation < POSITION_TOLERANCE, `deviation ${r.tools[0].maxDeviation}`);
  assert.match(r.detail, /traces the planned toolpath/);
});

/* ---------------- The failures it exists to catch ---------------- */

test("a dropped pass is caught", () => {
  // The last side of the square never gets cut. The program still runs to
  // completion and the part comes off with one wall uncut.
  const dropped = squareProgram.replace("G1 X0.0000 Y0.0000 Z-0.100\nM5", "M5");
  const r = reconcilePostedProgram(dropped, [tp(1, square)]);
  assert.equal(r.verified, false);
  assert.ok(
    r.findings.some((f) => f.severity === "ERROR" && /departs from the planned path|cuts .* against/.test(f.message)),
    r.findings.map((f) => f.message).join(" | "),
  );
});

test("one dropped pass among a hundred is caught, even though the distance barely moves", () => {
  /*
   * The case that isolates the reverse check.
   *
   * A hundred depth passes, one of them missing from the program. Total cutting
   * distance is 1% short — inside the 2% distance tolerance, so that check says
   * nothing. Comparing posted points against the plan says nothing either: every
   * point in the program IS on the planned path. Only asking the other question
   * — is every part of the PLAN in the program — finds it.
   *
   * It is also the realistic version of this failure. A dropped finish pass
   * leaves a part that measures oversize by one stepdown and looks perfect.
   */
  const PASSES = 100;
  const zAt = (k: number) => -0.1 - k * 0.005;
  const moves: Move[] = [{ type: "RAPID", x: 0, y: 0, z: 0.1, feed: null }];
  const lines: string[] = ["%", "O1000", "G20", "G17 G90", "T1 M6", "S5000 M3", "G0 X0.0000 Y0.0000 Z0.100"];
  for (let k = 0; k < PASSES; k++) {
    const z = zAt(k);
    moves.push({ type: "PLUNGE", x: 0, y: 0, z, feed: 5 });
    moves.push({ type: "CUT", x: 1, y: 0, z, feed: 20 });
    moves.push({ type: "CUT", x: 0, y: 0, z, feed: 20 });
    if (k === 50) continue; // the program skips this one
    lines.push(`G1 X0.0000 Y0.0000 Z${z.toFixed(3)} F5.`);
    lines.push(`G1 X1.0000 Y0.0000 Z${z.toFixed(3)} F20.`);
    lines.push(`G1 X0.0000 Y0.0000 Z${z.toFixed(3)}`);
  }
  lines.push("M30", "%");

  const r = reconcilePostedProgram(lines.join("\n"), [tp(1, moves)]);
  const drift = Math.abs(r.tools[0].postedCutting - r.tools[0].plannedCutting) / r.tools[0].plannedCutting;
  assert.ok(drift < 0.02, `the distance check would have caught this on its own (${(drift * 100).toFixed(1)}%)`);
  assert.equal(r.verified, false, "a dropped pass passed");
  assert.ok(r.findings.some((f) => /departs from the planned path/.test(f.message)));
});

test("a whole operation missing from the program is caught by name", () => {
  const r = reconcilePostedProgram(squareProgram, [tp(1, square), tp(7, square)]);
  assert.equal(r.verified, false);
  assert.ok(
    r.findings.some((f) => /T7 cuts .* and does not cut at all in the program/.test(f.message)),
    r.findings.map((f) => f.message).join(" | "),
  );
});

test("motion in the program that is in no plan is caught", () => {
  // Nothing has assessed that motion for reach, holding or collision.
  const extra = squareProgram.replace("M5\nM30", "T4 M6\nS3000 M3\nG1 X5.0000 Y5.0000 Z-0.500 F10.\nM5\nM30");
  const r = reconcilePostedProgram(extra, [tp(1, square)]);
  assert.equal(r.verified, false);
  assert.ok(r.findings.some((f) => /appears nowhere in the plan/.test(f.message)));
});

test("a coordinate shifted past tolerance is caught", () => {
  // A tenth of an inch: far too small to see in a backplot, far too big to cut.
  const shifted = squareProgram.replace("G1 X1.0000 Y1.0000 Z-0.100", "G1 X1.1000 Y1.0000 Z-0.100");
  const r = reconcilePostedProgram(shifted, [tp(1, square)]);
  assert.equal(r.verified, false);
  assert.ok(r.findings.some((f) => /departs from the planned path/.test(f.message)));
});

test("a reversed arc is caught", () => {
  // G2 where the plan says G3. Same endpoints, same I/J, the other half of the
  // circle — and a backplot at a glance looks like an arc either way.
  const from: Move = { type: "CUT", x: 1, y: 0, z: -0.1, feed: 20 };
  const planned = [
    { type: "RAPID", x: 1, y: 0, z: 0.1, feed: null } as Move,
    from,
    arcMove("ARC", from, 0, 0, { x: -1, y: 0, z: -0.1 }, false, 20),
  ];
  const good = `%
O1000
G20
G17 G90
T1 M6
S5000 M3
G0 X1.0000 Y0.0000 Z0.100
G1 X1.0000 Y0.0000 Z-0.100 F20.
G3 X-1.0000 Y0.0000 Z-0.100 I-1.0000 J0.0000
M30
%`;
  assert.equal(reconcilePostedProgram(good, [tp(1, planned)]).verified, true);
  const reversed = good.replace("G3 X-1.0000", "G2 X-1.0000");
  const r = reconcilePostedProgram(reversed, [tp(1, planned)]);
  assert.equal(r.verified, false, "a reversed arc passed");
  assert.ok(r.findings.some((f) => /departs from the planned path/.test(f.message)));
});

test("a program the parser could not finish reading is not verified", () => {
  // A refusal mid-program means everything after it is unread. Unread must
  // never come back verified — verified is what an operator reads as safe.
  const macro = squareProgram.replace("G1 X1.0000 Y1.0000 Z-0.100", "G65 P9010 X1.0000 Y1.0000");
  const r = reconcilePostedProgram(macro, [tp(1, square)]);
  assert.equal(r.verified, false);
  assert.ok(
    r.findings.some((f) => /could not be read past line/.test(f.message)),
    r.findings.map((f) => f.message).join(" | "),
  );
});

/* ---------------- Dialects it cannot read ---------------- */

test("a Heidenhain program is refused by name, not read wrongly", () => {
  const tnc = `BEGIN PGM 1000 INCH
1 TOOL CALL 1 Z S5000
2 L X+1.000 Y+0.000 Z-0.100 R0 F20
3 M30
END PGM 1000 INCH`;
  const r = reconcilePostedProgram(tnc, [tp(1, square)]);
  assert.equal(r.verified, false);
  assert.match(r.detail, /Heidenhain conversational/);
  // One honest refusal, not a page of confident nonsense about missing tools.
  assert.equal(r.findings.length, 1, r.findings.map((f) => f.message).join(" | "));
  assert.equal(r.tools.length, 0);
});

test("a Siemens program is refused by name", () => {
  const s840 = `; CANVAS
G70
G17 G90 G54
T="T1" M6
S5000 M3
G1 X=1.0000 Y=0.0000 Z=-0.100 F=20
M30`;
  const r = reconcilePostedProgram(s840, [tp(1, square)]);
  assert.equal(r.verified, false);
  assert.match(r.detail, /Siemens 840D/);
  assert.equal(r.findings.length, 1);
});

/* ---------------- A program with no tool changes ---------------- */

test("a program with no tool change is compared whole, and says so", () => {
  // GRBL has no changer, so the post writes M0 and there is no T word. Per-tool
  // comparison would report every planned tool missing and one phantom tool
  // unplanned: eight false alarms and nothing true.
  const grbl = squareProgram.replace("T1 M6\n", "");
  const r = reconcilePostedProgram(grbl, [tp(1, square)]);
  assert.equal(r.verified, true, r.detail);
  assert.match(r.detail, /Not checked tool by tool/);
  assert.ok(r.findings.some((f) => f.severity === "WARNING" && /no tool change/.test(f.message)));
});

/* ---------------- The number means what it says ---------------- */

test("the reported departure is the true worst, not where the search gave up", () => {
  // It used to stop searching as soon as a point was inside tolerance, which
  // made the reported figure track the TOLERANCE rather than the program:
  // raise the tolerance and the reported worst case rose with it.
  const src = readFileSync("src/lib/nc/reconcile.ts", "utf8");
  const block = /const worstAgainst =[\s\S]*?\n    \};/.exec(src);
  assert.ok(block, "the deviation search moved — this test cannot check it any more");
  assert.equal(
    /break;/.test(block![0]),
    false,
    "the deviation search exits early again, so the number it reports is not the worst case",
  );
});

/* ---------------- It gates the export ---------------- */

test("the mint refuses a program that does not match the plan", () => {
  const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
  const actions = strip(readFileSync("src/app/(app)/parts/[id]/nc/actions.ts", "utf8"));
  // A server action is a POST endpoint. Checking on the page is not a gate.
  assert.ok(/reconcilePostedProgram\(program\.code, pkg\.toolpaths\)/.test(actions), "the mint does not reconcile");
  assert.ok(/if \(!reconciled\.verified\) \{[\s\S]{0,200}?return \{\s*ok: false/.test(actions), "the mint does not refuse");
});
