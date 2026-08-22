import { test } from "node:test";
import assert from "node:assert/strict";
import { selectPrimaryMachine, selectMaterial } from "@/lib/package-selectors";

/**
 * Both of these ended in a silent fallback to the first row in the shop's
 * table, and both fed engines that are written to handle a null honestly.
 * The fallback talked over all of it.
 */

const machine = (id: string) => ({ id, model: id });
const material = (name: string, specificEnergy: number) => ({ name, specificEnergy });

const TABLE = [
  material("Aluminum 6061", 0.3),
  material("Aluminum 7075", 0.35),
  material("Steel 4140", 1.3),
  material("Titanium 6Al-4V", 1.6),
];

/* ---------------- Material ---------------- */

test("a material the shop has no record of is null, not the first row", () => {
  // `?? materials[0]` made `material` non-null with the WRONG material. A
  // part specified in Titanium 6Al-4V, with no titanium on file, was
  // force-modelled at aluminium's specific energy — 0.3 against 1.6 — and
  // that number feeds the holding margin deciding whether the part stays in
  // the vise.
  assert.equal(selectMaterial(TABLE, "Inconel 718"), null);
  assert.equal(selectMaterial(TABLE, "some alloy nobody stocks"), null);
});

test("a part with no material stated is null rather than the shop's first material", () => {
  // Four of the seven parts in the seeded database have no material recorded
  // at all, two of them reverse-engineering jobs where the material is
  // unknown by definition. Every one was being modelled as Aluminum 6061.
  assert.equal(selectMaterial(TABLE, null), null);
  assert.equal(selectMaterial(TABLE, ""), null);
});

test("a material that IS on file resolves to itself, not to a near match", () => {
  assert.equal(selectMaterial(TABLE, "Titanium 6Al-4V")?.specificEnergy, 1.6);
  assert.equal(selectMaterial(TABLE, "Aluminum 7075")?.specificEnergy, 0.35);
});

test("matching is exact — a close name is not the same material", () => {
  // "Aluminum 6061" and "Aluminum 7075" differ by 17% in specific energy and
  // far more in strength. A fuzzy match here would be the same fabrication in
  // a politer form.
  assert.equal(selectMaterial(TABLE, "Aluminum"), null);
  assert.equal(selectMaterial(TABLE, "6061"), null);
  assert.equal(selectMaterial(TABLE, "aluminum 6061"), null, "case included — this is a table key, not a search");
});

test("an empty material table yields null rather than throwing", () => {
  assert.equal(selectMaterial([], "Aluminum 6061"), null);
});

/* ---------------- Machine ---------------- */

test("no setup naming a machine means no machine, not the shop's first one", () => {
  // The fallback had the machine-envelope gate validating against whichever
  // machine happened to be first in the list, and every toolpath taking its
  // spindle and feed limits from it. readiness.ts already says "No machine is
  // selected, so travel and spindle limits cannot be validated" — the
  // fallback was talking over it.
  const machines = [machine("vf2"), machine("vf4")];
  assert.equal(selectPrimaryMachine([{ machineId: null }, { machineId: null }], machines), null);
  assert.equal(selectPrimaryMachine([], machines), null);
});

test("the machine a setup actually names is the one returned", () => {
  const machines = [machine("vf2"), machine("vf4")];
  assert.equal(selectPrimaryMachine([{ machineId: "vf4" }], machines)?.id, "vf4");
});

test("the first setup that names a machine decides, not the first setup", () => {
  const machines = [machine("vf2"), machine("vf4")];
  assert.equal(selectPrimaryMachine([{ machineId: null }, { machineId: "vf4" }], machines)?.id, "vf4");
});

test("a setup naming a machine the shop no longer has is null, not a substitute", () => {
  // A deleted machine is not an invitation to pick another one.
  assert.equal(selectPrimaryMachine([{ machineId: "scrapped" }], [machine("vf2")]), null);
});

test("an empty machine list yields null rather than throwing", () => {
  assert.equal(selectPrimaryMachine([{ machineId: "vf2" }], []), null);
});
