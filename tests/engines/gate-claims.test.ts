import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

/**
 * What the UI says a gate does must match what the gate does.
 *
 * The carousel page carried a notice titled "This does not yet gate
 * readiness", written while TOOLING LOADED was still a proposal and left
 * standing after it was built and made blocking. So the page told a machinist
 * their pocket map decided nothing, while the readiness engine was holding
 * parts off READY_TO_RUN on exactly that data.
 *
 * A stale sentence about a safety gate is worse than no sentence, because it
 * is read and believed. This is the same class as the docs-vs-code guard —
 * prose that outlived the code it described — except the prose is in the
 * product.
 */

const APP = "src/app";
const READINESS = readFileSync("src/lib/engines/readiness.ts", "utf8");

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) out.push(...walk(full));
    else if (full.endsWith(".tsx") || full.endsWith(".ts")) out.push(full);
  }
  return out;
}

test("the tooling gate is blocking in every branch it can take", () => {
  // The claim the UI is allowed to make rests on this. If the gate stops
  // being blocking, the page's wording has to change with it.
  const block = READINESS.slice(READINESS.indexOf("/* ---- Tooling loaded ----"));
  const branches = [...block.matchAll(/"Tooling loaded",\s*\n\s*"(\w+)",/g)].map((m) => m[1]);
  assert.ok(branches.length >= 4, `expected every tooling branch, found ${branches.length}`);
  // Each gate() call ends `detail, blocking, actions` — no branch may pass false.
  const nonBlocking = [...block.matchAll(/"Tooling loaded",[\s\S]{0,600}?\n\s{10}(true|false),/g)]
    .map((m) => m[1])
    .filter((b) => b === "false");
  assert.deepEqual(nonBlocking, [], "a tooling branch is non-blocking while the UI says the map gates readiness");
});

test("no page claims a gate does not gate", () => {
  const offenders: string[] = [];
  for (const file of walk(APP)) {
    const src = readFileSync(file, "utf8");
    // Prose in the product asserting that something does not yet gate, or does
    // not yet decide. If a gate really is not wired up, label it SHELL or
    // DEVELOPMENT — those say "not built", not "built and harmless".
    if (/does not (yet )?gate|does not (yet )?decide whether a job can run/i.test(src)) {
      offenders.push(file);
    }
  }
  assert.deepEqual(
    offenders,
    [],
    `these tell a machinist a gate is inert — check it still is:\n  ${offenders.join("\n  ")}`,
  );
});

test("the carousel page says what the gate actually does", () => {
  const src = readFileSync("src/app/(app)/machines/[id]/carousel/page.tsx", "utf8");
  assert.ok(/gates readiness/i.test(src), "the page no longer tells the machinist the map matters");
  // And it must keep explaining the case that is NOT a failure, because that
  // is the half a shop gets wrong: an unmapped changer is not a missing tool.
  assert.ok(
    /NOT_ATTEMPTED/.test(src),
    "the page does not explain that an unmapped changer is not a missing tool",
  );
});
