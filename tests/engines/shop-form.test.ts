import { test } from "node:test";
import assert from "node:assert/strict";
import { FormReader, FormRejected, rejectionQuery } from "@/lib/shop-form";

/**
 * "The field was left blank" and "the field was filled in with something that
 * is not a number" must never collapse into the same outcome. A blank
 * optional field becomes null, which every engine downstream already handles
 * by naming it as a missing input. Garbage is a rejected submission.
 *
 * The failure this guards is specific and stated in the file: if a tool's
 * stickout arrives as an empty string and 0 is stored, every reach check
 * downstream is computed against a fiction that looks like a measurement.
 */

const form = (fields: Record<string, string>) => {
  const fd = new FormData();
  for (const [k, v] of Object.entries(fields)) fd.set(k, v);
  return new FormReader(fd);
};

const problemsOf = (fn: () => void): string[] => {
  try {
    fn();
    return [];
  } catch (err) {
    assert.ok(err instanceof FormRejected, `threw something other than a rejection: ${err}`);
    return err.problems;
  }
};

/* ---------------- Blank is not zero ---------------- */

test("a blank optional number is null, never zero", () => {
  const f = form({ stickout: "" });
  assert.equal(f.optionalNumber("stickout", "Stickout"), null);
  assert.deepEqual(problemsOf(() => f.done()), [], "blank optional is not a problem");
});

test("an absent optional number is null", () => {
  const f = form({});
  assert.equal(f.optionalNumber("stickout", "Stickout"), null);
  assert.deepEqual(problemsOf(() => f.done()), []);
});

test("a blank required number is rejected, not defaulted", () => {
  const f = form({ diameter: "" });
  f.number("diameter", "Diameter");
  assert.deepEqual(problemsOf(() => f.done()), ["Diameter is required"]);
});

test("garbage in a numeric field is rejected rather than becoming null", () => {
  // This is the distinction the whole file exists for: "not recorded" and
  // "recorded as nonsense" are different answers.
  for (const bad of ["abc", "1.2.3", "--5", "NaN", "Infinity", "1,5"]) {
    const f = form({ stickout: bad });
    f.optionalNumber("stickout", "Stickout");
    assert.deepEqual(problemsOf(() => f.done()), ["Stickout is not a number"], `"${bad}"`);
  }
});

test("whitespace around a number is trimmed, not rejected", () => {
  assert.equal(form({ d: "  1.5  " }).optionalNumber("d", "D"), 1.5);
});

test("a field of only whitespace is blank, not garbage", () => {
  const f = form({ d: "   " });
  assert.equal(f.optionalNumber("d", "D"), null);
  assert.deepEqual(problemsOf(() => f.done()), []);
});

/* ---------------- Bounds ---------------- */

test("a value below the minimum is rejected and says so", () => {
  const f = form({ d: "-5" });
  f.number("d", "Diameter", { min: 0 });
  assert.deepEqual(problemsOf(() => f.done()), ["Diameter must be at least 0"]);
});

test("a value above the maximum is rejected and says so", () => {
  const f = form({ rpm: "99000" });
  f.number("rpm", "Spindle speed", { max: 30000 });
  assert.deepEqual(problemsOf(() => f.done()), ["Spindle speed must be at most 30000"]);
});

test("a bounds violation is one problem, not two", () => {
  // optionalNumber returns null on a bounds failure and number() then has to
  // decide whether the field was blank. If it got that wrong the operator
  // would be told the field is both out of range and missing.
  const f = form({ d: "-5" });
  f.number("d", "Diameter", { min: 0 });
  assert.equal(problemsOf(() => f.done()).length, 1);
});

test("the bounds are inclusive", () => {
  assert.equal(form({ d: "0" }).optionalNumber("d", "D", { min: 0 }), 0);
  assert.equal(form({ d: "100" }).optionalNumber("d", "D", { max: 100 }), 100);
});

test("zero entered deliberately is kept, not treated as blank", () => {
  // A recorded zero and an unrecorded field are different facts.
  const f = form({ regrinds: "0" });
  assert.equal(f.optionalNumber("regrinds", "Regrinds"), 0);
  assert.deepEqual(problemsOf(() => f.done()), []);
});

/* ---------------- Integers ---------------- */

test("a fractional value in an integer field is rejected", () => {
  const f = form({ flutes: "3.5" });
  f.integer("flutes", "Flutes");
  assert.deepEqual(problemsOf(() => f.done()), ["Flutes must be a whole number"]);
});

test("a blank required integer reports missing, not fractional", () => {
  const f = form({ flutes: "" });
  f.integer("flutes", "Flutes");
  assert.deepEqual(problemsOf(() => f.done()), ["Flutes is required"]);
});

test("garbage in an integer field is one problem about the number", () => {
  const f = form({ flutes: "abc" });
  f.integer("flutes", "Flutes");
  assert.deepEqual(problemsOf(() => f.done()), ["Flutes is not a number"]);
});

test("a blank optional integer is null", () => {
  const f = form({ pocket: "" });
  assert.equal(f.optionalInteger("pocket", "Pocket"), null);
  assert.deepEqual(problemsOf(() => f.done()), []);
});

/* ---------------- Vocabularies ---------------- */

const FAMILIES = ["ALUMINUM", "STEEL", "STAINLESS"] as const;

test("a value outside the vocabulary is rejected, never coerced", () => {
  // Coercing to the first allowed value would silently record a shop's
  // titanium as aluminium.
  const f = form({ family: "UNOBTAINIUM" });
  f.choice("family", "Family", FAMILIES);
  assert.deepEqual(problemsOf(() => f.done()), ["Family is not one of the recognised values"]);
});

test("vocabulary matching is exact", () => {
  const f = form({ family: "aluminum" });
  f.choice("family", "Family", FAMILIES);
  assert.equal(problemsOf(() => f.done()).length, 1, "lowercase is not the same key");
});

test("a recognised value passes through unchanged", () => {
  const f = form({ family: "STEEL" });
  assert.equal(f.choice("family", "Family", FAMILIES), "STEEL");
  assert.deepEqual(problemsOf(() => f.done()), []);
});

test("a blank optional choice is null, a blank required one is rejected", () => {
  assert.equal(form({ f: "" }).optionalChoice("f", "Family", FAMILIES), null);
  const req = form({ f: "" });
  req.choice("f", "Family", FAMILIES);
  assert.deepEqual(problemsOf(() => req.done()), ["Family is required"]);
});

/* ---------------- Text, booleans, lists ---------------- */

test("a blank required text field is rejected", () => {
  const f = form({ name: "   " });
  f.text("name", "Name");
  assert.deepEqual(problemsOf(() => f.done()), ["Name is required"]);
});

test("an unchecked checkbox is false and a checked one is true", () => {
  assert.equal(form({}).boolean("weldable"), false);
  assert.equal(form({ weldable: "on" }).boolean("weldable"), true);
});

test("a comma list becomes a JSON array, and a blank one an empty array", () => {
  assert.equal(form({ m: "6061, 7075 ,  " }).jsonList("m"), JSON.stringify(["6061", "7075"]));
  assert.equal(form({ m: "" }).jsonList("m"), "[]");
  assert.equal(form({}).jsonList("m"), "[]");
});

/* ---------------- Ranges ---------------- */

test("a minimum above its maximum is rejected", () => {
  const f = form({ lo: "900", hi: "300" });
  const lo = f.number("lo", "SFM min");
  const hi = f.number("hi", "SFM max");
  f.requireOrder(lo, hi, "Surface speed");
  assert.deepEqual(problemsOf(() => f.done()), ["Surface speed: minimum is above maximum"]);
});

test("an ordering check is skipped when either end is missing", () => {
  // Reporting "minimum is above maximum" for a field that was left blank
  // would be a second, confusing problem about a field that has one already.
  const f = form({ lo: "900", hi: "" });
  const lo = f.optionalNumber("lo", "SFM min");
  const hi = f.optionalNumber("hi", "SFM max");
  f.requireOrder(lo, hi, "Surface speed");
  assert.deepEqual(problemsOf(() => f.done()), []);
});

test("equal endpoints are a valid range", () => {
  const f = form({ lo: "500", hi: "500" });
  f.requireOrder(f.number("lo", "Lo"), f.number("hi", "Hi"), "Range");
  assert.deepEqual(problemsOf(() => f.done()), []);
});

/* ---------------- Reporting ---------------- */

test("every problem in a submission is reported, not just the first", () => {
  // A form that rejects one field at a time makes somebody submit five times.
  const f = form({ name: "", diameter: "abc", flutes: "2.5", family: "NOPE" });
  f.text("name", "Name");
  f.number("diameter", "Diameter");
  f.integer("flutes", "Flutes");
  f.choice("family", "Family", FAMILIES);
  assert.equal(problemsOf(() => f.done()).length, 4);
});

test("a clean submission throws nothing", () => {
  const f = form({ name: "1/2 end mill", diameter: "0.5", flutes: "3", family: "STEEL" });
  f.text("name", "Name");
  f.number("diameter", "Diameter", { min: 0 });
  f.integer("flutes", "Flutes", { min: 1 });
  f.choice("family", "Family", FAMILIES);
  assert.deepEqual(problemsOf(() => f.done()), []);
});

test("the rejection query carries the problems and stays short", () => {
  const q = rejectionQuery(new FormRejected(["A is required", "B is not a number"]));
  assert.match(q, /^\?problem=/);
  assert.match(decodeURIComponent(q), /A is required/);
  assert.match(decodeURIComponent(q), /B is not a number/);

  const many = rejectionQuery(new FormRejected(Array.from({ length: 20 }, (_, i) => `Problem ${i}`)));
  assert.ok(!decodeURIComponent(many).includes("Problem 9"), "a wall of text is not a field message");
});

test("an unexpected error does not leak a stack trace into the URL", () => {
  const q = rejectionQuery(new TypeError("Cannot read properties of undefined (reading 'x')"));
  assert.ok(!decodeURIComponent(q).includes("Cannot read properties"));
  assert.match(decodeURIComponent(q), /could not be saved/i);
});
