import { test } from "node:test";
import assert from "node:assert/strict";
import { parseNC } from "@/lib/nc/parse";
import { classifyOperations } from "@/lib/nc/classify";

test("drilling cycles classify DRILL; tapping classifies TAP", () => {
  const drill = parseNC(["G20 G90", "T3 M6", "S6000 M3", "G0 X-2 Y-1 Z0.5", "G81 Z-0.7 R0.1 F8.", "X2 Y-1", "X2 Y1", "G80"].join("\n"));
  const ops = classifyOperations(drill);
  const d = ops.find((o) => o.toolNumber === 3)!;
  assert.equal(d.kind, "DRILL");
  assert.ok(d.detail.includes("vertical"));

  const tap = parseNC(["G20 G90", "T4 M6", "S1000 M3", "G0 X0 Y0 Z0.5", "G84 Z-0.5 R0.1 F50.", "X1 Y0", "G80"].join("\n"));
  assert.equal(classifyOperations(tap).find((o) => o.toolNumber === 4)!.kind, "TAP");
});

test("single-Z broad cutting classifies FACE; ambiguous motion stays UNKNOWN", () => {
  const face = parseNC(["G20 G90", "T1 M6", "S4500 M3", "G0 X-4 Y-1 Z0.1", "G1 Z-0.05 F40", "G1 X4 F55", "G0 Z0.1", "G0 Y1", "G1 Z-0.05 F40", "G1 X-4 F55"].join("\n"));
  assert.equal(classifyOperations(face)[0].kind, "FACE");

  const odd = parseNC(["G20 G90", "T5 M6", "S3000 M3", "G0 X0 Y0 Z0.1", "G1 Z-0.2 F10", "G1 X1 Z-0.4 F10", "G1 Y1 Z-0.1 F10"].join("\n"));
  const u = classifyOperations(odd)[0];
  assert.equal(u.kind, "UNKNOWN");
  assert.ok(u.detail.includes("Unlabeled is honest"));
});

test("descending multi-level XY cutting classifies POCKET; no cutting is LINKING", () => {
  const pocket = parseNC(["G20 G90", "T2 M6", "S5000 M3", "G0 X0 Y0 Z0.1",
    "G1 Z-0.1 F20", "G1 X1 F30", "G1 Y1 F30", "G1 X0 F30", "G1 Y0 F30",
    "G1 Z-0.2 F20", "G1 X1 F30", "G1 Y1 F30", "G1 X0 F30", "G1 Y0 F30"].join("\n"));
  assert.equal(classifyOperations(pocket)[0].kind, "POCKET");

  const linking = parseNC(["G20 G90", "T9 M6", "G0 X0 Y0 Z1", "G0 X2 Y2"].join("\n"));
  assert.equal(classifyOperations(linking)[0].kind, "LINKING");
});

test("every group is method DETERMINISTIC — there is no other classifier", () => {
  const ops = classifyOperations(parseNC("G20 G90\nT1 M6\nS100 M3\nG1 X1 F10"));
  assert.ok(ops.every((o) => o.method === "DETERMINISTIC"));
});
