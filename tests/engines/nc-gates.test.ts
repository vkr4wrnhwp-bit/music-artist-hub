import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

/**
 * THE GATE THAT PRODUCES A THING MUST NOT DEPEND ON THAT THING.
 *
 * `canExport` grew a `reconciled?.verified` clause when the reconciler was
 * added, and the same flag also disabled the Generate button. `reconciled` is
 * null when no program exists, and generating is the only thing in the
 * repository that writes an NCProgram row — so no program disabled the button
 * that would have written one, and NC output was unreachable for every part
 * that had never been posted. Which is every new part.
 *
 * It survived because every gate here looks like every other gate: a boolean
 * named for a permission, ANDed with evidence. Nothing distinguished
 * "evidence you need before writing motion" from "evidence about motion you
 * have already written", and only the second kind can be circular.
 *
 * This is a source scan, and that is stated rather than hidden: it cannot run
 * a React server component, so it asserts the shape of the two gates instead
 * of their behaviour.
 */

const src = readFileSync("src/app/(app)/parts/[id]/nc/page.tsx", "utf8");

/** The file with comments stripped — a rule quoted in prose is not a rule. */
const code = src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");

function declaration(name: string): string {
  const m = code.match(new RegExp(`const ${name} =([\\s\\S]*?);`));
  assert.ok(m, `${name} is not declared in the NC page`);
  return m![1];
}

test("the generate gate cannot depend on the program it generates", () => {
  const gen = declaration("canGenerate");
  for (const circular of ["reconciled", "existing", "verifyBlockers"]) {
    assert.ok(
      !gen.includes(circular),
      `canGenerate reads \`${circular}\`, which only exists once a program has been posted — that is the deadlock`,
    );
  }
});

test("generating still requires the full readiness chain", () => {
  // The fix must not have bought reachability by relaxing the gate. All three
  // of these are what it takes to be allowed to write machine motion at all.
  const gen = declaration("canGenerate");
  assert.match(gen, /preflightPassed\(preflight\)/, "generating must require every required pre-flight item");
  assert.match(gen, /selectedPost/, "generating must require a post");
  assert.match(gen, /machine/, "generating must require a machine");
});

test("exporting the bytes still requires evidence about those bytes", () => {
  const exp = declaration("canExport");
  assert.match(exp, /canGenerate/, "export must carry everything generation required");
  assert.match(exp, /verifyBlockers\.length === 0/, "export must require a clean NC verification");
  assert.match(exp, /reconciled\?\.verified/, "export must require the program to reconcile against its toolpath");
});

test("the Generate button is bound to the generate gate, and the export panel to the export gate", () => {
  // The regression was not in the boolean, it was in which control read it.
  const generateBtn = code.match(/<Button[^>]*type="submit"[^>]*>\s*Generate program/);
  assert.ok(generateBtn, "the Generate program submit button was not found");
  assert.match(generateBtn![0], /disabled=\{!canGenerate\}/, "Generate is disabled by the export gate again");

  assert.match(code, /\{canExport && !isTraining && <NcExportPanel/, "the export panel must stay behind canExport");
  assert.match(code, /\{canExport \?[\s\S]{0,200}existing\.code/, "the program body must stay behind canExport");
});
