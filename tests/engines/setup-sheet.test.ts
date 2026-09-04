import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { buildSetupSheet } from "@/lib/setup-sheet";
import { PROGRAM_ORIGIN } from "@/lib/program-origin";
import type { ManufacturingPackage } from "@/lib/package";

/**
 * THE SETUP SHEET
 *
 * The dangerous setup sheet is the one that leaves a field blank. A blank grip
 * depth reads as "no grip depth needed"; a missing parallel height reads as
 * "sits on the floor of the vise". So the assertions here are mostly about
 * absence being STATED — a sheet that omits what it does not know is worse
 * than no sheet, because somebody sets up from it.
 */

const feature = (over: Record<string, unknown> = {}) => ({
  id: "f1",
  kind: "BORE",
  label: "1.000 bearing bore",
  functionalRole: "BEARING_SEAT",
  critical: true,
  diameter: 1.0,
  centerX: 0,
  centerY: 0,
  depth: 0.5,
  tolerance: { plus: 0.0005, minus: 0.0005 },
  inspectionMethod: "Bore gauge against a set ring",
  ...over,
});

const tool = (over: Record<string, unknown> = {}) => ({
  id: "t1",
  toolNumber: 4,
  description: "1/2 4FL carbide",
  diameter: 0.5,
  stickout: 1.25,
  pocket: 4,
  ...over,
});

const pkg = (over: Record<string, unknown> = {}): ManufacturingPackage =>
  ({
    revision: {
      partName: "Bearing support",
      partNumber: "BS-1041",
      revision: "A",
      units: "IN",
      stock: { form: "RECTANGULAR", x: 6, y: 4, z: 1, material: "Aluminum 6061", condition: "T6511" },
      features: [feature()],
      intent: {
        material: { value: "Aluminum 6061" },
        materialCondition: { value: "T6511" },
      },
    },
    setups: [
      {
        id: "s1",
        sequence: 1,
        name: "Top face and bore",
        orientation: "TOP",
        workOffset: "G54",
        datumNote: "Pick up the left rear corner and shift to centre.",
        machine: { manufacturer: "Haas", model: "VF-2" },
        workholding: { manufacturer: "Kurt", model: "DX6" },
        jawSurface: "SERRATED",
        jawAxis: "X",
        gripDepth: 0.5,
        gripLength: 4,
        parallelHeight: 0.75,
        stockProjection: 0.5,
        hasPositiveStop: true,
        geometrySource: "MEASURED",
        operations: [
          {
            id: "o1",
            sequence: 1,
            type: "BORE",
            label: "Bore 1.000",
            toolId: "t1",
            featureId: "f1",
            topZ: 0,
            finalZ: -0.5,
            tool: tool(),
            feature: { label: "1.000 bearing bore" },
          },
        ],
      },
    ],
    assignedTools: [{ id: "t1", holder: "CAT40 ER32", actualStickout: 1.31 }],
    workholdingBySetup: { s1: { level: "SAFE", holdingMargin: { margin: 3.2 } } },
    toolpaths: [
      { operationId: "o1", isPlaceholder: false, cycleTimeMinutes: 2.5, parameters: { rpm: 6000, feed: 42 } },
    ],
    readiness: { overall: "READY_TO_RUN", gates: [] },
    ...over,
  }) as unknown as ManufacturingPackage;

const sheet = (over: Record<string, unknown> = {}) => buildSetupSheet(pkg(over), "s1")!;

/* ---------------- How much air the part needs under it ---------------- */

const deepen = (finalZ: number) => {
  const p = pkg();
  (p.setups[0].operations[0] as unknown as Record<string, unknown>).finalZ = finalZ;
  return buildSetupSheet(p, "s1")!;
};

test("a cut that finishes below the stock says how far the part has to stand off", () => {
  /*
   * A through hole is drilled past the material by the drill's own point plus
   * a break allowance, so the tip finishes below the bottom of the stock. On
   * the sheet that reads as a Z deeper than the part is thick, and a machinist
   * who cannot see why will shorten it at the control — or set the part flat on
   * the parallels and drill them.
   */
  const row = deepen(-1.08).workholding.find((f) => f.label === "Clearance under part");
  assert.ok(row, "the sheet does not say the cut goes below the part");
  assert.match(row.value!, /^0\.080″/);
  assert.match(row.value!, /off the parallels by at least that, or run it on a sacrificial plate/);
});

test("a setup that stays inside the stock does not invent a clearance", () => {
  const has = (finalZ: number) => deepen(finalZ).workholding.some((f) => f.label === "Clearance under part");
  assert.equal(has(-0.5), false);
  // Exactly at the bottom is not below it.
  assert.equal(has(-1), false);
});

/* ---------------- It is about a setup, not a part ---------------- */

test("an unknown setup returns nothing rather than a sheet about some other setup", () => {
  assert.equal(buildSetupSheet(pkg(), "nope"), null);
});

/* ---------------- Program zero ---------------- */

test("the sheet states where program zero is", () => {
  const s = sheet();
  // The one sentence that decides whether the part is cut in the right place.
  // It lived in two source comments and reached the operator in neither.
  assert.equal(s.origin.xy, PROGRAM_ORIGIN.xy);
  assert.equal(s.origin.z, PROGRAM_ORIGIN.z);
  assert.match(s.origin.datumNote!, /left rear corner/);
});

/* ---------------- Tools ---------------- */

test("the tool table carries what a machinist sets, not what the catalogue said", () => {
  const t = sheet().tools[0];
  assert.equal(t.toolNumber, 4);
  // Measured stickout wins: it is the number that decides reach and the number
  // that goes on the presetter.
  assert.equal(t.stickout, 1.31);
  assert.equal(t.holder, "CAT40 ER32");
  assert.equal(t.pocket, 4);
  assert.deepEqual(t.operationLabels, ["Bore 1.000"]);
});

test("a tool with no pocket is named as one to load", () => {
  const p = pkg();
  (p.setups[0].operations[0] as unknown as { tool: Record<string, unknown> }).tool = tool({ pocket: null });
  const s = buildSetupSheet(p, "s1")!;
  assert.equal(s.tools[0].pocket, null);
  assert.ok(s.unknowns.some((u) => /T4[\s\S]*not assigned to a pocket/.test(u)), s.unknowns.join(" | "));
});

test("tool length offsets are always called out as set at the machine", () => {
  // H equals the tool number in this post. That is a convention, not a
  // measurement, and an operator who assumes CANVAS set the offsets crashes.
  assert.ok(sheet().unknowns.some((u) => /length offsets are set at the machine/i.test(u)));
});

/* ---------------- Operations ---------------- */

test("the sheet tells the machinist to set the D registers", () => {
  // Contours are cut with the control compensating now, so D holds the size.
  // A machinist who does not know that reaches for an offset that is zero.
  assert.ok(sheet().unknowns.some((u) => /Set the D register/i.test(u)));
});

test("speeds, feeds and cycle time come from the toolpath that was generated", () => {
  const o = sheet().operations[0];
  assert.equal(o.rpm, 6000);
  assert.equal(o.feed, 42);
  assert.equal(o.cycleMinutes, 2.5);
  assert.equal(o.noMotion, false);
});

test("an operation with no toolpath is marked, and named in the unknowns", () => {
  const s = sheet({ toolpaths: [] });
  assert.equal(s.operations[0].noMotion, true);
  assert.equal(s.operations[0].rpm, null, "a speed was printed for an operation that produced no motion");
  assert.ok(s.unknowns.some((u) => /written into the program as a skipped comment/i.test(u)));
});

test("cycle time refuses to total when an operation produced no path", () => {
  // A total that silently omits an operation is a number a shop quotes from.
  assert.equal(sheet({ toolpaths: [] }).cycleMinutes, null);
  assert.equal(sheet().cycleMinutes, 2.5);
});

/* ---------------- Absence is printed ---------------- */

test("a missing grip depth is stated, not left blank", () => {
  const p = pkg();
  (p.setups[0] as unknown as Record<string, unknown>).gripDepth = null;
  const s = buildSetupSheet(p, "s1")!;
  assert.equal(s.workholding.find((f) => f.label === "Grip depth")!.value, null);
  assert.ok(s.unknowns.some((u) => /Grip depth is not recorded/i.test(u)));
});

test("planned geometry is not presented as a measured setup", () => {
  const p = pkg();
  (p.setups[0] as unknown as Record<string, unknown>).geometrySource = "PLANNED";
  const s = buildSetupSheet(p, "s1")!;
  assert.equal(s.geometrySource, "PLANNED");
  assert.ok(
    s.unknowns.some((u) => /setup nobody has built yet/i.test(u)),
    "a planned grip was printed as though somebody had set it",
  );
});

test("no stock is the first thing the sheet says it cannot work without", () => {
  const p = pkg();
  (p.revision as unknown as Record<string, unknown>).stock = null;
  const s = buildSetupSheet(p, "s1")!;
  assert.ok(s.unknowns.some((u) => /Stock is not defined/i.test(u)));
});

test("a toleranced feature with no inspection method is named", () => {
  const p = pkg();
  (p.revision as unknown as Record<string, unknown>).features = [feature({ inspectionMethod: undefined })];
  const s = buildSetupSheet(p, "s1")!;
  assert.equal(s.characteristics[0].method, null);
  assert.ok(s.unknowns.some((u) => /no inspection method assigned/i.test(u)));
});

/* ---------------- What has to be checked ---------------- */

test("a characteristic prints its governing dimension, or none at all", () => {
  const c = sheet().characteristics[0];
  assert.match(c.nominal!, /1\.0000″ diameter/);
  assert.equal(c.tolerance, "±0.0005");

  // A rectangular pocket carries width, length and depth. Picking one and
  // printing it as THE nominal would look authoritative and describe the
  // wrong dimension — the same rule the inspection plan derives under.
  const p = pkg();
  (p.revision as unknown as Record<string, unknown>).features = [
    feature({ kind: "RECT_POCKET", label: "pocket", width: 2, length: 1, depth: 0.25 }),
  ];
  assert.equal(buildSetupSheet(p, "s1")!.characteristics[0].nominal, null);
});

/* ---------------- Coverage and the gate state ---------------- */

test("features nobody cuts are named on the sheet", () => {
  const p = pkg();
  (p.revision as unknown as Record<string, unknown>).features = [feature(), feature({ id: "f2", label: "M6 tap" })];
  const s = buildSetupSheet(p, "s1")!;
  assert.ok(s.unknowns.some((u) => /cut by no operation anywhere in the plan: M6 tap/.test(u)));
});

test("a feature somebody said is made elsewhere becomes an instruction on the sheet", () => {
  const p = pkg();
  (p.revision as unknown as Record<string, unknown>).features = [
    feature(),
    feature({ id: "f2", label: "0.02 chamfer", notMachinedReason: "broken at the bench", notMachinedBy: "R. Hale" }),
  ];
  const s = buildSetupSheet(p, "s1")!;
  assert.deepEqual(s.notMadeHere, [{ label: "0.02 chamfer", reason: "broken at the bench", by: "R. Hale" }]);
  // And it is NOT in the unknowns: somebody accounted for it.
  assert.equal(s.unknowns.some((u) => /0\.02 chamfer/.test(u)), false);
});

test("the sheet prints the blocking gates, so it is never mistaken for clearance", () => {
  const s = sheet({
    readiness: {
      overall: "NOT_READY_TO_RUN",
      gates: [
        { label: "Workholding", status: "MISSING", blocking: true, detail: "Workholding is not defined." },
        { label: "NC post", status: "REVIEW", blocking: false, detail: "Development post." },
        { label: "Geometry", status: "PASS", blocking: true, detail: "2 features defined." },
      ],
    },
  });
  assert.equal(s.gateState.overall, "NOT_READY_TO_RUN");
  assert.deepEqual(s.gateState.blocking.map((g) => g.label), ["Workholding"]);
});

test("the development notice is not conditional", () => {
  // There is no package state that makes a development post a certified one,
  // so there is no branch here to get wrong.
  assert.match(sheet().developmentNotice, /DEVELOPMENT post/);
  assert.match(sheet().developmentNotice, /feed hold/);
  const src = readFileSync("src/lib/setup-sheet.ts", "utf8");
  assert.equal(
    /developmentNotice:\s*\n?\s*[^,]*\?/.test(src),
    false,
    "the development notice became conditional",
  );
});

/* ---------------- One origin, everywhere it is stated ---------------- */

test("program zero is stated from one place", () => {
  const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
  const sheetSrc = strip(readFileSync("src/lib/setup-sheet.ts", "utf8"));
  assert.ok(/PROGRAM_ORIGIN/.test(sheetSrc), "the sheet writes its own origin sentence");
  // The analyzer's assumption list says the same thing to a different reader.
  const analyze = strip(readFileSync("src/lib/nc/analyze.ts", "utf8"));
  assert.ok(/PROGRAM_ORIGIN/.test(analyze), "the analyzer still carries its own copy of the origin convention");
  // And the program itself. A machinist reading the file at the control gets
  // the same sentence as the one reading the sheet at the vise.
  // Scoped to each header that writes it. An unscoped match passed while the
  // Fanuc header dropped the line, because the Heidenhain one still had it.
  const post = strip(readFileSync("src/lib/engines/cam/post.ts", "utf8"));
  const fanuc = /function header\([\s\S]*?\n}/.exec(post);
  assert.ok(fanuc, "the shared post header moved — this test cannot check it any more");
  assert.ok(/PROGRAM_ORIGIN\.sentence/.test(fanuc![0]), "the post header does not state where program zero is");
  const tnc = /const emitHeidenhain[\s\S]*?BEGIN PGM[\s\S]{0,400}/.exec(post);
  assert.ok(tnc && /PROGRAM_ORIGIN\.sentence/.test(tnc[0]), "the Heidenhain header does not state where program zero is");
});
