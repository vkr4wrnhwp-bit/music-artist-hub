import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

/**
 * Locked principles 5 and 12 as a property of the UI rather than of an
 * engine: "unimplemented systems stay visibly labelled", and "where an input
 * is missing they return null and say what is missing rather than
 * substituting a default".
 *
 * Every engine here already does its half. The failure this file is written
 * for is the other half — an engine computing an honest narrative that the
 * page then drops on the floor, so the operator reads a number without the
 * caveat that qualifies it. That is not a hypothetical: the three turning
 * hold panels each rendered a DIFFERENT subset of the same analysis type,
 * and the mill's holding margin rendered everything except the missing
 * inputs that name why it is indeterminate.
 *
 * These are source checks, and coarse on purpose. They cannot prove a panel
 * reads well — only that a field written for a human is not silently
 * discarded.
 */

const read = (p: string) => readFileSync(p, "utf8");

test("every narrative field on a TurnAnalysis is rendered, and by one component", () => {
  const analysis = read("src/lib/manufacturing/turn/analysis.ts");
  const iface = analysis.slice(analysis.indexOf("export interface TurnAnalysis"));
  const body = iface.slice(0, iface.indexOf("}"));
  const narrative = ["recommendations", "missingInputs", "assumptions"];
  for (const f of narrative) {
    assert.ok(body.includes(`${f}: string[]`), `precondition: TurnAnalysis declares ${f}`);
  }

  // One renderer, so a field cannot be shown in one panel and not another.
  const component = read("src/components/turn/analysis-narrative.tsx");
  // It must be destructured off the analysis AND actually rendered — naming
  // the field in a local that shadows it is how the first version of this
  // test was fooled.
  const destructured = /const \{([^}]*)\} = analysis;/.exec(component)?.[1] ?? "";
  for (const f of narrative) {
    assert.ok(destructured.includes(f), `TurnAnalysisNarrative does not read analysis.${f}`);
    assert.match(
      component,
      new RegExp(`${f}\\.(map|join)\\(`),
      `TurnAnalysisNarrative reads ${f} and never renders it — the engine writes it for a human`,
    );
  }

  // And the lathe workspace uses it for every analysis it shows, rather than
  // hand-rolling a different subset per panel.
  const page = read("src/app/(app)/lathe/[id]/page.tsx");
  const uses = page.match(/<TurnAnalysisNarrative analysis=\{(\w+)\}/g) ?? [];
  assert.deepEqual(
    uses.map((u) => /\{(\w+)\}/.exec(u)![1]).sort(),
    ["grip", "partOff", "stickout"],
    "each hold analysis on the lathe workspace must render through the shared narrative component",
  );
  // Each one still shows its own verdict reasoning next to the chip.
  for (const a of ["grip", "stickout", "partOff"]) {
    assert.ok(page.includes(`{${a}.detail}`), `${a}.detail is not rendered`);
  }
});

test("a calculation that could not be made says what it was never given", () => {
  // ShowCalculation's headline reads "—" when the engine returned null. The
  // reason belongs in the summary, not behind the fold: hidden one click
  // away is the same as not saying it.
  const sc = read("src/components/show-calculation.tsx");
  assert.match(sc, /missingInputs\?: string\[\]/, "ShowCalculation takes no missingInputs");
  const summaryEnd = sc.indexOf("</summary>");
  const foldStart = sc.indexOf('<div className="space-y-4 border-t border-line px-3 py-3">');
  assert.ok(summaryEnd > 0 && foldStart > summaryEnd, "precondition: the summary precedes the fold");
  assert.ok(
    sc.slice(summaryEnd, foldStart).includes("missingInputs.map"),
    "missing inputs are rendered behind the fold — they name the evidence that would move the answer",
  );

  // Both engines on the setups page carry missing inputs, and both pass them.
  const setups = read("src/app/(app)/parts/[id]/setups/page.tsx");
  for (const src of ["holdingMargin", "forceEstimate"]) {
    assert.ok(
      setups.includes(`missingInputs={a.${src}.missingInputs}`),
      `${src} names what it was never given and the setups page discards it`,
    );
  }
});

test("no engine names its missing evidence only where the answer is already absent", () => {
  /*
   * The third instance of this bug, so it is checked by shape now.
   *
   * missingInputs and a computed answer are INDEPENDENT: workholding can
   * return a 9.73x holding margin and "Workholding device not selected"
   * together, because clamp force is recorded on the setup rather than on
   * the vise. A page that renders the missing inputs only inside an
   * `else` — the branch for "no answer" — hides them in exactly the case
   * where a number is on screen to be believed.
   *
   * So: every file that reads `.missingInputs` must guard at least one of
   * those reads on the field being non-empty, rather than only on the
   * answer being absent. Files that delegate to a shared narrative
   * component do not read it here at all, which is the better shape and is
   * covered by the test above.
   */
  const readers = walk("src").filter((f) => f.endsWith(".tsx") && read(f).includes(".missingInputs"));
  assert.ok(readers.length > 0, "precondition: something renders missing inputs");
  for (const f of readers) {
    assert.match(
      read(f),
      /missingInputs\.length > 0/,
      `${f} renders missing inputs only as a fallback for a null answer — they are also true when there IS an answer`,
    );
  }
});

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const p = join(dir, entry);
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else out.push(p);
  }
  return out;
}
