import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { getPost, type PostContext } from "@/lib/engines/cam/post";
import type { MachineProfile } from "@/lib/domain/shop";
import type { Toolpath } from "@/lib/engines/cam/types";

/**
 * TWO SETUPS, ONE PROGRAM, NO FLIP
 *
 * A two-setup part posted as one continuous program. `Toolpath` dropped the
 * setup id on the way out of the engine, so every motion block called the one
 * work offset a dropdown asked for, and nothing whatever marked the boundary:
 * the control ran setup 1 and then ran setup 2's motion on a part still
 * clamped the first way.
 *
 * Setup 2 on the seeded demo part is "Flip, thickness and profile". It
 * machines the opposite face. That program drives the tool through the vise.
 *
 * The header had printed "G54 — …" and "G55 — …" since B3, which is what made
 * it look considered.
 */

const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");

const machine = {
  manufacturer: "Haas", model: "VF-2", controller: "HAAS_NGC", travelsX: 30, travelsY: 16, travelsZ: 20,
  maxSpindleRPM: 8100, maxFeed: 500, maxRapid: 1000,
} as unknown as MachineProfile;

const ORIGINS = [
  { setupId: "s1", name: "SETUP 1 — Top face and features", workOffset: "G54", sentence: "Z0 at the top of the stock." },
  {
    setupId: "s2",
    name: "SETUP 2 — Flip, thickness and profile",
    workOffset: "G55",
    sentence: "The part is turned over about X, so every Y on the model is on the other side of the machine.",
  },
];

const ctx = (origins: PostContext["origins"] = ORIGINS): PostContext => ({
  programNumber: "1001", programName: "TEST", machine, workOffset: "G54", units: "IN",
  toolTable: [
    { toolNumber: 1, description: "face mill", lengthOffset: 1, diameterOffset: 1, diameter: 2 },
    { toolNumber: 2, description: "end mill", lengthOffset: 2, diameterOffset: 2, diameter: 0.5 },
  ],
  safeZ: 1, partName: "test", revision: "A", generatedAtIso: "2026-09-04T00:00:00Z",
  origins,
});

const cut = (setupId: string, toolNumber: number, x = 1): Toolpath =>
  ({
    operationId: `op-${setupId}-${toolNumber}`,
    setupId,
    type: "FACE",
    toolId: `t${toolNumber}`,
    toolNumber,
    parameters: { rpm: 3000, feed: 20, plungeFeed: 8, coolant: "FLOOD" },
    cycleTimeMinutes: 1,
    materialRemoved: 0,
    cuttingDistance: 1,
    warnings: [],
    isPlaceholder: false,
    moves: [
      { type: "RAPID", x, y: 0, z: 1, feed: null },
      { type: "CUT", x: x + 1, y: 0, z: -0.1, feed: 20 },
    ],
  }) as unknown as Toolpath;

const emit = (id: string, tps: Toolpath[], c: PostContext = ctx()) => getPost(id)!.emit(tps, c);

/* ---------------- The stop ---------------- */

test("the part coming out of the vise is a hard stop, not a blank line", () => {
  const code = emit("haas-ngc-dev", [cut("s1", 1), cut("s2", 2)]);
  assert.match(code, /^M0$/m, "nothing stops the control between the two setups");
  // M0 and not M1: an optional stop is skipped by a control with optional-stop
  // off, which is a setting, and a part coming out of the vise is not.
  assert.equal(/^M1$/m.test(code), false, "the setup change is an optional stop");
});

test("the stop names the setup and says what has to happen", () => {
  const code = emit("haas-ngc-dev", [cut("s1", 1), cut("s2", 2)]);
  assert.match(code, /SETUP 2 - Flip, thickness and profile - THE PART COMES OUT OF THE VISE HERE/);
  assert.match(code, /RE-CLAMP AS THE SETUP SHEET SHOWS, THEN SET G55/);
  // The frame's own sentence, including the turnover warning. An operator who
  // picks up an edge under the wrong reading cuts a mirrored part.
  assert.match(code, /turned over about X/);
  assert.match(code, /CHECK IT BEFORE CYCLE START/);
});

test("the first setup gets no stop, because the operator just clamped the part", () => {
  // A stop asking somebody to do what they have this second done is a stop
  // they learn to cycle-start through, and the next one is the real one.
  const one = emit("haas-ngc-dev", [cut("s1", 1), cut("s1", 2)]);
  assert.equal(/^M0$/m.test(one), false, "a single-setup program stops for nothing");
  assert.equal(/COMES OUT OF THE VISE/.test(one), false);
});

test("the part is retracted and the table is out before the stop", () => {
  // A stop that leaves the tool over the part and the table at the back is a
  // stop somebody reaches past.
  const code = emit("haas-ngc-dev", [cut("s1", 1), cut("s2", 2)]);
  const lines = code.split("\n");
  const stop = lines.findIndex((l) => l === "M0");
  const before = lines.slice(Math.max(0, stop - 3), stop);
  assert.ok(before.includes("G53 G0 Z0."), "the tool is still down at the stop");
  assert.ok(before.includes("G53 G0 Y0."), "the table is still back at the stop");
});

test("the stop comes before the operation heading, not inside a tool's block", () => {
  /*
   * An operator single-blocking meets the heading first. A stop underneath one
   * reads as belonging to that cut rather than to the setup change.
   */
  const code = emit("haas-ngc-dev", [cut("s1", 1), cut("s2", 2)]);
  const lines = code.split("\n");
  const stop = lines.findIndex((l) => l === "M0");
  const nextHeading = lines.findIndex((l, i) => i > stop && /^\(FACE - T2/.test(l));
  assert.ok(nextHeading > stop, "the setup stop is buried inside the next operation's block");
});

test("the tool is called again after a setup change even if it is the same cutter", () => {
  // The operator has been at the machine. A program that assumes the spindle
  // came back holding what it held is a program that assumes nobody touched it.
  const code = emit("haas-ngc-dev", [cut("s1", 1), cut("s2", 1)]);
  assert.equal((code.match(/^T1 M6$/gm) ?? []).length, 2, "the tool is not re-called after the flip");
});

/* ---------------- The offsets ---------------- */

test("each setup's motion runs under that setup's own work offset", () => {
  const code = emit("haas-ngc-dev", [cut("s1", 1), cut("s2", 2)]);
  assert.match(code, /^G54 G0 /m, "setup 1 does not run under G54");
  assert.match(code, /^G55 G0 /m, "setup 2 does not run under G55");
});

test("a setup with no frame recorded falls back rather than borrowing the other one's", () => {
  /*
   * Borrowing G55 for motion nobody placed would be a second operation cut in
   * a coordinate system nothing recorded — the exact failure, arrived at from
   * the other direction.
   */
  const code = emit("haas-ngc-dev", [cut("s1", 1), cut("s3", 2)], ctx([ORIGINS[0]]));
  assert.match(code, /^G54 G0 /m);
  assert.equal(/^G55 G0 /m.test(code), false, "an unplaced setup borrowed another setup's offset");
  assert.match(code, /NO COORDINATE FRAME IS RECORDED FOR THIS SETUP. DO NOT RUN UNTIL IT IS/);
});

test("the header says the program contains more than one setup", () => {
  // A machinist loading one program has no other way to know it holds two
  // operations until they meet the M0 halfway down it.
  const code = emit("haas-ngc-dev", [cut("s1", 1), cut("s2", 2)]);
  assert.match(code, /THIS PROGRAM CONTAINS 2 SETUPS/);
  assert.match(code, /G54 SETUP 1[\s\S]*G55 SETUP 2/);
  // And a one-setup program does not announce a boundary it does not have.
  assert.equal(/CONTAINS 1 SETUPS/.test(emit("haas-ngc-dev", [cut("s1", 1)], ctx([ORIGINS[0]]))), false);
});

/* ---------------- A program never goes back ---------------- */

test("a setup entered twice is refused rather than described", () => {
  /*
   * Motion that is individually correct and collectively a part clamped four
   * times to make two cuts. A re-entered setup means the ordering upstream is
   * wrong, not that the program should ask for the flip twice.
   */
  assert.throws(
    () => emit("haas-ngc-dev", [cut("s1", 1), cut("s2", 2), cut("s1", 1)]),
    /entered twice in one program/,
    "the post described a program that flips the part back",
  );
});

/* ---------------- Every control answers for itself ---------------- */

test("GRBL stops too, and says the offset is the operator's to re-zero", () => {
  // GRBL runs everything this post writes under G54 — there is no offset the
  // program can switch to. Emitting a G55 it will not honour would be worse
  // than saying so.
  const code = emit("grbl-dev", [cut("s1", 1), cut("s2", 2)]);
  assert.match(code, /^M0$/m);
  // Hyphen: comment text is sanitised to the ASCII a control reads.
  assert.match(code, /RUNS EVERYTHING UNDER G54 - RE-ZERO G54/);
  assert.equal(/^G55/m.test(code), false, "GRBL was handed an offset it does not use");
});

test("Siemens stops and selects the new frame itself", () => {
  const code = emit("siemens-840d-dev", [cut("s1", 1), cut("s2", 2)]);
  assert.match(code, /^M0$/m);
  assert.match(code, /RE-CLAMP AS THE SETUP SHEET SHOWS, THEN SET G55/);
  assert.match(code, /^G55$/m, "840D was not switched to the setup's frame");
});

test("Heidenhain stops as a numbered block and says it emits no datum shift", () => {
  // Comments are not numbered blocks on a TNC. The stop is, and a stop that is
  // not a block is a stop the control skips.
  const code = emit("heidenhain-dev", [cut("s1", 1), cut("s2", 2)]);
  assert.match(code, /^\d+ STOP M0$/m, "the TNC stop is not a numbered block");
  assert.match(code, /EMITS NO DATUM SHIFT/);
});

/* ---------------- What made it possible ---------------- */

test("a toolpath knows which setup it belongs to", () => {
  // Dropped on the way out of the engine, which is why the post had no
  // information to do anything else even if it had wanted to.
  const src = strip(readFileSync("src/lib/engines/cam/types.ts", "utf8"));
  assert.ok(/export interface Toolpath \{[\s\S]*?\n  setupId: string;/.test(src), "Toolpath dropped the setup again");
  const eng = strip(readFileSync("src/lib/engines/cam/engine.ts", "utf8"));
  assert.equal(
    (eng.match(/setupId: req\.setupId,/g) ?? []).length,
    2,
    "a toolpath constructor exists that does not carry the setup",
  );
});

test("the work offset is not a dropdown any more", () => {
  /*
   * A fourth source of truth for something the setups record. Picking it wrong
   * silently overrode them: the program ran under whatever was chosen while
   * the header printed the setups' own offsets.
   */
  const src = strip(readFileSync("src/app/(app)/parts/[id]/nc/page.tsx", "utf8"));
  assert.equal(/select name="workOffset"/.test(src), false, "the work offset is still a choice on the form");
  assert.equal(/formData\.get\("workOffset"\)/.test(src), false, "the form's work offset is still read");
  assert.ok(/fresh\.setups\.find\(\(s\) => fresh\.framesBySetup\[s\.id\]\)\?\.workOffset/.test(src));
  // And the post is handed the setup ids, which is what the whole thing rests on.
  assert.ok(/setupId: s\.id,/.test(src), "the post is not told which setup each origin is");
});
