import { test } from "node:test";
import assert from "node:assert/strict";
import { parseToolList } from "@/lib/nc/tool-list";
import { evaluateAuditGates } from "@/lib/nc/audit-gates";
import { parseNC } from "@/lib/nc/parse";
import { analyzeNC } from "@/lib/nc/analyze";
import type { ParsedNC } from "@/lib/nc/parse";

/**
 * A program whose tools are not in the crib used to get no engagement bands
 * and no reach check, and the audit gate told the operator to type the tools
 * in by hand. They already have the list. What matters is that reading it
 * does not quietly turn a CAM document into shop-owned measured record.
 */

const CSV = [
  "Tool,Description,Diameter,Flutes,LOC,Stickout",
  '1,"1/2 flat endmill, 4FL",0.5,4,1.25,1.9',
  "2,3/8 ball,0.375,2,1.0,1.6",
].join("\n");

test("a straightforward CSV reads, with the columns it used named", () => {
  const r = parseToolList(CSV, "IN");
  assert.equal(r.entries.length, 2);
  assert.deepEqual(r.refusals, []);
  assert.equal(r.entries[0].toolNumber, 1);
  assert.equal(r.entries[0].diameter, 0.5);
  assert.equal(r.entries[0].flutes, 4);
  assert.equal(r.entries[0].fluteLength, 1.25);
  assert.equal(r.entries[0].stickout, 1.9);
  // The comma inside the quoted description does not split the row.
  assert.equal(r.entries[0].description, "1/2 flat endmill, 4FL");
  assert.equal(r.columns.diameter, "Diameter");
  assert.equal(r.columns.fluteLength, "LOC");
});

test("millimetres are converted, not carried through as inches", () => {
  // The whole reason units are stated rather than sniffed: a 6 mm cutter
  // read as 6 inch is a scrapped part.
  const r = parseToolList("T,Dia,Flutes\n1,6,2", "MM");
  assert.ok(Math.abs(r.entries[0].diameter - 6 / 25.4) < 1e-9, `diameter was ${r.entries[0].diameter}`);
  const inch = parseToolList("T,Dia,Flutes\n1,6,2", "IN");
  assert.equal(inch.entries[0].diameter, 6);
});

test("a tab separated export reads the same as a comma separated one", () => {
  const r = parseToolList("Tool\tDiameter\tFlutes\n1\t0.5\t4", "IN");
  assert.equal(r.entries.length, 1);
  assert.equal(r.entries[0].diameter, 0.5);
});

test("a header CANVAS cannot read is refused, never taken by position", () => {
  // Three unlabelled numbers in a row are not a tool list. Reading them
  // positionally would put a diameter where a flute count belongs.
  const r = parseToolList("Alpha,Beta,Gamma\n1,0.5,4", "IN");
  assert.equal(r.entries.length, 0);
  assert.equal(r.refusals.length, 1);
  assert.match(r.refusals[0].reason, /toolNumber|diameter|flutes/);
  assert.match(r.refusals[0].reason, /nothing here is taken by position/);
});

test("a missing diameter is a refused row that says so, not a zero", () => {
  const r = parseToolList("Tool,Diameter,Flutes\n1,0.5,4\n2,,2\n3,abc,3", "IN");
  assert.deepEqual(r.entries.map((e) => e.toolNumber), [1]);
  assert.equal(r.refusals.length, 2);
  assert.ok(r.refusals.every((f) => /diameter/.test(f.reason)));
  // And nothing landed with diameter 0 — a zero-diameter tool would compute
  // an engagement of zero on every cut and read as air.
  assert.ok(r.entries.every((e) => e.diameter > 0));
});

test("absent flute length and stickout stay null rather than becoming zero", () => {
  const r = parseToolList("Tool,Diameter,Flutes\n1,0.5,4", "IN");
  assert.equal(r.entries[0].fluteLength, null);
  assert.equal(r.entries[0].stickout, null);
  // A blank cell under a column that exists is the same answer.
  const blank = parseToolList("Tool,Diameter,Flutes,Stickout\n1,0.5,4,", "IN");
  assert.equal(blank.entries[0].stickout, null);
});

test("a repeated tool number keeps the first row and reports the second", () => {
  const r = parseToolList("Tool,Diameter,Flutes\n1,0.5,4\n1,0.25,2", "IN");
  assert.equal(r.entries.length, 1);
  assert.equal(r.entries[0].diameter, 0.5);
  assert.match(r.refusals[0].reason, /appears again/);
});

test("a column no synonym covers is reported as unread, not ignored", () => {
  const r = parseToolList("Tool,Diameter,Flutes,Coolant,Holder\n1,0.5,4,FLOOD,CAT40", "IN");
  assert.deepEqual(r.unreadColumns, ["Coolant", "Holder"]);
});

test("a header is matched whole, not as a substring", () => {
  // "Tool Diameter" contains "tool". Matching loosely would read the
  // diameter column as the tool number and then find no diameter at all.
  // Column order is the trap: "Diameter" contains the letter t, and "t" is a
  // synonym for the tool number, so a loose match claims "Cutter Diameter"
  // for the tool number before it ever reaches the column named T.
  const r = parseToolList("Cutter Diameter,T,Flutes\n0.75,7,3", "IN");
  assert.deepEqual(r.refusals, []);
  assert.equal(r.entries[0].toolNumber, 7);
  assert.equal(r.entries[0].diameter, 0.75);
  assert.equal(r.columns.toolNumber, "T");
  assert.equal(r.columns.diameter, "Cutter Diameter");
  // And the same header read whole, in the other order.
  const wide = parseToolList("Tool Number,Tool Diameter,Flutes\n7,0.75,3", "IN");
  assert.equal(wide.entries[0].toolNumber, 7);
  assert.equal(wide.entries[0].diameter, 0.75);
});

test("a T prefix on the tool number is read, and a fractional one is not", () => {
  const r = parseToolList("Tool,Diameter,Flutes\nT4,0.5,4\n1.5,0.5,4", "IN");
  assert.deepEqual(r.entries.map((e) => e.toolNumber), [4]);
  assert.match(r.refusals[0].reason, /positive whole number/);
});

/* ---- and the gate does not treat a list as a crib record ---- */

const parsed: Parameters<typeof evaluateAuditGates>[0]["parsed"] = {
  refusals: [], warnings: [], unitsExplicit: true, units: "IN",
  workOffsetsSeen: ["G54"], segments: [], lineCount: 10,
} as unknown as Pick<ParsedNC, "refusals" | "warnings" | "unitsExplicit" | "units" | "workOffsetsSeen" | "segments" | "lineCount">;

const gate = (toolsMapped: number[], toolsFromList: number[]) =>
  evaluateAuditGates({
    parsed, originalStored: true, digest: "d", toolsInProgram: [1, 2],
    toolsMapped, toolsFromList,
    machineKnown: true, axisAccelKnown: true, stockBound: true, materialMatched: true,
    compedSegments: 0, tappingSegments: 0,
  }).gates.find((x) => x.id === "tool-mapping")!;

test("a tool known only from the attached list is REVIEW, not PASS", () => {
  // PASS here would mean the shop has a measured record of a tool it may not
  // own. The list says what the programmer intended to use.
  assert.equal(gate([1, 2], []).status, "PASS");
  assert.equal(gate([1], [2]).status, "REVIEW");
  assert.equal(gate([], [1, 2]).status, "REVIEW");
  assert.equal(gate([1], []).status, "INSUFFICIENT_DATA");
});

test("the REVIEW wording tells the operator no feed proposal is coming", () => {
  const g = gate([1], [2]);
  assert.match(g.detail, /T2/);
  assert.match(g.detail, /chipload window/);
  assert.ok(!/All 2 program/.test(g.detail));
});

test("an unmapped tool outranks a list-supplied one", () => {
  // Worst-case, per principle 1: one tool CANVAS knows nothing about is not
  // averaged away by another it half knows.
  const g = gate([], [1]);
  assert.equal(g.status, "INSUFFICIENT_DATA");
  assert.match(g.detail, /T2/);
});


/* ---- and the reach check uses what the list did carry ---- */

const program = ["G20 G90 G54", "T1 M6", "S5000 M3", "G0 X0 Y0 Z0.1", "G1 Z-1.5 F10", "G1 X2. F20", "G0 Z1.", "M30"].join("\n");

const reach = (geom: { fluteLength: number; stickout: number; source?: "CRIB" | "TOOL_LIST" }) =>
  analyzeNC(parseNC(program), {
    stock: { x: 4, y: 4, z: 2 },
    toolDiameters: { 1: 0.5 },
    toolGeometry: { 1: { description: "1/2 EM", ...geom } },
    rapidRate: 600,
    axisAccel: null,
  }).findings.filter((f) => f.kind === "TOOL_REACH_REVIEW");

test("a list that carries only stickout still gets a reach verdict", () => {
  // The check used to need both figures and say nothing without them. A
  // 1.200 stickout against a 1.500 cut is a reach problem on its own.
  const f = reach({ stickout: 1.2, fluteLength: 0, source: "TOOL_LIST" });
  assert.equal(f.length, 1);
  assert.equal(f[0].verdict, "REVIEW");
  assert.match(f[0].detail, /1\.200/);
  // And it says which half did not run rather than implying both did.
  assert.match(f[0].detail, /flute length is not recorded/);
});

test("a figure from the list is attributed to the list, not to the crib", () => {
  // Reading it as a crib record would tell the machinist the shop measured a
  // tool it may not own.
  const f = reach({ stickout: 1.2, fluteLength: 2.0, source: "TOOL_LIST" });
  assert.match(f[0].detail, /attached tool list/);
  assert.ok(!/crib/.test(f[0].detail));
  assert.ok(f[0].assumptions.some((a) => /programmer's intent/.test(a)));
  const crib = reach({ stickout: 1.2, fluteLength: 2.0, source: "CRIB" });
  assert.match(crib[0].detail, /crib records/);
});

test("clearing on the one recorded figure is INSUFFICIENT_DATA, not silence", () => {
  // Reaching on stickout with no flute length recorded is not a pass.
  const f = reach({ stickout: 3.0, fluteLength: 0, source: "TOOL_LIST" });
  assert.equal(f.length, 1);
  assert.equal(f[0].verdict, "INSUFFICIENT_DATA");
  assert.match(f[0].detail, /half the reach check ran/);
  // Both figures present and both clear: nothing to say.
  assert.deepEqual(reach({ stickout: 3.0, fluteLength: 3.0, source: "CRIB" }), []);
});
