import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { evidenceDigest, RESOLUTION_STATUSES } from "@/lib/review-findings";
import type { FindingEvidence } from "@/lib/engines/review";

/**
 * "Do not make review findings only chat text." Persisting them is easy; the
 * risk is that persistence quietly becomes a way to make a finding go away by
 * clicking, which is exactly what principle 2 forbids.
 */

const ev = (pairs: [string, string][]): FindingEvidence[] => pairs.map(([label, value]) => ({ label, value }));

test("the digest moves when a number moves", () => {
  // This is the whole mechanism. A response is bound to a digest; if the
  // digest did not track the numbers, an acknowledgement of a 0.9 stickout
  // would silently carry over onto a 0.4 one.
  const a = evidenceDigest("HIGH", ev([["Stickout", '0.900"'], ["Depth", '1.500"']]));
  const b = evidenceDigest("HIGH", ev([["Stickout", '0.400"'], ["Depth", '1.500"']]));
  assert.notEqual(a, b);
});

test("the digest moves when the severity moves", () => {
  const same = ev([["Margin", "1.80×"]]);
  assert.notEqual(evidenceDigest("MEDIUM", same), evidenceDigest("HIGH", same));
});

test("the digest is stable for the same evidence", () => {
  const a = evidenceDigest("LOW", ev([["A", "1"], ["B", "2"]]));
  const b = evidenceDigest("LOW", ev([["A", "1"], ["B", "2"]]));
  assert.equal(a, b);
  // Order is part of the evidence, not an accident of iteration: two findings
  // whose rows are the same set in a different order are not the same finding
  // state, and treating them as one would silently keep a stale answer.
  assert.notEqual(a, evidenceDigest("LOW", ev([["B", "2"], ["A", "1"]])));
});

test("a label change is a different condition, not the same one reworded", () => {
  assert.notEqual(
    evidenceDigest("HIGH", ev([["Stickout", '0.900"']])),
    evidenceDigest("HIGH", ev([["Tool stickout", '0.900"']])),
  );
});

test("the vocabulary has no status that closes a finding", () => {
  // RESOLVED, CLOSED, DISMISSED, WAIVED would each be a click that ends an
  // engineering condition. The three that exist all leave the finding open.
  assert.deepEqual([...RESOLUTION_STATUSES], ["ACKNOWLEDGED", "ACTIONED", "DISPUTED"]);
  for (const s of RESOLUTION_STATUSES) {
    assert.ok(!/RESOLVED|CLOSED|DISMISS|WAIVE|IGNORE|ACCEPT/.test(s), `${s} reads as closing the finding`);
  }
});

/* ---- and the write path clears nothing ---- */

const strip = (src: string) => src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");

test("the resolution action writes one row and touches nothing else", () => {
  // The failure this guards is a later edit that "helpfully" lowers a
  // severity or marks a gate satisfied when somebody acknowledges a finding.
  const src = strip(readFileSync("src/app/(app)/parts/[id]/review/finding-actions.ts", "utf8"));
  const writes = [...src.matchAll(/db\.(\w+)\.(create|update|updateMany|upsert|delete|deleteMany)\b/g)];
  assert.deepEqual(
    writes.map((m) => `${m[1]}.${m[2]}`),
    ["findingResolution.create"],
    "the resolution action writes something other than a resolution row",
  );
});

test("the action takes its organisation from the session, never from the form", () => {
  const src = strip(readFileSync("src/app/(app)/parts/[id]/review/finding-actions.ts", "utf8"));
  assert.ok(/requireWrite\(\)/.test(src), "the action does not gate on a signed-in writer");
  assert.ok(/user\.organizationId/.test(src), "organisation is not read from the session");
  assert.ok(
    !/formData\.get\(\s*["'](organizationId|partRevisionId|revisionId|evidenceDigest)["']/.test(src),
    "the action reads an identity or a digest off the form",
  );
});

test("the actor type is written explicitly, never inferred", () => {
  // Principle 13: audit entries type the actor as HUMAN | AI | SYSTEM and it
  // is never inferred.
  const src = strip(readFileSync("src/app/(app)/parts/[id]/review/finding-actions.ts", "utf8"));
  assert.ok(/actorType:\s*"HUMAN"/.test(src));
});

test("the sync path never reads a stored finding in place of running the engine", () => {
  const src = strip(readFileSync("src/lib/review-findings-store.ts", "utf8"));
  // syncFindings takes the computed findings as an argument and returns
  // history keyed by them. If it ever grew a path that built findings out of
  // rows, this is where it would show.
  assert.ok(/findings: ReviewFinding\[\]/.test(src), "syncFindings no longer takes the computed findings");
  assert.ok(!/severity: row\.|title: row\.|detail: row\./.test(src), "a stored snapshot is being served as a finding");
});

test("the response panel offers no control that hides a finding", () => {
  const src = strip(readFileSync("src/components/review/finding-response.tsx", "utf8"));
  // A hidden input carrying the finding key is fine; a control that removes
  // the finding from the page is not.
  assert.ok(!/Resolve and|Dismiss|Close finding|Mark resolved|Waive/i.test(src));
  assert.ok(!/display:\s*none/.test(src));
  // And it says so, because a machinist should not have to infer it.
  assert.ok(/does not clear this finding/.test(src));
});
