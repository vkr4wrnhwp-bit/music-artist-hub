import { test } from "node:test";
import assert from "node:assert/strict";
import { techniqueFor, techniqueCoverage, UNIVERSAL_CAUTIONS } from "@/lib/metrology/technique";
import { METROLOGY_DEVICES } from "@/lib/domain/shop";

/**
 * The risk with this feature is not that the words are wrong — it is that
 * they stop being a lookup and start being advice about a particular part,
 * or that they start sounding like they verify something. These pin the
 * shape rather than the prose.
 */

test("every instrument the shop can record has technique on file", () => {
  const missing = METROLOGY_DEVICES.filter((d) => techniqueFor(d, null) === null);
  assert.deepEqual(missing, [], `no technique for: ${missing.join(", ")}`);
});

test("an unknown instrument type renders nothing rather than generic filler", () => {
  assert.equal(techniqueFor("PLASMA_CALIPER_9000", null), null);
  assert.equal(techniqueFor("", null), null);
});

test("technique is a pure lookup — the same inputs always give the same words", () => {
  const a = techniqueFor("BORE_GAUGE", "INTERNAL_ROUND");
  const b = techniqueFor("BORE_GAUGE", "INTERNAL_ROUND");
  assert.deepEqual(a, b);
});

test("geometry changes the technique where it genuinely differs", () => {
  const inside = techniqueFor("DIGITAL_CALIPER", "INTERNAL_ROUND");
  const outside = techniqueFor("DIGITAL_CALIPER", "EXTERNAL");
  assert.notDeepEqual(inside?.taking, outside?.taking);
  // Inside is the largest reading, outside is square-on. Getting these the
  // wrong way round is the classic caliper error.
  assert.ok(inside?.taking.some((s) => /largest|maximum/i.test(s)));
  assert.ok(outside?.taking.some((s) => /square/i.test(s)));
});

test("no entry claims that following it verifies, certifies or clears anything", () => {
  // The first version of this matched the WORD "verify" and tripped on the
  // tape rule saying "if a tolerance is being verified, this is the wrong
  // tool" — which is the opposite of the claim being guarded against. The
  // failure mode is an entry asserting that the technique or the instrument
  // does the verifying, so match the claim, not the vocabulary.
  const forbidden =
    /\b(this|these|it|the reading|the measurement|following (this|these))\s+(verif(y|ies)|certif(y|ies)|confirm(s)?|prove(s)?|guarantee(s)?)\b|clears the gate|makes it capable/i;
  for (const d of techniqueCoverage()) {
    const t = techniqueFor(d, null)!;
    for (const line of [...t.setup, ...t.taking, ...t.pitfalls]) {
      assert.ok(!forbidden.test(line), `${d} claims to verify something: "${line}"`);
    }
  }
});

test("every entry carries at least one pitfall — the part a machinist does not know", () => {
  for (const d of techniqueCoverage()) {
    const t = techniqueFor(d, null)!;
    assert.ok(t.pitfalls.length > 0, `${d} has no pitfalls`);
    assert.ok(t.setup.length > 0 && t.taking.length > 0, `${d} is incomplete`);
  }
});

test("the bore gauge says to take the minimum, not the maximum", () => {
  // The single most consequential technique detail in the set: rocking to the
  // reversal point. Getting it backwards reads every bore oversize.
  const t = techniqueFor("BORE_GAUGE", "INTERNAL_ROUND")!;
  assert.ok(t.taking.some((s) => /minimum/i.test(s)));
  assert.ok(!t.taking.some((s) => /take the maximum/i.test(s)));
});

test("the spindle probe admits it cannot independently verify the machine that cut the part", () => {
  const t = techniqueFor("MACHINE_PROBE", null)!;
  assert.ok(
    t.pitfalls.some((s) => /cannot see that machine|systematic error/i.test(s)),
    "probing on the cutting machine is not independent verification, and it must say so",
  );
});

test("universal cautions are stated once, not repeated into every entry", () => {
  assert.ok(UNIVERSAL_CAUTIONS.length > 0);
  assert.ok(UNIVERSAL_CAUTIONS.some((c) => /20 °C|68 °F/.test(c)), "the reference temperature belongs here");
  for (const d of techniqueCoverage()) {
    const t = techniqueFor(d, null)!;
    const all = [...t.setup, ...t.taking, ...t.pitfalls].join(" ");
    assert.ok(!/68 °F/.test(all), `${d} repeats a universal caution`);
  }
});
