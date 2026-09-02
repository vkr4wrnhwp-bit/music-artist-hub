import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  NEXT_QUOTE_STATUS,
  QUOTE_STATUSES,
  assumptionDrift,
  canSend,
  canTransitionQuote,
  compareQuoteToActual,
  type QuoteStatus,
} from "@/lib/engines/quoting";
import { computeCost, type CostAssumptions } from "@/lib/engines/cost";

/**
 * The Quoting page said quotes "carry their assumption set… so a quote can be
 * defended, re-run against changed rates, or compared against what the job
 * actually cost", and nothing in the application wrote a Quote or a
 * CostEstimate. The Cost panel computed a live figure and threw it away.
 */

const A: CostAssumptions = {
  materialCostPerPound: 3.2,
  materialDensity: 0.098,
  stockVolumePerPart: 6,
  materialUtilization: 0.45,
  machineRate: 85,
  operatorRate: 38,
  operatorAttendance: 0.5,
  setupHours: 1.5,
  cycleMinutes: 8,
  toolCostPerPart: 1.1,
  inspectionMinutes: 3,
  inspectionRate: 45,
  firstArticleHours: 1,
  scrapRate: 0.02,
  outsideProcessPerPart: 0,
  packagingPerPart: 0.4,
  overheadRate: 0.15,
  marginRate: 0.35,
};

/* ---------------- Lifecycle ---------------- */

test("a quote goes out once and is not edited back into a draft", () => {
  // The number the customer holds does not change when the shop changes its
  // mind. A revised price is a new quote.
  assert.equal(canTransitionQuote("DRAFT", "SENT"), true);
  assert.equal(canTransitionQuote("SENT", "DRAFT"), false);
  assert.equal(canTransitionQuote("WON", "DRAFT"), false);
  assert.equal(canTransitionQuote("LOST", "SENT"), false);
});

test("an outcome cannot be recorded before the quote is sent", () => {
  for (const to of ["WON", "LOST", "EXPIRED"] as const) {
    assert.equal(canTransitionQuote("DRAFT", to), false, `DRAFT → ${to} was allowed`);
    assert.equal(canTransitionQuote("SENT", to), true);
  }
});

test("won, lost and expired are terminal", () => {
  for (const from of ["WON", "LOST", "EXPIRED"] as const) {
    assert.deepEqual(NEXT_QUOTE_STATUS[from], []);
    for (const to of QUOTE_STATUSES) {
      assert.equal(canTransitionQuote(from, to), false, `${from} → ${to} was allowed`);
    }
  }
});

test("every status is declared and every target is a real status", () => {
  assert.deepEqual((Object.keys(NEXT_QUOTE_STATUS) as QuoteStatus[]).sort(), [...QUOTE_STATUSES].sort());
  for (const from of QUOTE_STATUSES) {
    for (const to of NEXT_QUOTE_STATUS[from]) {
      assert.ok((QUOTE_STATUSES as readonly string[]).includes(to), `${from} → ${to} is not a status`);
    }
  }
});

test("a quote with no estimate on it prices nothing and cannot be sent", () => {
  assert.equal(canSend(0), false);
  assert.equal(canSend(1), true);
});

/* ---------------- Drift ---------------- */

test("an unchanged assumption set reports no drift", () => {
  assert.deepEqual(assumptionDrift(A, { ...A }), []);
});

test("a moved rate is named, with both numbers", () => {
  // The point of storing the assumption set: the quote is not wrong, it is a
  // record of a promise made at $85/hr. What is useful is which input moved.
  const d = assumptionDrift(A, { ...A, machineRate: 95 });
  assert.equal(d.length, 1);
  assert.equal(d[0].key, "machineRate");
  assert.equal(d[0].quoted, 85);
  assert.equal(d[0].now, 95);
});

test("float noise is not reported as a rate change", () => {
  const d = assumptionDrift(A, { ...A, scrapRate: 0.02 + 1e-15 });
  assert.deepEqual(d, []);
});

test("every assumption the price actually moves on is watched", () => {
  // A rate that can change the number and is not watched makes a stale quote
  // look current, which is the failure this whole panel exists to prevent.
  const moved = { ...A, machineRate: 95, cycleMinutes: 12, materialCostPerPound: 4, marginRate: 0.4, setupHours: 2, scrapRate: 0.05, operatorRate: 44, materialUtilization: 0.6 };
  const keys = assumptionDrift(A, moved).map((d) => d.key).sort();
  assert.deepEqual(keys, [
    "cycleMinutes", "machineRate", "marginRate", "materialCostPerPound",
    "materialUtilization", "operatorRate", "scrapRate", "setupHours",
  ]);
  // And each of those genuinely changes the price, so none is watched for show.
  const base = computeCost(10, A).unitPrice;
  for (const key of keys) {
    const one = computeCost(10, { ...A, [key]: (moved as unknown as Record<string, number>)[key] });
    assert.notEqual(one.unitPrice, base, `${key} is watched but does not move the price`);
  }
});

/* ---------------- Quoted against actual ---------------- */

const quoted = computeCost(10, A);
const recompute = (a: CostAssumptions, q: number) => computeCost(q, a);

test("a job that recorded nothing produces no comparison", () => {
  // Rebuilding the cost from the quote's own numbers would return exactly
  // 1.00× and call it agreement.
  const r = compareQuoteToActual(quoted, A, { actualCycleMinutes: null, actualSetupHours: null, scrapCount: 0, quantityRun: 0 }, recompute);
  assert.equal(r, null);
});

test("a longer actual cycle costs more, and says which fact it used", () => {
  const r = compareQuoteToActual(
    quoted, A,
    { actualCycleMinutes: 12, actualSetupHours: 2, scrapCount: 1, quantityRun: 10 },
    recompute,
  )!;
  assert.ok(r.ratio > 1, `a 50% longer cycle did not cost more (${r.ratio})`);
  assert.ok(r.deltaPerPart > 0);
  assert.deepEqual(r.usedActuals.sort(), ["cycle time", "scrap rate", "setup hours"]);
  assert.deepEqual(r.assumedFromQuote, []);
});

test("what the job did not record is named as still being the quoted assumption", () => {
  // Otherwise part of the comparison is the quote against itself, presented
  // as if it were measured.
  const r = compareQuoteToActual(
    quoted, A,
    { actualCycleMinutes: 12, actualSetupHours: null, scrapCount: 0, quantityRun: 0 },
    recompute,
  )!;
  assert.deepEqual(r.usedActuals, ["cycle time"]);
  assert.deepEqual(r.assumedFromQuote.sort(), ["scrap rate", "setup hours"]);
});

test("scrap rate comes from the run, not from the quote, when the run recorded it", () => {
  const none = compareQuoteToActual(quoted, A, { actualCycleMinutes: 8, actualSetupHours: 1.5, scrapCount: 0, quantityRun: 10 }, recompute)!;
  const heavy = compareQuoteToActual(quoted, A, { actualCycleMinutes: 8, actualSetupHours: 1.5, scrapCount: 3, quantityRun: 10 }, recompute)!;
  assert.ok(heavy.actualUnitCost > none.actualUnitCost, "scrapping 3 of 10 cost no more than scrapping none");
});

test("a run that scrapped everything reaches the engine as 100%, uncapped", () => {
  // cost.ts clamps the divisor AND warns that no part ever ships at 100%.
  // Capping the rate here would suppress that warning and present a run where
  // nothing shipped as a slightly expensive one.
  let seen: number | null = null;
  const spy = (a: CostAssumptions, q: number) => {
    seen = a.scrapRate;
    return computeCost(q, a);
  };
  const r = compareQuoteToActual(quoted, A, { actualCycleMinutes: 8, actualSetupHours: 1.5, scrapCount: 10, quantityRun: 10 }, spy)!;
  assert.equal(seen, 1, `the observed scrap rate was altered on the way in (${seen})`);
  assert.ok(computeCost(10, { ...A, scrapRate: 1 }).warnings.some((w) => /no part ever ships/.test(w)));
  assert.ok(Number.isFinite(r.actualUnitCost), "the engine's clamp stopped working");
  assert.ok(r.ratio > 1);
});

test("the comparison uses the same engine, not a second cost model", () => {
  // A second model would attribute its own disagreement to the run.
  const r = compareQuoteToActual(quoted, A, { actualCycleMinutes: A.cycleMinutes, actualSetupHours: A.setupHours, scrapCount: 0, quantityRun: 0 }, recompute)!;
  // Same inputs as the quote, minus scrap which was not recorded: identical.
  assert.ok(Math.abs(r.ratio - 1) < 1e-9, `identical inputs gave ${r.ratio}`);
});

/* ---------------- The write path ---------------- */

const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
const actions = () => strip(readFileSync("src/app/(app)/quoting/actions.ts", "utf8"));

test("a stored price is computed server-side, never taken from the form", () => {
  // This number goes to a customer. A price that arrives in a form is a price
  // the caller chose.
  const src = actions();
  assert.match(src, /buildPackage\(user\.organizationId, partId\)/);
  assert.match(src, /computeCost\(quantity, assumptions\)/);
  for (const field of ["unitCost", "unitPrice", "lotPrice"]) {
    assert.ok(
      !new RegExp(`${field}:\\s*Number\\(formData`).test(src),
      `${field} is read off the form`,
    );
  }
});

test("the whole assumption set is stored, not just the price", () => {
  const src = actions();
  assert.match(src, /assumptionsJson: JSON\.stringify\(assumptions\)/);
  assert.match(src, /warnings: cost\.warnings/, "the assumption warnings are not stored with the estimate");
});

test("an estimate can only be attached to a quote for its own part", () => {
  // Attaching another part's price is how a wrong number reaches a customer.
  const src = actions();
  assert.match(src, /partRevision: \{ partId: quote\.partId/);
  assert.match(src, /organizationId: user\.organizationId/);
});

test("a sent quote does not gain new prices", () => {
  const src = actions();
  assert.match(src, /if \(quote\.status !== "DRAFT"\) return;/);
});

test("sending is refused without an estimate, server-side", () => {
  const src = actions();
  assert.match(src, /if \(to === "SENT" && !canSend\(quote\.estimates\.length\)\) return;/);
  assert.match(src, /if \(!canTransitionQuote\(quote\.status, to\)\) return;/);
});

test("every quoting write resolves its row against the session's organisation", () => {
  const src = actions();
  const writes = [...src.matchAll(/db\.(quote|costEstimate)\.(create|update)/g)];
  assert.ok(writes.length >= 4, `expected the four write sites, found ${writes.length}`);
  assert.ok(!/organizationId:\s*String\(formData/.test(src), "an organisation was read from a form");
});
