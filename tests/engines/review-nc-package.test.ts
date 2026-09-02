import { test } from "node:test";
import assert from "node:assert/strict";
import { reviewPackage, type ReviewInput } from "@/lib/engines/review";
import { parseNC } from "@/lib/nc/parse";
import { analyzeNC } from "@/lib/nc/analyze";

/**
 * The one piece of the job-package import that exists: a shop's own NC
 * program, uploaded through the analyzer, read by the pre-flight review.
 *
 * The distinction under test is what a review is FOR. The analyzer produces
 * cycle-time opportunities and engineering conditions from the same parse,
 * and only the second kind belongs in a list a machinist counts before Cycle
 * Start. A review padded with "you could save 40 seconds" is a review that
 * gets skimmed.
 */

const TOOL = {
  id: "t1", toolNumber: 2, description: '3/8" end mill', toolClass: "FLAT_END_MILL",
  diameter: 0.375, fluteLength: 1.25, overallLength: 3, stickout: 1.6, holderNoseDiameter: 1.5,
  flutes: 3, material: "CARBIDE", maxRPM: 8100,
};

const base = (over: Partial<ReviewInput> = {}): ReviewInput =>
  ({
    setups: [],
    workholdingBySetup: {},
    device: null,
    machine: null,
    tools: [TOOL],
    movesByOperation: {},
    capability: [],
    stockZ: 0.75,
    ...over,
  }) as unknown as ReviewInput;

const analyse = (lines: string[], jawAxis: string | null = null) =>
  analyzeNC(parseNC(["%", "O0001", "G20 G17 G90 G54", ...lines, "M30", "%"].join("\n")), {
    stock: null,
    toolDiameters: { 2: 0.375 },
    toolGeometry: { 2: { description: '3/8" end mill', fluteLength: 1.25, stickout: 1.6, source: "CRIB" } },
    workholding: jawAxis ? { jawAxis, hasPositiveStop: false, deviceDescription: null } : undefined,
    rapidRate: 1000,
    axisAccel: null,
  });

const uploaded = (analysis: ReturnType<typeof analyse>, over: Record<string, unknown> = {}) => ({
  filename: "OP10.nc",
  digest: "abc123",
  analysis,
  ...over,
});

const ncFindings = (r: ReturnType<typeof reviewPackage>) => r.findings.filter((f) => f.key.startsWith("nc-uploaded:"));

/* ---------------- What crosses into the review, and what does not ---------------- */

test("a tool programmed past its stickout becomes a HIGH review finding", () => {
  const a = analyse(["T2 M6", "G0 X0 Y0 Z0.1", "G1 Z-2.0 F5."]);
  const r = reviewPackage(base({ uploadedProgram: uploaded(a) } as Partial<ReviewInput>));
  const f = ncFindings(r);
  assert.equal(f.length, 1);
  assert.equal(f[0].severity, "HIGH");
  assert.equal(f[0].location.context, "CUT");
  // The detail is the engine's own words, not a paraphrase written here.
  assert.equal(f[0].detail, a.findings.find((x) => x.kind === "TOOL_REACH_REVIEW")!.detail);
});

test("cycle-time findings do not become review findings", () => {
  // Air cutting and a tall retract are real analyzer findings and worth
  // reading. They are not reasons not to run the program, and a review that
  // counts them tells a machinist there are more things wrong than there are.
  const a = analyse([
    "T2 M6",
    "G0 X0 Y0 Z0.1",
    "G1 Z-0.1 F5.",
    "G1 X1.0 F20.",
    "G0 Z6.0",
    "G0 X4.0 Y4.0",
    "G0 Z0.1",
    "G1 Z-0.1 F5.",
  ]);
  const timeKinds = a.findings.filter((f) => !/TOOL_REACH|WORKHOLDING/.test(f.kind));
  assert.ok(timeKinds.length > 0, "the fixture produces no cycle-time findings to exclude");

  const r = reviewPackage(base({ uploadedProgram: uploaded(a) } as Partial<ReviewInput>));
  assert.equal(ncFindings(r).length, 0);
  // And they are not silently dropped: the review says where they went.
  assert.ok(r.checksSkipped.some((c) => /Cycle time in OP10\.nc/.test(c.check)));
});

test("a cut running across the jaws becomes a MEDIUM finding pointing at HOLD", () => {
  const a = analyse(["T2 M6", "G0 X0 Y0 Z0.1", "G1 Z-0.2 F5.", "G1 Y4.0 F20."], "X");
  const r = reviewPackage(base({ uploadedProgram: uploaded(a) } as Partial<ReviewInput>));
  const f = ncFindings(r).filter((x) => x.key.includes("WORKHOLDING"));
  assert.equal(f.length, 1);
  assert.equal(f[0].severity, "MEDIUM");
  assert.equal(f[0].location.context, "HOLD");
});

test("a check that could not be completed is MEDIUM and says so, not HIGH", () => {
  // A tool with no stickout recorded gives INSUFFICIENT_DATA. Ranking that
  // alongside a tool that demonstrably cannot reach would claim a finding the
  // evidence does not support.
  const a = analyzeNC(parseNC(["T2 M6", "G0 X0 Y0 Z0.1", "G1 Z-2.0 F5.", "M30"].join("\n")), {
    stock: null,
    toolDiameters: { 2: 0.375 },
    toolGeometry: { 2: { description: "em", fluteLength: 0, stickout: 0, source: "CRIB" } },
    rapidRate: 1000,
    axisAccel: null,
  });
  const r = reviewPackage(base({ uploadedProgram: uploaded(a) } as Partial<ReviewInput>));
  const f = ncFindings(r);
  assert.equal(f.length, 1);
  assert.equal(f[0].severity, "MEDIUM");
  assert.match(f[0].title, /could not be checked/);
  assert.match(f[0].recommendation, /missing measurement/);
});

/* ---------------- Identity and provenance ---------------- */

test("a finding is keyed to the program's bytes, so an answer cannot carry to another program", () => {
  const a = analyse(["T2 M6", "G0 X0 Y0 Z0.1", "G1 Z-2.0 F5."]);
  const one = ncFindings(reviewPackage(base({ uploadedProgram: uploaded(a) } as Partial<ReviewInput>)));
  const two = ncFindings(reviewPackage(base({ uploadedProgram: uploaded(a, { digest: "different" }) } as Partial<ReviewInput>)));
  assert.notEqual(one[0].key, two[0].key);
  // Same bytes, same key — otherwise nothing could be tracked across reviews.
  const again = ncFindings(reviewPackage(base({ uploadedProgram: uploaded(a) } as Partial<ReviewInput>)));
  assert.equal(one[0].key, again[0].key);
});

test("an uploaded finding points at no setup, operation or feature", () => {
  // Nothing in posted code maps to a CANVAS setup. Guessing one would aim
  // SHOW ME at geometry the program may have nothing to do with.
  //
  // The package deliberately HAS a setup here, so "no location" has to be a
  // decision rather than an artefact of there being nothing to point at.
  const a = analyse(["T2 M6", "G0 X0 Y0 Z0.1", "G1 Z-2.0 F5."]);
  const withSetup = base({
    setups: [
      {
        id: "s1", name: "Op 1", sequence: 1, gripDepth: 0.375, stockProjection: 0.375,
        operations: [{ id: "o1", label: "Rough pocket", toolId: "t1", finalZ: -0.125, type: "POCKET_2D" }],
      },
    ],
    uploadedProgram: uploaded(a),
  } as unknown as Partial<ReviewInput>);
  const f = ncFindings(reviewPackage(withSetup))[0];
  assert.equal(f.location.setupId, null);
  assert.equal(f.location.operationId, null);
  assert.equal(f.location.featureId, null);
  assert.equal(f.location.point, null);
});

test("the finding names the program and the line it is in", () => {
  const a = analyse(["T2 M6", "G0 X0 Y0 Z0.1", "G1 Z-2.0 F5."]);
  const f = ncFindings(reviewPackage(base({ uploadedProgram: uploaded(a) } as Partial<ReviewInput>)))[0];
  assert.equal(f.evidence.find((e) => e.label === "Program")?.value, "OP10.nc");
  const line = a.findings.find((x) => x.kind === "TOOL_REACH_REVIEW")!.line;
  assert.equal(f.evidence.find((e) => e.label === "Line")?.value, String(line));
  assert.equal(f.evidence.find((e) => e.label === "Tool")?.value, "T2");
});

/* ---------------- Absence is declared, not silent ---------------- */

test("with no program uploaded the review says the shop's code was not read", () => {
  const r = reviewPackage(base());
  assert.equal(ncFindings(r).length, 0);
  const skipped = r.checksSkipped.find((c) => /shop's own NC program/i.test(c.check));
  assert.ok(skipped, "a review that never saw the running code does not say so");
  assert.match(skipped!.reason, /No program has been uploaded/);
  // And it does not claim to have run the check.
  assert.ok(!r.checksRun.some((c) => /uploaded program/i.test(c)));
});

test("the program's own skipped checks are carried through, named by file", () => {
  // The analyzer declares what it did not check. Dropping that on the way
  // into the review turns a check that did not run into one that passed.
  const a = analyse(["T2 M6", "G0 X0 Y0 Z0.1", "G1 Z-0.1 F5.", "G1 X1.0 F20."]);
  assert.ok(a.checksSkipped.length > 0, "the fixture skips no checks");
  const r = reviewPackage(base({ uploadedProgram: uploaded(a) } as Partial<ReviewInput>));
  for (const c of a.checksSkipped) {
    assert.ok(
      r.checksSkipped.some((x) => x.check === `${c.check} (OP10.nc)` && x.reason === c.reason),
      `the review dropped "${c.check}"`,
    );
  }
  assert.ok(r.checksRun.some((c) => /OP10\.nc/.test(c)));
});

test("uploaded findings are ranked with the rest, not appended after them", () => {
  // A HIGH from the program must not sort below a MEDIUM from the package
  // just because it arrived last.
  const a = analyse(["T2 M6", "G0 X0 Y0 Z0.1", "G1 Z-2.0 F5."]);
  const r = reviewPackage(
    base({
      uploadedProgram: uploaded(a),
      capability: [],
    } as Partial<ReviewInput>),
  );
  const severities = r.findings.map((f) => f.severity);
  const order = { HIGH: 0, MEDIUM: 1, LOW: 2 } as const;
  for (let i = 1; i < severities.length; i++) {
    assert.ok(order[severities[i - 1]] <= order[severities[i]], "findings are not ranked by severity");
  }
  assert.equal(r.highCount, r.findings.filter((f) => f.severity === "HIGH").length);
});
