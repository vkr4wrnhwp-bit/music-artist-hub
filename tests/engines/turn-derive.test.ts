import { test } from "node:test";
import assert from "node:assert/strict";
import {
  criticalToleranceBand,
  cutoffDistanceFromChuck,
  inspectionCapableFor,
  materialFromIntent,
  TURN_INSPECTION_RATIO,
} from "@/lib/manufacturing/turn/derive";
import { assessPartOff } from "@/lib/manufacturing/turn/analysis";
import type { ProfileSegment, RotationalProfile } from "@/lib/manufacturing/turn/geometry";

/**
 * The turning package's derivations. Each one decides whether a gate blocks,
 * which is why they live outside the database-bound assembly.
 */

const seg = (over: Partial<ProfileSegment>): ProfileSegment => ({
  id: "s1",
  kind: "CYLINDER",
  label: "journal",
  zStart: 0,
  zEnd: 1,
  diameterStart: 1,
  diameterEnd: 1,
  internal: false,
  functionalRole: "OD_JOURNAL",
  critical: false,
  source: "USER",
  confirmedByUser: true,
  ...over,
});

const profile = (segments: ProfileSegment[]): RotationalProfile => ({
  units: "IN",
  zZeroReference: "front face",
  stockDiameter: 2,
  stockLength: 6,
  barStock: true,
  segments,
});

/* ---------------- Part-off overhang ---------------- */

test("part-off overhang is measured from the jaw face and grows as the cutoff moves away from it", () => {
  // Z0 is the datum face, the part runs to +Z, the chuck grips the far end.
  // A cutoff near the jaws is the stable one; a cutoff out at the datum face
  // is the whole stickout out in the air.
  const nearJaws = cutoffDistanceFromChuck({ cutoffZ: 4.5, stickout: 5 });
  const atDatumFace = cutoffDistanceFromChuck({ cutoffZ: 0.5, stickout: 5 });
  assert.equal(nearJaws, 0.5);
  assert.equal(atDatumFace, 4.5);
  assert.ok(atDatumFace! > nearJaws!, "the far cutoff must read as the more overhung one");
});

test("the least stable part-off is not reported as the safest", () => {
  // The regression this pins: the old expression cancelled its own grip
  // terms and reduced to `cutoffZ - gripLength`, which is negative for a
  // short part parted near the datum face — a guaranteed PASS on the cutoff
  // most likely to whip and pinch the blade.
  const d = cutoffDistanceFromChuck({ cutoffZ: 0.5, stickout: 5 })!;
  assert.ok(d > 0);
  const verdict = assessPartOff({
    cutoffZ: 0.5,
    cutoffDiameter: 0.75,
    distanceFromChuck: d, // 6.0×D overhang
    toolWidth: 0.125,
    hasPartsCatcher: true,
    hasSubSpindle: false,
    tailstockActive: false,
  });
  assert.equal(verdict.verdict, "REVIEW");
  assert.match(verdict.detail, /unsupported at separation/);
});

test("an unrecorded stickout refuses the part-off check instead of assuming zero", () => {
  assert.equal(cutoffDistanceFromChuck({ cutoffZ: 2, stickout: null }), null);
  const a = assessPartOff({
    cutoffZ: 2,
    cutoffDiameter: 0.75,
    distanceFromChuck: null,
    toolWidth: 0.125,
    hasPartsCatcher: true,
    hasSubSpindle: false,
    tailstockActive: false,
  });
  // UNKNOWN, which the readiness engine turns into a blocking FAIL naming
  // the missing input — not a PASS computed from an assumed zero overhang.
  assert.equal(a.verdict, "UNKNOWN");
  assert.ok(a.missingInputs.some((m) => /stickout/i.test(m)));
});

test("parting with the tailstock engaged is refused whatever the stickout says", () => {
  const a = assessPartOff({
    cutoffZ: 2,
    cutoffDiameter: 0.75,
    distanceFromChuck: null,
    toolWidth: 0.125,
    hasPartsCatcher: true,
    hasSubSpindle: false,
    tailstockActive: true,
  });
  assert.equal(a.verdict, "FAIL");
  assert.match(a.detail, /pinches the blade/);
});

test("a cutoff recorded behind the jaws reads as zero overhang, never negative", () => {
  assert.equal(cutoffDistanceFromChuck({ cutoffZ: 7, stickout: 5 }), 0);
});

/* ---------------- Critical tolerance band ---------------- */

test("the tolerance band is the tightest critical one, and a plus-only dimension is not dropped", () => {
  assert.equal(criticalToleranceBand(profile([seg({ critical: false, tolerancePlus: 0.0002 })])), null);
  // Plus-only: the old filter demanded toleranceMinus and silently excluded
  // this dimension from the inspection check entirely.
  assert.equal(criticalToleranceBand(profile([seg({ critical: true, tolerancePlus: 0.001 })])), 0.001);
  assert.equal(criticalToleranceBand(profile([seg({ critical: true, toleranceMinus: 0.001 })])), 0.001);
  assert.equal(
    criticalToleranceBand(
      profile([
        seg({ id: "a", critical: true, tolerancePlus: 0.005, toleranceMinus: 0.005 }),
        seg({ id: "b", critical: true, tolerancePlus: 0.0005, toleranceMinus: 0.0005 }),
      ]),
    ),
    0.001,
  );
});

/* ---------------- Inspection capability ---------------- */

test("inspection capability is a property of the instruments, at the stated 4:1 ratio", () => {
  assert.equal(TURN_INSPECTION_RATIO, 4);
  const band = 0.001; // ±0.0005
  const mic = [{ deviceType: "MICROMETER", uncertainty: 0.0001 }];
  // A surface plate's uncertainty is tiny and it cannot measure a diameter.
  // Membership of the instrument vocabulary is the check, not the number.
  const plate = [{ deviceType: "SURFACE_PLATE", uncertainty: 0.00001 }];
  assert.equal(inspectionCapableFor(band, mic), true);
  assert.equal(inspectionCapableFor(band, plate), false);
  // An inside micrometer measures a bore, and a turned part's critical band
  // is as often in a bore as on a journal.
  assert.equal(inspectionCapableFor(band, [{ deviceType: "INSIDE_MICROMETER", uncertainty: 0.0001 }]), true);
  assert.equal(inspectionCapableFor(band, []), false);
  // Exactly at 4:1 passes; one step past it does not.
  assert.equal(inspectionCapableFor(band, [{ deviceType: "MICROMETER", uncertainty: 0.00025 }]), true);
  assert.equal(inspectionCapableFor(band, [{ deviceType: "MICROMETER", uncertainty: 0.00026 }]), false);
  // The best instrument is chosen, not the first on file.
  assert.equal(
    inspectionCapableFor(band, [
      { deviceType: "MICROMETER", uncertainty: 0.0005 },
      { deviceType: "BORE_GAUGE", uncertainty: 0.00005 },
    ]),
    true,
  );
});

test("a profile with no critical tolerance has no inspection gate to fail", () => {
  assert.equal(inspectionCapableFor(null, []), true);
});

/* ---------------- Material from intent ---------------- */

test("the material gate reads the part's own intent and can fail", () => {
  assert.equal(materialFromIntent(JSON.stringify({ material: { value: "4140 PH" } })), "4140 PH");
  assert.equal(materialFromIntent(JSON.stringify({ material: { value: "  " } })), null);
  assert.equal(materialFromIntent(JSON.stringify({ material: { value: 6061 } })), null);
  assert.equal(materialFromIntent(JSON.stringify({})), null);
  assert.equal(materialFromIntent(null), null);
  assert.equal(materialFromIntent("{ not json"), null);
});
