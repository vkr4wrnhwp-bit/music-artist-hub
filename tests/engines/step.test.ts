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

test("unrecognized surfaces are counted by name, including complex records", () => {
  const withSpline = SYNTHETIC.replace(
    "#14 = CYLINDRICAL_SURFACE('',#13,5.);",
    "#14 = ( BOUNDED_SURFACE() B_SPLINE_SURFACE(2,2,(),.UNSPECIFIED.,.F.,.F.,.F.) );",
  );
  const r = recognizeStep(withSpline);
  assert.equal(r.suggestions.length, 0);
  assert.ok(r.unrecognized.some((u) => /SURFACE/.test(u.type) && u.count === 1));
});
