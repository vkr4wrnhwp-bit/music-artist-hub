import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { confusableAlternatives, normaliseStamp, resolveStampReadings } from "@/lib/engines/bearing-stamp";
import { findBearing } from "@/lib/engines/mating";

/**
 * "Bearing number? Allow: TYPE NUMBER / UPLOAD PHOTO / UNKNOWN." The panel had
 * a free-text field and UNKNOWN, and no photo path at all.
 *
 * What makes this dangerous rather than convenient: a designation is
 * dimensions. findBearing turns 6203 into a 17 mm bore and 6208 into a 40 mm
 * one, and the mating analysis reasons about the fit from that. A misread
 * stamp does not produce a wrong caption, it produces the wrong bore.
 */

test("a designation really does decide a bore, which is why this is confirmed", () => {
  // The precondition the whole design rests on.
  assert.equal(findBearing("6203")!.bore, 17);
  assert.equal(findBearing("6208")!.bore, 40);
});

test("a clean reading resolves to the catalogue entry with its dimensions", () => {
  const [c] = resolveStampReadings([{ text: "6203-2RS", confidence: 0.95 }]);
  assert.equal(c.readAs, "6203-2RS");
  assert.equal(c.bearing?.designation, "6203");
  assert.match(c.note, /17 mm bore/);
  assert.match(c.note, /Measure the bearing to confirm/);
});

test("a designation the catalogue does not hold gets no invented dimensions", () => {
  const [c] = resolveStampReadings([{ text: "NU2210E", confidence: 0.9 }]);
  assert.equal(c.bearing, null);
  assert.match(c.note, /Not a designation CANVAS holds dimensions for/);
  assert.ok(!/mm bore/.test(c.note), "dimensions were stated for a bearing CANVAS does not hold");
});

test("confusable characters are offered as alternatives, never silently corrected", () => {
  // "62O3" with a letter O could be 6203. Correcting it quietly would hide
  // that the reading was ambiguous, and the machinist is holding the bearing.
  const out = resolveStampReadings([{ text: "62O3", confidence: 0.8 }]);
  const texts = out.map((c) => c.readAs);
  assert.ok(texts.includes("62O3"), "the reading as it actually appeared was dropped");
  assert.ok(texts.includes("6203"), "the alternative was not offered");
  const alt = out.find((c) => c.readAs === "6203")!;
  const orig = out.find((c) => c.readAs === "62O3")!;
  assert.ok(alt.confidence < 0.8, "an alternative was offered at the confidence of the reading it came from");
  assert.ok(alt.confidence <= orig.confidence, "a guess about a guess outranked the guess");
  assert.match(alt.note, /Could be this if the stamp reads/);
});

test("an alternative that is not in the catalogue is not offered at all", () => {
  // Substituting characters until something appears would manufacture
  // candidates out of noise.
  assert.deepEqual(confusableAlternatives("XYZO"), []);
});

test("normalisation strips separators and nothing else", () => {
  assert.equal(normaliseStamp("  6203 - 2RS "), "62032RS");
  // It must NOT substitute characters — that is what makes an alternative an
  // alternative rather than a correction.
  assert.equal(normaliseStamp("62O3"), "62O3");
});

test("readings are ordered by confidence, then by whether they are recognised", () => {
  const out = resolveStampReadings([
    { text: "NU2210E", confidence: 0.9 },
    { text: "6203", confidence: 0.9 },
    { text: "6208", confidence: 0.4 },
  ]);
  assert.equal(out[0].readAs, "6203", "an unrecognised designation outranked a recognised one at equal confidence");
  assert.equal(out[out.length - 1].readAs, "6208");
});

test("the same designation read twice appears once", () => {
  const out = resolveStampReadings([
    { text: "6203", confidence: 0.9 },
    { text: " 6203 ", confidence: 0.5 },
  ]);
  assert.equal(out.filter((c) => c.bearing?.designation === "6203" && c.readAs.trim() === "6203").length, 1);
});

test("a nonsense confidence does not escape 0..1", () => {
  for (const [given, expected] of [[2, 1], [-1, 0], [NaN, 0]] as const) {
    const [c] = resolveStampReadings([{ text: "6203", confidence: given }]);
    assert.equal(c.confidence, expected, `confidence ${given} became ${c.confidence}`);
  }
});

test("an empty reading produces no candidate", () => {
  assert.deepEqual(resolveStampReadings([{ text: "   ", confidence: 0.9 }]), []);
  assert.deepEqual(resolveStampReadings([]), []);
});

/* ---- the model reads characters and nothing else ---- */

const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");

test("the deterministic provider says it cannot see rather than guessing", () => {
  // Returning a plausible designation from nothing is the exact failure
  // principle 5 names, on a value that decides a bore diameter.
  const src = strip(readFileSync("src/lib/ai/deterministic.ts", "utf8"));
  const fn = /async readBearingStamp\([\s\S]{0,600}?\n  \}/.exec(src);
  assert.ok(fn, "the deterministic provider does not implement readBearingStamp");
  assert.match(fn![0], /connected: false/);
  assert.match(fn![0], /readings: \[\]/);
  assert.ok(!/6\d{3}/.test(fn![0]), "the deterministic provider returns a bearing number");
});

test("the vision prompt asks for characters, never for dimensions", () => {
  const src = readFileSync("src/lib/ai/anthropic.ts", "utf8");
  const fn = /async readBearingStamp\([\s\S]*?\n  \}\n/.exec(src)!;
  assert.match(fn[0], /Report the characters exactly as they appear/);
  assert.match(fn[0], /do not guess a common bearing number/);
  assert.match(fn[0], /Do not state the bearing's dimensions/);
});

test("the endpoint stores a photograph and never a designation", () => {
  // A candidate is not a value until a human accepts one.
  const src = strip(readFileSync("src/app/api/features/[fid]/bearing-stamp/route.ts", "utf8"));
  assert.ok(!/matingDesignation/.test(src), "the endpoint writes a designation");
  const writes = [...src.matchAll(/db\.(\w+)\.(create|update|delete|upsert)/g)].map((m) => `${m[1]}.${m[2]}`);
  assert.deepEqual(writes, ["uploadedAsset.create"], "the endpoint writes something other than the photograph");
  assert.match(src, /resolveStampReadings\(reading\.readings\)/, "readings are not resolved against the catalogue");
});

test("the endpoint resolves the feature through the session's organisation", () => {
  const src = strip(readFileSync("src/app/api/features/[fid]/bearing-stamp/route.ts", "utf8"));
  assert.match(src, /partRevision: \{ part: \{ organizationId: user\.organizationId \} \}/);
  assert.match(src, /requireWriteApi\(\)/);
});

test("the reading is audited as the model's work", () => {
  // Principle 13: the actor is stated. The model did the reading, and that it
  // produced nothing storable is the point.
  const src = strip(readFileSync("src/app/api/features/[fid]/bearing-stamp/route.ts", "utf8"));
  assert.match(src, /actorType: "AI"/);
});

test("a designation edited after being picked is recorded as typed", () => {
  // Otherwise a photograph is attached to a number it does not show.
  const src = strip(readFileSync("src/components/mating-designation.tsx", "utf8"));
  assert.match(src, /picked !== null && picked\.designation === value/);
  assert.match(src, /confirmedFromPhoto \? picked\.photoId : ""/);
});

test("the photo route is only offered when the mating component is a bearing", () => {
  const src = readFileSync("src/app/(app)/parts/[id]/features/[fid]/page.tsx", "utf8");
  assert.match(src, /showPhoto=\{component === "BEARING"\}/);
});

test("the saved provenance is verified server-side, not taken from the form", () => {
  const src = strip(readFileSync("src/app/(app)/parts/[id]/features/[fid]/page.tsx", "utf8"));
  // A photo id that is not this shop's is dropped rather than stored.
  assert.match(src, /db\.uploadedAsset\.findFirst\(\{\s*where: \{ id: photoRaw, organizationId: currentUser\.organizationId \}/);
  // And an unrecognised source falls to USER rather than being stored raw.
  assert.match(src, /sourceRaw === "PHOTO_CONFIRMED" \? "PHOTO_CONFIRMED" : "USER"/);
});
