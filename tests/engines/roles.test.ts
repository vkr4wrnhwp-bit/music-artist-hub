import { test } from "node:test";
import assert from "node:assert/strict";
import { ROLES, roleCanWrite, roleCanApprove } from "@/lib/roles";

/**
 * Principle 13's other half. The organisation boundary is enforced by taking
 * the org id from the session — that rule is honoured everywhere. What a
 * signed-in user may DO inside their own organisation is this file.
 */

test("the role vocabulary matches what the schema declares", () => {
  // User.role is a String with a comment naming four roles. A role added to
  // the schema and not here would fall to the unknown-role path below and get
  // nothing, which is the safe direction — but silently.
  assert.deepEqual([...ROLES], ["OWNER", "ENGINEER", "MACHINIST", "VIEWER"]);
});

test("a viewer may not change anything", () => {
  assert.equal(roleCanWrite("VIEWER"), false);
  assert.equal(roleCanApprove("VIEWER"), false);
});

test("a machinist may change parameters but may not approve for export", () => {
  // Approval is the last human gate before executable NC. It sits with the
  // people who own the engineering decision.
  assert.equal(roleCanWrite("MACHINIST"), true);
  assert.equal(roleCanApprove("MACHINIST"), false);
});

test("an owner and an engineer may do both", () => {
  for (const role of ["OWNER", "ENGINEER"]) {
    assert.equal(roleCanWrite(role), true, role);
    assert.equal(roleCanApprove(role), true, role);
  }
});

test("a role CANVAS does not recognise gets nothing", () => {
  // A typo in a seed script, or a role added to the schema and not to this
  // file, must withhold rather than grant.
  for (const role of ["ADMIN", "owner", "", "SUPERUSER", "Engineer"]) {
    assert.equal(roleCanWrite(role), false, `${role} may write`);
    assert.equal(roleCanApprove(role), false, `${role} may approve`);
  }
});

test("approval is never wider than write", () => {
  // Somebody who may approve a package for export must also be able to change
  // it; the reverse need not hold. A role that could approve but not edit
  // would be able to sign off work it cannot inspect the inputs of.
  for (const role of ROLES) {
    if (roleCanApprove(role)) assert.equal(roleCanWrite(role), true, `${role} may approve but not write`);
  }
});

test("at least one role can do each thing, and not every role can", () => {
  // A permission nobody has is a broken app; a permission everybody has is
  // not a permission.
  assert.ok(ROLES.some(roleCanWrite) && !ROLES.every(roleCanWrite));
  assert.ok(ROLES.some(roleCanApprove) && !ROLES.every(roleCanApprove));
});
