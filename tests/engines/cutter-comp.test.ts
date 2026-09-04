import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { generateToolpath } from "@/lib/engines/cam/engine";
import { getPost } from "@/lib/engines/cam/post";
import { reconcilePostedProgram } from "@/lib/nc/reconcile";
import { isArc } from "@/lib/engines/cam/arc";
import type { MachiningContext, Move, OperationRequest } from "@/lib/engines/cam/types";
import type { Feature, Stock } from "@/lib/domain/features";
import type { MachineProfile, Tool } from "@/lib/domain/shop";

/**
 * CUTTER COMPENSATION
 *
 * The offset used to be baked into the path and no G41/G42/D ever reached the
 * control, which takes away the machinist's only recourse for holding size. A
 * cutter a thou and a half under, a regrind, spring on a deep wall — the answer
 * to all of them is to nudge the D offset and re-run the finish pass.
 *
 * The dangerous thing about the fix is that there are now TWO paths: the
 * program carries the boundary and the move list carries the cutter centre.
 * Conflating them puts the simulator half a tool width from the truth, and
 * putting a comp code on the wrong block is a fault at best and a gouge at
 * worst. That is what these pin.
 */

const stock: Stock = { form: "RECTANGULAR", x: 8, y: 6, z: 1, material: "Aluminum 6061" };

const endmill = {
  id: "t2", toolNumber: 2, toolClass: "FLAT_END_MILL", description: "1/2 3FL", diameter: 0.5,
  cornerRadius: 0, flutes: 3, material: "CARBIDE", fluteLength: 1, overallLength: 3, stickout: 1.5,
  holder: "CAT40 ER32", holderNoseDiameter: 1.5, maxRPM: 8100, recommendedMaterials: [],
  chiploadMin: 0.001, chiploadMax: 0.004, sfmMin: 400, sfmMax: 1000, coolant: "FLOOD", lifeRemaining: 1,
  condition: "GOOD", regrindCount: 0,
} as unknown as Tool;

const ctx: MachiningContext = {
  tool: endmill, materialSfmMin: 600, materialSfmMax: 1000, materialName: "Aluminum 6061",
  rapidRate: 1000, maxSpindleRPM: 8100, maxFeed: 500,
};

const R = 0.25; // tool radius
const CONTOUR = { width: 5, length: 3, cornerRadius: 0.375 };
const contour = {
  id: "f1", kind: "OUTSIDE_CONTOUR", label: "Outside profile", functionalRole: "NONE", critical: false,
  ...CONTOUR, depth: 0.5,
} as unknown as Feature;

const req: OperationRequest = {
  id: "op", type: "CONTOUR_2D", label: "Finish outside profile", featureId: "f1", toolId: "t2", setupId: "s",
  topZ: 0, finalZ: -0.2, clearanceZ: 0.1, retractZ: 1,
};

const path = (): Move[] => {
  const r = generateToolpath(req, contour, ctx, stock);
  assert.ok(r.ok, "the contour did not generate");
  if (!r.ok) throw new Error("unreachable");
  return r.toolpath.moves;
};

/* ---------------- Two paths, and they mean different things ---------------- */

/**
 * Moves where compensation is fully ON — the steady state.
 *
 * The activating and cancelling moves are transitions: over them the cutter
 * centre ramps between the programmed point and the offset one, which is what
 * the control itself does. Their geometry is deliberately different from the
 * contour's and is checked separately.
 */
const compensated = (moves: Move[]) =>
  moves.filter((m) => m.program && m.feed !== null && !m.program.activate && !m.program.deactivate);

test("the program carries the part boundary and the moves carry the cutter centre", () => {
  const cutting = compensated(path());
  assert.ok(cutting.length > 4, "no compensated moves were produced");
  for (const m of cutting) {
    const off = Math.hypot(m.x - m.program!.x, m.y - m.program!.y);
    // Every compensated point sits exactly one tool radius off the boundary.
    // Anything else means the two paths were built from different geometry.
    assert.ok(Math.abs(off - R) < 1e-9, `centre is ${off.toFixed(4)} from the boundary, expected ${R}`);
  }
});

test("the boundary in the program is the feature, not the feature plus a tool", () => {
  // The bug this replaces: the program carried width + diameter, so a machinist
  // reading it saw a part 0.5" bigger than the drawing.
  const xs = path().filter((m) => m.program).map((m) => m.program!.x);
  assert.ok(Math.abs(Math.max(...xs) - CONTOUR.width / 2) < 1e-9, `boundary max X ${Math.max(...xs)}`);
});

test("the cutter centre still stands one radius outside the part", () => {
  const outer = Math.max(...path().filter((m) => m.feed !== null).map((m) => m.x));
  assert.ok(Math.abs(outer - (CONTOUR.width / 2 + R)) < 1e-9, `cutter reaches X${outer}`);
});

/* ---------------- The comp rules ---------------- */

test("compensation comes on over a straight move, never an arc", () => {
  const moves = path();
  const on = moves.filter((m) => m.program?.activate);
  assert.equal(on.length > 0, true, "compensation is never activated");
  for (const m of on) {
    assert.equal(isArc(m), false, "compensation activated on an arc — controls fault or ramp it through the cut");
  }
});

test("the activating move is at least a tool radius long, in free air", () => {
  const moves = path();
  const idx = moves.findIndex((m) => m.program?.activate);
  const prev = moves[idx - 1];
  const m = moves[idx];
  const length = Math.hypot(m.program!.x - prev.x, m.program!.y - prev.y);
  assert.ok(length >= R, `lead-in is ${length.toFixed(3)}" for a ${R}" radius`);
  // And it approaches from outside the part, so the ramp-on happens in air.
  assert.ok(prev.x < -CONTOUR.width / 2, `the lead-in starts at X${prev.x}, not clear of the part`);
});

test("compensation is cancelled on a move away from the part", () => {
  const moves = path();
  const off = moves.filter((m) => m.program?.deactivate);
  assert.ok(off.length > 0, "compensation is never cancelled");
  for (const m of off) {
    assert.equal(isArc(m), false, "compensation cancelled on an arc");
    // Away from the part in Y, not back along the wall just cut.
    assert.ok(m.program!.y < -CONTOUR.length / 2, `lead-out ends at Y${m.program!.y}, still on the part`);
  }
});

test("every pass that opens compensation closes it", () => {
  const moves = path();
  assert.equal(
    moves.filter((m) => m.program?.activate).length,
    moves.filter((m) => m.program?.deactivate).length,
    "a pass leaves compensation active",
  );
});

test("the side is G42 — the cutter runs outside a counter-clockwise profile", () => {
  // Travel at the bottom edge is +X with the part at +Y, so the cutter is to
  // the right of the path. G41 there drives the tool straight through the part.
  for (const m of path().filter((m) => m.program)) assert.equal(m.program!.side, "RIGHT");
});

/* ---------------- The gouge this rework also fixed ---------------- */

test("no cutting move cuts a diagonal across a corner", () => {
  /*
   * The lead-in used to land on the LEFT edge while the contour started on the
   * BOTTOM edge, so the first cutting move was a straight chord across the
   * bottom-left corner — 0.293 × the corner radius into the part, nearly a
   * tenth of an inch on an ordinary profile.
   *
   * On a rounded rectangle every cut is either axis-parallel or an arc. A
   * diagonal is the signature of a corner being cut off.
   */
  // Checked on the PROGRAMMED path, because that is what defines the shape,
  // and only where compensation is steady — the lead moves ramp diagonally by
  // design, which is what the control does when it brings the offset on.
  const moves = path();
  for (let i = 1; i < moves.length; i++) {
    const a = moves[i - 1];
    const b = moves[i];
    if (b.feed === null || !b.program || isArc(b)) continue;
    if (b.program.activate || b.program.deactivate) continue;
    const ax = a.program?.x ?? a.x;
    const ay = a.program?.y ?? a.y;
    const dx = Math.abs(b.program.x - ax);
    const dy = Math.abs(b.program.y - ay);
    assert.ok(
      dx < 1e-9 || dy < 1e-9,
      `a cutting move runs diagonally from (${ax.toFixed(3)}, ${ay.toFixed(3)}) to (${b.program.x.toFixed(3)}, ${b.program.y.toFixed(3)})`,
    );
  }
});

test("the contour has no zero-length blocks", () => {
  // Legal, and four wasted blocks a pass that a machinist single-blocking
  // through has to step past.
  const moves = path();
  for (let i = 1; i < moves.length; i++) {
    const a = moves[i - 1];
    const b = moves[i];
    if (b.feed === null) continue;
    assert.ok(
      Math.hypot(b.x - a.x, b.y - a.y, b.z - a.z) > 1e-9 || isArc(b),
      `zero-length cutting block at index ${i}`,
    );
  }
});

/* ---------------- What reaches the control ---------------- */

const machine = {
  manufacturer: "Haas", model: "VF-2", controller: "HAAS_NGC", travelsX: 30, travelsY: 16, travelsZ: 20,
  maxSpindleRPM: 8100, maxFeed: 500, maxRapid: 1000,
} as unknown as MachineProfile;

const postCtx = {
  programNumber: "1001", programName: "TEST", machine, workOffset: "G54", units: "IN" as const,
  toolTable: [{ toolNumber: 2, description: "1/2 3FL", lengthOffset: 2, diameter: 0.5 }],
  safeZ: 1, partName: "test", revision: "A", generatedAtIso: "2026-09-04T00:00:00Z",
};

const emit = (postId: string) => {
  const r = generateToolpath(req, contour, ctx, stock);
  assert.ok(r.ok);
  if (!r.ok) throw new Error("unreachable");
  return { code: getPost(postId)!.emit([r.toolpath], postCtx), toolpath: r.toolpath };
};

test("the Haas post emits G42 with a D register and cancels with G40", () => {
  const { code } = emit("haas-ngc-dev");
  assert.match(code, /G42 D2 G1 X-?\d+\.\d+ Y-?\d+\.\d+/, "no compensated lead-in");
  assert.match(code, /G40 G1 X-?\d+\.\d+/, "compensation is never cancelled");
  // On the boundary, not on the boundary plus a tool.
  assert.ok(code.includes("X2.5000"), "the program does not carry the part boundary");
  assert.equal(code.includes("X2.7500"), false, "the program carries the cutter centre while comp is on");
});

test("a program never ends a tool with compensation still open", () => {
  const { code } = emit("haas-ngc-dev");
  const g42 = (code.match(/\bG4[12]\b/g) ?? []).length;
  const g40 = (code.match(/\bG40\b/g) ?? []).length;
  // The safe-start line carries a G40 of its own, so cancels always exceed.
  assert.ok(g40 > g42, `${g42} activations against ${g40} cancels`);
});

test("GRBL emits the cutter centre and says size is not adjustable", () => {
  // GRBL has no offset table to hold a D value. Correct motion with no
  // adjustment available is the honest trade — and the machinist has to be
  // told, because reaching for an offset that does not exist is the failure.
  const { code } = emit("grbl-dev");
  assert.equal(/\bG4[12]\b/.test(code), false, "GRBL was handed a comp code");
  assert.match(code, /NO CUTTER COMPENSATION ON GRBL/);
  assert.ok(code.includes("X2.7500"), "GRBL did not get the cutter centre");
});

test("the reconciler compares against the programmed path, not the cutter centre", () => {
  // Comparing a compensated contour against the cutter centre would report it
  // as exactly one tool radius wrong — a false alarm on the one operation a
  // machinist most needs to trust.
  const { code, toolpath } = emit("haas-ngc-dev");
  const r = reconcilePostedProgram(code, [toolpath]);
  assert.equal(r.verified, true, r.detail);

  const src = readFileSync("src/lib/nc/reconcile.ts", "utf8");
  assert.ok(/flattenArcs\(programmedPath\(tp\.moves\)/.test(src), "the reconciler flattens the cutter centre");
});
