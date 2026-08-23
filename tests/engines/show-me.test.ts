import { test } from "node:test";
import assert from "node:assert/strict";
import { showMeHrefFor } from "@/lib/guide/show-me";
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
  approval: "Operator approval",
};

/** Gates with no physical scene, deliberately: no link beats a vague one. */
const NO_SCENE = ["engineering", "critical-review", "simulation", "nc", "approval"];

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

test("substring matching cannot cross-wire the inspection family", () => {
  // "inspection-capability" and "inspection" share a prefix; both must land
  // on the inspection plan, and "tolerance" must not swallow either.
  assert.match(showMeHrefFor("p1", "inspection-capability", "Inspection capability")!, /\/inspection\?/);
  assert.match(showMeHrefFor("p1", "inspection", "Inspection plan")!, /\/inspection\?/);
  assert.match(showMeHrefFor("p1", "tolerance", "Tolerance achievability")!, /\/inspection\?/);
});

test("an unknown gate returns null rather than a guessed page", () => {
  assert.equal(showMeHrefFor("p1", "somenewgate", "Some new gate"), null);
});
