import { test } from "node:test";
import assert from "node:assert/strict";
import { parseNC } from "@/lib/nc/parse";
import { analyzeNC, type AnalysisContext } from "@/lib/nc/analyze";

/**
 * Two findings CANVAS ran on a plan it generated and never on a program a
 * shop handed it — which is the program most likely to have come from
 * somebody else's post with somebody else's tool lengths.
 */

const ctx = (over: Partial<AnalysisContext> = {}): AnalysisContext => ({
  stock: null,
  toolDiameters: { 1: 0.5, 2: 0.375 },
  rapidRate: 1000,
  axisAccel: null,
  ...over,
});

const GEOMETRY = {
  1: { description: '1/2" end mill', fluteLength: 1.0, stickout: 1.6 },
  2: { description: '3/8" end mill', fluteLength: 1.25, stickout: 1.6 },
};

const program = (lines: string[]) => parseNC(["%", "O0001", "G20 G17 G90 G54", ...lines, "M30", "%"].join("\n"));

/* ---- can the tool reach what it is asked to cut? ---- */

test("a tool programmed deeper than its stickout is flagged", () => {
  const p = program(["T2 M6", "S6000 M3", "G0 X0 Y0 Z0.1", "G1 Z-2.0 F5.", "G1 X1.0 F20."]);
  const a = analyzeNC(p, ctx({ toolGeometry: GEOMETRY }));
  const reach = a.findings.filter((f) => f.kind === "TOOL_REACH_REVIEW");
  assert.equal(reach.length, 1);
  assert.equal(reach[0].verdict, "REVIEW");
  assert.equal(reach[0].toolNumber, 2);
  assert.match(reach[0].detail, /2\.000/);
  assert.match(reach[0].detail, /1\.600/);
  // A reach warning is not a time saving.
  assert.equal(reach[0].seconds, 0);
});

test("the clearance bites, not just the bare stickout", () => {
  // 1.550 deep on 1.600 of stickout leaves 0.050 — inside the shop's 0.100
  // clearance. A bare `stickout >= depth` comparison would call this fine.
  //
  // The flute is deliberately long enough that the flute check CANNOT fire,
  // so only the clearance can produce this finding.
  const longFlute = { 2: { description: "em", fluteLength: 3.0, stickout: 1.6 } };
  const p = program(["T2 M6", "G0 X0 Y0 Z0.1", "G1 Z-1.55 F5."]);
  const a = analyzeNC(p, ctx({ toolGeometry: longFlute }));
  const reach = a.findings.filter((f) => f.kind === "TOOL_REACH_REVIEW");
  assert.equal(reach.length, 1, "0.050 of clearance passed as acceptable");
  assert.match(reach[0].detail, /clearance/);

  // And 1.400 deep on the same tool leaves 0.200 — comfortably clear.
  const ok = analyzeNC(program(["T2 M6", "G0 X0 Y0 Z0.1", "G1 Z-1.4 F5."]), ctx({ toolGeometry: longFlute }));
  assert.equal(ok.findings.filter((f) => f.kind === "TOOL_REACH_REVIEW").length, 0);
});

test("a cut deeper than the flute length is flagged even when the tool reaches", () => {
  // 1.4 deep: inside 1.6 of stickout, past a 1.25 flute. The shank would be
  // rubbing the wall.
  const p = program(["T2 M6", "G0 X0 Y0 Z0.1", "G1 Z-1.4 F5."]);
  const a = analyzeNC(p, ctx({ toolGeometry: { 2: { description: "em", fluteLength: 1.25, stickout: 2.5 } } }));
  const reach = a.findings.filter((f) => f.kind === "TOOL_REACH_REVIEW");
  assert.equal(reach.length, 1);
  assert.match(reach[0].detail, /flute length/);
  assert.ok(!/clearance/.test(reach[0].detail), "it claims the tool cannot reach when it can");
});

test("a shallow cut within both limits says nothing", () => {
  const p = program(["T2 M6", "G0 X0 Y0 Z0.1", "G1 Z-0.25 F5."]);
  const a = analyzeNC(p, ctx({ toolGeometry: GEOMETRY }));
  assert.equal(a.findings.filter((f) => f.kind === "TOOL_REACH_REVIEW").length, 0);
});

test("no crib record for a tool invents no reach finding", () => {
  const p = program(["T7 M6", "G0 X0 Y0 Z0.1", "G1 Z-3.0 F5."]);
  const a = analyzeNC(p, ctx({ toolGeometry: GEOMETRY }));
  assert.equal(a.findings.filter((f) => f.kind === "TOOL_REACH_REVIEW").length, 0);
});

test("a tool with no stickout recorded says so rather than passing", () => {
  const p = program(["T2 M6", "G0 X0 Y0 Z0.1", "G1 Z-2.0 F5."]);
  const a = analyzeNC(p, ctx({ toolGeometry: { 2: { description: "em", fluteLength: 0, stickout: 0 } } }));
  const reach = a.findings.filter((f) => f.kind === "TOOL_REACH_REVIEW");
  assert.equal(reach.length, 1);
  assert.equal(reach[0].verdict, "INSUFFICIENT_DATA");
});

test("no crib at all means no reach findings, not silent passes", () => {
  const p = program(["T2 M6", "G0 X0 Y0 Z0.1", "G1 Z-2.0 F5."]);
  const a = analyzeNC(p, ctx());
  assert.equal(a.findings.filter((f) => f.kind === "TOOL_REACH_REVIEW").length, 0);
});

/* ---- is a tool loaded more than once? ---- */

test("a tool loaded twice is reported, with the change count", () => {
  const p = program(["T1 M6", "G1 Z-0.1 F10.", "T2 M6", "G1 Z-0.1 F10.", "T1 M6", "G1 Z-0.2 F10."]);
  const a = analyzeNC(p, ctx());
  const seq = a.findings.filter((f) => f.kind === "SEQUENCING_OPPORTUNITY");
  assert.equal(seq.length, 1);
  assert.equal(seq[0].toolNumber, 1);
  assert.match(seq[0].detail, /loaded 2 times/);
  assert.match(seq[0].detail, /3 tool changes for 2 distinct tools/);
  // The lines cited are the M6 lines, not wherever that tool happened to cut.
  // Counting cutting segments instead would name a dozen lines per tool.
  const m6Lines = p.toolChanges.filter((t) => t.toolNumber === 1).map((t) => t.line);
  for (const line of m6Lines) assert.match(seq[0].detail, new RegExp(`\\b${line}\\b`));
  assert.equal((seq[0].detail.match(/\d+,|\d+\)/g) ?? []).length, m6Lines.length);
});

test("no saving is claimed, because no tool-change time is recorded", () => {
  const p = program(["T1 M6", "G1 Z-0.1 F10.", "T2 M6", "G1 Z-0.1 F10.", "T1 M6", "G1 Z-0.2 F10."]);
  const a = analyzeNC(p, ctx());
  const seq = a.findings.find((f) => f.kind === "SEQUENCING_OPPORTUNITY")!;
  assert.equal(seq.seconds, 0);
  assert.ok(
    seq.assumptions.some((x) => /no saving is claimed/i.test(x)),
    "the finding does not say why it prices nothing",
  );
  // And it does not pretend to know whether the revisit was wasteful.
  assert.ok(seq.assumptions.some((x) => /cannot tell a wasteful return from a deliberate one/i.test(x)));
});

test("each tool loaded once is not a finding", () => {
  const p = program(["T1 M6", "G1 Z-0.1 F10.", "T2 M6", "G1 Z-0.1 F10."]);
  const a = analyzeNC(p, ctx());
  assert.equal(a.findings.filter((f) => f.kind === "SEQUENCING_OPPORTUNITY").length, 0);
});

/* ---- a preselect is not a tool change ---- */

test("a T word mid-cut does not become a tool change or a reach finding", () => {
  // THE REGRESSION. A controller stages the next tool while the current one
  // is still cutting; `T2` alone is a preselect. Treating it as a change
  // stamped the deep cut T2 while T1 was in the spindle — a reach warning
  // naming the wrong tool, which is worse than none.
  const p = program(["T1 M6", "S6000 M3", "G0 X0 Y0 Z0.1", "G1 Z-0.5 F10.", "T2", "G1 Z-2.0 F5."]);
  assert.equal(p.toolChanges.length, 1, "a preselect was counted as a tool change");
  const cuts = p.segments.filter((s) => s.feed !== null);
  assert.ok(cuts.every((s) => s.toolNumber === 1), "a segment was attributed to the preselected tool");

  const a = analyzeNC(p, ctx({ toolGeometry: GEOMETRY }));
  assert.equal(a.findings.filter((f) => f.kind === "SEQUENCING_OPPORTUNITY").length, 0);
  const reach = a.findings.filter((f) => f.kind === "TOOL_REACH_REVIEW");
  assert.equal(reach.length, 1);
  assert.equal(reach[0].toolNumber, 1, "the deep cut was blamed on the tool that was only staged");
});

test("a program with no M6 says what it assumed about the tool", () => {
  const p = parseNC(["T3", "G1 Z-0.2 F10.", "M30"].join("\n"));
  assert.equal(p.segments.find((s) => s.feed !== null)?.toolNumber, 3);
  assert.ok(
    p.warnings.some((w) => /No M6 before the first cut/.test(w)),
    "the parser guessed the tool without saying so",
  );
});

/* ---- what was not checked ---- */

test("the load-direction check is declared as not run, not silently absent", () => {
  // A check that is silently missing reads as a check that passed.
  const a = analyzeNC(program(["T1 M6", "G1 Z-0.1 F10."]), ctx());
  const skipped = a.checksSkipped.find((c) => /load direction/i.test(c.check));
  assert.ok(skipped, "the load-direction check is not declared");
  assert.match(skipped!.reason, /magnitude, not a vector/);
  // And it emits no finding, because any direction it printed would be
  // invented: the force model is scalar and no jaw axis is recorded.
  assert.ok(a.findings.every((f) => !/WORKHOLDING/.test(f.kind)));
});

test("the new findings do not move the recoverable total", () => {
  const p = program(["T1 M6", "G1 Z-0.1 F10.", "T2 M6", "G1 Z-2.0 F5.", "T1 M6", "G1 Z-0.2 F10."]);
  const withGeometry = analyzeNC(p, ctx({ toolGeometry: GEOMETRY }));
  const without = analyzeNC(p, ctx());
  assert.ok(withGeometry.findings.length > without.findings.length, "the fixture produces no new findings");
  assert.equal(withGeometry.recoverableSeconds, without.recoverableSeconds);
});
