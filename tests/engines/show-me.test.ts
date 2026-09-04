import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { findingShowMeHref, pickFocus, showMeHrefFor } from "@/lib/guide/show-me";
import { READINESS_GATE_IDS } from "@/lib/engines/readiness";

/**
 * SHOW ME routing. The map is hand-kept and matched by substring against
 * gate ids the readiness engine owns — the exact lookup-table-drift shape
 * that has already bitten three other files. Every gate id is accounted
 * for here: it either resolves to a scene or is on the stated no-scene
 * list, so a new gate cannot silently join the unlinked.
 */

const GATE_LABEL: Record<string, string> = {
  geometry: "Geometry",
  coverage: "Feature coverage",
  material: "Material",
  engineering: "Engineering input",
  machine: "Machine envelope",
  reach: "Tool reach",
  corners: "Internal corners",
  tools: "Tool availability",
  "tool-loading": "Tooling loaded",
  "inspection-capability": "Inspection capability",
  "critical-review": "Critical feature review",
  workholding: "Workholding",
  tolerance: "Tolerance achievability",
  inspection: "Inspection plan",
  simulation: "Simulation",
  nc: "NC post",
  proof: "Proven on the machine",
  approval: "Operator approval",
};

/** Gates with no physical scene, deliberately: no link beats a vague one. */
const NO_SCENE = [
  "engineering",
  "critical-review",
  "simulation",
  "nc",
  // Proof-out is resolved at the machine with a part in the vise. There is no
  // scene in the app that shows it, and a link to one would be a link to the
  // wrong thing.
  "proof",
  "approval",
];

test("every readiness gate either resolves to a scene or is deliberately unlinked", () => {
  for (const gid of READINESS_GATE_IDS) {
    const href = showMeHrefFor("p1", gid, GATE_LABEL[gid] ?? gid);
    if (NO_SCENE.includes(gid)) {
      assert.equal(href, null, `${gid} is on the no-scene list and resolved anyway`);
    } else {
      assert.ok(href, `${gid} is a gate with a physical scene and SHOW ME returns nothing for it`);
      assert.ok(href!.startsWith("/"), `${gid} -> ${href}`);
    }
  }
});

test("the blocking tool-loading gate points at the changer, not at nothing", () => {
  // Its evidence is pockets on a machine, not tool assignments on the part.
  // This returned null before — no link on the one blocking gate whose fix
  // lives furthest from the part.
  assert.equal(showMeHrefFor("p1", "tool-loading", "Tooling loaded"), "/machines");
});

test("capability and plan are different gates and go to different scenes", () => {
  // They share a prefix, and pointing both at the part's inspection page was
  // wrong for the capability one: it is a property of the instruments the
  // shop owns, and nothing on that page can change it. A machinist sent
  // there with a failing capability gate gets the one screen that cannot
  // help him.
  assert.equal(showMeHrefFor("p1", "inspection-capability", "Inspection capability"), "/metrology");
  // The plan gate is about sessions and readings, which do live on the part.
  assert.match(showMeHrefFor("p1", "inspection", "Inspection plan")!, /\/parts\/p1\/inspection\?/);
  assert.match(showMeHrefFor("p1", "tolerance", "Tolerance achievability")!, /\/parts\/p1\/inspection\?/);
});

test("an unknown gate returns null rather than a guessed page", () => {
  assert.equal(showMeHrefFor("p1", "somenewgate", "Some new gate"), null);
});

/* ---- SHOW ME on a review finding ---- */

/**
 * The link tested `setupId` first. Four of the six finding kinds carry both a
 * setupId and CUT context — including the lateral rapid below the jaw line,
 * the case the review engine's own tests say the check exists for — so all
 * four landed on a list of setup cards, which cannot show a move. The
 * coordinate triple was printed beside the button instead: a machinist
 * reading numbers where they could be looking at the thing.
 */

const loc = (over: Partial<Parameters<typeof findingShowMeHref>[1]> = {}) => ({
  setupId: null,
  operationId: null,
  featureId: null,
  context: "PART" as const,
  ...over,
});

test("a cut finding opens the part in CUT with its operation selected", () => {
  assert.equal(
    findingShowMeHref("p1", loc({ context: "CUT", operationId: "o1", setupId: "s1" }), "s1"),
    "/parts/p1?context=CUT&op=o1",
  );
});

test("a setup-level cut finding still opens CUT, without an operation", () => {
  // Spindle power is assessed per setup and carries no operation.
  assert.equal(findingShowMeHref("p1", loc({ context: "CUT", setupId: "s1" }), "s1"), "/parts/p1?context=CUT");
});

test("an inspection finding opens VERIFY on the feature it is about", () => {
  assert.equal(
    findingShowMeHref("p1", loc({ context: "VERIFY", featureId: "f1" }), null),
    "/parts/p1?context=VERIFY&feature=f1",
  );
});

test("a grip finding on the primary setup opens HOLD", () => {
  assert.equal(findingShowMeHref("p1", loc({ context: "HOLD", setupId: "s1" }), "s1"), "/parts/p1?context=HOLD");
});

test("a grip finding on a LATER setup goes to the setup list, not HOLD", () => {
  // The workspace builds its HOLD scene from the first setup alone. Opening
  // HOLD for setup 2 would draw setup 1's vise while claiming to show setup
  // 2's problem — a picture of the wrong workholding is worse than a list.
  assert.equal(findingShowMeHref("p1", loc({ context: "HOLD", setupId: "s2" }), "s1"), "/parts/p1/setups");
  assert.equal(findingShowMeHref("p1", loc({ context: "HOLD", setupId: "s2" }), null), "/parts/p1/setups");
});

test("context decides the destination, not setupId", () => {
  // The exact bug: every finding carrying a setupId went to /setups.
  for (const context of ["CUT", "VERIFY", "PART"] as const) {
    const href = findingShowMeHref("p1", loc({ context, setupId: "s1", operationId: "o1", featureId: "f1" }), "s1");
    assert.ok(!href.endsWith("/setups"), `${context} with a setupId still lands on the setup list`);
  }
});

/* ---- what a deep link is allowed to focus ---- */

test("a feature or operation from another part is dropped, not trusted", () => {
  const focus = pickFocus({ context: "CUT", feature: "f-elsewhere", op: "o-elsewhere" }, ["f1"], ["o1"]);
  assert.equal(focus.featureId, null, "a feature id from a URL was accepted without checking it exists here");
  assert.equal(focus.operationId, null, "an operation id from a URL was accepted without checking it exists here");
  assert.equal(focus.context, "CUT");
});

test("an unrecognised context is dropped rather than passed through", () => {
  assert.equal(pickFocus({ context: "COST" }, [], []).context, null);
  assert.equal(pickFocus({ context: "<script>" }, [], []).context, null);
  assert.equal(pickFocus({}, [], []).context, null);
});

test("ids that do exist on this part are kept", () => {
  const focus = pickFocus({ context: "VERIFY", feature: "f1", op: "o1" }, ["f1", "f2"], ["o1"]);
  assert.deepEqual(focus, { context: "VERIFY", featureId: "f1", operationId: "o1" });
});

test("the review page and the workspace are actually wired to this", () => {
  const review = readFileSync("src/app/(app)/parts/[id]/review/page.tsx", "utf8");
  assert.ok(/findingShowMeHref\(id, f\.location/.test(review), "the review page still routes SHOW ME itself");
  assert.ok(!/f\.location\.setupId\s*$/m.test(review), "the setupId-first branch is still there");

  const page = readFileSync("src/app/(app)/parts/[id]/page.tsx", "utf8");
  assert.ok(/pickFocus\(/.test(page), "the workspace page ignores the deep link");
  assert.ok(/focus=\{focus\}/.test(page), "the focus is computed and not passed to the workspace");

  const ws = readFileSync("src/components/workspace/workspace.tsx", "utf8");
  assert.ok(/props\.focus\?\.operationId/.test(ws), "the runway does not open on the finding's operation");
  assert.ok(/focusApplied/.test(ws), "nothing applies the deep link on arrival");
  // And that the effect reads the prop and acts on all three parts of it — a
  // guard that runs against nothing is not applying anything.
  const effect = /const focusApplied[\s\S]{0,900}?\}, \[\]\);/.exec(ws);
  assert.ok(effect, "the arrival effect is not there");
  for (const call of ["props.focus", "setContext(focus.context)", "selectFeature(focus.featureId)"]) {
    assert.ok(effect![0].includes(call), `the arrival effect never calls ${call}`);
  }
});
