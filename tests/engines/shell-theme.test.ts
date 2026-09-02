import { test } from "node:test";
import assert from "node:assert/strict";
import {
  DEFAULT_ENVIRONMENT,
  VIEW_PRESETS,
  shellLegibilityProblems,
  contrastRatio,
} from "@/lib/view-environment";

/**
 * The application chrome's ground, and what it is allowed to become.
 *
 * The drawer's "Background" colour has always repainted the 3D work window
 * only, so picking a colour there left the rail, header and panels exactly
 * as they were — the control reading as if it did nothing. The chrome is now
 * settable separately, which means it can now be set to something unreadable.
 */

test("the shell ground defaults to the approved near-black, on every preset", () => {
  // A machinist picking "Dark Machine Bay" for the part is not asking for a
  // different application. Presets tune the work window; the chrome is a
  // separate, explicit act.
  assert.equal(DEFAULT_ENVIRONMENT.shellBackground, null);
  for (const [name, p] of Object.entries(VIEW_PRESETS)) {
    assert.equal(p.env.shellBackground, null, `preset ${name} repaints the chrome`);
  }
});

test("a shell ground that erases the interface is named, not silently accepted", () => {
  // The chrome carries running text in a near-white foreground. A light
  // ground does not restyle the interface, it deletes it.
  const white = shellLegibilityProblems("#ffffff");
  assert.ok(white.some((p) => /7:1/.test(p)), white.join(" | "));

  // The approved shell passes its own check — a rule the product breaks on
  // its own default would be the wrong rule.
  assert.deepEqual(shellLegibilityProblems("#06111c"), []);
});

test("a shell ground that drowns a status colour is named on the same footing", () => {
  // Red blocking that stops reading as red is the failure the whole colour
  // vocabulary exists to prevent — it is not a lesser problem than text.
  const problems = shellLegibilityProblems("#c22a1e");
  assert.ok(problems.some((p) => /blocking/.test(p)), problems.join(" | "));
});

test("both failures are reported together, text first", () => {
  // A mid grey can be illegible AND drown a marker. Reporting one and
  // stopping would send someone to fix half of it.
  const problems = shellLegibilityProblems("#8a8a8a");
  assert.ok(problems.length >= 2, `expected both failures, got ${problems.length}: ${problems.join(" | ")}`);
  assert.match(problems[0], /7:1/);
});

test("the contrast floor is a real measurement, not a hand-wave", () => {
  // Anchor the helper to the arithmetic it claims: white on the approved
  // shell is high contrast, white on white is 1:1.
  const onShell = contrastRatio("#06111c", "#f2f6fa");
  assert.ok(onShell !== null && onShell > 15, `${onShell}`);
  assert.equal(contrastRatio("#ffffff", "#ffffff"), 1);
});

test("the small labels are checked, not only the brightest text", () => {
  // The labels go first. A ground the 15:1 body text is comfortable on can
  // still leave the 9px uppercase type — which names every value on screen —
  // below the floor, and only the label check catches it.
  const problems = shellLegibilityProblems("#3d4c5a");
  assert.ok(
    problems.some((p) => /Labels sit at/.test(p)),
    `a ground that fails the labels was accepted: ${problems.join(" | ")}`,
  );
});

test("the approved shell clears the raised floor on both inks", () => {
  // A rule the product breaks on its own default would be the wrong rule.
  assert.deepEqual(shellLegibilityProblems("#06111c"), []);
});
