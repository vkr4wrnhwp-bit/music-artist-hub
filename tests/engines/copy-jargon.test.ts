import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { actionLabel, entityLabel, fieldLabel } from "@/lib/audit-labels";

/**
 * The interface is written for a machinist, not for whoever built it.
 *
 * The part history printed Prisma model names and column names at the
 * operator — "PartResponsibilityProfile · matingComponent",
 * "LatheWorkholding · clampForceLbf". A runway tooltip explained itself with
 * "OperationState has no write sites". A panel footer was headed "What this
 * panel is not".
 */

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) out.push(...walk(full));
    else if (full.endsWith(".tsx")) out.push(full);
  }
  return out;
}

/** Source with comments stripped — a note to the next developer is not UI. */
function rendered(file: string): string {
  return readFileSync(file, "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");
}

const UI_FILES = [...walk("src/app"), ...walk("src/components")];

test("no schema noun is shown to an operator", () => {
  const banned = [
    { re: /what this [\w\s]{1,20} is not/i, why: "a heading written for the builder, not the reader" },
    { re: /without an engine/i, why: "'engine' is an internal word" },
    { re: /no write sites?/i, why: "a schema fact stated at an operator" },
    { re: /has no status column/i, why: "a column name stated at an operator" },
    { re: />No engine</, why: "'engine' is an internal word" },
  ];
  const offenders: string[] = [];
  for (const file of UI_FILES) {
    const src = rendered(file);
    for (const { re, why } of banned) {
      if (re.test(src)) offenders.push(`${file}: ${re.source} — ${why}`);
    }
  }
  assert.deepEqual(offenders, [], `debug jargon still rendered:\n  ${offenders.join("\n  ")}`);
});

test("the part history reads as words, not as a schema", () => {
  const src = rendered("src/app/(app)/parts/[id]/page.tsx");
  assert.ok(/entityLabel\(a\.entityType\)/.test(src), "the history prints the model name");
  assert.ok(/fieldLabel\(a\.field\)/.test(src), "the history prints the column name");
  assert.ok(/actionLabel\(a\.action\)/.test(src), "the history prints the raw action constant");
});

test("every entity and field written to the audit log renders as words", () => {
  // Collected from the call sites rather than hand-listed, so a new one is
  // caught the day it is added.
  const all = [...walk("src/app"), ...walk("src/lib"), ...walk("src/components")]
    .map((f) => readFileSync(f, "utf8"))
    .join("\n");
  const entities = [...all.matchAll(/entityType: "(\w+)"/g)].map((m) => m[1]);
  const fields = [...all.matchAll(/field: "(\w+)"/g)].map((m) => m[1]);
  assert.ok(entities.length > 10, "no audit call sites found — the collector is broken, not the code");

  for (const e of new Set(entities)) {
    const label = entityLabel(e);
    assert.ok(
      !/[a-z][A-Z]/.test(label),
      `${e} renders as "${label}" — that is still an identifier, not words`,
    );
  }
  for (const f of new Set(fields)) {
    const label = fieldLabel(f);
    assert.ok(!/[a-z][A-Z]/.test(label), `${f} renders as "${label}" — that is still an identifier`);
  }
});

test("translation does not launder who acted or what was overridden", () => {
  // The dangerous half of a rename. An operator has to see that a model was
  // the actor, and a disagreement has to stay visible as one.
  assert.equal(entityLabel("AIRecommendation"), "AI recommendation");
  assert.ok(/^AI /.test(entityLabel("AIRecommendation")), "the AI actor was renamed away");
  assert.equal(entityLabel("Disagreement"), "Disagreement");
});

test("a field the call site already wrote as prose is left alone", () => {
  assert.equal(fieldLabel("MANUFACTURING datum A"), "MANUFACTURING datum A");
  assert.equal(fieldLabel("RE step 2"), "RE step 2");
});

test("every audit action has a word for it", () => {
  const src = readFileSync("src/lib/audit.ts", "utf8");
  const decl = /action: ((?:"\w+" \| )*"\w+");/.exec(src);
  assert.ok(decl, "the action union moved — this test cannot check it any more");
  for (const a of decl![1].split("|").map((s) => s.trim().replace(/"/g, ""))) {
    assert.ok(actionLabel(a) !== a, `${a} is shown to the operator as its own constant`);
  }
});

test("the runway explains itself in the page, not in a tooltip", () => {
  const src = rendered("src/components/workspace/operation-runway.tsx");
  assert.ok(/LimitsDisclosure/.test(src), "the runway's limit is not an expandable element");
  assert.ok(
    !/title="Operation has no status column/.test(src),
    "the limit is back in a tooltip — a limit that changes what an operator would do is never only in a tooltip",
  );
});

test("nothing was softened while being reworded", () => {
  // The two feature-panel sentences are load-bearing and stay verbatim.
  const src = readFileSync("src/components/workspace/feature-panel.tsx", "utf8");
  assert.ok(/no point cloud and no least-squares routine/.test(src), "the surface-fitting statement was softened");
  assert.ok(/which is evidence and clears nothing/.test(src), "the disagreement statement was softened");
});

test("the placeholder warning survived the reword", () => {
  // A future contributor must not satisfy the jargon test by deleting the
  // warning instead of rewording it. An operation with no toolpath is
  // something the machinist has to be told about.
  const runway = rendered("src/components/workspace/operation-runway.tsx");
  assert.ok(/data\.placeholderCount/.test(runway), "the runway stopped counting operations with no toolpath");
  assert.ok(/DevLabel>No toolpath/.test(runway), "the per-row warning was deleted rather than reworded");
  const page = rendered("src/app/(app)/parts/[id]/page.tsx");
  assert.ok(/DevLabel>No toolpath/.test(page), "the operation plan stopped flagging rows with no toolpath");
});
