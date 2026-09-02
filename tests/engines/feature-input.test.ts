import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { FEATURE_FIELDS, coerceFeatureParameters, validateFeatureParameters } from "@/lib/domain/feature-input";
import { FEATURE_KINDS, type Feature } from "@/lib/domain/features";

/**
 * `db.feature.create` existed in exactly one place: accepting an AI proposal.
 * The empty state said "add features" and no control existed, so the only
 * route into a part's geometry was to accept something a model proposed.
 *
 * And `parametersJson` was a free record — featureSuggestionSchema types the
 * parameters as Record<string, number | string | boolean> — so a proposal
 * missing a diameter was written straight through, and every engine
 * downstream met undefined where it expected a number.
 */

const BORE = { centerX: 0, centerY: 0, diameter: 1.5748, depth: 0.75, bottomRadius: 0, top: 0, through: false };

test("a complete parameter set is accepted", () => {
  assert.deepEqual(validateFeatureParameters("BORE", BORE), []);
});

test("a missing required parameter is refused by name, never defaulted", () => {
  // A zero-depth pocket removes no material and every engine downstream would
  // treat it as real.
  for (const field of ["diameter", "depth", "centerX", "top"]) {
    const p: Record<string, unknown> = { ...BORE };
    delete p[field];
    const r = validateFeatureParameters("BORE", p);
    assert.equal(r.length, 1, `${field} was not refused`);
    assert.equal(r[0].field, field);
    assert.match(r[0].reason, /required and was not given/);
  }
});

test("an empty string is absent, not zero", () => {
  // What an untouched form field actually sends. On a field with a positive
  // floor it would at least be caught by the floor; on one where zero is a
  // legitimate value it would sail through as a number nobody typed, which is
  // the case that matters.
  const r = validateFeatureParameters("BORE", { ...BORE, diameter: "" });
  assert.equal(r.length, 1);
  assert.equal(r[0].field, "diameter");
  assert.match(r[0].reason, /required and was not given/, "an untouched field was reported as an out-of-range value");

  for (const field of ["top", "centerX", "bottomRadius"]) {
    const blank = validateFeatureParameters("BORE", { ...BORE, [field]: "" });
    assert.equal(blank.length, 1, `an empty ${field} was accepted as zero`);
    assert.equal(blank[0].field, field);
    assert.match(blank[0].reason, /required and was not given/);
  }
});

test("a dimension that must be positive is refused at zero and below", () => {
  for (const v of [0, -1]) {
    const r = validateFeatureParameters("BORE", { ...BORE, diameter: v });
    assert.equal(r.length, 1, `diameter ${v} was accepted`);
    assert.match(r[0].reason, /greater than zero/);
  }
});

test("a centre coordinate may be negative and a radius may be zero", () => {
  // These cannot share a rule with a diameter. A pocket at X-2.5 is ordinary,
  // and a zero corner radius is a real thing to state — the corner-access gate
  // is what has an opinion about it.
  assert.deepEqual(validateFeatureParameters("BORE", { ...BORE, centerX: -2.5, centerY: -1 }), []);
  assert.deepEqual(
    validateFeatureParameters("RECT_POCKET", {
      centerX: -2.5, centerY: 0, width: 1, length: 2, depth: 0.5, cornerRadius: 0, bottomRadius: 0, top: 0,
    }),
    [],
  );
  // But negative is still refused where zero is the floor.
  const r = validateFeatureParameters("RECT_POCKET", {
    centerX: 0, centerY: 0, width: 1, length: 2, depth: 0.5, cornerRadius: -0.1, bottomRadius: 0, top: 0,
  });
  assert.match(r[0].reason, /cannot be negative/);
});

test("a non-numeric value is refused rather than becoming NaN", () => {
  const r = validateFeatureParameters("BORE", { ...BORE, diameter: "about an inch" });
  assert.equal(r[0].field, "diameter");
  assert.match(r[0].reason, /not a number/);
});

test("a choice outside its list is refused", () => {
  const ok = { width: 0.02, angle: 45, applyTo: "OUTSIDE_TOP" };
  assert.deepEqual(validateFeatureParameters("CHAMFER", ok), []);
  const r = validateFeatureParameters("CHAMFER", { ...ok, applyTo: "EVERYWHERE" });
  assert.equal(r[0].field, "applyTo");
});

test("a required text field cannot be whitespace", () => {
  const base = { centerX: 0, centerY: 0, diameter: 0.201, depth: 0.5, top: 0, through: false };
  assert.deepEqual(validateFeatureParameters("TAPPED_HOLE", { ...base, thread: "1/4-20 UNC" }), []);
  const r = validateFeatureParameters("TAPPED_HOLE", { ...base, thread: "   " });
  assert.equal(r[0].field, "thread");
});

test("an unknown kind is refused before its fields are looked up", () => {
  const r = validateFeatureParameters("WORMHOLE", {});
  assert.equal(r.length, 1);
  assert.equal(r[0].field, "kind");
});

test("every feature kind has fields declared", () => {
  // A kind with no fields would validate anything, including nothing, and
  // write a feature with no geometry at all.
  for (const k of FEATURE_KINDS) {
    assert.ok(FEATURE_FIELDS[k]?.length > 0, `${k} declares no fields`);
  }
  assert.deepEqual(Object.keys(FEATURE_FIELDS).sort(), [...FEATURE_KINDS].sort());
});

test("the declared fields match the domain models the engines read", () => {
  // The spec drives both the form and the accept path. If it drifts from the
  // interfaces, features validate and then read as undefined downstream.
  const src = readFileSync("src/lib/domain/features.ts", "utf8");
  const checks: [string, string[]][] = [
    ["CircPocketFeature", ["centerX", "centerY", "diameter", "depth", "bottomRadius", "top", "through"]],
    ["RectPocketFeature", ["centerX", "centerY", "width", "length", "depth", "cornerRadius", "bottomRadius", "top"]],
    ["SlotFeature", ["startX", "startY", "endX", "endY", "width", "depth", "top"]],
    ["BossFeature", ["centerX", "centerY", "diameter", "height"]],
  ];
  for (const [iface, expected] of checks) {
    const body = new RegExp(`interface ${iface}[\\s\\S]*?\\n}`).exec(src);
    assert.ok(body, `${iface} moved`);
    for (const field of expected) {
      assert.ok(new RegExp(`\\n  ${field}[?]?:`).test(body![0]), `${iface} no longer declares ${field}`);
    }
  }
  const bore = FEATURE_FIELDS.BORE.map((f) => f.name).sort();
  assert.deepEqual(bore, ["bottomRadius", "centerX", "centerY", "depth", "diameter", "through", "top"]);
});

test("coercion produces the types the domain models expect", () => {
  const out = coerceFeatureParameters("BORE", { centerX: "-1.25", centerY: "0", diameter: "1.5748", depth: "0.75", bottomRadius: "0", top: "0", through: true });
  assert.equal(typeof out.centerX, "number");
  assert.equal(out.centerX, -1.25);
  assert.equal(out.through, true);
  const f = { id: "x", kind: "BORE", label: "b", functionalRole: "NONE", critical: false, ...out } as unknown as Feature;
  assert.equal((f as { diameter: number }).diameter, 1.5748);
});

test("an absent optional boolean becomes false, and nothing else is filled in", () => {
  const out = coerceFeatureParameters("BORE", { centerX: 0, centerY: 0, diameter: 1, depth: 1, bottomRadius: 0, top: 0 });
  assert.equal(out.through, false);
  const sparse = coerceFeatureParameters("BORE", { centerX: 0 });
  assert.deepEqual(Object.keys(sparse).sort(), ["centerX", "through"], "an absent number was filled in");
});

/* ---- both doors go through the same validation ---- */

const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");

test("hand entry validates server-side", () => {
  const src = strip(readFileSync("src/app/(app)/parts/[id]/features/feature-actions.ts", "utf8"));
  assert.match(src, /validateFeatureParameters\(kind, params\)/);
  assert.match(src, /if \(refusals\.length > 0\) return/);
  assert.match(src, /coerceFeatureParameters\(/);
  assert.match(src, /actorType: "HUMAN"/);
});

test("accepting a proposal validates through the same spec", () => {
  // This was the hole: a suggestion missing a diameter was written straight
  // through, because featureSuggestionSchema accepts any record.
  const src = strip(readFileSync("src/app/(app)/parts/[id]/proposals/page.tsx", "utf8"));
  assert.match(src, /validateFeatureParameters\(s\.kind, params\)/);
  assert.match(src, /skipped\.push\(/, "an unbuildable suggestion is written anyway");
  assert.match(src, /coerceFeatureParameters\(s\.kind, params\)/);
});

test("a blank tolerance is no tolerance, not a zero one", () => {
  // A ±0.0000 band is unmeasurable and would fail every capability check for
  // a reason nobody typed.
  const src = strip(readFileSync("src/app/(app)/parts/[id]/features/feature-actions.ts", "utf8"));
  assert.match(src, /tolerancePlus: tolPlus === "" \? null : Number\(tolPlus\)/);
  assert.match(src, /toleranceMinus: tolMinus === "" \? null : Number\(tolMinus\)/);
});

test("the form renders from the spec rather than a second list of fields", () => {
  const src = strip(readFileSync("src/components/add-feature.tsx", "utf8"));
  assert.match(src, /FEATURE_FIELDS\[kind\]/);
  assert.ok(!/centerX|diameter|bottomRadius/.test(src), "the form hardcodes field names the spec already declares");
});

test("removing a feature removes the operations planned for it", () => {
  const src = strip(readFileSync("src/app/(app)/parts/[id]/features/feature-actions.ts", "utf8"));
  assert.match(src, /db\.operation\.deleteMany\(\{ where: \{ featureId: owned\.id \} \}\)/);
  // And only within this revision — the feature is resolved through it first.
  assert.match(src, /partRevisionId: revision\.revisionId/);
});
