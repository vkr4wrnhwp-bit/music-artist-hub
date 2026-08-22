import { test } from "node:test";
import assert from "node:assert/strict";
import { DeterministicProvider } from "@/lib/ai/deterministic";

/**
 * This is the DEFAULT provider — it runs whenever no API key is configured,
 * which is the out-of-the-box deployment. Most shops would only ever meet
 * this parser, so "it is only the fallback" is exactly backwards.
 *
 * Everything stored inside CANVAS is inches. The STEP importer scales
 * millimetre files and records what the file said; the NC parser does the
 * same for a G21 program. So the central test here is that a dimension
 * arrives in inches however the operator wrote it — because every engine
 * downstream, from envelope banding to cutting force to cost, reads these
 * numbers as inches without asking.
 *
 * The recognition vocabulary is not pinned exhaustively. Which words a
 * machinist might type is open-ended and a shop may want more; what is pinned
 * is that nothing recognised is mis-scaled and nothing unrecognised is
 * guessed at.
 */

const p = new DeterministicProvider();
const parse = (prompt: string) => p.interpretPartPrompt(prompt);

const MM = 25.4;
const close = (a: number, b: number, tol = 5e-4) => Math.abs(a - b) <= tol;

/* ---------------- Units ---------------- */

test("a metric envelope is stored in inches", () => {
  // "150 x 100 x 25 mm" was stored as 150 x 100 x 25 and every engine
  // downstream read it as a 150 INCH part.
  return parse("6061 bracket 150 x 100 x 25 mm, qty 10").then((r) => {
    assert.ok(r.finishedEnvelope);
    assert.ok(close(r.finishedEnvelope.x, 150 / MM), `x = ${r.finishedEnvelope.x}`);
    assert.ok(close(r.finishedEnvelope.y, 100 / MM));
    assert.ok(close(r.finishedEnvelope.z, 25 / MM));
    assert.equal(r.units, "MM", "what the operator typed is still recorded");
  });
});

test("an inch envelope is untouched", async () => {
  const r = await parse("6061 bracket 6 x 4 x 1, qty 10");
  assert.deepEqual(r.finishedEnvelope, { x: 6, y: 4, z: 1 });
  assert.equal(r.units, "IN");
});

test("the facing allowance is inches, not whatever unit the text used", async () => {
  // The allowance is a fixed 0.125 and was being added to the raw parsed
  // number, so a metric part got 0.125 MILLIMETRES of stock to face — two
  // thou per side, which is not a facing allowance at all.
  const metric = await parse("6061 bracket 150 x 100 x 25 mm");
  const inch = await parse("6061 bracket 6 x 4 x 1");
  const allowance = (r: Awaited<ReturnType<typeof parse>>) => r.stock!.z! - r.finishedEnvelope!.z;
  assert.ok(close(allowance(metric), allowance(inch)), `metric leaves ${allowance(metric)}" and inch leaves ${allowance(inch)}"`);
  assert.ok(allowance(metric) > 0.1, "a facing allowance you can actually face");
});

test("stock is always larger than the finished part, in either unit", async () => {
  for (const prompt of ["6061 bracket 6 x 4 x 1", "6061 bracket 150 x 100 x 25 mm"]) {
    const r = await parse(prompt);
    for (const axis of ["x", "y", "z"] as const) {
      assert.ok(r.stock![axis]! > r.finishedEnvelope![axis], `${prompt}: stock ${axis} is not oversize`);
    }
  }
});

test("a metric tolerance is stored in inches", async () => {
  const r = await parse("6061 bracket 6 x 4 x 1, ±0.13 mm");
  assert.ok(close(r.generalTolerance!, 0.13 / MM), `got ${r.generalTolerance}`);
});

test("an inch tolerance is untouched", async () => {
  const r = await parse("6061 bracket 6 x 4 x 1, ±0.005");
  assert.equal(r.generalTolerance, 0.005);
});

test("the unit is read at each measurement, not once for the sentence", async () => {
  // Inch plate with a metric bearing bore is an ordinary thing for a shop to
  // type, and a sentence-wide flag gets it wrong whichever way it falls. The
  // first version of this fix used one flag and converted the envelope too.
  // Written "40 mm" with the space deliberately: `\bmm\b` does not match
  // "40mm", because there is no word boundary between a digit and a letter.
  // The first version of this test used "40mm", so the sentence-wide flag was
  // false either way and the test could not tell the two behaviours apart.
  const r = await parse("6061 plate 6 x 4 x 1 with a 40 mm bearing bore, qty 10");
  assert.deepEqual(r.finishedEnvelope, { x: 6, y: 4, z: 1 }, "the inch envelope must not be scaled");
  assert.ok(close(r.stock!.z!, 1.125), `the inch stock must not be scaled either; got ${r.stock!.z}`);
  assert.ok(
    r.features?.some((f) => /1\.574/.test(f)),
    `the metric bore must be; got [${(r.features ?? []).join(" | ")}]`,
  );
});

test("a metric feature inside a metric part is converted once, not twice", async () => {
  const r = await parse("6061 plate 150 x 100 x 25 mm with a 40 mm bore");
  assert.ok(r.features?.some((f) => /1\.574/.test(f)), `got [${(r.features ?? []).join(" | ")}]`);
});

/* ---------------- The phrasing the app's own data uses ---------------- */

test("a bearing bore is recognised however it is phrased", async () => {
  // The pattern wanted the number immediately before the word "bore", so
  // "40 mm bearing bore" — the phrasing this application's own seed part
  // uses for its headline feature — came back as "diameter not stated".
  const phrasings = [
    "6061 plate 6 x 4 x 1 with a 40mm bearing bore",
    "6061 plate 6 x 4 x 1, 40 mm bearing bore",
    "6061 plate 6 x 4 x 1, bore 40 mm",
    "6061 plate 6 x 4 x 1 with a 1.5748 bore",
    "6061 plate 6 x 4 x 1 with a 1.5748 dia bore",
  ];
  for (const prompt of phrasings) {
    const r = await parse(prompt);
    assert.ok(
      r.features?.some((f) => /⌀1\.574\d bore/.test(f)),
      `"${prompt}" -> [${(r.features ?? []).join(" | ")}]`,
    );
  }
});

test("a qualifier list, not any word, sits between the size and the bore", async () => {
  // `\w+` between the number and "bore" would read "2 inch thick plate with a
  // bore" as a two inch bore.
  // Two words is what the qualifier list allows, so the probe has to be a
  // phrase with exactly two: "0.250 wall around bore" reads as a quarter inch
  // bore under `\w+` and as no bore at all under the closed list. The first
  // version of this test used four intervening words, which the {0,2} bound
  // rejected on its own — so it proved nothing about the list.
  const r = await parse("6061 plate 6 x 4 x 1, 0.250 wall around bore");
  assert.ok(
    !r.features?.some((f) => /⌀0\.2500/.test(f)),
    `a wall thickness became a bore diameter: [${(r.features ?? []).join(" | ")}]`,
  );
});

test("a bore with no size says so rather than guessing one", async () => {
  const r = await parse("6061 plate 6 x 4 x 1 with a bearing bore");
  assert.ok(r.features?.some((f) => /diameter not stated/i.test(f)));
});

/* ---------------- Nothing unrecognised is guessed ---------------- */

test("what it could not read becomes an unknown, not a default", async () => {
  const r = await parse("make me a bracket");
  for (const pattern of [/material/i, /envelope/i, /quantity/i, /tolerance/i]) {
    assert.ok(r.unknowns.some((u) => pattern.test(u)), `${pattern} is not listed as unknown`);
  }
  assert.equal(r.material, undefined, "no material is not a default material");
  assert.equal(r.finishedEnvelope, undefined);
  assert.equal(r.quantity, undefined);
  assert.equal(r.generalTolerance, undefined);
  assert.equal(r.stock, undefined, "and no stock either");
});

test("responsibility is always listed as outstanding, however complete the rest is", async () => {
  // No description, however detailed, tells you what happens when the part
  // fails. That is an interview question.
  const r = await parse("6061-T6 bracket 6 x 4 x 1, qty 100, ±0.002, 63 Ra, four 1/4-20 tapped holes");
  assert.ok(r.unknowns.some((u) => /functional responsibility/i.test(u)), `got [${r.unknowns.join(" | ")}]`);
});

test("confidence reflects how much was read and never reaches certainty on a bare prompt", async () => {
  const bare = await parse("make me a bracket");
  const full = await parse("6061-T6 bracket 6 x 4 x 1, qty 100, ±0.002, four 1/4-20 tapped holes");
  assert.ok(full.confidence > bare.confidence);
  assert.ok(bare.confidence < 0.5, `a prompt with nothing in it scored ${bare.confidence}`);
  assert.ok(full.confidence <= 1);
});

/* ---------------- Recognition ---------------- */

test("materials a shop types are recognised with their condition", async () => {
  const cases: [string, string][] = [
    ["6061-T6 plate", "Aluminum 6061"], ["7075-T651 block", "Aluminum 7075"],
    ["4140 pre-hard", "Steel 4140"], ["1018 bar", "Steel 1018"],
    ["304 stainless", "Stainless 304"], ["17-4 PH", "Stainless 17-4 PH"],
    ["Ti-6Al-4V", "Titanium 6Al-4V"], ["Delrin", "Acetal (Delrin)"],
  ];
  for (const [text, name] of cases) {
    const r = await parse(`${text} 6 x 4 x 1`);
    assert.equal(r.material, name, `"${text}"`);
    assert.ok(r.materialCondition, `${name} has no condition`);
  }
});

test("a specific alloy beats the generic word for its family", async () => {
  // "7075 aluminum plate" must not fall through to the generic aluminium row.
  const r = await parse("7075-T651 aluminum plate 6 x 4 x 1");
  assert.equal(r.material, "Aluminum 7075");
});

test("counts written as words are read", async () => {
  const r = await parse("6061 plate 6 x 4 x 1 with four 1/4-20 tapped holes");
  assert.ok(r.features?.some((f) => /^4 × /.test(f)), `got [${(r.features ?? []).join(" | ")}]`);
});

test("a feature named with no size is listed as unsized rather than dropped", async () => {
  const r = await parse("6061 plate 6 x 4 x 1 with a pocket and a chamfer");
  assert.ok(r.features?.some((f) => /pocket \(depth not stated\)/i.test(f)));
  assert.ok(r.features?.some((f) => /chamfer \(size not stated\)/i.test(f)));
});

test("features are not duplicated when a phrase matches twice", async () => {
  const r = await parse("6061 plate 6 x 4 x 1 with a 0.500 deep pocket, 0.500 deep pocket");
  assert.equal(new Set(r.features).size, r.features?.length);
});

test("the part is named from what it is, not left blank", async () => {
  for (const [text, name] of [["bracket", "Bracket"], ["housing", "Housing"], ["spacer", "Spacer"]] as const) {
    const r = await parse(`6061 ${text} 6 x 4 x 1`);
    assert.equal(r.partName, name);
  }
});

test("parsing is deterministic — that is the whole point of this provider", async () => {
  const prompt = "6061-T6 bracket 150 x 100 x 25 mm, qty 10, ±0.13 mm, 40 mm bore, four M6 tapped holes";
  assert.deepEqual(await parse(prompt), await parse(prompt));
});
