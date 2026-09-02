import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolveCollapsed } from "@/lib/panel-preference";

/**
 * Layout preferences, and the one rule about them that matters: FOCUS is a
 * look at the part, not an answer to which panels the machinist keeps open.
 * Entering focus collapses; leaving it restores what was stored. The bug this
 * pins is the reverse — leaving focus used to expand three panels that had
 * been shut, so the way out of a clean screen was a messier one.
 */

test("an explicit stored choice beats the default, in both directions", () => {
  assert.equal(resolveCollapsed("1", "1", false), true);
  assert.equal(resolveCollapsed("0", "1", true), false);
  assert.equal(resolveCollapsed("collapsed", "collapsed", false), true);
  assert.equal(resolveCollapsed("open", "collapsed", true), false);
});

test("no stored choice falls back to the panel's own default", () => {
  assert.equal(resolveCollapsed(null, "1", true), true);
  assert.equal(resolveCollapsed(null, "1", false), false);
});

test("an unrecognised stored value reads as expanded, not as collapsed", () => {
  // Storage is shared with the browser and with older builds. A value this
  // code does not recognise must not silently hide a panel.
  assert.equal(resolveCollapsed("yes", "1", true), false);
  assert.equal(resolveCollapsed("", "collapsed", true), false);
});

/* ---- the focus contract, read off the source ---- */

const SOURCES = [
  "src/components/nav.tsx",
  "src/components/workspace/workspace.tsx",
  "src/components/workspace/operation-runway.tsx",
];

test("leaving focus restores the stored preference rather than expanding", () => {
  for (const file of SOURCES) {
    const src = readFileSync(file, "utf8");
    // Every focus receiver must consult the stored preference on the way out.
    // `setCollapsed(Boolean(detail))` is the shape that caused the bug: it
    // makes focus-off mean "open everything".
    assert.ok(
      !/setCollapsed\(Boolean\(\(e as CustomEvent\)\.detail\)\)/.test(src),
      `${file} sets collapsed straight from the focus flag — leaving focus will expand a panel the machinist shut`,
    );
    assert.ok(
      /readCollapsed\(/.test(src),
      `${file} listens for focus but never reads the stored preference back`,
    );
  }
});

test("panels render collapsed on first paint, not expanded-then-corrected", () => {
  // Initialising expanded and fixing it in an effect puts every panel on
  // screen for the first frame — the "screen full of boxes to close" that the
  // collapse defaults exist to prevent, and what stays there if hydration
  // stalls.
  for (const file of SOURCES) {
    const src = readFileSync(file, "utf8");
    for (const state of ["collapsed", "panelCollapsed"]) {
      const init = new RegExp(`const \\[${state}, set\\w+\\] = useState\\((\\w+)\\)`);
      const m = src.match(init);
      if (!m) continue;
      assert.equal(m[1], "true", `${file}: ${state} starts expanded on first paint`);
    }
  }
});

test("the guide card remembers being closed, and closes with the workspace", () => {
  const src = readFileSync("src/components/guide/guide-card.tsx", "utf8");
  assert.ok(/canvas\.guideCard/.test(src), "the guide card's visibility is not persisted");
  assert.ok(
    /addEventListener\("canvas:focus"/.test(src),
    "focus hands the screen to the part but leaves the guide card standing on it",
  );
  assert.ok(
    /if \(mode === "OFF"\) setOpen\(false\)/.test(src),
    "tutoring set to OFF still opens a card that says tutoring is off",
  );
});

/* ---- one owner per viewport corner ---- */

const OVERLAY_FILES = [
  "src/components/workspace/workspace.tsx",
  "src/components/workspace/dimension-card.tsx",
  "src/components/workspace/sim-transport.tsx",
  "src/components/workspace/feature-lens.tsx",
];

test("each bottom corner of the viewport has exactly one anchored owner", () => {
  // The complaint this pins: surfaces that anchored themselves independently
  // landed on top of each other. Select a feature in HOLD and the measurement
  // strip and the dimension card shared `bottom-3 right-3 z-20` — same corner,
  // same z-index, DOM order deciding which numbers an operator got to read.
  // A corner now has one dock and its contents stack inside it.
  const corners = ["bottom-3 right-3", "bottom-3 left-3"];
  for (const corner of corners) {
    let owners = 0;
    for (const file of OVERLAY_FILES) {
      const src = readFileSync(file, "utf8");
      for (const m of src.matchAll(/className="([^"]*)"/g)) {
        const cls = m[1];
        if (cls.includes("absolute") && cls.includes(corner)) owners++;
      }
    }
    assert.equal(owners, 1, `${corner} has ${owners} anchored owners — it must have exactly one dock`);
  }
});

test("overlay children do not anchor themselves — the dock places them", () => {
  // A presentational card that positions itself cannot be stacked with
  // anything, and the next surface added to that corner collides silently.
  for (const file of OVERLAY_FILES.slice(1)) {
    const src = readFileSync(file, "utf8");
    assert.ok(
      !/className="[^"]*absolute[^"]*bottom-3[^"]*(?:left-|right-)/.test(src),
      `${file} anchors itself to a viewport corner instead of being placed by a dock`,
    );
  }
});
