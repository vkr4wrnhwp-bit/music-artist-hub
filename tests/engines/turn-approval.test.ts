import { test } from "node:test";
import assert from "node:assert/strict";
import {
  turnApprovalDigest,
  turnApprovalState,
  type ApprovableTurnState,
} from "@/lib/manufacturing/turn/approval";

/**
 * On the milling side an Approval row is bound to a partRevisionId, so
 * changing the part means a new revision and the approval does not follow it.
 *
 * A rotational part has no revision. Profile, plan, lathe, workholding, grip,
 * stickout, clamp force and RPM clamp all sit on one mutable row, so a boolean
 * there would let an operator approve a package, let somebody halve the grip
 * length, and still read PASS over geometry nobody approved.
 */

const state = (over: Partial<ApprovableTurnState> = {}): ApprovableTurnState => ({
  profileJson: '{"segments":[{"d":1,"l":2}],"stockDiameter":1.25,"stockLength":6}',
  planJson: '[{"op":"ROUGH_OD","toolStation":1}]',
  latheMachineId: "lathe1",
  workholdingId: "chuck1",
  gripLength: 0.75,
  stickout: 2.5,
  clampForceLbf: 1800,
  tailstockActive: false,
  maxRpmClamp: 2400,
  ...over,
});

const approved = (s: ApprovableTurnState) => ({
  humanApproved: true,
  approvedAt: new Date("2026-01-01"),
  approvedDigest: turnApprovalDigest(s),
});

/* ---------------- What the approval is an approval OF ---------------- */

test("the same state digests the same way every time", () => {
  assert.equal(turnApprovalDigest(state()), turnApprovalDigest(state()));
});

test("changing anything that decides how the part is cut invalidates it", () => {
  const base = state();
  const changes: Partial<ApprovableTurnState>[] = [
    { profileJson: '{"segments":[{"d":2,"l":2}],"stockDiameter":1.25,"stockLength":6}' },
    { planJson: "[]" },
    { latheMachineId: "lathe2" },
    { workholdingId: "collet1" },
    { gripLength: 0.375 },
    { stickout: 5 },
    { clampForceLbf: 400 },
    { tailstockActive: true },
    { maxRpmClamp: 6000 },
  ];
  for (const c of changes) {
    const key = Object.keys(c)[0];
    assert.notEqual(
      turnApprovalDigest(state(c)),
      turnApprovalDigest(base),
      `changing ${key} left the approval reading as current`,
    );
    assert.equal(turnApprovalState(approved(base), state(c)), "STALE", `${key} did not go stale`);
  }
});

test("a null field is not the same as a different value in it", () => {
  // Joining the fields naively lets `gripLength: null, stickout: 25` collide
  // with `gripLength: 0.75, stickout: null` if the separator is weak.
  assert.notEqual(
    turnApprovalDigest(state({ gripLength: null, stickout: 2.5 })),
    turnApprovalDigest(state({ gripLength: 2.5, stickout: null })),
  );
  assert.notEqual(turnApprovalDigest(state({ gripLength: null })), turnApprovalDigest(state()));
});

test("clearing the lathe is a change, not a no-op", () => {
  assert.equal(turnApprovalState(approved(state()), state({ latheMachineId: null })), "STALE");
});

/* ---------------- The three states ---------------- */

test("an unapproved part is NONE, not stale", () => {
  assert.equal(
    turnApprovalState({ humanApproved: false, approvedAt: null, approvedDigest: null }, state()),
    "NONE",
  );
});

test("an approval of this exact state passes", () => {
  assert.equal(turnApprovalState(approved(state()), state()), "APPROVED");
});

test("an approval with no digest is STALE, never APPROVED", () => {
  // Rows predating the column were approved by nothing — the flag had no
  // writer in this application's history. Even if one had, an approval whose
  // subject cannot be identified is not evidence that this package was
  // reviewed, so it must not be the more permissive of the two readings.
  assert.equal(
    turnApprovalState({ humanApproved: true, approvedAt: new Date("2020-01-01"), approvedDigest: null }, state()),
    "STALE",
  );
});

test("changing the part back restores the approval, because it is the same package", () => {
  // Not a loophole: the digest is of the state, so a part edited and edited
  // back IS the package that was approved. Pretending otherwise would make
  // approvals expire for no reason a machinist could see.
  const original = state();
  const record = approved(original);
  assert.equal(turnApprovalState(record, state({ gripLength: 0.2 })), "STALE");
  assert.equal(turnApprovalState(record, original), "APPROVED");
});
