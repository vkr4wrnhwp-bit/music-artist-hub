import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { offsetRegisters, assumedOffsetsNote } from "@/lib/engines/cam/offsets";
import { getPost, commentText, type PostContext } from "@/lib/engines/cam/post";
import type { MachineProfile } from "@/lib/domain/shop";
import type { Toolpath } from "@/lib/engines/cam/types";

/**
 * THE OFFSET REGISTERS THE PROGRAM CALLS FOR
 *
 * `G43 H6` applies the length in row 6 of the control's offset table; `G41 D6`
 * applies its radius. CANVAS wrote `lengthOffset: t.toolNumber` in three
 * places — H and D were the tool number everywhere, with no shop record behind
 * them, printed in the program header and on the setup sheet as though CANVAS
 * knew what that control held.
 *
 * It usually IS the tool number. The point is that a shop where it is not has
 * no way to say so, and that a guess printed in the same ink as a fact is one
 * nobody thinks to check. A wrong H puts the tool at the wrong Z.
 */

const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");

test("recorded registers are what the program calls", () => {
  const r = offsetRegisters({ toolNumber: 6, lengthOffset: 21, diameterOffset: 71 });
  assert.deepEqual(r, { h: 21, d: 71, source: "RECORDED", hRecorded: true, dRecorded: true });
});

test("with nothing recorded the tool number stands in, and it says so", () => {
  const r = offsetRegisters({ toolNumber: 6, lengthOffset: null, diameterOffset: null });
  assert.equal(r.h, 6);
  assert.equal(r.d, 6);
  assert.equal(r.source, "ASSUMED", "an assumption was reported as a record");
});

test("half a record is not a record", () => {
  // A shop that recorded H and not D has still not told CANVAS what D is, and
  // the tool number standing in for it is still an assumption.
  const r = offsetRegisters({ toolNumber: 6, lengthOffset: 21, diameterOffset: null });
  assert.equal(r.h, 21);
  assert.equal(r.d, 6);
  assert.equal(r.source, "PARTLY_RECORDED");
  const q = offsetRegisters({ toolNumber: 6, lengthOffset: null, diameterOffset: 71 });
  assert.equal(q.h, 6);
  assert.equal(q.d, 71);
  assert.equal(q.source, "PARTLY_RECORDED");
});

test("a recorded register is never marked assumed because the other one is blank", () => {
  /*
   * The mirror of the defect this engine exists to fix: a true number labelled
   * as a guess. The sheet marks each column from its own flag, because a shop
   * records them one at a time.
   */
  const r = offsetRegisters({ toolNumber: 6, lengthOffset: 21, diameterOffset: null });
  assert.equal(r.hRecorded, true, "a recorded H was flagged as assumed");
  assert.equal(r.dRecorded, false);
  const src = strip(readFileSync("src/lib/setup-sheet.ts", "utf8"));
  assert.ok(/lengthOffsetAssumed: !reg\.hRecorded/.test(src));
  assert.ok(/diameterOffsetAssumed: !reg\.dRecorded/.test(src));
});

test("zero is not a register", () => {
  /*
   * D0 is not "no offset selected" — it is compensate by ZERO, and every wall
   * comes back a tool radius oversize. H0 cancels the length offset, which puts
   * the tool at machine zero. Neither is a value to inherit from a blank field.
   */
  for (const bad of [0, -3]) {
    const r = offsetRegisters({ toolNumber: 6, lengthOffset: bad, diameterOffset: bad });
    assert.equal(r.h, 6, `H${bad} was accepted as a register`);
    assert.equal(r.d, 6, `D${bad} was accepted as a register`);
    assert.equal(r.source, "ASSUMED");
  }
});

test("a register is a table row, so it is a whole number", () => {
  const r = offsetRegisters({ toolNumber: 6, lengthOffset: 2.5, diameterOffset: 2.5 });
  assert.equal(r.h, 6);
  assert.equal(r.source, "ASSUMED");
});

test("the assumed note names the tools rather than counting them", () => {
  // The operator is standing at the control with the offset page open. "T5, T6"
  // is something they can check; "2 tools" is not.
  const note = assumedOffsetsNote([
    { toolNumber: 5, lengthOffset: null, diameterOffset: null },
    { toolNumber: 6, lengthOffset: 6, diameterOffset: 6 },
    { toolNumber: 7, lengthOffset: 7, diameterOffset: null },
  ]);
  assert.ok(note);
  assert.match(note!, /T5, T7/);
  assert.equal(/T6/.test(note!), false, "a recorded tool was named as assumed");
  assert.match(note!, /CHECK H AND D AGAINST THE CONTROL/);
});

test("a fully recorded crib carries no note at all", () => {
  assert.equal(assumedOffsetsNote([{ toolNumber: 5, lengthOffset: 5, diameterOffset: 5 }]), null);
});

/* ---------------- What reaches the control ---------------- */

const machine = {
  manufacturer: "Haas", model: "VF-2", controller: "HAAS_NGC", travelsX: 30, travelsY: 16, travelsZ: 20,
  maxSpindleRPM: 8100, maxFeed: 500, maxRapid: 1000,
} as unknown as MachineProfile;

const ctx = (toolTable: PostContext["toolTable"]): PostContext => ({
  programNumber: "1001", programName: "TEST", machine, workOffset: "G54", units: "IN",
  toolTable, safeZ: 1, partName: "test", revision: "A", generatedAtIso: "2026-09-04T00:00:00Z",
});

/** A straight cut with compensation opened on the lead-in and cancelled after. */
const compPath = (over: Partial<Toolpath> = {}): Toolpath =>
  ({
    id: "tp1",
    type: "CONTOUR",
    toolId: "t1",
    toolNumber: 6,
    parameters: { rpm: 3000, feed: 20, plungeFeed: 8, coolant: "FLOOD" },
    cycleTimeMinutes: 1,
    moves: [
      { type: "RAPID", x: 0, y: 0, z: 1, feed: null },
      { type: "PLUNGE", x: 0, y: 0, z: -0.1, feed: 8 },
      { type: "LEAD_IN", x: 1, y: 0, z: -0.1, feed: 20, program: { x: 0.75, y: 0, side: "RIGHT", activate: true } },
      { type: "CUT", x: 2, y: 0, z: -0.1, feed: 20, program: { x: 2, y: 0, side: "RIGHT" } },
      { type: "LEAD_OUT", x: 3, y: 0, z: -0.1, feed: 20, program: { x: 3, y: 0, side: "RIGHT", deactivate: true } },
    ],
    ...over,
  }) as unknown as Toolpath;

const haas = () => getPost("haas-ngc-dev")!;

test("the program calls the registers the crib recorded, not the tool number", () => {
  const code = haas().emit(
    [compPath()],
    ctx([{ toolNumber: 6, description: "1/2 3FL", lengthOffset: 21, diameterOffset: 71, diameter: 0.5 }]),
  );
  assert.match(code, /G43 H21 /, "G43 called a register nobody recorded");
  assert.match(code, /G42 D71 /, "G41/G42 called a register nobody recorded");
  assert.equal(/G43 H6\b/.test(code), false, "the tool number was used as the length offset anyway");
});

test("a drilled hole calls the recorded H too", () => {
  /*
   * The branch that matters most and the one a single-site fix misses. A canned
   * cycle drives Z under the length offset like everything else — a wrong H
   * here is a drill through the table rather than a wall left oversize.
   */
  const drill = {
    id: "tp2", type: "DRILL", toolId: "t2", toolNumber: 6,
    parameters: { rpm: 2400, feed: 12, plungeFeed: 12, coolant: "FLOOD" },
    cycleTimeMinutes: 0.4,
    moves: [{ type: "RAPID", x: 1, y: 1, z: 1, feed: null }],
    cannedCycle: { code: "G81", x: 1, y: 1, z: -0.5, r: 0.1, feed: 12, rpm: 2400 },
  } as unknown as Toolpath;

  const code = haas().emit(
    [drill],
    ctx([{ toolNumber: 6, description: "#7 drill", lengthOffset: 21, diameterOffset: 71, diameter: 0.201 }]),
  );
  assert.match(code, /G43 H21 /, "the drilling branch called a register nobody recorded");
  assert.equal(/G43 H6\b/.test(code), false, "the tool number was used as the length offset for the cycle");
  assert.match(code, /G81 /, "the fixture did not reach the canned-cycle branch");
});

test("H and D are separate words, because they are separate numbers", () => {
  // They index the same row on most controls in this family and they are not
  // the same word: H decides Z, D decides size.
  const code = haas().emit(
    [compPath()],
    ctx([{ toolNumber: 6, description: "1/2 3FL", lengthOffset: 21, diameterOffset: 71, diameter: 0.5 }]),
  );
  assert.match(code, /T6 1\/2 3FL .*H21 D71/, "the header does not print both registers");
});

test("an assumed register goes out labelled, in the header and beside the tool", () => {
  const code = haas().emit(
    [compPath()],
    ctx([{ toolNumber: 6, description: "1/2 3FL", lengthOffset: null, diameterOffset: null, diameter: 0.5 }]),
  );
  // Square brackets: a nested "(" would close a Fanuc comment early.
  assert.match(code, /H6 D6 \[ASSUMED\]/, "an assumption is printed in the same ink as a record");
  assert.match(code, /OFFSET REGISTERS ASSUMED EQUAL TO THE TOOL NUMBER FOR T6/);
  assert.match(code, /CHECK H AND D AGAINST THE CONTROL/);
  // And the program still calls something, because a program has to.
  assert.match(code, /G43 H6 /);
});

test("a fully recorded program carries no assumption line", () => {
  const code = haas().emit(
    [compPath()],
    ctx([{ toolNumber: 6, description: "1/2 3FL", lengthOffset: 6, diameterOffset: 6, diameter: 0.5 }]),
  );
  assert.equal(/ASSUMED/.test(code), false, "a recorded crib was reported as assumed");
});

/* ---------------- Text a control can read ---------------- */

test("a bracket in a description does not close the comment early", () => {
  /*
   * Found by emitting the seeded crib. A Fanuc-family comment runs from `(` to
   * the FIRST `)`, and T6 is described as `#7 (0.201") carbide drill` — so the
   * comment ended after 0.201 and the control read ` carbide drill` as G-code
   * words. The description is correct English and it is not a comment.
   */
  assert.equal(commentText('#7 (0.201") carbide drill'), '#7 [0.201"] carbide drill');
  const code = haas().emit(
    [compPath()],
    ctx([{ toolNumber: 6, description: '#7 (0.201") carbide drill', lengthOffset: 6, diameterOffset: 6, diameter: 0.201 }]),
  );
  for (const line of code.split("\n").filter((l) => l.startsWith("("))) {
    assert.equal(
      (line.match(/\(/g) ?? []).length,
      1,
      `a comment carries a nested bracket and ends early: ${line}`,
    );
    assert.ok(line.endsWith(")"), `a comment does not end where it looks like it ends: ${line}`);
  }
});

test("the program name is sanitised too, because a part name reaches it", () => {
  // `O1001 (BRACKET (REV 2))` closes on the inner bracket and leaves `REV 2))`
  // to be read as words.
  const code = haas().emit(
    [compPath()],
    ctx([{ toolNumber: 6, description: "em", lengthOffset: 6, diameterOffset: 6, diameter: 0.5 }]),
  );
  assert.ok(code.split("\n")[1].startsWith("O1001 ("));
  const src = strip(readFileSync("src/lib/engines/cam/post.ts", "utf8"));
  assert.ok(/O\$\{ctx\.programNumber\} \(\$\{commentText\(/.test(src), "the program name reaches the O line raw");
});

test("comments go out in the ASCII a control's reader accepts", () => {
  /*
   * ⌀, ″, °, — and · all come from CANVAS's own screens, where they belong. A
   * lot of iron in the field reads ASCII, and a control that chokes on a byte
   * in a comment is not a control with a bug — so they go out as the words a
   * machinist would have typed.
   */
  assert.equal(commentText("⌀0.5000 90° 1/2″ face — mill · P01 6×4 ±0.002"), 'DIA 0.5000 90 DEG 1/2" face - mill - P01 6x4 +/-0.002');
  // And anything else non-ASCII is dropped rather than sent as a byte nobody
  // can predict.
  assert.equal(commentText("café ✓ Ω"), "caf");

  const code = haas().emit(
    [compPath()],
    ctx([{ toolNumber: 6, description: '1/2" 90° chamfer mill', lengthOffset: 6, diameterOffset: 6, diameter: 0.5 }]),
  );
  const bad = code.split("\n").filter((l) => /[^\x20-\x7E]/.test(l));
  assert.deepEqual(bad, [], "the program carries bytes a control's reader may not accept");
});

/* ---------------- Two blocks this post must not write ---------------- */

test("compensation is never opened with D0", () => {
  /*
   * `G41 D0` is not "no offset selected" — it is compensate by zero, so the
   * control cuts on the programmed boundary and every wall comes back a tool
   * radius oversize. It reads like a real block and it runs.
   *
   * Unreachable through the tool table, which always resolves to a positive
   * register — this pins the fallback that used to sit in the emitter as
   * `D${dOffset ?? 0}`.
   */
  const src = strip(readFileSync("src/lib/engines/cam/post.ts", "utf8"));
  assert.equal(/D\$\{dOffset \?\? 0\}/.test(src), false, "the post still falls back to D0");
  assert.ok(/dOffset: number \| null/.test(src), "the D register is optional at the emitter");
  assert.ok(
    /if \(pg\?\.activate && !\(dOffset !== null && dOffset > 0\)\)/.test(src),
    "compensation can be opened with no register to name",
  );
});

test("compensation on an arc block is refused rather than dropped", () => {
  /*
   * G41/G42 must be commanded in G0 or G1 mode; this family alarms on comp
   * commanded in a circular block. The arc branch returned before the comp
   * words were ever used, so an arc lead-in would have gone out silently
   * uncompensated — the same oversize part with nothing to read. No arc lead-in
   * exists in the engine today, which is exactly why the trap would have been
   * sprung by whoever added one.
   */
  const arcLeadIn = compPath({
    moves: [
      { type: "RAPID", x: 0, y: 0, z: 1, feed: null },
      { type: "PLUNGE", x: 0, y: 0, z: -0.1, feed: 8 },
      {
        type: "LEAD_IN", x: 1, y: 0, z: -0.1, feed: 20, i: 0.5, j: 0, cw: true,
        program: { x: 0.75, y: 0, side: "RIGHT", activate: true },
      },
      { type: "CUT", x: 2, y: 0, z: -0.1, feed: 20, program: { x: 2, y: 0, side: "RIGHT" } },
    ],
  } as unknown as Partial<Toolpath>);

  assert.throws(
    () =>
      haas().emit(
        [arcLeadIn],
        ctx([{ toolNumber: 6, description: "1/2 3FL", lengthOffset: 6, diameterOffset: 6, diameter: 0.5 }]),
      ),
    /must be commanded in G0 or G1/,
    "an arc lead-in went out with the compensation word silently dropped",
  );
});

/* ---------------- The sheet in the operator's hand ---------------- */

test("the setup sheet reads the same engine as the post", () => {
  // A sheet that named a different register from the program is worse than one
  // that named none: the operator would set the length into the row the paper
  // says and the program would call another.
  const src = strip(readFileSync("src/lib/setup-sheet.ts", "utf8"));
  assert.ok(/offsetRegisters\(\{/.test(src), "the sheet derives the registers itself");
  assert.ok(/lengthOffset: reg\.h/.test(src));
  assert.ok(/diameterOffset: reg\.d/.test(src));
  assert.ok(/lengthOffsetAssumed: !reg\.hRecorded/.test(src));
  assert.equal(/lengthOffset: row\.toolNumber/.test(src), false, "the sheet still hardcodes the tool number");
  // And it tells the operator which of these numbers it was told.
  assert.ok(/are assumed equal to the tool number/.test(src), "the sheet does not say which registers were assumed");
});

test("the printed sheet gives H and D their own columns", () => {
  const src = strip(readFileSync("src/app/(app)/parts/[id]/setups/[sid]/sheet/page.tsx", "utf8"));
  assert.equal(/H \/ D/.test(src), false, "H and D are still printed as one number");
  assert.ok(/t\.lengthOffset/.test(src) && /t\.diameterOffset/.test(src));
  assert.ok(/t\.lengthOffsetAssumed &&/.test(src) && /t\.diameterOffsetAssumed &&/.test(src), "an assumed register prints as a plain fact");
});

test("the NC page hands the crib's registers over rather than the tool number", () => {
  const src = strip(readFileSync("src/app/(app)/parts/[id]/nc/page.tsx", "utf8"));
  assert.equal(/lengthOffset: t\.toolNumber/.test(src), false, "the NC page still substitutes the tool number");
  assert.ok(/lengthOffset: t\.lengthOffset \?\? null/.test(src));
  assert.ok(/diameterOffset: t\.diameterOffset \?\? null/.test(src));
});
