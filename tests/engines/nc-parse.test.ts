import { test } from "node:test";
import assert from "node:assert/strict";
import { parseNC } from "@/lib/nc/parse";
import { analyzeNC } from "@/lib/nc/analyze";
import { generateToolpath } from "@/lib/engines/cam/engine";
import { getPost } from "@/lib/engines/cam/post";
import type { MachiningContext, OperationRequest } from "@/lib/engines/cam/types";
import type { Feature, Stock } from "@/lib/domain/features";
import type { Tool, MachineProfile } from "@/lib/domain/shop";

/**
 * Phase 4A/4B of the NC optimizer. What is pinned: modal interpretation,
 * unit conversion, arc endpoints, honest refusals, the never-retime tapping
 * flag — and the self-consistency test: the parser must read the programs
 * CANVAS's own posts emit, with zero refusals.
 */

test("modal motion and absolute coordinates: sticky G1, G0 rapids", () => {
  const p = parseNC("G20 G90\nG0 X0 Y0 Z1\nG1 Z-0.1 F10\nX2\nY1\nG0 Z1");
  assert.equal(p.refusals.length, 0);
  const cuts = p.segments.filter((s) => s.kind === "CUT");
  assert.equal(cuts.length, 3); // plunge + two sticky-G1 moves
  assert.equal(cuts[1].x1, 2);
  assert.equal(cuts[2].y1, 1);
  assert.equal(p.segments.filter((s) => s.kind === "RAPID").length, 2);
});

test("G21 converts to inches; G91 incremental accumulates", () => {
  const p = parseNC("G21 G91\nG0 X0 Y0 Z0\nG1 X25.4 F254\nX25.4");
  const cuts = p.segments.filter((s) => s.kind === "CUT");
  assert.ok(Math.abs(cuts[0].x1 - 1) < 1e-9);
  assert.ok(Math.abs(cuts[1].x1 - 2) < 1e-9);
  assert.ok(Math.abs((cuts[0].feed ?? 0) - 10) < 1e-9);
});

test("arcs land exactly on their endpoint and stay on radius", () => {
  const p = parseNC("G20 G90\nG0 X1 Y0 Z0\nG3 X-1 Y0 I-1 J0 F20");
  const arcs = p.segments.filter((s) => s.kind === "ARC");
  assert.ok(arcs.length >= 2);
  const last = arcs[arcs.length - 1];
  assert.ok(Math.abs(last.x1 - -1) < 1e-9 && Math.abs(last.y1) < 1e-9);
  for (const a of arcs) assert.ok(Math.abs(Math.hypot(a.x1, a.y1) - 1) < 0.002);
});

test("macros refuse with the line number; nothing after is interpreted", () => {
  const p = parseNC("G20\nG1 X1 F10\n#100 = 5\nG1 X9 F10");
  assert.equal(p.refusals.length, 1);
  assert.equal(p.refusals[0].line, 3);
  assert.ok(!p.segments.some((s) => s.x1 === 9));
});

test("G84 tapping segments carry the never-retime flag", () => {
  const p = parseNC("G20 G90\nG0 X0 Y0 Z1\nG84 Z-0.5 R0.1 F40\nG80");
  assert.ok(p.segments.some((s) => s.tapping && s.feed === 40));
  assert.ok(p.warnings.some((w) => /never be retimed/.test(w)));
});

test("G83 expands pecks that reach depth", () => {
  const p = parseNC("G20 G90\nG0 X0 Y0 Z1\nG83 Z-0.6 R0.1 Q0.25 F8\nG80");
  const cuts = p.segments.filter((s) => s.kind === "CUT");
  assert.ok(cuts.length >= 3);
  assert.ok(Math.abs(Math.min(...cuts.map((s) => s.z1)) - -0.6) < 1e-9);
});

test("self-consistency: the parser reads CANVAS's own Haas output with zero refusals", () => {
  const stock: Stock = { form: "RECTANGULAR", x: 6, y: 4, z: 0.75, material: "AL" };
  const tool = {
    id: "t", toolNumber: 2, toolClass: "FLAT_END_MILL", description: "em", diameter: 0.5, cornerRadius: 0,
    flutes: 3, material: "CARBIDE", fluteLength: 1.25, overallLength: 3, stickout: 1.6, holder: "CAT40",
    holderNoseDiameter: 1.75, maxRPM: 8100, recommendedMaterials: [], chiploadMin: 0.002, chiploadMax: 0.005,
    sfmMin: 600, sfmMax: 1000, coolant: "FLOOD", lifeRemaining: 1, condition: "GOOD", regrindCount: 0,
  } as unknown as Tool;
  const ctx: MachiningContext = { tool, materialSfmMin: 600, materialSfmMax: 1000, materialName: "AL", rapidRate: 1000, maxSpindleRPM: 8100, maxFeed: 500 };
  const feature = { id: "f", kind: "RECT_POCKET", label: "P", functionalRole: "NONE", critical: false, centerX: 0, centerY: 0, width: 3, length: 2, depth: 0.25, cornerRadius: 0.25, top: 0 } as unknown as Feature;
  const req: OperationRequest = { id: "op", type: "POCKET_2D", label: "P", featureId: "f", toolId: "t", setupId: "s", topZ: 0, finalZ: -0.25, clearanceZ: 0.1, retractZ: 1 };
  const r = generateToolpath(req, feature, ctx, stock);
  assert.ok(r.ok);
  if (!r.ok) return;
  const machine = { id: "m", manufacturer: "Haas", model: "VF-2", controller: "HAAS_NGC", travelsX: 30, travelsY: 16, travelsZ: 20, maxSpindleRPM: 8100, spindleTaper: "CAT40", maxFeed: 500, rapidRate: 1000, toolCapacity: 20, hasToolChanger: true, accuracy: 0.0002 } as unknown as MachineProfile;
  const nc = getPost("haas-ngc-dev")!.emit([r.toolpath], {
    programNumber: "1", programName: "t", machine, workOffset: "G54", units: "IN",
    toolTable: [{ toolNumber: 2, description: "em", lengthOffset: 2, diameter: 0.5 }],
    safeZ: 1, partName: "t", revision: "A", generatedAtIso: "2026-08-10T00:00:00Z",
  });
  const p = parseNC(nc);
  assert.equal(p.refusals.length, 0, JSON.stringify(p.refusals));
  assert.ok(p.segments.length > 50);
  const a = analyzeNC(p, { stock: { x: 6, y: 4, z: 0.75 }, toolDiameters: { 2: 0.5 }, rapidRate: 1000 });
  // Same arithmetic as the engine's own cycle time, so the totals must agree
  // to within the parsing round-trip.
  assert.ok(Math.abs(a.cutMinutes - r.toolpath.cycleTimeMinutes) / r.toolpath.cycleTimeMinutes < 0.25,
    `parsed ${a.cutMinutes} vs engine ${r.toolpath.cycleTimeMinutes}`);
});

test("air cutting is replay-proven: a repeated pass over removed material is air", () => {
  const prog = "G20 G90\nG0 X-2 Y0 Z0.2\nG1 Z-0.1 F5\nG1 X2 F20\nG0 Z0.2\nG0 X-2\nG1 Z-0.1 F5\nG1 X2 F20";
  const p = parseNC(prog);
  const a = analyzeNC(p, { stock: { x: 6, y: 4, z: 0.75 }, toolDiameters: { 0: 0.5 }, rapidRate: 600 });
  // BOTH the repeated pass and its re-plunge are air — the first pass already
  // cut the plunge point to depth. The replay is more thorough than the test
  // first assumed, which is exactly what a replay is for.
  const air = a.findings.filter((f) => f.kind === "AIR_CUTTING");
  assert.equal(air.length, 2, JSON.stringify(a.findings));
  assert.ok(air.every((f) => f.verdict === "CONFIDENT"));
  assert.deepEqual(air.map((f) => f.line).sort(), [7, 8]);
});

test("without stock nothing rises above REVIEW; unknown tools say INSUFFICIENT_DATA", () => {
  const prog = "G20 G90\nG0 X0 Y0 Z0.2\nG1 X3 F10";
  const p = parseNC(prog);
  const noStock = analyzeNC(p, { stock: null, toolDiameters: {}, rapidRate: 600 });
  assert.ok(noStock.findings.every((f) => f.verdict !== "CONFIDENT"));
  const cut = parseNC("G20 G90\nT7 M6\nG0 X0 Y0 Z0.2\nG1 Z-0.2 F5\nG1 X2 F20");
  const noTool = analyzeNC(cut, { stock: { x: 6, y: 4, z: 0.75 }, toolDiameters: {}, rapidRate: 600 });
  assert.ok(noTool.findings.some((f) => f.kind === "UNKNOWN_CONTEXT" && f.verdict === "INSUFFICIENT_DATA"));
});

test("slow linking moves above the stock are found with the rapid-delta saving", () => {
  const p = parseNC("G20 G90\nG0 X-3 Y0 Z0.5\nG1 X3 F10");
  const a = analyzeNC(p, { stock: { x: 6, y: 4, z: 0.75 }, toolDiameters: { 0: 0.5 }, rapidRate: 600 });
  const slow = a.findings.find((f) => f.kind === "SLOW_LINKING_MOVE");
  assert.ok(slow);
  assert.ok(slow!.seconds > 30); // 6" at F10 is 36s; a rapid is under a second
});

/* ---------------- Every refusal, and what a refusal promises ---------------- */

/**
 * The analyzer tells the operator "Interpretation stopped at line N.
 * Everything before that line is analyzed; nothing after it is." Three of the
 * four refusals had no test, so a parser that quietly carried on reading
 * would have kept that message truthful only by accident — and the optimiser
 * proposes feed changes against whatever the parser believes it read.
 */

test("a subprogram call is refused, and nothing after it is interpreted", () => {
  // M98 jumps somewhere the parser cannot follow. Continuing past it means
  // believing the program is what remains in this file, which it is not.
  const p = parseNC("G20 G90\nG1 X1 F10\nM98 P1000\nG1 X5 F60\nG1 X9 F60");
  assert.equal(p.refusals.length, 1);
  assert.match(p.refusals[0].reason, /subprogram/i);
  assert.equal(p.refusals[0].line, 3);
  for (const s of p.segments) assert.ok(s.line < 3, `line ${s.line} was interpreted past the refusal`);
});

test("M97 is refused as well as M98 — both are calls", () => {
  // The pattern is M9[78], and the reason says "Subprogram call". M97 is
  // Haas's local subprogram call and M98 the standard one, so both belong.
  //
  // M99 is deliberately not here: it is the subprogram RETURN, not a call.
  // A first version of this test asserted M99 was refused, which was an
  // assumption about the code rather than a reading of it — the reason
  // string says what the pattern is for.
  for (const call of ["M97 P1000", "M98 P1000"]) {
    const p = parseNC(`G20 G90\nG1 X1 F10\n${call}`);
    assert.equal(p.refusals.length, 1, call);
    assert.match(p.refusals[0].reason, /subprogram/i);
  }
});

test("an arc outside the XY plane is refused rather than flattened", () => {
  // A G18/G19 arc read as though it were in XY produces a segment of the
  // wrong length in the wrong place, and every downstream number — arc
  // length, engagement, cycle time — is computed from that.
  const p = parseNC("G20 G90\nG18\nG1 X1 F10\nG2 X2 Z1 I0.5 K0");
  assert.equal(p.refusals.length, 1);
  assert.match(p.refusals[0].reason, /G17|plane/i);
});

test("an arc whose I/J/R cannot be resolved is refused, not guessed at", () => {
  // An R that cannot reach between the endpoints has no solution. Inventing
  // one puts the toolpath somewhere the program does not go.
  const p = parseNC("G20 G90\nG1 X0 Y0 F10\nG2 X10 Y0 R0.1");
  assert.equal(p.refusals.length, 1, `got ${JSON.stringify(p.refusals)}`);
  assert.match(p.refusals[0].reason, /arc geometry|I\/J\/R/i);
});

test("a macro or control-flow word is refused", () => {
  for (const line of ["#100 = 5", "IF [#1 GT 2] GOTO 50", "WHILE [#1 LT 10] DO 1", "GOTO 100"]) {
    const p = parseNC(`G20 G90\nG1 X1 F10\n${line}\nG1 X5 F60`);
    assert.equal(p.refusals.length, 1, line);
    assert.match(p.refusals[0].reason, /macro|control flow/i);
  }
});

test("every refusal stops interpretation, which is what the analyzer promises", () => {
  // The promise is in the UI: "Everything before that line is analyzed;
  // nothing after it is." A refusal that did not stop would make that false.
  const programs = [
    "G20 G90\nG1 X1 F10\n#100 = 5\nG1 X5 F60",
    "G20 G90\nG1 X1 F10\nM98 P1000\nG1 X5 F60",
    "G20 G90\nG18\nG1 X1 F10\nG2 X2 Z1 I0.5 K0\nG1 X9 F60",
    "G20 G90\nG1 X0 Y0 F10\nG2 X10 Y0 R0.1\nG1 X20 F60",
  ];
  for (const src of programs) {
    const p = parseNC(src);
    assert.equal(p.refusals.length, 1, src.split("\n")[2]);
    const stoppedAt = p.refusals[0].line;
    for (const s of p.segments) {
      assert.ok(s.line <= stoppedAt, `a segment at line ${s.line} survived a refusal at ${stoppedAt}`);
    }
  }
});

test("a refusal names a line the operator can go and look at", () => {
  const p = parseNC("G20 G90\nG1 X1 F10\nG1 X2\nM98 P1000");
  assert.equal(p.refusals[0].line, 4);
  assert.ok(p.refusals[0].reason.length > 10, "a reason has to say what stopped it");
});

test("a clean program refuses nothing", () => {
  const p = parseNC("G20 G90\nG0 X0 Y0 Z1\nG1 Z-0.1 F10\nG1 X2 F30\nG2 X3 Y1 I0.5 J0\nG0 Z1\nM30");
  assert.deepEqual(p.refusals, []);
  assert.ok(p.segments.length > 0);
});

/* ------------------------------------------------------------------ */
/* Canned cycles repeat at a new position — Z, R and Q are all modal   */
/* ------------------------------------------------------------------ */

test("a drilling cycle repeated across a hole pattern drills every hole", () => {
  // The classic Fanuc/Haas idiom: state the cycle once, then give bare XY
  // positions. Z, R and Q are modal to the cycle. Only R was kept modal —
  // the depth was re-read from the CURRENT Z, which after the first hole is
  // the retract plane, so `while (depth > finalZ)` was `while (0.1 > 0.1)`
  // and every repeat drilled nothing. The program lost 2 of 3 holes and
  // said nothing about it.
  const nc = [
    "G20 G90 G17",
    "T2 M06",
    "S2200 M03",
    "G00 X1.0 Y1.0",
    "G83 Z-0.75 R0.1 Q0.15 F9.",
    "X2.0",
    "X3.0",
    "G80",
    "M30",
  ].join("\n");
  const p = parseNC(nc);
  assert.deepEqual(p.refusals, []);
  const cuts = p.segments.filter((s) => s.kind === "CUT" && s.feed !== null);
  const spots = new Set(cuts.map((s) => `${s.x1.toFixed(2)},${s.y1.toFixed(2)}`));
  assert.equal(spots.size, 3, `drilled ${spots.size} of 3 positions`);
  // Every hole reaches the modal depth, not the retract plane.
  for (const spot of spots) {
    const atSpot = cuts.filter((s) => `${s.x1.toFixed(2)},${s.y1.toFixed(2)}` === spot);
    assert.ok(Math.min(...atSpot.map((s) => s.z1)) <= -0.75 + 1e-9, `${spot} never reached depth`);
    // And pecks, not one plunge: Q0.15 over 0.85" of travel is several.
    assert.ok(atSpot.length >= 5, `${spot} pecked ${atSpot.length} times — Q was not modal`);
  }
});

test("the peck increment stays modal across repeats, and G80 clears the cycle", () => {
  const nc = "G20 G90\nG00 X0 Y0\nG83 Z-0.6 R0.1 Q0.2 F9.\nX1.0\nG80\nX2.0\nM30";
  const p = parseNC(nc);
  const cuts = p.segments.filter((s) => s.kind === "CUT" && s.feed !== null);
  // Two positions drilled; the move after G80 is not a third hole.
  assert.equal(new Set(cuts.map((s) => s.x1.toFixed(2))).size, 2);
  assert.ok(!cuts.some((s) => s.x1 === 2.0), "a move after G80 was still treated as a cycle");
});

test("a new cycle after G80 does not inherit the cancelled cycle's depth", () => {
  // G80 cancels the cycle, so its depth is gone with it. A later G83 that
  // omits Z has no depth of its own, and silently drilling to the PREVIOUS
  // cycle's depth is how a 0.6" hole appears where a through-hole was
  // meant — or worse, where a shallow one was. Refuse and name it.
  const nc = [
    "G20 G90",
    "G00 X0 Y0",
    "G83 Z-0.6 R0.1 Q0.2 F9.",
    "G80",
    "G00 X1.0",
    "G83 R0.1 Q0.2 F9.",
    "X2.0",
    "M30",
  ].join("\n");
  const p = parseNC(nc);
  assert.equal(p.refusals.length, 1, "the depthless second cycle was accepted");
  assert.match(p.refusals[0].reason, /no depth/i);
  // And nothing was drilled at the second position on a stale depth.
  const cuts = p.segments.filter((s) => s.kind === "CUT" && s.feed !== null);
  assert.ok(!cuts.some((s) => s.x1 >= 1.0), "drilled on a depth that belonged to a cancelled cycle");
});

test("a cycle with no depth anywhere is refused rather than drilled to nothing", () => {
  // No Z on the line and none modal from an earlier cycle: there is no
  // depth to drill to, and inventing one is how a hole ends up at the
  // retract plane while the report claims it was drilled.
  // The cycle line itself carries no X/Y/Z so it is skipped as a
  // non-motion line; the refusal lands on the first position that tries to
  // use the cycle, which is where a machinist would look for it.
  const p = parseNC("G20 G90\nG00 X0 Y0\nG83 R0.1 Q0.1 F9.\nX1.0\nM30");
  assert.equal(p.refusals.length, 1);
  assert.match(p.refusals[0].reason, /no depth/i);
});

test("an unreadable cycle stops interpretation instead of rapiding through the part", () => {
  // Ignoring a G-word does not ignore its line. The coordinates are still
  // consumed by whatever motion was modal — usually the G00 that positioned
  // over the hole. A G82 spot cycle became a RAPID from clearance straight
  // down to depth, and the bare X after it a RAPID across the part at that
  // depth: a modelled crash, reported as a warning, with the replay and the
  // cycle time computed over it.
  for (const g of ["G82 Z-0.2 R0.1 P100 F5.", "G73 Z-0.6 R0.1 Q0.1 F9.", "G85 Z-0.5 R0.1 F6."]) {
    const nc = `G20 G90\nG00 X1 Y1 Z1.0\n${g}\nX2.0\nG80\nM30`;
    const p = parseNC(nc);
    assert.equal(p.refusals.length, 1, `${g} was not refused`);
    assert.match(p.refusals[0].reason, /motion vocabulary/i);
    // Nothing below the clearance plane was ever emitted.
    const belowStock = p.segments.filter((s) => s.z1 < 0);
    assert.deepEqual(belowStock, [], `${g} emitted motion into the part`);
  }
});

test("an unknown G-code with no coordinates of its own is only a warning", () => {
  // G28 on its own line takes no coordinates that a stale motion mode could
  // swallow, so refusing the whole program over it would be wrong.
  const p = parseNC("G20 G90\nG00 X1 Y1\nG01 Z-0.1 F10.\nG01 X2.0\nM30\nG91 G28 Z0");
  assert.deepEqual(p.refusals, []);
  assert.ok(p.segments.some((s) => s.kind === "CUT"));
});

test("a cut with no feed rate is refused, not timed at the rapid rate", () => {
  // Null feed reads as "rapid" everywhere downstream, so a feed move with
  // no F was timed at the machine's rapid rate — the fastest number
  // available. On a two-move program that is 0.004 minutes against 0.22:
  // fifty-five times under, silently, with no assumption naming it. There
  // is no honest number to substitute; the feed is simply not in the file.
  const p = parseNC("G20 G90\nG00 X0 Y0 Z0.1\nG01 Z-0.1\nG01 X2.0\nM30");
  assert.equal(p.refusals.length, 1);
  assert.match(p.refusals[0].reason, /no feed rate/i);
  assert.deepEqual(p.segments.filter((s) => s.kind === "CUT"), []);
});

test("feed stays modal across a tool change, and tapping is exempt", () => {
  // The refusal must not fire on legitimate modal feed: an F set for tool 1
  // still applies to tool 2 unless the program changes it.
  const modal = parseNC(
    "G20 G90\nT1 M06\nG00 X0 Y0 Z0.1\nG01 Z-0.1 F12.\nG01 X2.\nT2 M06\nG00 X0 Y1 Z0.1\nG01 Z-0.1\nG01 X2.\nM30",
  );
  assert.deepEqual(modal.refusals, []);
  assert.equal(modal.segments.filter((s) => s.kind === "CUT").length, 4);

  // A rigid tap's feed is the thread, and the cycle handles it — the
  // refusal is scoped to G01/G02/G03 and must not catch it.
  const tap = parseNC("G20 G90\nT3 M06\nS500 M03\nG00 X1 Y1 Z0.5\nG84 Z-0.5 R0.1 F25.\nX2.0\nG80\nM30");
  assert.deepEqual(tap.refusals, []);
  assert.ok(tap.segments.some((s) => s.tapping));
});

test("a program whose lines end in bare carriage returns is read, not swallowed", () => {
  // `/\r?\n/` made such a file ONE line: one segment, and — worse — zero
  // refusals. A clean report on a program the parser had never read, which is
  // the one thing this file refuses to do everywhere else.
  const blocks = ["%", "O0001", "G20 G17 G90 G54", "G00 X0 Y0", "G01 Z-0.25 F10.", "G01 X2.0 F20.", "M30", "%"];
  const lf = parseNC(blocks.join("\n"));
  const cr = parseNC(blocks.join("\r"));
  assert.ok(lf.segments.length > 1, "the fixture must produce several segments or this proves nothing");
  assert.equal(cr.lineCount, lf.lineCount);
  assert.equal(cr.segments.length, lf.segments.length);
  assert.deepEqual(cr.refusals, lf.refusals);
});
