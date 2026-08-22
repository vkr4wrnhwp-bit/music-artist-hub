import { test } from "node:test";
import assert from "node:assert/strict";
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
const sum = (ns: number[]) => ns.reduce((a, b) => a + b, 0);

/* ---------------- The arithmetic hangs together ---------------- */

test("the breakdown lines sum to the unit cost", () => {
  // If the lines a customer is shown do not add up to the number at the top,
  // the meeting is over.
  for (const qty of [1, 10, 250]) {
    const c = computeCost(qty, A());
    assert.ok(
      Math.abs(sum(c.lines.map((l) => l.perPart)) - c.unitCost) < 1e-9,
      `quantity ${qty}: lines total ${sum(c.lines.map((l) => l.perPart))} against unit cost ${c.unitCost}`,
    );
  }
});

test("price is above cost, and the margin is the difference", () => {
  const c = computeCost(10, A({ marginRate: 0.32 }));
  assert.ok(c.unitPrice > c.unitCost);
  assert.ok(Math.abs(c.marginDollars - (c.unitPrice - c.unitCost) * c.quantity) < 1e-9);
  assert.ok(Math.abs(c.lotPrice - c.unitPrice * c.quantity) < 1e-9);
});

test("margin is a fraction of price, not a markup on cost", () => {
  // 32% margin on a $68 cost is a $100 price, not $89.76. Getting this
  // backwards is the single most common quoting error there is.
  const c = computeCost(1, A({ marginRate: 0.5 }));
  assert.ok(Math.abs(c.unitPrice - c.unitCost * 2) < 1e-9, "a 50% margin doubles the cost");
  const realised = (c.unitPrice - c.unitCost) / c.unitPrice;
  assert.ok(Math.abs(realised - 0.5) < 1e-9, `realised margin ${realised} is not the target`);
});

test("setup amortises across the lot and never changes the lot total", () => {
  const one = computeCost(1, A());
  const hundred = computeCost(100, A());
  assert.ok(hundred.setupCostPerPart < one.setupCostPerPart, "that is what amortisation means");
  const setupLine = (c: ReturnType<typeof computeCost>) => c.lines.find((l) => /setup/i.test(l.label))!;
  assert.ok(
    Math.abs(setupLine(one).perLot - setupLine(hundred).perLot) < 1e-9,
    "the setup is done once whatever the quantity",
  );
});

test("the unit cost falls as the quantity rises, and never rises", () => {
  const breaks = quantityBreaks(A());
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
    const c = computeCost(q, A());
    assert.equal(c.quantity, 1);
    assert.ok(Number.isFinite(c.unitCost) && c.unitCost > 0, `quantity ${q}`);
  }
});

test("scrap is charged on the whole cost, not just on material", () => {
  // A scrapped part consumed machine time and an operator too.
  const none = computeCost(10, A({ scrapRate: 0 }));
  const some = computeCost(10, A({ scrapRate: 0.05 }));
  assert.equal(none.scrapAdder, 0);
  assert.ok(some.scrapAdder > some.materialCost * 0.05, "scrap on material alone would be smaller than this");
});

test("every line states where its number came from", () => {
  const c = computeCost(25, A());
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
  const c = computeCost(10, A({ marginRate: 1 }));
  assert.equal(c.unitPrice, c.unitCost, "precondition: it still quotes at cost");
  assert.ok(c.warnings.some((w) => /margin/i.test(w)), `got [${c.warnings.join(" | ")}]`);
  assert.ok(c.warnings.some((w) => /50%/.test(w)), "it says what they probably meant");
});

test("a margin above 100% is caught too", () => {
  const c = computeCost(10, A({ marginRate: 32 }));
  assert.ok(c.warnings.some((w) => /margin/i.test(w)));
});

test("an ordinary margin produces no warning", () => {
  for (const m of [0, 0.1, 0.32, 0.6, 0.95]) {
    assert.deepEqual(computeCost(10, A({ marginRate: m })).warnings, [], `margin ${m}`);
  }
});

test("utilisation entered as a percentage rather than a fraction is caught", () => {
  // 85 instead of 0.85 divides material cost by 85 and makes the metal
  // almost free — a quote that loses money on every part.
  const c = computeCost(10, A({ materialUtilization: 85 }));
  assert.ok(c.warnings.some((w) => /utilisation/i.test(w)), `got [${c.warnings.join(" | ")}]`);
});

test("a scrap rate of 100% is caught rather than multiplying the cost by a hundred", () => {
  const c = computeCost(10, A({ scrapRate: 1 }));
  assert.ok(c.warnings.some((w) => /scrap/i.test(w)));
});

test("an assumption that is not a number is named by name", () => {
  const c = computeCost(10, A({ materialDensity: Number.NaN }));
  assert.ok(c.warnings.some((w) => /materialDensity/.test(w)), `got [${c.warnings.join(" | ")}]`);
});

test("a complete, sane assumption set warns about nothing", () => {
  assert.deepEqual(computeCost(10, A()).warnings, []);
  assert.deepEqual(computeCost(1, DEFAULT_ASSUMPTIONS).warnings, [], "the shipped defaults must be clean");
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
  const cost = computeCost(100, A({ cycleMinutes: 12, setupHours: 1.5 }));
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
  const cost = computeCost(100, A({ cycleMinutes: 12, setupHours: 1.5 }));
  const c = compareMakeVsBuy(100, cost, [], 10);
  const caveat = c.caveats.find((x) => /displaces other work/i.test(x))!;
  assert.match(caveat, /21\.5 spindle hours/, `got: ${caveat}`);
  assert.ok(!/NaN/.test(caveat));
});

test("unrecorded capacity is stated as unrecorded, not assumed infinite", () => {
  const c = compareMakeVsBuy(10, computeCost(10, A()), [], null);
  assert.ok(c.caveats.some((x) => /capacity is not recorded/i.test(x)));
});

/* ---------------- Make vs buy ---------------- */

test("with no external quote there is no recommendation to make", () => {
  // CANVAS will not estimate a supplier price it has no basis for.
  const c = compareMakeVsBuy(10, computeCost(10, A()), [], null);
  assert.equal(c.recommendation, null);
  assert.ok(c.caveats.some((x) => /no external quotes/i.test(x)));
  assert.equal(c.options.length, 1, "only the in-house route exists");
});

test("a cheaper external quote wins and is named", () => {
  const make = computeCost(10, A());
  const c = compareMakeVsBuy(10, make, [{ label: "Supplier A", unitCost: 5, leadTimeDays: 14, source: "email 2026-03-02" }], null);
  assert.ok(c.recommendation);
  assert.match(c.recommendation, /Supplier A/);
  assert.match(c.recommendation, /\$5\.00/);
});

test("a dearer external quote does not displace making it in-house", () => {
  const make = computeCost(1000, A());
  const c = compareMakeVsBuy(1000, make, [{ label: "Supplier A", unitCost: 9999, leadTimeDays: 14, source: "email" }], null);
  assert.match(c.recommendation!, /Make in-house/);
});

test("every option records what it assumed", () => {
  const c = compareMakeVsBuy(10, computeCost(10, A()), [{ label: "Supplier A", unitCost: 5, leadTimeDays: 14, source: "email" }], null);
  for (const o of c.options) {
    assert.ok(o.assumptions.length > 0, `${o.label} records no assumptions`);
    assert.equal(typeof o.grounded, "boolean");
  }
  assert.equal(c.options.find((o) => o.route === "MAKE")!.leadTimeDays, null, "lead time is not modelled and says so");
});

test("the comparison is deterministic", () => {
  const make = computeCost(10, A());
  const quotes = [{ label: "Supplier A", unitCost: 5, leadTimeDays: 14, source: "email" }];
  assert.deepEqual(compareMakeVsBuy(10, make, quotes, 40), compareMakeVsBuy(10, make, quotes, 40));
});

test("computing a cost is deterministic", () => {
  assert.deepEqual(computeCost(25, A()), computeCost(25, A()));
});
