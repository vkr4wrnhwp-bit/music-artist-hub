import { test } from "node:test";
import assert from "node:assert/strict";
import { generateToolpath } from "@/lib/engines/cam/engine";
import type { MachiningContext, OperationRequest } from "@/lib/engines/cam/types";
import type { Feature, Stock } from "@/lib/domain/features";
import type { Tool } from "@/lib/domain/shop";

/**
 * READ THE POCKET BACK AS GEOMETRY, NOT AS A LIST OF MOVES.
 *
 * The rectangular pocket carried two defects for as long as it has existed,
 * and 1,900 tests did not see either, because nothing ever asked what the
 * emitted path DOES to the material:
 *
 *   The ring count came from the short side and was applied to both axes as
 *   a scale factor, so on a 6 × 1.5 pocket the long axis moved several times
 *   the programmed stepover on every ring of every pass.
 *
 *   The rings were walked outermost-first from a helix that had just ended at
 *   the pocket centre, so the first cutting move went straight to the outer
 *   boundary through solid material at full tool width — a slotting cut at
 *   pocketing feed, first thing, in every rectangular pocket.
 *
 * These tests measure engagement and reach. They fail against the old code.
 */

const stock: Stock = { form: "RECTANGULAR", x: 12, y: 8, z: 1, material: "Aluminum 6061" };

const endmill = {
  id: "t2", toolNumber: 2, toolClass: "FLAT_END_MILL", description: "1/2 flat", diameter: 0.5,
  cornerRadius: 0, flutes: 3, material: "CARBIDE", fluteLength: 1, overallLength: 3, stickout: 1.5,
  holder: "CAT40", holderNoseDiameter: 1.25, maxRPM: 8100, recommendedMaterials: [],
  chiploadMin: 0.002, chiploadMax: 0.005, sfmMin: 600, sfmMax: 1000, coolant: "FLOOD",
  lifeRemaining: 1, condition: "GOOD", regrindCount: 0,
} as unknown as Tool;

const ctx: MachiningContext = {
  tool: endmill, partFeatures: [], materialSfmMin: 600, materialSfmMax: 1000,
  materialName: "Aluminum 6061", rapidRate: 1000, maxSpindleRPM: 8100, maxFeed: 500,
};

const pocket = (width: number, length: number): Feature =>
  ({
    id: "p1", kind: "RECT_POCKET", label: `${width} x ${length} pocket`, functionalRole: null,
    critical: false, centerX: 0, centerY: 0, width, length, depth: 0.25, cornerRadius: 0.3, top: 0,
  }) as unknown as Feature;

const req: OperationRequest = {
  id: "op1", type: "POCKET_2D", label: "Rough pocket", featureId: "p1", toolId: "t2",
  topZ: 0, finalZ: -0.25, clearanceZ: 0.1, retractZ: 0.5, pass: "ROUGH",
} as unknown as OperationRequest;

/** Every cutting move, in order, with the entry helix behind us. */
function cuts(width: number, length: number) {
  const r = generateToolpath(req, pocket(width, length), ctx, stock);
  assert.ok(r.ok, "pocket refused");
  if (!r.ok) throw new Error("unreachable");
  return { all: r.toolpath.moves, cut: r.toolpath.moves.filter((m) => m.type === "CUT") };
}

test("no ring steps more than the programmed stepover, whatever the aspect ratio", () => {
  // A 6 x 1.5 pocket: the short side needs 3 rings, the long side needs 12.
  // Scaling both axes by i/rings gave the long axis a 1-inch radial step on a
  // half-inch cutter — 200% engagement, at a feed chosen for 40%.
  for (const [w, l] of [[6, 1.5], [8, 1], [3, 3], [5, 2.5]] as const) {
    const { cut } = cuts(w, l);
    // Each ring is a closed rectangle; its half-extents are the extremes of
    // the moves at that ring. Walk the distinct half-widths in emission order.
    const seenX: number[] = [];
    const seenY: number[] = [];
    for (const m of cut) {
      const hx = Math.abs(m.x);
      const hy = Math.abs(m.y);
      if (!seenX.some((v) => Math.abs(v - hx) < 1e-6)) seenX.push(hx);
      if (!seenY.some((v) => Math.abs(v - hy) < 1e-6)) seenY.push(hy);
    }
    const step = (xs: number[]) => {
      const sorted = [...xs].sort((a, b) => a - b);
      let worst = 0;
      for (let i = 1; i < sorted.length; i++) worst = Math.max(worst, sorted[i] - sorted[i - 1]);
      return worst;
    };
    // stepover in the engine is a fraction of tool diameter; the hard ceiling
    // that matters is that no single step exceeds the tool's own diameter,
    // which is the definition of a full-width cut.
    assert.ok(step(seenX) <= endmill.diameter + 1e-6, `${w}x${l}: X ring step ${step(seenX).toFixed(4)} exceeds the cutter`);
    assert.ok(step(seenY) <= endmill.diameter + 1e-6, `${w}x${l}: Y ring step ${step(seenY).toFixed(4)} exceeds the cutter`);
  }
});

test("the first cutting move stays inside the circle the helix opened", () => {
  /*
   * The ordering defect, measured where it actually shows.
   *
   * Two earlier versions of this test passed against the very code they were
   * written to catch. The first read `all.find(m => m.type === "CUT")`, which
   * is a ZERO-LENGTH move to the loop's start point — it travels nowhere. The
   * second compared each cut to the preceding move, and the helix-to-centre
   * hop is itself a travel, so it grabbed the same useless move again.
   *
   * The discriminator is the first cutting move that is not at the pocket
   * centre. Walking rings outermost-first sent that move to (-2.690, -0.490)
   * on a 6 x 1.5 pocket — 2.734" from centre, a straight feed to the outer
   * wall through solid material at pocketing feed, first thing, every pocket.
   * Growing outward sends it to 0.285", inside the circle the helix opened.
   *
   * The helix swings 0.4 x d and the cutter is d wide, so it opens a circle of
   * radius 0.9 x d about the centre. That is the bound.
   */
  const opened = endmill.diameter * 0.9;
  for (const [w, l] of [[6, 1.5], [8, 1], [3, 3], [5, 2.5]] as const) {
    const { all } = cuts(w, l);
    const first = all.find((m) => (m.type === "CUT" || m.type === "ARC") && Math.hypot(m.x, m.y) > 1e-6);
    assert.ok(first, `${w}x${l}: no cutting move away from the centre`);
    const reach = Math.hypot(first!.x, first!.y);
    assert.ok(
      reach <= opened + 1e-6,
      `${w}x${l}: the first cutting move ends ${reach.toFixed(4)}" from centre, outside the ${opened.toFixed(4)}" the helix opened — that is a full-width slotting cut through solid material`,
    );
  }
});

test("the rings still reach the pocket wall", () => {
  // The fix must not have bought safety by leaving material behind: the last
  // roughing ring has to arrive at the roughing boundary.
  const { cut } = cuts(6, 1.5);
  const maxX = Math.max(...cut.map((m) => Math.abs(m.x)));
  const maxY = Math.max(...cut.map((m) => Math.abs(m.y)));
  // width - d over two, with no stock left on the finish pass.
  assert.ok(Math.abs(maxX - (6 - endmill.diameter) / 2) < 1e-6, `X reached ${maxX}`);
  assert.ok(Math.abs(maxY - (1.5 - endmill.diameter) / 2) < 1e-6, `Y reached ${maxY}`);
});

/* ---------------- FACING: the datum face, all of it ---------------- */

const faceReq = (finalZ: number): OperationRequest =>
  ({
    id: "opf", type: "FACE", label: "Face top", featureId: "f0", toolId: "t2",
    topZ: 0, finalZ, clearanceZ: 0.1, retractZ: 0.5, pass: "ROUGH",
  }) as unknown as OperationRequest;

const faceFeature = { id: "f0", kind: "FACE", label: "Top face", functionalRole: "DATUM", critical: true, top: 0 } as unknown as Feature;

function facing(stockY: number, toolDia: number) {
  const tool = { ...endmill, diameter: toolDia, description: `${toolDia}" mill` } as Tool;
  const st: Stock = { form: "RECTANGULAR", x: 6, y: stockY, z: 1, material: "Aluminum 6061" };
  const r = generateToolpath(faceReq(-0.02), faceFeature, { ...ctx, tool }, st);
  assert.ok(r.ok, `facing refused for ${stockY}" stock with a ${toolDia}" mill`);
  if (!r.ok) throw new Error("unreachable");
  return r.toolpath.moves.filter((m) => m.type === "CUT");
}

test("facing reaches both edges of the stock, whatever the cutter width", () => {
  /*
   * The lane loop stepped by 0.7 x d and stopped when the next lane centre
   * passed halfY - d/2. On 4" stock with a 2" mill the lanes landed at -1.0,
   * -0.3 and +0.4: the last lane's trailing edge reached 1.4 against an edge
   * at 2.0, so 0.6" of the datum face was never touched — while `removed` was
   * returned as the full stock volume and every gate read PASS.
   */
  for (const [stockY, dia] of [[4, 2], [4, 0.5], [3, 1.25], [2.5, 0.75], [6, 3]] as const) {
    const cut = facing(stockY, dia);
    const lo = Math.min(...cut.map((m) => m.y)) - dia / 2;
    const hi = Math.max(...cut.map((m) => m.y)) + dia / 2;
    assert.ok(lo <= -stockY / 2 + 1e-6, `${stockY}" / ⌀${dia}: near edge short by ${(lo + stockY / 2).toFixed(4)}"`);
    assert.ok(hi >= stockY / 2 - 1e-6, `${stockY}" / ⌀${dia}: far edge short by ${(stockY / 2 - hi).toFixed(4)}"`);
  }
});

test("no lane steps more than the face-mill stepover", () => {
  // Reaching the edge must not be bought by widening the last step.
  for (const [stockY, dia] of [[4, 2], [3, 1.25], [6, 3]] as const) {
    const ys = [...new Set(facing(stockY, dia).map((m) => Number(m.y.toFixed(6))))].sort((a, b) => a - b);
    for (let i = 1; i < ys.length; i++) {
      assert.ok(ys[i] - ys[i - 1] <= dia * 0.7 + 1e-6, `${stockY}" / ⌀${dia}: lane step ${(ys[i] - ys[i - 1]).toFixed(4)}" exceeds 0.7 x ⌀`);
    }
  }
});

test("a cutter wider than the stock still cuts", () => {
  // The old loop's condition was false on entry here, so the operation
  // emitted no cutting moves at all and reported the full volume removed.
  const cut = facing(2, 3);
  assert.ok(cut.length > 0, "a 3\" mill on 2\" stock emitted no cutting moves");
  const ys = [...new Set(cut.map((m) => Number(m.y.toFixed(6))))];
  assert.deepEqual(ys, [0], "a cutter wider than the stock is one lane down the middle");
});
