import { test } from "node:test";
import assert from "node:assert/strict";
import { generateCinematic, DISCLAIMER, type CinematicInput, type CinematicSettings } from "@/lib/cinematic";

/**
 * The cinematic generator is a communication tool, and the things pinned here
 * are its honesty rules: the disclaimer is inescapable, missing values are
 * never invented, timing sums to the requested duration, and customer-safe
 * mode strips identity by construction.
 */

const input: CinematicInput = {
  partName: "CANVAS Bearing Support",
  partNumber: "CNV-001",
  material: "Aluminum 6061 · T6511",
  stock: { x: 6, y: 4, z: 0.75 },
  setupName: "SETUP 1 — Top face, bore, holes",
  workholding: '6" machinist vise',
  hasSoftJaws: true,
  readiness: "NOT_READY_TO_RUN",
  operations: [
    { id: "a", label: "Face top", type: "FACE", toolDescription: '2" face mill', cycleMinutes: 0.45 },
    { id: "b", label: "Finish bore to 40 mm", type: "BORE", toolDescription: "boring head", cycleMinutes: 0.4 },
    { id: "c", label: "Tap 1/4-20 mounting holes", type: "TAP", toolDescription: "1/4-20 tap", cycleMinutes: 0.1 },
  ],
};

const settings: CinematicSettings = {
  durationSeconds: 10,
  style: "PREMIUM_PRODUCT_RENDER",
  include: {
    softJaws: true, stock: true, toolAndHolder: true, toolpathTrace: true, materialRemoval: true,
    datumLabels: true, measurementOverlays: true, operationLabels: true, coolantChips: false, finalReveal: true,
  },
  customerSafe: false,
};

test("the disclaimer is on every output shape", () => {
  const r = generateCinematic(input, settings);
  assert.equal(r.disclaimer, DISCLAIMER);
  assert.equal(r.storyboard.disclaimer, DISCLAIMER);
});

test("shot timing covers the full duration, contiguous and ordered", () => {
  const r = generateCinematic(input, settings);
  assert.equal(r.shots[0].start, 0);
  assert.equal(r.shots[r.shots.length - 1].end, 10);
  for (let i = 1; i < r.shots.length; i++) assert.equal(r.shots[i].start, r.shots[i - 1].end);
});

test("missing material is written as unspecified, never invented", () => {
  const r = generateCinematic({ ...input, material: null }, settings);
  assert.equal(r.storyboard.material, "unspecified");
  assert.ok(!/6061/.test(r.prompt));
});

test("customer-safe strips part identity, tool specifics and material temper", () => {
  const r = generateCinematic(input, { ...settings, customerSafe: true });
  const all = r.prompt + r.shortPrompt + JSON.stringify(r.storyboard);
  assert.ok(!/CNV-001/.test(all), "part number leaked");
  assert.ok(!/Bearing Support/.test(all), "part name leaked");
  assert.ok(!/40 mm/.test(all), "feature dimension leaked");
  assert.ok(!/boring head/.test(all), "tool description leaked");
  assert.ok(!/T6511/.test(all), "material temper leaked");
  assert.ok(/Aluminum/.test(all), "material family should survive");
  assert.match(all, /Precision boring/);
});

test("the full prompt names real operations and carries the constraint block", () => {
  const r = generateCinematic(input, settings);
  assert.match(r.prompt, /Face top/);
  assert.match(r.prompt, /boring/i);
  assert.match(r.prompt, /no sci-fi glow/i);
  assert.match(r.prompt, /Photorealistic/);
});
