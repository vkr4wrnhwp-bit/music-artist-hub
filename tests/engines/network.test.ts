import { test } from "node:test";
import assert from "node:assert/strict";
import {
  buildFingerprint,
  describeFingerprintDisclosure,
  materialFamilyOf,
  MATERIAL_FAMILIES,
  WORKHOLDING_CLASSES,
  FINGERPRINT_OPERATIONS,
  SHARING_LEVELS,
  SHARING_DESCRIPTION,
  JOB_OUTCOMES,
  OUTCOME_CAUSES,
  OUTCOME_LABEL,
  type FingerprintInput,
  type ManufacturingFingerprint,
} from "@/lib/engines/network";
import { emptyPartIntent, type PartIntent } from "@/lib/domain/part-intent";
import type { Provenanced } from "@/lib/provenance";
import type { Feature, Stock } from "@/lib/domain/features";

/**
 * Locked principle 13. A shop's part geometry is its livelihood, and this is
 * the only engine whose output is designed to leave the organisation.
 *
 * The file states its own rules: a fingerprint carries "bands, families and
 * classes, never dimensions, never names, never text, never geometry". So
 * the central test here is not about any one field — it is that NO field can
 * carry a string the user typed, and that every field which leaves appears on
 * the page where the user consents to it leaving.
 */

const P = <T,>(value: T): Provenanced<T> => ({
  value, source: "USER", confidence: "HIGH", confirmedByUser: true,
});

const intent = (o: Partial<PartIntent> = {}): PartIntent => ({ ...emptyPartIntent("Rotor housing"), ...o });

const input = (over: Partial<FingerprintInput> = {}): FingerprintInput => ({
  intent: intent({ material: P("Aluminum 6061"), quantity: P(50) }),
  stock: { form: "RECTANGULAR", x: 6, y: 4, z: 1, material: "Aluminum 6061" } as Stock,
  features: [],
  setupCount: 2,
  workholdingType: "VISE",
  machineTravelX: 30,
  operationTypes: ["FACE", "DRILL"],
  ...over,
});

/** Everything a shop might type that must never appear in a fingerprint. */
const SECRETS = ["ACME-Aerospace", "Boeing", "Rotor housing", "customer", "proprietary"];

const stringsIn = (v: unknown): string[] => {
  if (typeof v === "string") return [v];
  if (Array.isArray(v)) return v.flatMap(stringsIn);
  if (v && typeof v === "object") return Object.values(v).flatMap(stringsIn);
  return [];
};

/* ---------------- Nothing the user typed leaves ---------------- */

test("free text a shop typed never reaches the fingerprint", () => {
  // Three fields were passing user input straight through. The material field
  // took the first whitespace-delimited token, so "Boeing-spec Ti-6Al-4V ELI"
  // left as "BOEING-SPEC". workholdingType was cast into a closed union
  // without being checked. operationTypes is a caller-filled string[], so an
  // operation LABEL went with it.
  const fp = buildFingerprint(
    input({
      intent: intent({ material: P("Boeing-spec Ti-6Al-4V ELI"), quantity: P(50) }),
      workholdingType: "Kurt 6in with ACME-Aerospace custom jaws",
      operationTypes: ["FACE", "Rough the ACME-Aerospace rotor pocket", "DRILL"],
    }),
  );
  const text = stringsIn(fp).join(" | ");
  for (const secret of SECRETS) {
    assert.ok(!text.toLowerCase().includes(secret.toLowerCase()), `"${secret}" leaked: ${text}`);
  }
});

test("every string in a fingerprint comes from a closed vocabulary", () => {
  // The general form of the rule, so a new free-text field fails here rather
  // than needing its own test.
  const allowed = new Set<string>([
    ...MATERIAL_FAMILIES, ...WORKHOLDING_CLASSES, ...FINGERPRINT_OPERATIONS,
    "PRISMATIC_PLATE", "PRISMATIC_BLOCK", "ROTATIONAL", "THIN_WALL", "COMPLEX",
    "MILL_3AXIS", "MILL_MULTIAXIS", "TURN", "TURN_MILL", "FABRICATION", "ADDITIVE",
    "XS", "S", "M", "L", "XL", "UNKNOWN",
    "COARSE", "STANDARD", "PRECISION", "HIGH_PRECISION",
    "AS_MACHINED", "FINE", "GROUND", "POLISHED",
    "ONE_OFF", "LOW", "MEDIUM", "HIGH", "VERY_HIGH",
    "BENCHTOP", "STANDARD_VMC", "LARGE_VMC", "HMC", "MULTIAXIS",
    // Feature kinds are a closed enum in the domain layer.
    "FACE", "RECT_POCKET", "CIRC_POCKET", "SLOT", "DRILLED_HOLE", "TAPPED_HOLE",
    "BORE", "OUTSIDE_CONTOUR", "CHAMFER", "ENGRAVING",
  ]);

  const wild = buildFingerprint(
    input({
      intent: intent({ material: P("Unobtainium Grade 9 — ACME proprietary") }),
      workholdingType: "something nobody has classified",
      operationTypes: ["FACE", "not an operation type at all"],
      features: [
        { id: "f1", kind: "BORE", label: "ACME rotor bore", functionalRole: "BEARING_SEAT", critical: true } as unknown as Feature,
      ],
    }),
  );
  for (const v of stringsIn(wild)) {
    assert.ok(allowed.has(v), `"${v}" is not in any closed vocabulary`);
  }
});

test("an unrecognised material becomes OTHER rather than the shop's words for it", () => {
  assert.equal(materialFamilyOf("Unobtainium Grade 9"), "OTHER");
  assert.equal(materialFamilyOf("ACME-CUSTOMER-ALLOY-7"), "OTHER");
  assert.equal(materialFamilyOf(null), "UNKNOWN");
  assert.equal(materialFamilyOf("   "), "UNKNOWN");
});

test("materials a shop actually types map to the right family", () => {
  const cases: [string, string][] = [
    ["Aluminum 6061", "ALUMINUM"], ["6061-T6", "ALUMINUM"], ["7075-T651", "ALUMINUM"], ["MIC-6", "ALUMINUM"],
    ["Steel 1018", "STEEL"], ["4140 pre-hard", "STEEL"], ["A36 plate", "STEEL"],
    ["Stainless 304", "STAINLESS"], ["316L", "STAINLESS"], ["17-4 PH", "STAINLESS"],
    ["Titanium 6Al-4V", "TITANIUM"], ["Ti-6Al-4V ELI", "TITANIUM"],
    ["Inconel 718", "NICKEL_ALLOY"],
    ["Ductile cast iron", "CAST_IRON"],
    ["Brass 360", "BRASS"], ["Delrin", "PLASTIC"], ["PEEK", "PLASTIC"],
  ];
  for (const [raw, family] of cases) {
    assert.equal(materialFamilyOf(raw), family, `"${raw}"`);
  }
});

test("every material family the mapper can return is in the declared vocabulary", () => {
  const samples = ["6061", "1018", "304", "Ti", "Inconel", "cast iron", "brass", "bronze", "copper", "magnesium", "Delrin", "G10", "mystery", null];
  for (const s of samples) {
    assert.ok(MATERIAL_FAMILIES.includes(materialFamilyOf(s)), `${s} -> ${materialFamilyOf(s)}`);
  }
});

test("an unrecognised workholding type is CUSTOM, not the description", () => {
  for (const raw of ["Kurt 6in with ACME jaws", "", "vise", null]) {
    const fp = buildFingerprint(input({ workholdingType: raw }));
    assert.ok(WORKHOLDING_CLASSES.includes(fp.workholdingClass), `"${raw}" -> ${fp.workholdingClass}`);
  }
  assert.equal(buildFingerprint(input({ workholdingType: "Kurt 6in with ACME jaws" })).workholdingClass, "CUSTOM");
  assert.equal(buildFingerprint(input({ workholdingType: "SOFT_JAWS" })).workholdingClass, "SOFT_JAWS");
});

test("an operation that is not a known type is dropped, not disclosed", () => {
  const fp = buildFingerprint(input({ operationTypes: ["FACE", "Rough the ACME rotor pocket", "DRILL", "TAP"] }));
  assert.deepEqual(fp.operationSequence, ["FACE", "DRILL", "TAP"]);
  for (const op of fp.operationSequence) assert.ok(FINGERPRINT_OPERATIONS.includes(op));
});

/* ---------------- The consent page shows everything that leaves ---------------- */

test("every field in the fingerprint appears on the disclosure table", () => {
  // The table was a hand-written list and it had drifted: surfaceFinishClass
  // and operationSequence were both in the fingerprint and absent from it. A
  // user consenting on the strength of that page consented to thirteen fields
  // while fifteen left.
  const fp = buildFingerprint(input());
  const rows = describeFingerprintDisclosure(fp);
  assert.equal(rows.length, Object.keys(fp).length, "one row per field, no more and no fewer");

  // Row count alone is not enough: an unclassified field still produces a
  // row, so removing a field's entry keeps the count right while the user
  // sees "NOT CLASSIFIED" where a real disclosure should be. Every field the
  // builder actually emits has to be classified.
  const unclassified = rows.filter((r) => r.risk === "UNCLASSIFIED");
  assert.deepEqual(
    unclassified.map((r) => r.field),
    [],
    "a field is leaving that nobody has classified for the consent page",
  );
});

test("a field with no classification is loud rather than absent", () => {
  // The structural point: the table is derived from the fingerprint, so a
  // field added without a disclosure entry cannot silently fail to appear.
  const fp = { ...buildFingerprint(input()), someNewField: "whatever" } as unknown as ManufacturingFingerprint;
  const rows = describeFingerprintDisclosure(fp);
  const row = rows.find((r) => /someNewField/.test(r.field));
  assert.ok(row, "an unclassified field must still appear");
  assert.equal(row.risk, "UNCLASSIFIED");
  assert.match(row.field, /review before this ships/i);
});

test("every disclosure row shows a real value", () => {
  const fp = buildFingerprint(input());
  for (const r of describeFingerprintDisclosure(fp)) {
    assert.ok(r.field.length > 0);
    assert.ok(r.value.length > 0, `${r.field} shows nothing`);
    assert.ok(!/undefined|NaN|\[object/.test(r.value), `${r.field} = ${r.value}`);
  }
});

test("the disclosure values are the fingerprint's values", () => {
  // A table that showed something other than what leaves would be worse than
  // no table.
  const fp = buildFingerprint(input({ operationTypes: ["FACE", "DRILL"] }));
  const rows = describeFingerprintDisclosure(fp);
  assert.equal(rows.find((r) => r.field === "Material family")!.value, fp.materialFamily);
  assert.equal(rows.find((r) => r.field === "Operation sequence")!.value, "FACE, DRILL");
  assert.equal(rows.find((r) => r.field === "Setup count")!.value, String(fp.setupCount));
});

/* ---------------- Unknown is a band, not a guess ---------------- */

test("a part with nothing recorded is banded UNKNOWN, not average", () => {
  // Stock absent came back "M", quantity absent came back "ONE_OFF",
  // tolerance absent "STANDARD" and machine travel absent "STANDARD_VMC". A
  // made-up band is both a false statement about the shop's part and a false
  // match against somebody else's.
  const fp = buildFingerprint(
    input({ intent: emptyPartIntent("X"), stock: null, machineTravelX: null, operationTypes: [] }),
  );
  assert.equal(fp.envelopeBand, "UNKNOWN");
  assert.equal(fp.quantityBand, "UNKNOWN");
  assert.equal(fp.toleranceClass, "UNKNOWN");
  assert.equal(fp.machineClass, "UNKNOWN");
  assert.equal(fp.materialFamily, "UNKNOWN");
});

test("a recorded value is banded, not reported as unknown", () => {
  // The base fixture deliberately records no general tolerance, so it has to
  // be supplied here — otherwise this asserts the opposite of what it says.
  const fp = buildFingerprint(
    input({ intent: intent({ material: P("Aluminum 6061"), quantity: P(50), generalTolerance: P(0.005) }) }),
  );
  for (const v of [fp.envelopeBand, fp.quantityBand, fp.toleranceClass, fp.machineClass, fp.materialFamily]) {
    assert.notEqual(v, "UNKNOWN");
  }
});

test("bands are ordered by size and never invert", () => {
  const at = (max: number) =>
    buildFingerprint(input({ stock: { form: "RECTANGULAR", x: max, y: 1, z: 1, material: "Al" } as Stock })).envelopeBand;
  assert.deepEqual([at(1), at(4), at(10), at(20), at(60)], ["XS", "S", "M", "L", "XL"]);
});

test("quantity bands rise with quantity", () => {
  const at = (q: number) => buildFingerprint(input({ intent: intent({ material: P("6061"), quantity: P(q) }) })).quantityBand;
  assert.deepEqual([at(1), at(10), at(100), at(1000), at(50000)], ["ONE_OFF", "LOW", "MEDIUM", "HIGH", "VERY_HIGH"]);
});

test("a tighter tolerance never reports a coarser class", () => {
  const at = (t: number) =>
    buildFingerprint(input({ intent: intent({ material: P("6061"), generalTolerance: P(t) }) })).toleranceClass;
  assert.deepEqual([at(0.02), at(0.005), at(0.001), at(0.0002)], ["COARSE", "STANDARD", "PRECISION", "HIGH_PRECISION"]);
});

/* ---------------- No dimension survives ---------------- */

test("two parts of different size in the same band fingerprint identically", () => {
  // If a band leaked its underlying dimension, these would differ.
  // Both sit inside the S envelope band AND on the same side of the
  // plate/block threshold — the first pair I picked straddled it, which is a
  // real distinction the fingerprint is entitled to make.
  const a = buildFingerprint(input({ stock: { form: "RECTANGULAR", x: 6, y: 4, z: 2, material: "Al" } as Stock }));
  const b = buildFingerprint(input({ stock: { form: "RECTANGULAR", x: 5.874, y: 3.219, z: 1.913, material: "Al" } as Stock }));
  assert.deepEqual(a, b, "the fingerprint distinguishes two parts inside one band");
});

test("no number in a fingerprint is a dimension", () => {
  // Counts and bands only. A non-integer would mean a measurement got out.
  const fp = buildFingerprint(
    input({ stock: { form: "RECTANGULAR", x: 5.874, y: 3.219, z: 1.913, material: "Al" } as Stock }),
  );
  for (const [k, v] of Object.entries(fp)) {
    if (typeof v !== "number") continue;
    assert.ok(Number.isInteger(v), `${k} = ${v} is not a count`);
  }
});

/* ---------------- Sharing levels ---------------- */

test("PRIVATE is the first level and says nothing leaves", () => {
  assert.equal(SHARING_LEVELS[0], "PRIVATE", "the default must be the most restrictive");
  assert.match(SHARING_DESCRIPTION.PRIVATE, /nothing about this part leaves/i);
  assert.match(SHARING_DESCRIPTION.PRIVATE, /default/i);
});

test("every sharing level is described, and the broader ones say what they cost", () => {
  for (const l of SHARING_LEVELS) {
    assert.ok(SHARING_DESCRIPTION[l] && SHARING_DESCRIPTION[l].length > 30, `${l} is undescribed`);
  }
  assert.match(SHARING_DESCRIPTION.NETWORK_MATCH, /identity is only revealed if you accept/i);
  assert.match(SHARING_DESCRIPTION.MARKETPLACE, /explicit per-part opt-in/i);
});

/* ---------------- Outcome vocabulary stays analysable ---------------- */

test("every outcome has a label and a cause list", () => {
  for (const code of JOB_OUTCOMES) {
    assert.ok(OUTCOME_LABEL[code], `${code} has no label`);
    assert.ok(OUTCOME_CAUSES[code] && OUTCOME_CAUSES[code].length > 0, `${code} offers no causes`);
  }
});

test("causes are chosen from a list rather than typed, so the data stays analysable", () => {
  // Free-text causes are both unanalysable and a disclosure risk.
  for (const code of JOB_OUTCOMES) {
    if (code === "SUCCESS" || code === "OTHER") continue;
    assert.ok(OUTCOME_CAUSES[code].length >= 4, `${code} offers too few causes to avoid "Other"`);
  }
});

test("fingerprinting is deterministic", () => {
  assert.deepEqual(buildFingerprint(input()), buildFingerprint(input()));
});
