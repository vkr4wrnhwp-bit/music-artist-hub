import { test } from "node:test";
import assert from "node:assert/strict";
import { HeightField, StockRemovalSimulator, buildTimeline, type SimOperation } from "@/lib/sim/stock-removal";
import type { Move } from "@/lib/engines/cam/types";

/**
 * The stock-removal simulator is geometry, and geometry is checkable: known
 * cuts must remove known volumes, scrubbing must be bit-identical to playing
 * forward, and the collision pass must find the crashes planted in the data.
 */

const stock = { x: 4, y: 3, z: 1 };

const mv = (x: number, y: number, z: number, feed: number | null): Move => ({ type: feed === null ? "RAPID" : "CUT", x, y, z, feed });

const op = (moves: Move[], over: Partial<SimOperation> = {}): SimOperation => ({
  operationId: "op", label: "test op", toolNumber: 1, toolDiameter: 0.5, fluteLength: 1.25, rpm: 5000,
  moves, ...over,
});

test("a full-width facing pass removes area × depth", () => {
  // Sweep a 0.5" tool across the full stock at z = -0.1 in stripes.
  const moves: Move[] = [mv(-2.5, -1.5 + 0.25, 0.5, null)];
  for (let y = -1.5 + 0.25; y <= 1.5 - 0.25 + 1e-9; y += 0.2) {
    moves.push(mv(-2.5, y, -0.1, 20), mv(2.5, y, -0.1, 20), mv(2.5, y + 0.2, -0.1, 20), mv(-2.5, y + 0.2, -0.1, 20));
  }
  const sim = new StockRemovalSimulator(stock, [op(moves)], 600, 200);
  sim.seek(sim.totalTime);
  const expected = stock.x * stock.y * 0.1;
  const err = Math.abs(sim.field.removedVolume - expected) / expected;
  assert.ok(err < 0.05, `facing volume off by ${(err * 100).toFixed(1)}%`);
});

test("a plunge leaves a hole of the tool's area × depth", () => {
  const moves: Move[] = [mv(0, 0, 0.5, null), mv(0, 0, -0.4, 5), mv(0, 0, 0.5, null)];
  const sim = new StockRemovalSimulator(stock, [op(moves, { toolDiameter: 0.5 })], 600, 400);
  sim.seek(sim.totalTime);
  const expected = Math.PI * 0.25 ** 2 * 0.4;
  const err = Math.abs(sim.field.removedVolume - expected) / expected;
  assert.ok(err < 0.05, `hole volume off by ${(err * 100).toFixed(1)}%`);
  assert.ok(Math.abs(sim.field.heightAt(0, 0) - 0.6) < 1e-6, "floor height wrong");
  assert.equal(sim.field.heightAt(1.5, 1), 1, "untouched stock must stay at full height");
});

test("seek backward then forward reproduces the forward-only state exactly", () => {
  const moves: Move[] = [mv(-1, 0, 0.2, null), mv(-1, 0, -0.25, 10), mv(1, 0, -0.25, 15), mv(1, 0, 0.2, null)];
  const a = new StockRemovalSimulator(stock, [op(moves)], 600, 150);
  const b = new StockRemovalSimulator(stock, [op(moves)], 600, 150);
  const t = a.totalTime * 0.6;
  a.seek(t);
  b.seek(b.totalTime); // to the end…
  b.seek(t);           // …and back
  assert.equal(a.field.removedVolume, b.field.removedVolume);
  assert.deepEqual(Array.from(a.field.data), Array.from(b.field.data));
});

test("a rapid through standing material is flagged as a crash, once", () => {
  // Cut a shoulder, then rapid straight through the remaining material.
  const moves: Move[] = [
    mv(-1.5, 0, 0.2, null),
    mv(-1.5, 0, -0.2, 10), mv(0, 0, -0.2, 20),         // pocket to x=0
    mv(0, 0, 0.2, null),
    mv(0, 0, -0.9, 5),                                  // deep plunge at x=0
    mv(1.9, 0, -0.9, null),                             // RAPID through the un-cut wall
  ];
  const sim = new StockRemovalSimulator(stock, [op(moves)], 600, 150);
  const crashes = sim.collisions.filter((c) => c.kind === "RAPID_INTO_STOCK");
  assert.equal(crashes.length, 1);
  assert.match(crashes[0].detail, /Rapid/);
});

test("cutting deeper than the flute length flags holder contact", () => {
  const moves: Move[] = [mv(0, 0, 0.2, null), mv(0, 0, -0.9, 5)];
  const sim = new StockRemovalSimulator(stock, [op(moves, { fluteLength: 0.5 })], 600, 150);
  assert.ok(sim.collisions.some((c) => c.kind === "HOLDER_CONTACT"));
  // Same cut with enough flute is clean.
  const ok = new StockRemovalSimulator(stock, [op(moves, { fluteLength: 1.2 })], 600, 150);
  assert.equal(ok.collisions.filter((c) => c.kind === "HOLDER_CONTACT").length, 0);
});

test("timeline times derive from distance over feed, rapids from the rapid rate", () => {
  const ops = [op([mv(0, 0, 1, null), mv(0, 0, 0, 10), mv(2, 0, 0, 20)])];
  const tl = buildTimeline(ops, 600);
  assert.equal(tl.segments.length, 2);
  assert.ok(Math.abs(tl.segments[0].t1 - tl.segments[0].t0 - 1 / 10) < 1e-9);
  assert.ok(Math.abs(tl.segments[1].t1 - tl.segments[1].t0 - 2 / 20) < 1e-9);
});

test("height field never cuts below the machine table", () => {
  const hf = new HeightField(stock, 100);
  hf.cut(0, 0, -0.5, 0.25); // tip below z=0 clamps at 0
  assert.equal(hf.heightAt(0, 0), 0);
});
