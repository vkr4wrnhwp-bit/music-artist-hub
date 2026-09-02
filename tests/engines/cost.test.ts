import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  computeCost,
  quantityBreaks,
  compareMakeVsBuy,
  money,
  DEFAULT_ASSUMPTIONS,
  STANDARD_QUANTITY_BREAKS,
  type CostAssumptions,
} from "@/lib/engines/cost";

/**
 * "A quote you cannot defend in a customer meeting is worthless." That is the
 * file's own opening claim, and it sets what these tests are for.
 *
 * The rates themselves are not pinned — a shop's machine rate is a shop's
 * business. What is pinned is that the arithmetic is internally consistent
 * (the lines sum to the cost, the cost is under the price), that an
 * assumption the model cannot work with is named rather than absorbed, and
 * that no figure reaches a quoting page as "$NaN".
 */

const A = (over: Partial<CostAssumptions> = {}): CostAssumptions => ({ ...DEFAULT_ASSUMPTIONS, ...over });
const sum = (ns: (number | null)[]) => ns.reduce((a: number, b) => a + (b ?? 0), 0);

/**
 * Every figure a costed result carries, narrowed.
 *
 * A result can legitimately have null totals now — that is the point of the
 * change — so the tests that are ABOUT the arithmetic assert first that this
 * one costed, and fail loudly rather than passing vacuously if it did not.
 */
const costed = (c: ReturnType<typeof computeCost>) => {
  assert.equal(c.missingInputs.length, 0, `fixture did not cost: ${c.missingInputs.join(" ")}`);
  assert.ok(c.unitCost != null && c.unitPrice != null && c.lotPrice != null && c.marginDollars != null);
  return c as Omit<typeof c, "setupHours" | "cycleHoursPerPart" | "unitCost" | "unitPrice" | "lotPrice" | "marginDollars" | "setupCostPerPart" | "machineCost" | "labourCost" | "toolingCost" | "scrapAdder" | "overhead" | "lines"> & {
    unitCost: number;
    unitPrice: number;
    lotPrice: number;
    marginDollars: number;
    setupHours: number;
    cycleHoursPerPart: number;
    setupCostPerPart: number;
    machineCost: number;
    labourCost: number;
    toolingCost: number;
    scrapAdder: number;
    overhead: number;
    lines: (Omit<(typeof c)["lines"][number], "perPart" | "perLot"> & { perPart: number; perLot: number })[];
  };
};

/* ---------------- The arithmetic hangs together ---------------- */

test("the breakdown lines sum to the unit cost", () => {
  // If the lines a customer is shown do not add up to the number at the top,
  // the meeting is over.
  for (const qty of [1, 10, 250]) {
    const c = costed(computeCost(qty, A()));
    assert.ok(
      Math.abs(sum(c.lines.map((l) => l.perPart)) - c.unitCost) < 1e-9,
      `quantity ${qty}: lines total ${sum(c.lines.map((l) => l.perPart))} against unit cost ${c.unitCost}`,
    );
  }
});

test("price is above cost, and the margin is the difference", () => {
  const c = costed(computeCost(10, A({ marginRate: 0.32 })));
  assert.ok(c.unitPrice > c.unitCost);
  assert.ok(Math.abs(c.marginDollars - (c.unitPrice - c.unitCost) * c.quantity) < 1e-9);
  assert.ok(Math.abs(c.lotPrice - c.unitPrice * c.quantity) < 1e-9);
});

test("margin is a fraction of price, not a markup on cost", () => {
  // 32% margin on a $68 cost is a $100 price, not $89.76. Getting this
  // backwards is the single most common quoting error there is.
  const c = costed(computeCost(1, A({ marginRate: 0.5 })));
  assert.ok(Math.abs(c.unitPrice - c.unitCost * 2) < 1e-9, "a 50% margin doubles the cost");
  const realised = (c.unitPrice - c.unitCost) / c.unitPrice;
  assert.ok(Math.abs(realised - 0.5) < 1e-9, `realised margin ${realised} is not the target`);
});

test("setup amortises across the lot and never changes the lot total", () => {
  const one = costed(computeCost(1, A()));
  const hundred = costed(computeCost(100, A()));
  assert.ok(hundred.setupCostPerPart < one.setupCostPerPart, "that is what amortisation means");
  const setupLine = (c: ReturnType<typeof costed>) => c.lines.find((l) => /setup/i.test(l.label))!;
  assert.ok(
    Math.abs(setupLine(one).perLot - setupLine(hundred).perLot) < 1e-9,
    "the setup is done once whatever the quantity",
  );
});

test("the unit cost falls as the quantity rises, and never rises", () => {
  const breaks = quantityBreaks(A()).map(costed);
  assert.equal(breaks.length, STANDARD_QUANTITY_BREAKS.length);
  for (let i = 1; i < breaks.length; i++) {
    assert.ok(
      breaks[i].unitCost <= breaks[i - 1].unitCost + 1e-9,
      `cost went up from qty ${breaks[i - 1].quantity} to ${breaks[i].quantity}`,
    );
  }
});

test("a quantity below one is treated as one rather than dividing by zero", () => {
  for (const q of [0, -5, 0.4]) {
    const c = costed(computeCost(q, A()));
    assert.equal(c.quantity, 1);
    assert.ok(Number.isFinite(c.unitCost) && c.unitCost > 0, `quantity ${q}`);
  }
});

test("scrap is charged on the whole cost, not just on material", () => {
  // A scrapped part consumed machine time and an operator too.
  const none = costed(computeCost(10, A({ scrapRate: 0 })));
  const some = costed(computeCost(10, A({ scrapRate: 0.05 })));
  assert.equal(none.scrapAdder, 0);
  assert.ok(some.scrapAdder > some.materialCost * 0.05, "scrap on material alone would be smaller than this");
});

test("every line states where its number came from", () => {
  const c = costed(computeCost(25, A()));
  for (const l of c.lines) {
    assert.ok(l.basis.length > 5, `${l.label} has no basis`);
    assert.ok(!/NaN|undefined/.test(l.basis), `${l.label} basis: ${l.basis}`);
  }
});

/* ---------------- Assumptions the model cannot work with ---------------- */

test("a margin of 100% is named rather than quietly quoted at cost", () => {
  // The settings form divides a typed percentage by 100, so a shop owner
  // entering 100 meaning "100% markup" lands here. The quote came back at
  // cost with zero margin and said nothing at all.
  const c = costed(computeCost(10, A({ marginRate: 1 })));
  assert.equal(c.unitPrice, c.unitCost, "precondition: it still quotes at cost");
  assert.ok(c.warnings.some((w) => /margin/i.test(w)), `got [${c.warnings.join(" | ")}]`);
  assert.ok(c.warnings.some((w) => /50%/.test(w)), "it says what they probably meant");
});

test("a margin above 100% is caught too", () => {
  const c = costed(computeCost(10, A({ marginRate: 32 })));
  assert.ok(c.warnings.some((w) => /margin/i.test(w)));
});

test("an ordinary margin produces no warning", () => {
  for (const m of [0, 0.1, 0.32, 0.6, 0.95]) {
    assert.deepEqual(costed(computeCost(10, A({ marginRate: m }))).warnings, [], `margin ${m}`);
  }
});

test("utilisation entered as a percentage rather than a fraction is caught", () => {
  // 85 instead of 0.85 divides material cost by 85 and makes the metal
  // almost free — a quote that loses money on every part.
  const c = costed(computeCost(10, A({ materialUtilization: 85 })));
  assert.ok(c.warnings.some((w) => /utilisation/i.test(w)), `got [${c.warnings.join(" | ")}]`);
});

test("a scrap rate of 100% is caught rather than multiplying the cost by a hundred", () => {
  const c = costed(computeCost(10, A({ scrapRate: 1 })));
  assert.ok(c.warnings.some((w) => /scrap/i.test(w)));
});

test("an assumption that is not a number is named by name", () => {
  const c = costed(computeCost(10, A({ materialDensity: Number.NaN })));
  assert.ok(c.warnings.some((w) => /materialDensity/.test(w)), `got [${c.warnings.join(" | ")}]`);
});

test("a complete, sane assumption set warns about nothing", () => {
  assert.deepEqual(costed(computeCost(10, A())).warnings, []);
  assert.deepEqual(costed(computeCost(1, DEFAULT_ASSUMPTIONS)).warnings, [], "the shipped defaults must be clean");
});

/* ---------------- Nothing reaches a quoting page as $NaN ---------------- */

test("money never renders NaN or Infinity as a price", () => {
  // money() is the last thing between the cost model and five pages a shop
  // owner quotes from. "$NaN" is worse than a blank because it looks like a
  // number until you read it.
  for (const bad of [Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY]) {
    assert.equal(money(bad), "—", `money(${bad})`);
  }
});

test("money puts the sign in front of the dollar, not after it", () => {
  assert.equal(money(-3), "-$3.00");
  assert.equal(money(-250), "-$250");
});

test("money shows cents on small figures and drops them on large ones", () => {
  assert.equal(money(5), "$5.00");
  assert.equal(money(12.5), "$12.50");
  assert.equal(money(99.994), "$99.99");
  assert.equal(money(100), "$100");
  assert.equal(money(1234.5), "$1235");
});

/* ---------------- Capacity ---------------- */

test("the lot's spindle demand is hours, not the part count", () => {
  // This read
  //   quantity * (machineCost / Math.max(machineCost, 1))
  // which collapses to the quantity for any machine cost at or above $1. A
  // lot of 100 parts at 12 minutes each is 20 spindle hours plus setup, and
  // it reported 100 — so a shop with 50 hours free was told the lot displaced
  // other work.
  const cost = costed(computeCost(100, A({ cycleMinutes: 12, setupHours: 1.5 })));
  const expected = 1.5 + (12 / 60) * 100; // 21.5 hours
  assert.ok(Math.abs(cost.setupHours + cost.cycleHoursPerPart * cost.quantity - expected) < 1e-9);

  const fits = compareMakeVsBuy(100, cost, [], 50);
  assert.ok(
    !fits.caveats.some((c) => /displaces other work/i.test(c)),
    `21.5 hours fits in 50: [${fits.caveats.join(" | ")}]`,
  );

  const doesNot = compareMakeVsBuy(100, cost, [], 10);
  assert.ok(doesNot.caveats.some((c) => /displaces other work/i.test(c)), "21.5 hours does not fit in 10");
});

test("the capacity caveat quotes the hours it is talking about", () => {
  const cost = costed(computeCost(100, A({ cycleMinutes: 12, setupHours: 1.5 })));
  const c = compareMakeVsBuy(100, cost, [], 10);
  const caveat = c.caveats.find((x) => /displaces other work/i.test(x))!;
  assert.match(caveat, /21\.5 spindle hours/, `got: ${caveat}`);
  assert.ok(!/NaN/.test(caveat));
});

test("unrecorded capacity is stated as unrecorded, not assumed infinite", () => {
  const c = compareMakeVsBuy(10, costed(computeCost(10, A())), [], null);
  assert.ok(c.caveats.some((x) => /capacity is not recorded/i.test(x)));
});

/* ---------------- Make vs buy ---------------- */

test("with no external quote there is no recommendation to make", () => {
  // CANVAS will not estimate a supplier price it has no basis for.
  const c = compareMakeVsBuy(10, costed(computeCost(10, A())), [], null);
  assert.equal(c.recommendation, null);
  assert.ok(c.caveats.some((x) => /no external quotes/i.test(x)));
  assert.equal(c.options.length, 1, "only the in-house route exists");
});

test("a cheaper external quote wins and is named", () => {
  const make = costed(computeCost(10, A()));
  const c = compareMakeVsBuy(10, make, [{ label: "Supplier A", unitCost: 5, leadTimeDays: 14, source: "email 2026-03-02" }], null);
  assert.ok(c.recommendation);
  assert.match(c.recommendation, /Supplier A/);
  assert.match(c.recommendation, /\$5\.00/);
});

test("a dearer external quote does not displace making it in-house", () => {
  const make = costed(computeCost(1000, A()));
  const c = compareMakeVsBuy(1000, make, [{ label: "Supplier A", unitCost: 9999, leadTimeDays: 14, source: "email" }], null);
  assert.match(c.recommendation!, /Make in-house/);
});

test("every option records what it assumed", () => {
  const c = compareMakeVsBuy(10, costed(computeCost(10, A())), [{ label: "Supplier A", unitCost: 5, leadTimeDays: 14, source: "email" }], null);
  for (const o of c.options) {
    assert.ok(o.assumptions.length > 0, `${o.label} records no assumptions`);
    assert.equal(typeof o.grounded, "boolean");
  }
  assert.equal(c.options.find((o) => o.route === "MAKE")!.leadTimeDays, null, "lead time is not modelled and says so");
});

test("the comparison is deterministic", () => {
  const make = costed(computeCost(10, A()));
  const quotes = [{ label: "Supplier A", unitCost: 5, leadTimeDays: 14, source: "email" }];
  assert.deepEqual(compareMakeVsBuy(10, make, quotes, 40), compareMakeVsBuy(10, make, quotes, 40));
});

test("computing a cost is deterministic", () => {
  assert.deepEqual(costed(computeCost(25, A())), costed(computeCost(25, A())));
});

/* ---------------- Nothing is substituted for a missing input ---------------- */

/**
 * `package.ts` read `cycleMinutes || DEFAULT_ASSUMPTIONS.cycleMinutes`.
 * JavaScript's `||` treats 0 as absent, and the derived figure is exactly 0
 * when nothing could produce it — so a part whose operations the toolpath
 * engine refused was priced at a 12-minute cycle nobody calculated. The cost
 * page printed "12.00 min × $75.00/hr" as the basis beneath a tile reading
 * "CYCLE TIME 0.00 min FROM GENERATED TOOLPATHS", and storing the estimate
 * froze that number into a customer price.
 */

test("a missing cycle time produces no unit cost and no price", () => {
  const c = computeCost(10, A({ cycleMinutes: null }));
  assert.equal(c.unitCost, null);
  assert.equal(c.unitPrice, null);
  assert.equal(c.lotPrice, null);
  assert.equal(c.marginDollars, null);
});

test("it says what is missing, in terms a machinist can act on", () => {
  const c = computeCost(10, A({ cycleMinutes: null }));
  assert.equal(c.missingInputs.length, 1);
  assert.match(c.missingInputs[0], /cycle time/i);
  assert.match(c.missingInputs[0], /toolpath/i);
});

test("each missing input is named separately, not collapsed into one", () => {
  const c = computeCost(10, A({ cycleMinutes: null, setupHours: null, toolCostPerPart: null }));
  assert.equal(c.missingInputs.length, 3);
  assert.ok(c.missingInputs.some((m) => /cycle time/i.test(m)));
  assert.ok(c.missingInputs.some((m) => /setup/i.test(m)));
  assert.ok(c.missingInputs.some((m) => /tooling/i.test(m)));
});

test("the affected lines are null, and their basis says why rather than quoting a rate", () => {
  // THE SPECIFIC LIE. This line read "12.00 min × $75.00/hr".
  const c = computeCost(10, A({ cycleMinutes: null }));
  const machine = c.lines.find((l) => l.label === "Machine time")!;
  assert.equal(machine.perPart, null);
  assert.equal(machine.perLot, null);
  assert.ok(!/min ×/.test(machine.basis), `the basis still quotes a cycle: "${machine.basis}"`);
  assert.match(machine.basis, /no cycle time/i);
});

test("a line that does not depend on the missing input still computes", () => {
  // Material does not need a cycle time, and blanking it would hide a figure
  // the shop legitimately has.
  const c = computeCost(10, A({ cycleMinutes: null }));
  const material = c.lines.find((l) => l.label === "Material")!;
  assert.ok(material.perPart != null && material.perPart > 0);
});

test("zero is never used as the stand-in, because zero is a claim", () => {
  // $0.00 machine time says this part costs nothing to cut. That is a
  // different lie from a 12-minute default, and an easier one to miss.
  const c = computeCost(10, A({ cycleMinutes: null }));
  assert.notEqual(c.machineCost, 0);
  assert.equal(c.machineCost, null);
  assert.equal(money(c.machineCost), "—");
  assert.equal(money(c.unitCost), "—");
});

test("a costed part still reports nothing missing", () => {
  // The mechanism has to be quiet when everything is known, or it becomes
  // noise that gets ignored on the part where it matters.
  const c = computeCost(10, A());
  assert.deepEqual(c.missingInputs, []);
  assert.ok(c.unitCost != null);
});

test("quantity breaks are all uncosted when the cycle time is", () => {
  // Not some of them: a break table with prices on half the rows would read
  // as though the larger quantities were better understood.
  for (const b of quantityBreaks(A({ cycleMinutes: null }))) {
    assert.equal(b.unitPrice, null, `quantity ${b.quantity} produced a price`);
  }
});

test("make-vs-buy declines to compare capacity rather than inventing spindle hours", () => {
  const c = computeCost(100, A({ cycleMinutes: null }));
  const r = compareMakeVsBuy(100, c, [], 50);
  assert.ok(
    r.caveats.some((x) => /Spindle hours for this lot cannot be worked out/i.test(x)),
    "capacity was compared against a cycle time nobody derived",
  );
  assert.ok(!r.caveats.some((x) => /displaces other work/i.test(x)));
});

/* ---------------- The substitution cannot come back ---------------- */

/**
 * The engine tests above prove that a null input produces a null total. They
 * cannot prove that the CALLER passes null, and the caller is where the bug
 * was: `package.ts` turned a derived 0 into a 12-minute default before the
 * engine ever saw it. Nothing in the suite exercises buildPackage, so this
 * reads the source.
 *
 * Comments are stripped first. The comment at that call site quotes the very
 * pattern being banned, and asserting against the raw text fails on the
 * explanation of the fix rather than on the fix.
 */

const stripComments = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");

test("the package builder never substitutes a default for a derived quantity", () => {
  const src = stripComments(readFileSync("src/lib/package.ts", "utf8"));
  // Scoped to the object literal that is actually handed to the cost engine.
  // Searching the whole file matched a type declaration — `cycleMinutes:
  // number;` — and failed on a line that assigns nothing.
  const block = /const costAssumptions: CostAssumptions = \{([\s\S]*?)\n  \};/.exec(src);
  assert.ok(block, "the costAssumptions literal has moved — this guard has gone stale");
  for (const field of ["cycleMinutes", "setupHours", "toolCostPerPart"]) {
    const line = block![1].split("\n").find((l) => l.trim().startsWith(`${field}:`));
    assert.ok(line, `${field} is no longer assigned in package.ts — this guard has gone stale`);
    assert.ok(
      !/\|\|\s*DEFAULT_ASSUMPTIONS/.test(line!),
      `${field} falls back to a default: ${line!.trim()}`,
    );
    assert.ok(
      /null/.test(line!),
      `${field} does not pass null when nothing derived it: ${line!.trim()}`,
    );
  }
});

test("the plan reviewer never substitutes one either", () => {
  // machinist-review.ts carried the same `|| default`, so an approach whose
  // operations could not be toolpathed was ranked against the others at a
  // cycle time nobody derived.
  const src = stripComments(readFileSync("src/lib/machinist-review.ts", "utf8"));
  // Scoped for the same reason as the guard above: the ScoredPlan interface
  // declares `cycleMinutes: number;` earlier in the file, so an unscoped
  // search inspected a type and passed whatever the assignment did.
  const block = /const assumptions: CostAssumptions = \{([\s\S]*?)\n  \};/.exec(src);
  assert.ok(block, "the assumptions literal has moved — this guard has gone stale");
  const line = block![1].split("\n").find((l) => l.trim().startsWith("cycleMinutes:"));
  assert.ok(line, "cycleMinutes is no longer assigned in machinist-review.ts");
  assert.ok(!/costAssumptions\.cycleMinutes/.test(line!), `it falls back: ${line!.trim()}`);
});
