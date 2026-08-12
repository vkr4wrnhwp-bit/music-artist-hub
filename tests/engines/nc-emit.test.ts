import { test } from "node:test";
import assert from "node:assert/strict";
import { emitOptimized, maskedDiff } from "@/lib/nc/emit";
import type { FeedProposal } from "@/lib/nc/load";

/**
 * Phase 4E invariants: feed words change, nothing else does, and the masked
 * diff catches anything that would break that promise.
 */

const proposal = (l0: number, l1: number, from: number, to: number): FeedProposal => ({
  kind: "RAISE" as const, lines: [l0, l1], toolNumber: 2, originalFeed: from, proposedFeed: to,
  estimatedSecondsSaved: 5, reason: "test", risk: "LOW", assumptions: [],
  requiredEvidence: "", geometryChanges: false,
});

const PROG = "G20 G90\nG0 X0 Y0 Z1\nG1 Z-0.1 F5.\nG1 X2 F10.\nG1 Y1\nG0 Z1";

test("feed words on the proposal's lines are rewritten; line count is unchanged", () => {
  const r = emitOptimized(PROG, [proposal(4, 5, 10, 14)]);
  assert.ok(r.ok);
  const lines = r.text.split("\n");
  assert.equal(lines.length, 6);
  assert.equal(lines[3], "G1 X2 F14.");
  assert.equal(lines[4], "G1 Y1"); // modal line untouched — no word inserted
  assert.equal(r.applied.length, 1);
});

test("a fully modal range is refused with a reason, never guessed at", () => {
  const r = emitOptimized(PROG, [proposal(5, 5, 10, 14)]);
  assert.ok(r.ok); // emission itself is fine — the proposal is just unapplied
  assert.equal(r.applied.length, 0);
  assert.equal(r.unapplied.length, 1);
  assert.match(r.unapplied[0].reason, /modal/);
  assert.equal(r.text, PROG);
});

test("non-matching feeds on the same lines are left alone", () => {
  const r = emitOptimized(PROG, [proposal(3, 4, 10, 14)]);
  const lines = r.text.split("\n");
  assert.equal(lines[2], "G1 Z-0.1 F5."); // F5 plunge on line 3 untouched
  assert.equal(lines[3], "G1 X2 F14.");
});

test("the masked diff ignores feed differences and catches everything else", () => {
  const a = PROG.split("\n");
  // Feed-only difference: clean.
  const feedOnly = PROG.replace("F10.", "F14.").split("\n");
  assert.equal(maskedDiff(a, feedOnly).length, 0);
  // A coordinate change: caught, with the line number.
  const coord = PROG.replace("X2", "X2.5").split("\n");
  const v1 = maskedDiff(a, coord);
  assert.equal(v1.length, 1);
  assert.equal(v1[0].line, 4);
  // A dropped line: caught.
  assert.ok(maskedDiff(a, a.slice(0, -1)).length > 0);
  // A G-word change hiding behind an identical feed: caught.
  const gword = PROG.replace("G1 X2 F10.", "G0 X2 F10.").split("\n");
  assert.equal(maskedDiff(a, gword).length, 1);
});
