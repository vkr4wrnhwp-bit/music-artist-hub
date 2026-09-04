import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { toolLife, minutesPerTool, formatMinutes, type ToolLifeInput } from "@/lib/engines/tool-life";

/**
 * TOOL LIFE
 *
 * `Tool.lifeRemaining` was a 0-1 float. It was required on the tool form,
 * rendered on the crib page as a colour-coded percentage — green above 40%,
 * review above 15%, risk below — and nothing in the system ever changed it.
 * It was whatever somebody typed when the tool was added, presented ever after
 * as a live gauge. "T2 · 100%" in green is read by a machinist as a tool with
 * plenty of edge left, and that is worse than showing nothing.
 *
 * What replaced it counts minutes from jobs marked complete, says out loud
 * that the count is a floor rather than a total, and refuses to put a
 * percentage on a tool with no expected life recorded.
 */

const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");

const tool = (over: Partial<ToolLifeInput> = {}): ToolLifeInput => ({
  description: '1/2" 3-flute carbide end mill',
  minutesUsed: 0,
  partsCut: 0,
  expectedLifeMinutes: 240,
  lifeCountedFrom: new Date("2026-07-01T00:00:00Z"),
  regrindCount: 0,
  ...over,
});

/* ---------------- No denominator, no percentage ---------------- */

test("a tool with no expected life recorded gets no percentage at all", () => {
  /*
   * Inventing a denominator is how the 0-1 float got there in the first
   * place. There is nothing to be a percentage of, so the verdict carries the
   * minutes and says what is missing.
   */
  const l = toolLife(tool({ expectedLifeMinutes: 0, minutesUsed: 140, partsCut: 12 }));
  assert.equal(l.state, "UNTRACKED");
  assert.equal(l.fractionUsed, null, "a fraction was computed with nothing to measure against");
  assert.equal(/%/.test(l.summary), false, "the summary put a percentage on a tool with no expected life");
  assert.match(l.summary, /No expected life recorded/);
  assert.match(l.summary, /140 min over 12 parts/);
});

test("a negative or absent expected life is not a denominator either", () => {
  // NaN and negatives reach this from a form somebody edited, and `x > 0` is
  // the only comparison that refuses all three.
  for (const bad of [-1, Number.NaN]) {
    const l = toolLife(tool({ expectedLifeMinutes: bad, minutesUsed: 10 }));
    assert.equal(l.state, "UNTRACKED", `expectedLifeMinutes ${bad} was treated as a denominator`);
    assert.equal(l.fractionUsed, null);
  }
});

/* ---------------- The states ---------------- */

test("an edge nothing has been charged to is unused, not fresh-looking", () => {
  const l = toolLife(tool());
  assert.equal(l.state, "FRESH");
  assert.equal(l.fractionUsed, 0);
  assert.match(l.summary, /Nothing recorded against it yet/);
  assert.match(l.summary, /240 min/);
});

test("part way through, the fraction is minutes over expected", () => {
  const l = toolLife(tool({ minutesUsed: 60, partsCut: 5 }));
  assert.equal(l.state, "IN_USE");
  assert.equal(l.fractionUsed, 0.25);
  assert.match(l.summary, /60 min over 5 parts/);
  assert.match(l.summary, /against 240 min expected/);
});

test("the near-end threshold is 80 percent and it includes 80 percent", () => {
  // The boundary a mutation walks straight through. 0.8 exactly is the point
  // a shop wants somebody looking at the edge before the next job.
  assert.equal(toolLife(tool({ minutesUsed: 192 })).state, "NEAR_END");
  assert.equal(toolLife(tool({ minutesUsed: 191.9 })).state, "IN_USE");
});

test("past the expected life it says so, and says to look at the edge", () => {
  assert.equal(toolLife(tool({ minutesUsed: 240 })).state, "PAST_EXPECTED");
  const l = toolLife(tool({ minutesUsed: 300, partsCut: 40 }));
  assert.equal(l.state, "PAST_EXPECTED");
  assert.ok(l.fractionUsed! > 1);
  assert.match(l.summary, /past the 240 min/);
  assert.match(l.summary, /Look at the edge before the next job/);
});

/* ---------------- The caveat is the point ---------------- */

test("every verdict says the count is a floor and not a total", () => {
  /*
   * A machinist who believes 40% is left and actually has 5% is the person
   * this feature exists to protect. The caveat is not a footnote — it is the
   * difference between a figure that can be acted on and one that cannot.
   */
  for (const t of [
    tool(),
    tool({ minutesUsed: 60 }),
    tool({ minutesUsed: 300 }),
    tool({ expectedLifeMinutes: 0, minutesUsed: 60 }),
  ]) {
    const l = toolLife(t);
    assert.match(l.caveat, /floor and not a total/, `${l.state} did not qualify the count`);
    assert.match(l.caveat, /jobs marked complete/);
    assert.match(l.caveat, /borrowed for another part/);
  }
});

test("a count with no start date says so rather than implying one", () => {
  assert.match(toolLife(tool({ minutesUsed: 60, lifeCountedFrom: null })).summary, /since nobody said when/);
  assert.match(toolLife(tool({ minutesUsed: 60 })).summary, /since 2026-07-01/);
});

test("regrinds are named in the caveat, because a reground cutter is not the catalogue cutter", () => {
  assert.equal(/Reground/.test(toolLife(tool()).caveat), false);
  assert.match(toolLife(tool({ regrindCount: 1 })).caveat, /Reground 1 time\./);
  assert.match(toolLife(tool({ regrindCount: 3 })).caveat, /Reground 3 times\./);
});

test("a real charge never rounds down to nothing", () => {
  /*
   * A spot drill charged 0.4 min of a job read "0 min over 1 part" at
   * whole-minute resolution, which says the tool did nothing. Same class of
   * error as the float this replaced, just small — wrong in a direction a
   * machinist cannot see. Found by completing a job in the browser, not here.
   */
  assert.equal(formatMinutes(0), "0");
  assert.equal(formatMinutes(0.02), "under 0.1");
  assert.equal(formatMinutes(0.4), "0.4");
  assert.equal(formatMinutes(9.5), "9.5");
  assert.equal(formatMinutes(64.2), "64");
  assert.match(toolLife(tool({ minutesUsed: 0.4, partsCut: 1 })).summary, /0\.4 min over 1 part/);
  assert.equal(/\b0 min\b/.test(toolLife(tool({ minutesUsed: 0.02, partsCut: 1 })).summary), false);
});

test("a tool charged a fraction of a minute is not IN_USE at zero percent on the page", () => {
  // "0% used" and "unused" are the same sentence to somebody glancing down a
  // column, and one of them is false.
  const src = strip(readFileSync("src/app/(app)/tools/page.tsx", "utf8"));
  assert.ok(/pct < 1 \? "under 1% used"/.test(src), "a counted tool can render as 0% used");
});

test("one part reads as one part", () => {
  assert.match(toolLife(tool({ minutesUsed: 8, partsCut: 1 })).summary, /over 1 part /);
  assert.match(toolLife(tool({ minutesUsed: 8, partsCut: 2 })).summary, /over 2 parts /);
});

/* ---------------- What a completed job charges ---------------- */

const tp = (toolId: string, cycleTimeMinutes: number) => ({ toolId, cycleTimeMinutes });

test("each tool is charged its own cutting time, times the quantity made", () => {
  const { byTool, source } = minutesPerTool([tp("a", 4), tp("b", 6)], 10, null);
  assert.equal(source, "ESTIMATED");
  assert.equal(byTool.get("a"), 40);
  assert.equal(byTool.get("b"), 60);
});

test("a tool used by two operations is charged for both", () => {
  // The bug this pins: a Map assignment rather than an accumulation charges a
  // roughing-and-finishing tool for the finish pass only.
  const { byTool } = minutesPerTool([tp("a", 4), tp("a", 3), tp("b", 1)], 1, null);
  assert.equal(byTool.get("a"), 7);
  assert.equal(byTool.get("b"), 1);
});

test("a recorded cycle time is what the tool was in the cut for, and it is apportioned", () => {
  /*
   * Actual time is one number for the whole job. There is nothing per tool to
   * measure against, so it is split in the ratio of the estimates — and the
   * source says MEASURED for the total, not for the share.
   */
  const { byTool, source } = minutesPerTool([tp("a", 4), tp("b", 6)], 2, 20);
  assert.equal(source, "MEASURED");
  // 20 actual against 10 estimated is a scale of 2, then 2 parts.
  assert.equal(byTool.get("a"), 16);
  assert.equal(byTool.get("b"), 24);
  const total = [...byTool.values()].reduce((s, m) => s + m, 0);
  assert.equal(total, 40, "the charged total is not the recorded cycle time times the quantity");
});

test("a cycle time of zero or none falls back to the estimate and says so", () => {
  for (const actual of [null, 0]) {
    const { source, byTool } = minutesPerTool([tp("a", 4)], 1, actual);
    assert.equal(source, "ESTIMATED", `actual ${actual} was treated as a measurement`);
    assert.equal(byTool.get("a"), 4);
  }
});

test("a job with no estimated cutting time cannot apportion a measured one", () => {
  // Dividing by a zero estimate is how every tool ends up charged Infinity.
  const { byTool, source } = minutesPerTool([tp("a", 0)], 5, 30);
  assert.equal(source, "ESTIMATED");
  assert.equal(byTool.get("a"), 0);
  assert.ok(Number.isFinite(byTool.get("a")!));
});

test("a quantity nobody recorded charges one part, not none", () => {
  // A job row with quantity 0 would otherwise charge zero minutes for work
  // that was done, and the whole count is already a floor.
  assert.equal(minutesPerTool([tp("a", 4)], 0, null).byTool.get("a"), 4);
});

test("no toolpaths charges nothing", () => {
  const { byTool, source } = minutesPerTool([], 5, 30);
  assert.equal(byTool.size, 0);
  assert.equal(source, "ESTIMATED");
});

/* ---------------- The write path ---------------- */

test("a completed job charges its tools, scoped to the shop that ran it", () => {
  const src = strip(readFileSync("src/app/(app)/jobs/actions.ts", "utf8"));
  assert.ok(/minutesPerTool\(/.test(src), "nothing charges tools when a job completes");
  // Org from the session, id re-checked against it. A toolpath's toolId is a
  // value another shop could name.
  assert.ok(
    /db\.tool\.findFirst\(\{\s*where: \{ id: toolId, organizationId: user\.organizationId \}/.test(src),
    "a tool is charged without being checked against the session's organisation",
  );
  assert.ok(/minutesUsed: \{ increment:/.test(src), "minutes are set rather than accumulated");
  assert.ok(/partsCut: \{ increment:/.test(src));
  // Placeholders are the operations CANVAS could not plan. Charging a tool for
  // motion that does not exist is inventing time.
  assert.ok(/filter\(\(tp\) => !tp\.isPlaceholder\)/.test(src), "placeholder toolpaths charge tool life");
  assert.ok(/actorType: "SYSTEM"/.test(src), "the accumulation is logged as a human action");
});

test("the count gets a start date the first time something is charged to it", () => {
  // Otherwise the crib reads "since nobody said when" for ever, which is a
  // figure with no window around it.
  const src = strip(readFileSync("src/app/(app)/jobs/actions.ts", "utf8"));
  assert.ok(
    /owned\.lifeCountedFrom === null \? \{ lifeCountedFrom: new Date\(\) \} : \{\}/.test(src),
    "lifeCountedFrom is never written, or an existing start date is overwritten",
  );
});

test("a fresh edge restarts the count and keeps the old one in the trail", () => {
  /*
   * Minutes never fall on their own, which is right until somebody regrinds
   * the cutter or swaps the inserts. A count that cannot be restarted reads
   * PAST_EXPECTED on a brand new edge — wrong in the direction of alarm, and
   * ignored exactly as fast as one wrong the other way.
   */
  const src = strip(readFileSync("src/app/(app)/tools/actions.ts", "utf8"));
  assert.ok(/export async function freshEdge/.test(src), "there is no way to restart the count");
  assert.ok(/minutesUsed: 0,\s*partsCut: 0,\s*lifeCountedFrom: new Date\(\)/.test(src));
  assert.ok(/organizationId: user\.organizationId/.test(src), "the tool is not scoped to the session's shop");
  assert.ok(/regrindCount: \{ increment: 1 \}/.test(src), "a regrind does not count as a regrind");
  assert.ok(
    /oldValue: `\$\{formatMinutes\(existing\.minutesUsed\)\} min over \$\{existing\.partsCut\} part/.test(src),
    "the cleared count is not kept in the audit trail",
  );
  assert.ok(/actorType: "HUMAN"/.test(src));
  // What went in decides the condition, so an unnamed event cannot clear it.
  assert.ok(/if \(!event\) \{/.test(src), "the count can be cleared without saying what went in");
});

test("nothing reads the dead float any more", () => {
  /*
   * It stays in the schema so no shop's data is thrown away, and it stays in
   * the domain type so the mapper is honest about what the row holds. What it
   * must never do again is reach a screen: a colour-coded gauge nothing
   * updates is the defect, not the column.
   */
  for (const f of [
    "src/app/(app)/tools/page.tsx",
    "src/app/(app)/tools/tool-fields.ts",
    "src/app/(app)/tools/[id]/edit/page.tsx",
  ]) {
    const src = strip(readFileSync(f, "utf8"));
    assert.equal(/lifeRemaining/.test(src), false, `${f} still reads lifeRemaining`);
  }
});

test("the crib page shows what the tool has done, through the engine", () => {
  const src = strip(readFileSync("src/app/(app)/tools/page.tsx", "utf8"));
  assert.ok(/toolLife\(\{/.test(src), "the crib page does not read the life engine");
  // UNTRACKED is a missing input, not a worn cutter. Colouring it as risk is
  // the same lie in the other direction.
  assert.ok(/UNTRACKED: "unknown"/.test(src));
  assert.ok(/PAST_EXPECTED: "risk"/.test(src));
  // The caveat travels with the number rather than living somewhere else.
  assert.ok(/life\.caveat/.test(src), "the number is shown without what it does not include");
});
