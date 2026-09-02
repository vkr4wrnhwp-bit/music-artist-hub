import { test } from "node:test";
import assert from "node:assert/strict";
import { methodOptions, validateMethod, geometryPhrase } from "@/lib/engines/inspection-method";
import { assessCapability, type Instrument } from "@/lib/engines/inspection-capability";
import type { Feature } from "@/lib/domain/features";

/**
 * The gate "Critical tolerance strategy" asked the shop to assign an
 * inspection method and nothing in the application could write one. Any part
 * with a critical feature could never post.
 *
 * The rule that makes this a decision rather than a confirm button: a method
 * may only name an instrument the shop OWNS that can physically reach the
 * feature, and once assigned it is the method the capability gate judges.
 */

const inst = (deviceType: string, uncertainty: number, over: Partial<Instrument> = {}): Instrument => ({
  id: deviceType,
  deviceType,
  description: `${deviceType} unit`,
  resolution: uncertainty / 2,
  uncertainty,
  rangeMin: 0,
  rangeMax: 12,
  calibrated: true,
  ...over,
});

const bore = (band: number, over: Record<string, unknown> = {}): Feature =>
  ({
    id: "f1",
    kind: "BORE",
    label: "⌀1.2500 bore",
    functionalRole: "BEARING_FIT",
    critical: true,
    diameter: 1.25,
    depth: 0.5,
    tolerance: { plus: band / 2, minus: band / 2 },
    ...over,
  }) as unknown as Feature;

/* ---------------- Only what the shop owns and can reach ---------------- */

test("an instrument class the shop does not own is refused, and says so", () => {
  const r = validateMethod(bore(0.002), [inst("BORE_GAUGE", 0.0002)], "CMM");
  assert.equal(r.ok, false);
  assert.match((r as { reason: string }).reason, /metrology list records no/i);
  assert.match((r as { reason: string }).reason, /cmm/i);
});

test("an instrument that cannot reach the geometry is refused", () => {
  // A depth micrometer measures a flat internal depth; it does not measure a
  // bore diameter. Recommending it would be the kind of wrong that erodes
  // trust in every other recommendation on the screen.
  const r = validateMethod(bore(0.002), [inst("DEPTH_MICROMETER", 0.0005)], "DEPTH_MICROMETER");
  assert.equal(r.ok, false);
  assert.match((r as { reason: string }).reason, /cannot reach/i);
});

test("a class that is not in the vocabulary at all is refused", () => {
  const r = validateMethod(bore(0.002), [inst("EYEBALL", 0.5)], "EYEBALL");
  assert.equal(r.ok, false);
  assert.match((r as { reason: string }).reason, /not an instrument class/i);
});

test("an owned instrument that can reach it is accepted", () => {
  const r = validateMethod(bore(0.02), [inst("BORE_GAUGE", 0.0002)], "BORE_GAUGE");
  assert.equal(r.ok, true);
  assert.equal((r as { deviceType: string }).deviceType, "BORE_GAUGE");
  assert.equal((r as { verdict: string }).verdict, "CAPABLE");
});

/* ---------------- The choice is allowed to be a poor one ---------------- */

test("a marginal method is accepted, because guard-banding is ordinary practice", () => {
  // 0.0002 on a 0.001 band is 20% — past the 10% target, inside the 25%
  // limit. A shop may decide to run it and guard-band; CANVAS records the
  // decision rather than refusing to let them make it.
  const r = validateMethod(bore(0.001), [inst("BORE_GAUGE", 0.0002)], "BORE_GAUGE");
  assert.equal(r.ok, true);
  assert.equal((r as { verdict: string }).verdict, "MARGINAL");
});

test("choosing a coarser instrument than the best owned makes the part read WORSE", () => {
  // THE POINT OF THE WHOLE MECHANISM. The shop owns a bore gauge and a
  // caliper. Judging the drawer says CAPABLE on the bore gauge it is not
  // going to pick up; judging the method says what the plan is actually worth.
  const owned = [inst("BORE_GAUGE", 0.0002), inst("DIGITAL_CALIPER", 0.002)];
  const req = {
    featureId: "f1",
    featureLabel: "bore",
    geometry: "INTERNAL_ROUND" as const,
    nominal: 1.25,
    toleranceBand: 0.005,
    critical: true,
  };
  const drawer = assessCapability(req, owned);
  assert.equal(drawer.verdict, "CAPABLE");

  const chosen = assessCapability({ ...req, chosenDeviceType: "DIGITAL_CALIPER" }, owned);
  assert.equal(chosen.verdict, "NOT_CAPABLE");
  assert.equal(chosen.bestInstrument?.deviceType, "DIGITAL_CALIPER");
});

test("assigning the probe as the method cannot make the feature verifiable", () => {
  // The probe is excluded from acceptance everywhere. Naming it as the method
  // must not be a way back in.
  const r = assessCapability(
    {
      featureId: "f1",
      featureLabel: "bore",
      geometry: "INTERNAL_ROUND",
      nominal: 1.25,
      toleranceBand: 0.02,
      critical: true,
      chosenDeviceType: "MACHINE_PROBE",
    },
    [inst("MACHINE_PROBE", 0.0001)],
  );
  assert.equal(r.verdict, "NO_INSTRUMENT");
  assert.match(r.reason, /machine's own scales|fixture that cut it/);
});

/* ---------------- The picker ---------------- */

test("options list only reachable, owned classes and rank the best first", () => {
  const owned = [
    inst("DIGITAL_CALIPER", 0.002),
    inst("BORE_GAUGE", 0.0002),
    inst("DEPTH_MICROMETER", 0.0005), // cannot reach a bore
  ];
  const opts = methodOptions(bore(0.005), owned);
  const types = opts.map((o) => o.deviceType);
  assert.ok(!types.includes("DEPTH_MICROMETER"), "an unreachable class was offered");
  assert.equal(types[0], "BORE_GAUGE", "the better instrument is not offered first");
  assert.ok(types.includes("DIGITAL_CALIPER"), "a workable but poor class was hidden rather than ranked");
});

test("a finer but uncalibrated instrument is not offered ahead of a calibrated one", () => {
  // This is where ranking by verdict and ranking by uncertainty disagree, and
  // it is the case that matters: an uncalibrated instrument has no traceable
  // uncertainty at all, so being finer on paper must not float it to the top
  // of the list a machinist picks from.
  const owned = [
    inst("PIN_GAUGE", 0.00002, { calibrated: false }),
    inst("BORE_GAUGE", 0.0002, { calibrated: true }),
  ];
  const opts = methodOptions(bore(0.02), owned);
  assert.equal(opts[0].deviceType, "BORE_GAUGE", "an uncalibrated instrument was offered first");
  assert.equal(opts[0].verdict, "CAPABLE");
  const pin = opts.find((o) => o.deviceType === "PIN_GAUGE")!;
  assert.equal(pin.verdict, "NOT_CAPABLE");
  assert.ok(pin.consumedFraction! < opts[0].consumedFraction!, "the fixture does not actually separate the two rules");
});

test("each option carries the verdict that choosing it would produce", () => {
  const owned = [inst("BORE_GAUGE", 0.0002), inst("DIGITAL_CALIPER", 0.002)];
  const opts = methodOptions(bore(0.005), owned);
  const gauge = opts.find((o) => o.deviceType === "BORE_GAUGE")!;
  const caliper = opts.find((o) => o.deviceType === "DIGITAL_CALIPER")!;
  assert.equal(gauge.verdict, "CAPABLE");
  assert.equal(caliper.verdict, "NOT_CAPABLE");
  // And each states what it consumes, so the choice is informed rather than
  // a name in a list.
  assert.ok(gauge.consumedFraction != null && caliper.consumedFraction != null);
  assert.ok(caliper.consumedFraction! > gauge.consumedFraction!);
});

test("an option lists only the units that can actually reach this size", () => {
  // Found by driving the real UI: a 1" air gauge appeared under the bore-gauge
  // method for a 1.5748" bore. The verdict had already excluded it on range,
  // so it sat in the picker as though it were one of the two instruments the
  // shop would reach for.
  const owned = [
    inst("BORE_GAUGE", 0.0002, { id: "dial", description: '1-2" dial bore gauge', rangeMin: 1, rangeMax: 2 }),
    inst("BORE_GAUGE", 0.00005, { id: "air", description: 'air gauge 1.000 bore', rangeMin: 0.99, rangeMax: 1.01 }),
  ];
  const opt = methodOptions(bore(0.005, { diameter: 1.5748 }), owned).find((o) => o.deviceType === "BORE_GAUGE")!;
  const shown = opt.instruments.map((d) => d.id);
  assert.deepEqual(shown, ["dial"], "an out-of-range instrument was listed under the method");
  // And the verdict is the dial gauge's, not the finer air gauge's.
  assert.match(opt.reason, /0\.0002/);
});

test("the stored sentence carries what the instrument consumes, not just its name", () => {
  // "Micrometer" on an inspection report tells the next reader nothing about
  // whether the micrometer was up to the job.
  const r = validateMethod(bore(0.005), [inst("BORE_GAUGE", 0.0002)], "BORE_GAUGE");
  assert.equal(r.ok, true);
  assert.match((r as { method: string }).method, /Bore gauge/);
  assert.match((r as { method: string }).method, /% of the tolerance band/);
});

test("the spindle probe is never offered as a method, tolerance or no tolerance", () => {
  // Found by driving the real UI: with a tolerance, assessCapability refuses
  // the probe and methodOptions drops it. WITHOUT a tolerance it returns
  // NOT_REQUIRED before the instrument split ever runs, so the probe was
  // offered as an inspection method for exactly the features nobody checks
  // the verdict on.
  const owned = [inst("MACHINE_PROBE", 0.0001), inst("BORE_GAUGE", 0.0002)];
  for (const f of [bore(0.02), bore(0.02, { tolerance: undefined })]) {
    const types = methodOptions(f, owned).map((o) => o.deviceType);
    assert.ok(!types.includes("MACHINE_PROBE"), "the probe was offered as an acceptance method");
    assert.ok(types.includes("BORE_GAUGE"), "the fixture offers nothing at all, so it proves nothing");
  }
});

test("assigning the probe is refused at the write, not only hidden in the picker", () => {
  // The picker is UI. The validator is the rule.
  const r = validateMethod(bore(0.02, { tolerance: undefined }), [inst("MACHINE_PROBE", 0.0001)], "MACHINE_PROBE");
  assert.equal(r.ok, false);
});

test("a shop that owns nothing that reaches the feature gets no options, not a bad one", () => {
  const opts = methodOptions(bore(0.005), [inst("DEPTH_MICROMETER", 0.0005)]);
  assert.equal(opts.length, 0);
});

test("a feature with no tolerance still offers methods", () => {
  // No tolerance means no capability requirement, but a shop may still record
  // how it intends to check the feature.
  const opts = methodOptions(bore(0.005, { tolerance: undefined }), [inst("BORE_GAUGE", 0.0002)]);
  assert.equal(opts.length, 1);
  assert.equal(opts[0].verdict, "NOT_REQUIRED");
});

test("geometry reads as English in the refusal, not as an enum token", () => {
  assert.equal(geometryPhrase("INTERNAL_ROUND"), "round internal");
  assert.equal(geometryPhrase("POSITION"), "position");
  for (const g of ["INTERNAL_ROUND", "INTERNAL_FLAT", "EXTERNAL", "POSITION"] as const) {
    assert.ok(!/_/.test(geometryPhrase(g)), `${g} leaks an underscore`);
  }
});

/* ---------------- The engine is not duplicated here ---------------- */

test("the picker's verdicts come from assessCapability, not from a second rule", () => {
  // A picker that ranked instruments its own way would eventually disagree
  // with the gate that blocks NC export. Every option must equal what the
  // capability engine says for that same choice.
  const owned = [inst("BORE_GAUGE", 0.0002), inst("DIGITAL_CALIPER", 0.002), inst("PIN_GAUGE", 0.0002)];
  const f = bore(0.003);
  for (const o of methodOptions(f, owned)) {
    const direct = assessCapability(
      {
        featureId: f.id,
        featureLabel: f.label,
        geometry: "INTERNAL_ROUND",
        nominal: 1.25,
        toleranceBand: 0.003,
        critical: true,
        chosenDeviceType: o.deviceType,
      },
      owned,
    );
    assert.equal(o.verdict, direct.verdict, `${o.deviceType} disagrees with the capability engine`);
    assert.equal(o.consumedFraction, direct.consumedFraction, `${o.deviceType} consumed fraction disagrees`);
  }
});
