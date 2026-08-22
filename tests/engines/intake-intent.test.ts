import { test } from "node:test";
import assert from "node:assert/strict";
import { buildIntakeIntent, stockFromExtraction } from "@/lib/ai/intake-intent";
import { partIntentExtractionSchema, type PartIntent, type PartIntentExtraction } from "@/lib/domain/part-intent";
import { isEngineeringGrade } from "@/lib/provenance";

/**
 * Locked principle 3: AI inference never satisfies a required gate. "The model
 * may suggest, identify patterns, recommend, question, compare and explain. It
 * may not silently certify."
 *
 * This is the doorway that rule has to hold at — everything a model produces
 * about a part enters the system here. So the central test is not per-field:
 * it is that NOTHING arriving from an extraction is engineering-grade, and
 * that no dimension gets invented on the way in.
 */

const ex = (o: Partial<PartIntentExtraction> = {}): PartIntentExtraction =>
  partIntentExtractionSchema.parse({ confidence: 0.9, unknowns: [], ...o });

const PROMPT = "6061 bracket, 6 x 4 x 1, ten off, 40mm bearing bore";

/** Every provenanced field on an intent, by name. */
const fieldsOf = (intent: PartIntent) =>
  (Object.entries(intent) as [string, unknown][]).filter(
    ([, v]) => v !== null && typeof v === "object" && v !== undefined && "source" in (v as object),
  ) as [string, { source: string; confirmedByUser: boolean; value: unknown }][];

/* ---------------- Nothing the model produced is engineering grade ---------------- */

test("no field the model extracted arrives engineering grade", () => {
  // Units were tagged userValue — source USER, confidence VERIFIED,
  // confirmedByUser true — so isEngineeringGrade() passed on them the instant
  // the model returned, with no human having seen the value. Every other
  // extracted field was correctly AI_INFERENCE. Units decide whether every
  // dimension on the part is inches or millimetres.
  const extraction = ex({
    partName: "Bracket", units: "MM", material: "6061-T6", materialCondition: "T6",
    stock: { form: "RECTANGULAR", x: 6, y: 4, z: 1 },
    finishedEnvelope: { x: 5.8, y: 3.8, z: 0.9 },
    quantity: 10, generalTolerance: 0.005, surfaceFinish: "125 Ra",
    features: ["40mm bore"], notes: "bearing fit",
  });
  const { intent } = buildIntakeIntent(PROMPT, extraction);

  const extractedFields = ["units", "material", "materialCondition", "stock", "finishedEnvelope", "quantity", "generalTolerance", "surfaceFinish", "features", "notes"];
  for (const name of extractedFields) {
    const f = (intent as unknown as Record<string, { source: string; confirmedByUser: boolean }>)[name];
    assert.equal(f.source, "AI_INFERENCE", `${name} is tagged ${f.source}, not as an inference`);
    assert.equal(f.confirmedByUser, false, `${name} arrives pre-confirmed`);
    assert.equal(isEngineeringGrade(f as never), false, `${name} is engineering grade before anyone has seen it`);
  }
});

test("units specifically are an inference, whatever the model said", () => {
  for (const units of ["IN", "MM"] as const) {
    const { intent } = buildIntakeIntent(PROMPT, ex({ units }));
    assert.equal(intent.units.value, units);
    assert.equal(intent.units.source, "AI_INFERENCE");
    assert.equal(isEngineeringGrade(intent.units), false);
  }
});

test("the operator's own sentence is a user value, not an inference", () => {
  // The description was tagged AI_INFERENCE with a confidence of 1, which
  // asked someone to confirm the words they had just typed. Over-marking is
  // the safe direction to be wrong in, but a wrong source is a wrong answer
  // whichever way it leans.
  const { intent } = buildIntakeIntent(PROMPT, ex());
  assert.equal(intent.description.value, PROMPT);
  assert.equal(intent.description.source, "USER");
});

test("responsibility is never inferred — it is asked", () => {
  // A model cannot know whether a part carries load. Even if the description
  // says so, that is an interview question with a human on the other end.
  const { intent } = buildIntakeIntent("safety critical load bearing bracket, structural", ex({ notes: "load bearing" }));
  for (const field of ["loadBearing", "safetyCritical", "failureConsequence"] as const) {
    assert.equal(intent[field].value, null, `${field} was answered by the intake`);
    assert.match(intent[field].note ?? "", /responsibility interview/i);
  }
});

test("every provenanced field on a fresh intent is either unknown or explicitly sourced", () => {
  const { intent } = buildIntakeIntent(PROMPT, ex({ material: "6061", quantity: 10 }));
  for (const [name, f] of fieldsOf(intent)) {
    assert.ok(typeof f.source === "string" && f.source.length > 0, `${name} has no source`);
    if (f.source === "AI_INFERENCE") {
      assert.equal(f.confirmedByUser, false, `${name} is an inference marked confirmed`);
    }
  }
});

test("a low-confidence extraction does not become high-confidence provenance", () => {
  const { intent } = buildIntakeIntent(PROMPT, ex({ material: "6061", confidence: 0.2 }));
  assert.equal(intent.material.confidence, "LOW");
  assert.equal(isEngineeringGrade(intent.material), false);
});

test("the extraction's own unknowns are carried through, not discarded", () => {
  const { intent } = buildIntakeIntent(PROMPT, ex({ unknowns: ["Bore tolerance not stated", "No quantity given"] }));
  assert.deepEqual(intent.unknowns, ["Bore tolerance not stated", "No quantity given"]);
});

/* ---------------- No dimension is invented ---------------- */

test("a form with no dimensions produces no stock at all", () => {
  // The route wrote `x: extraction.stock.x ?? 0` per axis, so a model naming a
  // form and no sizes produced a 0 x 0 x 0 block. A zero-sized stock is not a
  // missing stock downstream: it satisfies "thin" in the flatness test, fits
  // inside every machine envelope, and weighs nothing in the cost model.
  assert.equal(stockFromExtraction(ex({ stock: { form: "RECTANGULAR" } })), null);
  assert.equal(stockFromExtraction(ex({ stock: { form: "RECTANGULAR", x: 6, y: 4 } })), null, "two of three is not a block");
  assert.equal(stockFromExtraction(ex({})), null, "no stock at all is no stock");
});

test("a round bar keeps its diameter instead of being written as a zero block", () => {
  // ROUND carries diameter and length rather than x/y/z, and the write only
  // ever looked at x/y/z — so a round extraction became a rectangular record
  // of zeros with the diameter discarded entirely.
  const s = stockFromExtraction(ex({ stock: { form: "ROUND", diameter: 2.5, length: 8 }, material: "1018" }));
  assert.ok(s, "a fully described round bar is a stock");
  assert.equal(s.form, "ROUND");
  assert.equal(s.diameter, 2.5);
  assert.ok(s.x > 0 && s.y > 0 && s.z > 0, "its bounding box is real");
  assert.equal(s.z, 8, "length runs along Z");
});

test("a round bar missing its diameter or length is not a stock either", () => {
  assert.equal(stockFromExtraction(ex({ stock: { form: "ROUND", length: 8 } })), null);
  assert.equal(stockFromExtraction(ex({ stock: { form: "ROUND", diameter: 2.5 } })), null);
});

test("no stock this function returns has a zero dimension", () => {
  const cases: PartIntentExtraction[] = [
    ex({ stock: { form: "RECTANGULAR", x: 6, y: 4, z: 1 } }),
    ex({ stock: { form: "ROUND", diameter: 2.5, length: 8 } }),
    ex({ stock: { form: "TUBE", diameter: 3, length: 12 } }),
    ex({ stock: { form: "RECTANGULAR" } }),
    ex({ stock: { form: "NEAR_NET", x: 3 } }),
    ex({}),
  ];
  for (const c of cases) {
    const s = stockFromExtraction(c);
    if (!s) continue;
    for (const axis of ["x", "y", "z"] as const) {
      assert.ok(s[axis] > 0, `${c.stock?.form} produced ${axis} = ${s[axis]}`);
    }
  }
});

test("the stock carries the extracted material rather than being left blank", () => {
  const s = stockFromExtraction(ex({ stock: { form: "RECTANGULAR", x: 6, y: 4, z: 1 }, material: "Aluminum 6061" }))!;
  assert.equal(s.material, "Aluminum 6061");
  const none = stockFromExtraction(ex({ stock: { form: "RECTANGULAR", x: 6, y: 4, z: 1 } }))!;
  assert.equal(none.material, "Unspecified", "and says so plainly when there is none");
});

/* ---------------- Shape ---------------- */

test("an empty extraction still produces a usable, honest intent", () => {
  const { intent, stock } = buildIntakeIntent("make me something", ex());
  assert.equal(stock, null);
  assert.equal(intent.material.value, null);
  assert.equal(intent.quantity.value, null);
  assert.ok(intent.partName.value, "it is still named");
});

test("the part name falls back rather than being empty", () => {
  const { intent } = buildIntakeIntent(PROMPT, ex());
  assert.ok((intent.partName.value ?? "").length > 0);
});

test("building an intent is deterministic and does not mutate the extraction", () => {
  const e = ex({ material: "6061", quantity: 10, stock: { form: "RECTANGULAR", x: 6, y: 4, z: 1 } });
  const before = JSON.stringify(e);
  const a = buildIntakeIntent(PROMPT, e);
  const b = buildIntakeIntent(PROMPT, e);
  assert.deepEqual(a, b);
  assert.equal(JSON.stringify(e), before, "the extraction is read, not edited");
});
