import { test } from "node:test";
import assert from "node:assert/strict";
import { parseStep, asNum, asList } from "@/lib/step/parse";
import { recognizeStep } from "@/lib/step/recognize";

/**
 * The STEP pipeline is a parser plus geometry — deterministic end to end.
 * The synthetic file below exercises the exact subgraph the recognizer
 * traverses; the real-file behaviours (assembly refusal, B-spline naming,
 * off-axis warnings) were verified against the stepcode corpus at build time
 * and their logic is pinned here with minimal fixtures.
 */

const SYNTHETIC = `ISO-10303-21;
HEADER;
FILE_DESCRIPTION((''),'2;1');
FILE_NAME('C:\\\\exports\\\\test-plate.stp','2026-08-10',(''),(''),'','','');
FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));
ENDSEC;
DATA;
#1 = CARTESIAN_POINT('corner',(0.,0.,0.));
#2 = CARTESIAN_POINT('corner',(101.6,76.2,12.7));
#10 = CARTESIAN_POINT('loc',(25.4,38.1,12.7));
#11 = DIRECTION('axis',(0.,0.,1.));
#12 = DIRECTION('ref',(1.,0.,0.));
#13 = AXIS2_PLACEMENT_3D('',#10,#11,#12);
#14 = CYLINDRICAL_SURFACE('',#13,5.);
#20 = CARTESIAN_POINT('vtop',(30.4,38.1,12.7));
#21 = CARTESIAN_POINT('vbot',(30.4,38.1,0.));
#22 = VERTEX_POINT('',#20);
#23 = VERTEX_POINT('',#21);
#24 = EDGE_CURVE('',#22,#23,#22,.T.);
#25 = ORIENTED_EDGE('',*,*,#24,.T.);
#26 = EDGE_LOOP('',(#25));
#27 = FACE_BOUND('',#26,.T.);
#28 = ADVANCED_FACE('it''s a hole',(#27),#14,.T.);
ENDSEC;
END-ISO-10303-21;
`;

test("parser reads entities, escaped quotes, refs, lists and enums", () => {
  const f = parseStep(SYNTHETIC);
  assert.equal(f.warnings.length, 0);
  const face = f.entities.get(28)!;
  assert.equal(face.type, "ADVANCED_FACE");
  assert.deepEqual(face.args[0], { kind: "STR", value: "it's a hole" });
  const cyl = f.entities.get(14)!;
  assert.equal(asNum(cyl.args[2]), 5);
  const pt = f.entities.get(2)!;
  assert.deepEqual(asList(pt.args[1]).map(asNum), [101.6, 76.2, 12.7]);
});

test("recognizer converts mm, recenters, and measures depth from the face's own vertices", () => {
  const r = recognizeStep(SYNTHETIC);
  assert.equal(r.units, "MM");
  assert.equal(r.partName, "test-plate");
  assert.deepEqual(r.envelope, { x: 4, y: 3, z: 0.5 });
  assert.equal(r.suggestions.length, 1);
  const s = r.suggestions[0];
  assert.equal(s.kind, "DRILLED_HOLE"); // ⌀10 mm = 0.3937" — under the BORE heuristic
  assert.equal(s.parameters.diameter, 0.3937);
  assert.equal(s.parameters.through, true);
  // Placement was at x=25.4 mm = 1" from the corner; the part is 4" wide, so
  // the recentered X is 1 − 2 = −1.
  assert.equal(s.parameters.centerX, -1);
  assert.equal(s.parameters.centerY, 0);
});

test("an assembly is warned about, not pooled into wrong coordinates", () => {
  const assembly = SYNTHETIC.replace(
    "ENDSEC;\nEND-ISO",
    "#90 = NEXT_ASSEMBLY_USAGE_OCCURRENCE('','','',$,$,$);\nENDSEC;\nEND-ISO",
  );
  const r = recognizeStep(assembly);
  assert.ok(r.warnings.some((w) => /assembly/.test(w)));
});

test("a file with no data section reports itself instead of pretending", () => {
  const r = recognizeStep("not a step file at all");
  assert.equal(r.suggestions.length, 0);
  assert.ok(r.warnings.length > 0);
});

/* ---- pocket / slot floors ---- */

// Splice extra DATA entities into the synthetic plate before ENDSEC.
const withData = (extra: string) => SYNTHETIC.replace("ENDSEC;\nEND-ISO", `${extra}\nENDSEC;\nEND-ISO`);

const PLANE_FLOOR = (id: number, bounds: string) => `
#${id} = CARTESIAN_POINT('',(0.,0.,6.35));
#${id + 1} = DIRECTION('',(0.,0.,1.));
#${id + 2} = AXIS2_PLACEMENT_3D('',#${id},#${id + 1},$);
#${id + 3} = PLANE('',#${id + 2});
#${id + 4} = ADVANCED_FACE('floor',(${bounds}),#${id + 3},.T.);`;

test("a rectangular interior floor is proposed as a RECT_POCKET, depth from the top face", () => {
  // Four corner vertices at z=6.35 mm on a 30×20 mm boundary.
  const corners = [[20, 20], [50, 20], [50, 40], [20, 40]]
    .map(([x, y], i) => `#${60 + i} = CARTESIAN_POINT('',(${x}.,${y}.,6.35));\n#${70 + i} = VERTEX_POINT('',#${60 + i});`)
    .join("\n");
  const r = recognizeStep(withData(`${corners}\n#80 = EDGE_LOOP('',(#70,#71,#72,#73));\n#81 = FACE_OUTER_BOUND('',#80,.T.);${PLANE_FLOOR(90, "#81")}`));
  const p = r.suggestions.find((s) => s.kind === "RECT_POCKET");
  assert.ok(p, "rect pocket not proposed");
  assert.equal(p!.parameters.width, 1.1811); // 30 mm
  assert.equal(p!.parameters.length, 0.7874); // 20 mm
  assert.equal(p!.parameters.cornerRadius, 0);
  assert.equal(p!.parameters.depth, 0.25); // 12.7 − 6.35 mm
  // Center 35,30 mm recentered against the 101.6×76.2 plate.
  assert.equal(p!.parameters.centerX, r4(35 / 25.4 - 2));
  assert.equal(p!.parameters.centerY, r4(30 / 25.4 - 1.5));
});

test("a floor bounded by one circle is a CIRC_POCKET at the circle's center", () => {
  const circ = `
#60 = CARTESIAN_POINT('',(76.2,38.1,6.35));
#61 = DIRECTION('',(0.,0.,1.));
#62 = AXIS2_PLACEMENT_3D('',#60,#61,$);
#63 = CIRCLE('',#62,8.);
#64 = CARTESIAN_POINT('',(84.2,38.1,6.35));
#65 = VERTEX_POINT('',#64);
#66 = EDGE_CURVE('',#65,#65,#63,.T.);
#67 = ORIENTED_EDGE('',*,*,#66,.T.);
#68 = EDGE_LOOP('',(#67));
#69 = FACE_OUTER_BOUND('',#68,.T.);`;
  const r = recognizeStep(withData(`${circ}${PLANE_FLOOR(90, "#69")}`));
  const p = r.suggestions.find((s) => s.kind === "CIRC_POCKET");
  assert.ok(p, "circular pocket not proposed");
  assert.equal(p!.parameters.diameter, r4(16 / 25.4));
  assert.equal(p!.parameters.depth, 0.25);
  assert.equal(p!.parameters.centerX, 1); // 76.2 mm = 3", plate half-width 2"
  assert.equal(p!.parameters.centerY, 0);
});

test("two equal end arcs make a SLOT between the arc centers", () => {
  const slot = `
#55 = CARTESIAN_POINT('',(30.,20.,6.35));
#56 = DIRECTION('',(0.,0.,1.));
#57 = AXIS2_PLACEMENT_3D('',#55,#56,$);
#58 = CIRCLE('',#57,5.);
#60 = CARTESIAN_POINT('',(60.,20.,6.35));
#61 = AXIS2_PLACEMENT_3D('',#60,#56,$);
#62 = CIRCLE('',#61,5.);
#63 = CARTESIAN_POINT('',(30.,15.,6.35));
#64 = CARTESIAN_POINT('',(60.,25.,6.35));
#65 = VERTEX_POINT('',#63);
#66 = VERTEX_POINT('',#64);
#67 = EDGE_CURVE('',#65,#66,#58,.T.);
#68 = EDGE_CURVE('',#66,#65,#62,.T.);
#69 = EDGE_LOOP('',(#67,#68));
#70 = FACE_OUTER_BOUND('',#69,.T.);`;
  const r = recognizeStep(withData(`${slot}${PLANE_FLOOR(90, "#70")}`));
  const p = r.suggestions.find((s) => s.kind === "SLOT");
  assert.ok(p, "slot not proposed");
  assert.equal(p!.parameters.width, r4(10 / 25.4));
  assert.equal(p!.parameters.depth, 0.25);
  // Arc centers 30 mm apart along X.
  const span = Math.abs((p!.parameters.endX as number) - (p!.parameters.startX as number));
  assert.equal(span, r4(30 / 25.4));
});

test("a floor boundary that fits no profile is warned about, never force-fitted", () => {
  // An L-shaped boundary: the notch vertex sits inside the bounding rect.
  const lShape = [[20, 20], [50, 20], [50, 30], [35, 30], [35, 40], [20, 40]]
    .map(([x, y], i) => `#${60 + i} = CARTESIAN_POINT('',(${x}.,${y}.,6.35));\n#${70 + i} = VERTEX_POINT('',#${60 + i});`)
    .join("\n");
  const r = recognizeStep(withData(`${lShape}\n#80 = EDGE_LOOP('',(#70,#71,#72,#73,#74,#75));\n#81 = FACE_OUTER_BOUND('',#80,.T.);${PLANE_FLOOR(90, "#81")}`));
  assert.ok(!r.suggestions.some((s) => s.kind === "RECT_POCKET" || s.kind === "CIRC_POCKET" || s.kind === "SLOT"));
  assert.ok(r.warnings.some((w) => /did not match a circular, slot or rectangular floor profile/.test(w)));
});

const r4 = (v: number) => Number(v.toFixed(4));

test("unrecognized surfaces are counted by name, including complex records", () => {
  const withSpline = SYNTHETIC.replace(
    "#14 = CYLINDRICAL_SURFACE('',#13,5.);",
    "#14 = ( BOUNDED_SURFACE() B_SPLINE_SURFACE(2,2,(),.UNSPECIFIED.,.F.,.F.,.F.) );",
  );
  const r = recognizeStep(withSpline);
  assert.equal(r.suggestions.length, 0);
  assert.ok(r.unrecognized.some((u) => /SURFACE/.test(u.type) && u.count === 1));
});
