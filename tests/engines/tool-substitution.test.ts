import { test } from "node:test";
import assert from "node:assert/strict";
import {
  planHole,
  describeSubstitution,
  MAX_FINISH_PER_SIDE,
  type SubstitutionResult,
} from "@/lib/engines/tool-substitution";
import type { Tool } from "@/lib/domain/shop";

/**
 * "Drill a 1.000 hole." The answer a machinist gives is never "you cannot
 * make this part" — it is a chain. So the two failures that matter here are
 * opposite in shape: refusing a job the crib CAN do, and planning a step the
 * crib cannot physically perform.
 *
 * The second is the dangerous one, and it has a specific form throughout this
 * engine: a cutter is checked against the FINISHED diameter and then handed a
 * roughing pass at a smaller one. So the invariant every chain is checked
 * against below is simply that each step's tool fits inside the hole that
 * step produces.
 *
 * The allowance constants are not pinned. Whether a boring head should take
 * 0.010 or 0.015 per side is a shop's argument to have, and freezing today's
 * number would make the engine harder to improve rather than safer.
 */

const tool = (id: string, n: number, cls: string, d: number, stick = 3): Tool =>
  ({
    id, toolNumber: n, toolClass: cls, description: `${cls} ⌀${d}`, diameter: d,
    cornerRadius: 0, flutes: 3, material: "CARBIDE", fluteLength: 2, overallLength: 5, stickout: stick,
    holder: "CAT40", holderNoseDiameter: 1.5, maxRPM: 8000, recommendedMaterials: [],
    chiploadMin: 0.001, chiploadMax: 0.006, sfmMin: 300, sfmMax: 900, coolant: "FLOOD",
    lifeRemaining: 1, condition: "GOOD", regrindCount: 0,
  }) as unknown as Tool;

const DRILL = (n: number, d: number) => tool(`d${d}`, n, "DRILL", d);
const MILL = (n: number, d: number) => tool(`m${d}`, n, "FLAT_END_MILL", d);
const REAMER = (n: number, d: number) => tool(`r${d}`, n, "REAMER", d);
const BORE = (n: number, d: number) => tool(`b${d}`, n, "BORING_TOOL", d);

const plan = (target: number, tools: Tool[], precision = false, depth = 0.5) =>
  planHole({ targetDiameter: target, depth, precision, tools });

/**
 * The invariant. Every step's tool has to fit inside the hole that step
 * leaves, except a drill or reamer producing a hole at its own size.
 */
function assertStepsArePossible(r: SubstitutionResult, tools: Tool[], label: string) {
  for (const s of r.steps) {
    const t = tools.find((x) => x.id === s.toolId);
    assert.ok(t, `${label}: ${s.action} names a tool not in the crib`);
    // A tool may produce a hole at its own size only if it is a drill or a
    // reamer — those cut at their diameter. A mill has to CIRCLE inside the
    // hole, so it must be strictly smaller. Excusing any same-size tool here
    // was a hole in this checker: a ⌀0.980 mill "interpolating" a ⌀0.980 hole
    // slipped through as though it were a drill.
    const cutsAtItsOwnSize = t.toolClass === "DRILL" || t.toolClass === "REAMER";
    const sameSize = Math.abs(t.diameter - s.resultingDiameter) < 0.0006;
    // A boring head's recorded diameter is the nominal centre of its range,
    // not a cutting diameter, so it carries no such relationship.
    if ((cutsAtItsOwnSize && sameSize) || t.toolClass === "BORING_TOOL") continue;
    assert.ok(
      t.diameter < s.resultingDiameter,
      `${label}: "${s.action}" uses ⌀${t.diameter} to produce ⌀${s.resultingDiameter} — the cutter is bigger than the hole`,
    );
  }
}

/* ---------------- The file's own worked example ---------------- */

test("drill 15/16 then bore to 1.000 — the example in this file's header", () => {
  // This came back BLOCKED: "nothing in the crib is small enough to produce a
  // 1.0000 hole". 15/16 leaves 0.03125 per side, a thousandth over the
  // single-pass finishing ceiling, and with no end mill in the crib to rough
  // with, the engine gave up — while a boring head sat in the crib and 15/16
  // is exactly the drill a machinist reaches for. A boring head is not
  // limited to one pass.
  const tools = [DRILL(1, 0.9375), BORE(2, 1.0)];
  const r = plan(1.0, tools, true);
  assert.equal(r.blocked, null, `blocked: ${r.blocked}`);
  assert.equal(r.ok, true);
  assert.equal(r.strategy, "DRILL_THEN_BORE");
  assert.equal(r.steps[0].toolNumber, 1, "it starts with the 15/16 drill");
  assert.equal(r.steps[r.steps.length - 1].resultingDiameter, 1.0, "it ends at size");
  assertStepsArePossible(r, tools, "15/16 then bore");
});

/* ---------------- No step may be physically impossible ---------------- */

test("a rougher is never handed a hole smaller than itself", () => {
  // The filter checked the FINISHED size while the mill was then asked to
  // interpolate the rough hole. A ⌀0.980 mill passed for a ⌀1.000 hole and
  // was handed a ⌀0.940 rough pass it cannot make.
  const tools = [MILL(1, 0.98), BORE(2, 1.0), DRILL(3, 0.5)];
  const r = plan(1.0, tools, true);
  assertStepsArePossible(r, tools, "rough-then-bore");
});

test("a precision interpolation checks the mill against the rough pass, not the finished size", () => {
  // A ⌀0.985 mill was accepted for a ⌀1.000 precision hole and told to
  // interpolate ⌀0.976 first.
  const tools = [MILL(1, 0.985)];
  const r = plan(1.0, tools, true);
  if (r.ok) assertStepsArePossible(r, tools, "precision mill");
  else assert.ok(r.blocked, "refusing is the correct answer here");
});

test("every chain the engine will produce is physically possible", () => {
  const cribs: [string, Tool[]][] = [
    ["drill only", [DRILL(1, 0.9375), DRILL(2, 0.5)]],
    ["mill only", [MILL(1, 0.25)]],
    ["near-size mill", [MILL(1, 0.98)]],
    ["reamer", [REAMER(1, 0.5), DRILL(2, 0.484)]],
    ["boring head", [BORE(1, 1.0), DRILL(2, 0.9375)]],
    ["everything", [DRILL(1, 0.9375), DRILL(2, 0.5), MILL(3, 0.375), MILL(4, 0.98), BORE(5, 1.0), REAMER(6, 0.5)]],
  ];
  for (const [name, tools] of cribs) {
    for (const target of [0.25, 0.5, 0.75, 1.0, 1.25]) {
      for (const precision of [true, false]) {
        const r = plan(target, tools, precision);
        assertStepsArePossible(r, tools, `${name} ⌀${target} precision=${precision}`);
      }
    }
  }
});

test("the last pass in a chain is a finishing pass", () => {
  // The module's promise: it "refuses the chain when the remainder lands
  // somewhere a finishing pass will not behave — too much and it is a
  // roughing pass wearing a finishing pass's name". Nothing checked it.
  //
  // Without the rough-boring step, drill 15/16 then bore to 1.000 comes back
  // as a two-step chain that looks entirely reasonable and hands the boring
  // head 0.031 per side in a single pass — over the engine's own ceiling.
  const cribs: [string, Tool[]][] = [
    ["15/16 and a boring head", [DRILL(1, 0.9375), BORE(2, 1.0)]],
    ["half-inch drill and a boring head", [DRILL(1, 0.5), BORE(2, 1.0)]],
    ["mill and boring head", [MILL(1, 0.375), BORE(2, 1.0), DRILL(3, 0.5)]],
    ["mill only", [MILL(1, 0.25)]],
    ["reamer", [REAMER(1, 0.5), DRILL(2, 0.484)]],
  ];
  for (const [name, tools] of cribs) {
    for (const target of [0.5, 1.0, 1.25]) {
      const r = plan(target, tools, true);
      if (!r.ok || r.steps.length < 2) continue;
      const beforeLast = r.steps[r.steps.length - 2];
      assert.ok(
        beforeLast.remainingPerSide <= MAX_FINISH_PER_SIDE + 1e-9,
        `${name} ⌀${target}: "${beforeLast.action}" leaves ${beforeLast.remainingPerSide}" per side for the final pass, above the ${MAX_FINISH_PER_SIDE}" ceiling — that is a roughing pass wearing a finishing pass's name`,
      );
    }
  }
});

test("a chain always ends at the requested size", () => {
  const tools = [DRILL(1, 0.9375), BORE(2, 1.0), MILL(3, 0.375)];
  for (const precision of [true, false]) {
    const r = plan(1.0, tools, precision);
    assert.equal(r.ok, true);
    assert.equal(r.steps[r.steps.length - 1].resultingDiameter, 1.0, `precision=${precision}`);
    assert.equal(r.steps[r.steps.length - 1].remainingPerSide, 0, "nothing is left on the wall at the end");
  }
});

test("the chain only ever opens the hole, never closes it", () => {
  const tools = [DRILL(1, 0.5), MILL(2, 0.375), BORE(3, 1.0)];
  const r = plan(1.0, tools, true);
  for (let i = 1; i < r.steps.length; i++) {
    assert.ok(
      r.steps[i].resultingDiameter > r.steps[i - 1].resultingDiameter,
      `step ${i + 1} produces a smaller hole than step ${i}`,
    );
  }
});

/* ---------------- The strategy names what is in the chain ---------------- */

test("a chain with no drilling step is not called DRILL_THEN_MILL", () => {
  // The label read `steps.length > 1`, so a precision hole interpolated in
  // two passes with no drill anywhere came back as DRILL_THEN_MILL.
  const r = plan(1.0, [MILL(1, 0.25)], true);
  assert.equal(r.ok, true);
  assert.equal(r.steps.length, 2);
  assert.ok(!r.steps.some((s) => /drill/i.test(s.action)), "precondition: nothing is drilled");
  assert.equal(r.strategy, "MILL_ONLY");
});

test("a chain that does drill first is called DRILL_THEN_MILL", () => {
  const r = plan(1.0, [MILL(1, 0.25), DRILL(2, 0.5)], true);
  assert.equal(r.strategy, "DRILL_THEN_MILL");
  assert.ok(/drill/i.test(r.steps[0].action));
});

test("every strategy label matches the operations in its chain", () => {
  const check = (r: SubstitutionResult) => {
    if (!r.ok) return;
    const hasDrill = r.steps.some((s) => /^drill/i.test(s.action));
    if (r.strategy?.startsWith("DRILL_THEN")) {
      assert.ok(hasDrill, `${r.strategy} but nothing is drilled: [${r.steps.map((s) => s.action).join(" → ")}]`);
    }
    if (r.strategy === "MILL_ONLY") {
      assert.ok(!hasDrill, `MILL_ONLY but something is drilled`);
    }
  };
  check(plan(1.0, [MILL(1, 0.25)], true));
  check(plan(1.0, [MILL(1, 0.25), DRILL(2, 0.5)], true));
  check(plan(1.0, [DRILL(1, 0.9375), BORE(2, 1.0)], true));
  check(plan(0.5, [REAMER(1, 0.5), DRILL(2, 0.484)], true));
});

/* ---------------- Refusal is honest about what is in the crib ---------------- */

test("the blocked message counts every cutter class, not just mills and drills", () => {
  // "The smallest usable cutter" was read off mills and drills only, so a
  // crib holding a boring head at size was told nothing in it was small
  // enough — while naming a drill as the smallest thing available.
  const r = plan(2.0, [REAMER(1, 0.25), BORE(2, 0.25)]);
  if (r.blocked) {
    assert.match(r.blocked, /0\.2500/, `the reamer and boring head are the smallest cutters: ${r.blocked}`);
  }
});

test("a crib whose tools cannot reach the depth says so, rather than blaming size", () => {
  const shallow = [tool("m", 1, "FLAT_END_MILL", 0.25, 0.3)];
  const r = plan(1.0, shallow, false, 2.0);
  assert.equal(r.ok, false);
  assert.match(r.blocked!, /reach(es)? this depth/i, `got: ${r.blocked}`);
});

test("an empty crib is blocked and does not claim a smallest cutter", () => {
  const r = plan(1.0, []);
  assert.equal(r.ok, false);
  assert.ok(r.blocked);
  assert.ok(!/⌀0\.0000/.test(r.blocked), `a crib with no tools has no smallest cutter: ${r.blocked}`);
});

test("no hole diameter is refused rather than planned around", () => {
  for (const bad of [Number.NaN, 0, -1, Number.POSITIVE_INFINITY]) {
    const r = plan(bad, [DRILL(1, 0.5), MILL(2, 0.25), BORE(3, 1.0)]);
    assert.equal(r.ok, false, `target ${bad}`);
    assert.deepEqual(r.steps, [], `target ${bad} produced steps`);
    assert.ok(r.blocked && !/NaN|Infinity/.test(r.blocked), `target ${bad}: ${r.blocked}`);
  }
});

test("a blocked result suggests a purchase rather than stopping at 'no'", () => {
  const r = plan(1.0, [MILL(1, 1.5)]);
  assert.equal(r.ok, false);
  assert.ok(r.suggestedPurchase && r.suggestedPurchase.length > 10, "it must say what to buy");
});

/* ---------------- The straightforward routes still work ---------------- */

test("an exact drill and no tolerance is one operation", () => {
  const r = plan(0.5, [DRILL(1, 0.5), MILL(2, 0.25)]);
  assert.equal(r.exact, true);
  assert.equal(r.strategy, "EXACT_DRILL");
  assert.equal(r.steps.length, 1);
});

test("an exact drill is not enough when the hole has to hold size", () => {
  const r = plan(0.5, [DRILL(1, 0.5)], true);
  assert.equal(r.exact, false, "a drilled hole does not hold a tolerance");
});

test("a reamer at size drills under and reams to it", () => {
  const tools = [REAMER(1, 0.5), DRILL(2, 0.484)];
  const r = plan(0.5, tools, true);
  assert.equal(r.strategy, "DRILL_THEN_REAM");
  assert.equal(r.steps.length, 2);
  assert.equal(r.steps[1].resultingDiameter, 0.5);
  const allowance = r.steps[0].remainingPerSide;
  assert.ok(allowance >= 0.005 && allowance <= 0.016, `reaming allowance ${allowance} is outside what a reamer wants`);
});

test("a reamer with no workable undersize drill warns instead of reaming badly", () => {
  // The only drill is 0.250 under — far too much for a reamer to hold size.
  const r = plan(0.5, [REAMER(1, 0.5), DRILL(2, 0.25), MILL(3, 0.25)], true);
  assert.notEqual(r.strategy, "DRILL_THEN_REAM");
  assert.ok(r.warnings.some((w) => /reaming allowance/i.test(w)), `got [${r.warnings.join(" | ")}]`);
});

test("a boring head with a well-sized drill is a single finishing pass", () => {
  const tools = [DRILL(1, 0.98), BORE(2, 1.0)];
  const r = plan(1.0, tools, true);
  assert.equal(r.strategy, "DRILL_THEN_BORE");
  assert.equal(r.steps.length, 2, "0.010 per side is one clean pass, not two");
});

test("an interpolated precision hole warns that roundness is the weak point", () => {
  const r = plan(1.0, [MILL(1, 0.375)], true);
  assert.equal(r.ok, true);
  assert.ok(r.warnings.some((w) => /roundness/i.test(w)), "the machinist has to know what they are trading");
});

/* ---------------- Output is fit to display ---------------- */

test("no displayed number carries floating point noise", () => {
  // (1.0 - 0.99) / 2 is 0.0050000000000000044, and a stock allowance printed
  // to seventeen decimal places reads as a bug exactly where a machinist is
  // deciding whether the pass is sane.
  const r = plan(1.0, [DRILL(1, 0.99), BORE(2, 1.0)], true);
  for (const s of r.steps) {
    assert.equal(s.remainingPerSide, Number(s.remainingPerSide.toFixed(5)), `${s.action}: ${s.remainingPerSide}`);
    assert.equal(s.resultingDiameter, Number(s.resultingDiameter.toFixed(4)), `${s.action}: ${s.resultingDiameter}`);
  }
});

test("every step names a real tool, a reason, and its order", () => {
  const tools = [DRILL(1, 0.9375), BORE(2, 1.0)];
  const r = plan(1.0, tools, true);
  r.steps.forEach((s, i) => {
    assert.equal(s.order, i + 1, "steps are numbered in order");
    assert.ok(s.toolId && tools.some((t) => t.id === s.toolId), `${s.action} names no real tool`);
    assert.ok(s.rationale.length > 20, `${s.action} gives no reason`);
    assert.ok(s.action.length > 0);
  });
});

test("the one-line summary says the same thing as the chain", () => {
  const blocked = plan(1.0, [MILL(1, 1.5)]);
  assert.equal(describeSubstitution(blocked), blocked.blocked);

  const exact = plan(0.5, [DRILL(1, 0.5)]);
  assert.match(describeSubstitution(exact), /one operation/);

  const chain = plan(1.0, [DRILL(1, 0.9375), BORE(2, 1.0)], true);
  const summary = describeSubstitution(chain);
  for (const s of chain.steps) assert.ok(summary.includes(s.action), `${s.action} missing from the summary`);
});

test("the plan is deterministic", () => {
  const tools = [DRILL(1, 0.9375), BORE(2, 1.0), MILL(3, 0.375)];
  assert.deepEqual(plan(1.0, tools, true), plan(1.0, tools, true));
});
