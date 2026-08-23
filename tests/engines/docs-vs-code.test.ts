import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join } from "node:path";

/**
 * The docs are audited against the code, and this keeps the audit from
 * rotting the way the docs did. What the audit found, as a pattern: a
 * "NOT BUILT — planned" doc written first, the feature built later with
 * its own "BUILT" doc, and the stale stub left standing (three of them),
 * plus not-built lists that named seven things that now exist. A stale
 * architecture doc is the same failure mode as a principle nothing
 * enforces — it reads as authoritative and is not.
 *
 * Coarse checks, deliberately: they cannot prove a doc is truthful, only
 * that two specific shapes of lie fail loudly.
 */

const DOCS = "docs";
const docs = readdirSync(DOCS).filter((f) => f.endsWith(".md"));

test("every source path a doc cites exists", () => {
  // A doc pointing at a file that has been renamed or deleted is a doc
  // nobody can follow. Backticked src/ paths are the checkable claims.
  const missing: string[] = [];
  for (const f of docs) {
    const body = readFileSync(join(DOCS, f), "utf8");
    for (const m of body.matchAll(/`(src\/[A-Za-z0-9/._[\]()-]+)`/g)) {
      // A path with a glob or placeholder is prose, not a claim.
      if (m[1].includes("*")) continue;
      if (!existsSync(m[1])) missing.push(`${f} -> ${m[1]}`);
    }
  }
  assert.deepEqual(missing, [], "docs cite source files that do not exist");
});

test("a doc headlined NOT BUILT does not sit beside the module that builds it", () => {
  // The stubs the audit deleted all had the same tell: a title claiming
  // NOT BUILT while a src/ module named in the body (or a sibling BUILT
  // doc for the same feature) existed. Any doc whose TITLE says NOT BUILT
  // must not cite an existing src file as its subject.
  for (const f of docs) {
    const body = readFileSync(join(DOCS, f), "utf8");
    const title = body.split("\n")[0] ?? "";
    if (!/NOT BUILT/i.test(title)) continue;
    const cited = [...body.matchAll(/`(src\/[A-Za-z0-9/._[\]()-]+\.ts)`/g)].map((m) => m[1]);
    const existing = cited.filter((p) => existsSync(p));
    assert.deepEqual(
      existing,
      [],
      `${f} is headlined NOT BUILT but cites ${existing.join(", ")} — either the feature shipped or the doc names the wrong subject`,
    );
  }
});
