import { test } from "node:test";
import assert from "node:assert/strict";
import {
  proposeSequence,
  countToolChanges,
  precedenceEdges,
  type SequencedOperation,
} from "@/lib/engines/sequencing";

/**
 * The invariant that matters here is not "fewer tool changes" — it is that a
 * proposal never reorders something that must not move. A sequencer that
 * taps a hole nobody drilled, or finishes before roughing, is worse than no
 * sequencer at all, and no amount of saved seconds buys that back.
 *
 * So the safety tests come first and the optimisation tests come second.
 */

let n = 0;
function op(partial: Partial<SequencedOperation> & { type: string; toolNumber: number | null }): SequencedOperation {
  n += 1;
  return {
    id: partial.id ?? `op${n}`,
    sequence: partial.sequence ?? n,
    type: partial.type,
    label: partial.label ?? partial.type,
    featureId: partial.featureId ?? null,
    featureLabel: partial.featureLabel ?? null,
    toolNumber: partial.toolNumber,
  };
}

const order = (ids: string[], ops: SequencedOperation[]) => ids.map((id) => ops.find((o) => o.id === id)!);
const posOf = (id: string, ids: string[]) => ids.indexOf(id);

/* ---------------- Safety ---------------- */

test("facing never moves after anything that cuts to its datum", () => {
  const ops = [
    op({ id: "pocket", sequence: 1, type: "POCKET_2D", toolNumber: 2, featureId: "f1" }),
    op({ id: "face", sequence: 2, type: "FACE", toolNumber: 1, featureId: "f0" }),
    op({ id: "drill", sequence: 3, type: "DRILL", toolNumber: 2, featureId: "f2" }),
  ];
  const p = proposeSequence(ops);
  assert.ok(
    posOf("face", p.proposedOrder) < posOf("pocket", p.proposedOrder),
    "facing must precede the pocket even though moving it would group T2",
  );
  assert.ok(posOf("face", p.proposedOrder) < posOf("drill", p.proposedOrder));
});

test("a hole is spotted, drilled and only then tapped", () => {
  const ops = [
    op({ id: "spot", sequence: 1, type: "DRILL", toolNumber: 5, featureId: "hole" }),
    op({ id: "drill", sequence: 2, type: "PECK_DRILL", toolNumber: 6, featureId: "hole" }),
    op({ id: "tap", sequence: 3, type: "TAP", toolNumber: 10, featureId: "hole" }),
    op({ id: "other", sequence: 4, type: "POCKET_2D", toolNumber: 5, featureId: "pocket" }),
  ];
  const p = proposeSequence(ops);
  const o = p.proposedOrder;
  assert.ok(posOf("spot", o) < posOf("drill", o), "spot before drill");
  assert.ok(posOf("drill", o) < posOf("tap", o), "drill before tap");
});

test("the outside profile stays last — the part is held by its stock", () => {
  const ops = [
    op({ id: "face", sequence: 1, type: "FACE", toolNumber: 1, featureId: "f0" }),
    op({ id: "contour", sequence: 2, type: "CONTOUR_2D", toolNumber: 2, featureId: "prof" }),
    op({ id: "pocket", sequence: 3, type: "POCKET_2D", toolNumber: 2, featureId: "pkt" }),
  ];
  const p = proposeSequence(ops);
  // Grouping T2 by pulling the pocket forward next to the contour is exactly
  // the tempting wrong answer: it would profile the part before pocketing it.
  assert.equal(p.proposedOrder[p.proposedOrder.length - 1], "contour");
});

test("an operation with no tool assigned is never moved", () => {
  const ops = [
    op({ id: "a", sequence: 1, type: "POCKET_2D", toolNumber: 3, featureId: "f1" }),
    op({ id: "untooled", sequence: 2, type: "POCKET_2D", toolNumber: null, featureId: "f2" }),
    op({ id: "c", sequence: 3, type: "POCKET_2D", toolNumber: 3, featureId: "f3" }),
  ];
  const p = proposeSequence(ops);
  assert.equal(p.proposedOrder[1], "untooled", "an operation CANVAS knows nothing about stays put");
});

test("no operation is ever dropped or duplicated by a proposal", () => {
  const ops = [
    op({ id: "a", sequence: 1, type: "FACE", toolNumber: 1, featureId: "f0" }),
    op({ id: "b", sequence: 2, type: "POCKET_2D", toolNumber: 2, featureId: "f1" }),
    op({ id: "c", sequence: 3, type: "DRILL", toolNumber: 3, featureId: "f2" }),
    op({ id: "d", sequence: 4, type: "POCKET_2D", toolNumber: 2, featureId: "f3" }),
  ];
  const p = proposeSequence(ops);
  assert.equal(p.proposedOrder.length, ops.length);
  assert.deepEqual([...p.proposedOrder].sort(), ops.map((o) => o.id).sort());
});

test("contradictory rules fall back to the planned order rather than losing work", () => {
  // Two facing operations each demand to precede the other. The engine must
  // not loop and must not drop either one.
  const ops = [
    op({ id: "f1", sequence: 1, type: "FACE", toolNumber: 1, featureId: "a" }),
    op({ id: "f2", sequence: 2, type: "FACE", toolNumber: 1, featureId: "b" }),
  ];
  const p = proposeSequence(ops);
  assert.deepEqual([...p.proposedOrder].sort(), ["f1", "f2"]);
});

/* ---------------- Honesty ---------------- */

test("when every operation uses a different tool it says so instead of shuffling", () => {
  const ops = [
    op({ id: "a", sequence: 1, type: "FACE", toolNumber: 1, featureId: "f0" }),
    op({ id: "b", sequence: 2, type: "POCKET_2D", toolNumber: 2, featureId: "f1" }),
    op({ id: "c", sequence: 3, type: "DRILL", toolNumber: 3, featureId: "f2" }),
  ];
  const p = proposeSequence(ops);
  assert.equal(p.saved, 0);
  assert.deepEqual(p.proposedOrder, p.currentOrder, "no churn when there is nothing to gain");
  assert.ok(p.reason && /different tool/i.test(p.reason), "it must say why, not just decline");
});

test("a proposal that saves nothing never claims a different order", () => {
  const ops = [
    op({ id: "a", sequence: 1, type: "POCKET_2D", toolNumber: 2, featureId: "f1" }),
    op({ id: "b", sequence: 2, type: "POCKET_2D", toolNumber: 2, featureId: "f2" }),
  ];
  const p = proposeSequence(ops);
  assert.equal(p.saved, 0);
  assert.deepEqual(p.proposedOrder, p.currentOrder);
  assert.ok(p.reason);
});

test("limitations are always carried, including that toolpaths are not regenerated", () => {
  const p = proposeSequence([op({ id: "a", sequence: 1, type: "FACE", toolNumber: 1 })]);
  assert.ok(p.limitations.length > 0);
  assert.ok(p.limitations.some((l) => /re-verified|regenerated/i.test(l)));
  assert.ok(p.limitations.some((l) => /deflection/i.test(l)), "it must admit what it cannot see");
});

test("every precedence edge carries a machinist-readable reason", () => {
  const ops = [
    op({ id: "face", sequence: 1, type: "FACE", toolNumber: 1, featureId: "f0" }),
    op({ id: "drill", sequence: 2, type: "DRILL", toolNumber: 2, featureId: "h" }),
    op({ id: "tap", sequence: 3, type: "TAP", toolNumber: 3, featureId: "h" }),
  ];
  for (const e of precedenceEdges(ops)) {
    assert.ok(e.rule && e.rule.length > 10, `edge ${e.beforeId}->${e.afterId} must explain itself`);
  }
});

/* ---------------- Optimisation ---------------- */

test("it groups a repeated tool when nothing forbids it", () => {
  // T2 is used twice with a T3 operation stranded between them, on three
  // independent features. Nothing pins the order, so the T2 pair should join.
  const ops = [
    op({ id: "face", sequence: 1, type: "FACE", toolNumber: 1, featureId: "f0" }),
    op({ id: "p1", sequence: 2, type: "POCKET_2D", toolNumber: 2, featureId: "f1" }),
    op({ id: "p2", sequence: 3, type: "POCKET_2D", toolNumber: 3, featureId: "f2" }),
    op({ id: "p3", sequence: 4, type: "POCKET_2D", toolNumber: 2, featureId: "f3" }),
  ];
  const p = proposeSequence(ops);
  assert.equal(p.currentToolChanges, 3, "T1→T2→T3→T2");
  assert.equal(p.proposedToolChanges, 2, "T1→T2→T3");
  assert.equal(p.saved, 1);
  assert.ok(posOf("p1", p.proposedOrder) + 1 === posOf("p3", p.proposedOrder), "the two T2 operations end up adjacent");
});

test("grouping never comes at the cost of a precedence rule", () => {
  // The same shape, but the stranded operation is a drill on the SAME feature
  // as the second T2 pocket, so the pocket cannot jump ahead of it.
  const ops = [
    op({ id: "face", sequence: 1, type: "FACE", toolNumber: 1, featureId: "f0" }),
    op({ id: "p1", sequence: 2, type: "POCKET_2D", toolNumber: 2, featureId: "f1" }),
    op({ id: "d", sequence: 3, type: "DRILL", toolNumber: 3, featureId: "f2" }),
    op({ id: "bore", sequence: 4, type: "BORE", toolNumber: 2, featureId: "f2" }),
  ];
  const p = proposeSequence(ops);
  assert.ok(posOf("d", p.proposedOrder) < posOf("bore", p.proposedOrder), "drill still precedes the bore on its feature");
});

test("countToolChanges ignores untooled operations rather than counting them as a change", () => {
  const ops = [
    op({ id: "a", sequence: 1, type: "POCKET_2D", toolNumber: 4 }),
    op({ id: "b", sequence: 2, type: "POCKET_2D", toolNumber: null }),
    op({ id: "c", sequence: 3, type: "POCKET_2D", toolNumber: 4 }),
  ];
  assert.equal(countToolChanges(order(["a", "b", "c"], ops)), 0);
});

/* ---------------- Violations in the plan as written ---------------- */

test("a plan that profiles before pocketing is reported, even with nothing to save", () => {
  const ops = [
    op({ id: "face", sequence: 1, type: "FACE", toolNumber: 1, featureId: "f0" }),
    op({ id: "contour", sequence: 2, type: "CONTOUR_2D", toolNumber: 2, featureId: "prof" }),
    op({ id: "pocket", sequence: 3, type: "POCKET_2D", toolNumber: 2, featureId: "pkt" }),
  ];
  const p = proposeSequence(ops);
  assert.equal(p.saved, 0, "there are no tool changes to save here");
  assert.ok(p.violations.length > 0, "but the order is wrong and must be reported anyway");
  assert.ok(p.violations.some((v) => /held by its stock/i.test(v.rule)));
  // And it must fix it, because a violation is reason enough to reorder.
  assert.equal(p.proposedOrder[p.proposedOrder.length - 1], "contour");
});

test("a tap before its drill is reported as a violation", () => {
  const ops = [
    op({ id: "tap", sequence: 1, type: "TAP", toolNumber: 10, featureId: "hole" }),
    op({ id: "drill", sequence: 2, type: "PECK_DRILL", toolNumber: 6, featureId: "hole" }),
  ];
  const p = proposeSequence(ops);
  assert.ok(p.violations.length > 0);
  assert.ok(posOf("drill", p.proposedOrder) < posOf("tap", p.proposedOrder), "and corrected");
});

test("a correctly ordered plan reports no violations", () => {
  const ops = [
    op({ id: "face", sequence: 1, type: "FACE", toolNumber: 1, featureId: "f0" }),
    op({ id: "drill", sequence: 2, type: "PECK_DRILL", toolNumber: 6, featureId: "hole" }),
    op({ id: "tap", sequence: 3, type: "TAP", toolNumber: 10, featureId: "hole" }),
    op({ id: "contour", sequence: 4, type: "CONTOUR_2D", toolNumber: 2, featureId: "prof" }),
  ];
  const p = proposeSequence(ops);
  assert.equal(p.violations.length, 0);
  assert.equal(p.saved, 0);
  assert.deepEqual(p.proposedOrder, p.currentOrder, "nothing to fix and nothing to save means no churn");
});
