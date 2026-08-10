import { test } from "node:test";
import assert from "node:assert/strict";
import { createDxf } from "@/lib/export/dxf";
import { softJawDxf } from "@/lib/export/soft-jaw-dxf";
import { generateSoftJaws, type JawGeometry } from "@/lib/engines/workholding";
import type { WorkholdingDevice, JawBlank } from "@/lib/domain/shop";

/**
 * The jaw drawing leaves the shop and outlives the screen it came from, so
 * what it contains is pinned: real arcs for the reliefs, the stop only on
 * the jaw that carries one, and the DEVELOPMENT caveat inside the file.
 */

test("dxf writer emits well-formed LINE, ARC and TEXT records ending in EOF", () => {
  const d = createDxf();
  d.comment("hello");
  d.line("OUTLINE", 0, 0, 1, 0);
  d.arc("CUT", 0.5, 0.5, 0.25, 180, 270);
  d.text("NOTES", 0, -0.2, 0.1, "NOTE");
  const out = d.build();
  assert.match(out, /999\nhello/);
  assert.match(out, /0\nLINE\n8\nOUTLINE\n10\n0\n20\n0\n11\n1\n21\n0/);
  assert.match(out, /0\nARC\n8\nCUT\n10\n0\.5\n20\n0\.5\n40\n0\.25\n50\n180\n51\n270/);
  assert.ok(out.trimEnd().endsWith("0\nEOF"));
});

const geometryPair = () => {
  const device = { id: "v", type: "VISE", description: "vise", jawWidth: 6, jawHeight: 1.25, maxOpening: 8, clampForce: 6000 } as WorkholdingDevice;
  const blank: JawBlank = { id: "b", material: "ALUMINUM_6061", width: 6, height: 2, thickness: 1, boltPattern: 'Two 3/8-16 on 4" centres' };
  const r = generateSoftJaws({
    device, blank, partWidth: 5.875, partLength: 3.875, partHeight: 0.625,
    desiredGrip: 0.25, jawAllowance: 0.01, clearance: 0.03, includeStop: true,
    clampingDirection: "X", cornerRadius: 0.25,
  });
  assert.ok(r.ok && r.left && r.right);
  return { left: r.left!, right: r.right! };
};

const meta = { partName: "Bearing Support", partNumber: "CNV-001", setupName: "SETUP 2", generatedAtIso: "2026-08-10T00:00:00Z" };

test("jaw drawing carries both relief arcs at the generator's radius", () => {
  const { left } = geometryPair();
  const dxf = softJawDxf(left, meta);
  const arcs = dxf.split("0\nARC").length - 1;
  assert.equal(arcs, 2);
  assert.match(dxf, new RegExp(`40\\n${left.seatCornerRadius}`));
});

test("the stop is drawn on the left jaw and absent on the right", () => {
  const { left, right } = geometryPair();
  assert.match(softJawDxf(left, meta), /STOP/);
  assert.ok(!/1\nSTOP/.test(softJawDxf(right, meta)));
});

test("the drawing carries its own DEVELOPMENT caveat and units", () => {
  const { left } = geometryPair();
  const dxf = softJawDxf(left, meta);
  assert.match(dxf, /DEVELOPMENT/);
  assert.match(dxf, /VERIFY BEFORE MACHINING/);
  assert.match(dxf, /INCHES/);
  assert.match(dxf, /BOLT HOLES NOT DRAWN/);
});

test("blank outline spans the recorded blank, not an assumed one", () => {
  const { left } = geometryPair();
  const dxf = softJawDxf({ ...left, blankWidth: 8, blankHeight: 2.5 } as JawGeometry, meta);
  assert.match(dxf, /11\n8\n21\n0/);      // bottom edge runs to x=8
  assert.match(dxf, /BLANK 8\.00 x 2\.50/);
});
