import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { emptyPartIntent } from "@/lib/domain/part-intent";
import type { Stock } from "@/lib/domain/features";
import {
  EVALUATED_PROCESSES,
  PROCESSES,
  PROCESS_LABEL,
  UNEVALUATED_PROCESSES,
  analyzeProcesses,
} from "@/lib/engines/process-advisor";

/**
 * "Do not fake capabilities." Unimplemented systems stay visibly labelled;
 * never fill an unimplemented feature with plausible-looking results.
 *
 * These pin three places the application was claiming more than it does.
 */

/* ---- the process advisor knows the edge of what it reasons about ---- */

/** A part answered well enough that the advisor is not blocked on inputs. */
function answeredInput() {
  const intent = emptyPartIntent("TEST");
  intent.quantity = { value: 25, source: "USER", confidence: "VERIFIED", confirmedByUser: true };
  intent.material = { value: "Aluminum 6061", source: "USER", confidence: "VERIFIED", confirmedByUser: true };
  intent.loadBearing = { value: true, source: "USER", confidence: "VERIFIED", confirmedByUser: true };
  intent.failureConsequence = { value: "LOW", source: "USER", confidence: "VERIFIED", confirmedByUser: true };
  return {
    intent,
    features: [],
    stock: { form: "RECTANGULAR", x: 6, y: 4, z: 0.75, material: "Aluminum 6061" } as Stock,
    finishedVolume: 12,
    machinedUnitCost: 48,
  };
}

test("every process the engine claims to evaluate actually produces a recommendation", () => {
  // The list must be what the engine DOES, not what it intends to. An entry
  // added here without a rule behind it is the failure this test exists for.
  const analysis = analyzeProcesses(answeredInput());
  const produced = new Set(analysis.recommendations.map((r) => r.process));
  for (const p of EVALUATED_PROCESSES) {
    assert.ok(produced.has(p), `${p} is listed as evaluated but the engine never recommends on it`);
  }
});

test("nothing outside the evaluated list quietly produces a recommendation", () => {
  const analysis = analyzeProcesses(answeredInput());
  for (const r of analysis.recommendations) {
    assert.ok(
      EVALUATED_PROCESSES.includes(r.process),
      `${r.process} is recommended on but is not declared as evaluated — the coverage note on the readiness page would understate what ran`,
    );
  }
});

test("the two lists partition the vocabulary — nothing is in both or neither", () => {
  const both = EVALUATED_PROCESSES.filter((p) => UNEVALUATED_PROCESSES.includes(p));
  assert.deepEqual(both, [], "a process is claimed as both evaluated and not");
  assert.equal(
    EVALUATED_PROCESSES.length + UNEVALUATED_PROCESSES.length,
    PROCESSES.length,
    "a process is in neither list — the coverage note would silently omit it",
  );
});

test("every named process has a label, so the coverage note can name it", () => {
  for (const p of PROCESSES) {
    assert.equal(typeof PROCESS_LABEL[p], "string", `${p} has no label`);
    assert.ok(PROCESS_LABEL[p].length > 0, `${p} has an empty label`);
  }
});

test("the readiness page says what the comparison does not cover", () => {
  const src = readFileSync("src/app/(app)/parts/[id]/readiness/page.tsx", "utf8");
  // The note must NAME them. An import that is no longer rendered leaves the
  // page looking like the whole field again.
  assert.ok(
    /UNEVALUATED_PROCESSES\.map\(/.test(src),
    "the process comparison is rendered as if it were the whole field — reading four options as 'the options' is how somebody rules out turning for a part that should be turned",
  );
  assert.ok(
    /EVALUATED_PROCESSES\.length/.test(src),
    "the note does not say how many processes were actually reasoned about",
  );
  assert.ok(
    /not\s*\n?\s*ruled out, they are not assessed/.test(src),
    "the coverage note does not distinguish 'not assessed' from 'ruled out'",
  );
});

/* ---- sections that cannot be used say so ---- */

test("a section is labelled a shell exactly while nothing can write to it", () => {
  // Quoting still renders real engines over a schema nothing in the
  // application writes, so a shop sees an empty section forever.
  const nav = readFileSync("src/components/nav.tsx", "utf8");
  assert.ok(
    /href: "\/quoting", label: "[^"]+", shell: true/.test(nav),
    "/quoting presents as a working section while nothing can write to it",
  );
  // Jobs has a write path now — release a revision, raise a job, record
  // actuals and outcomes. Leaving the shell label on would be the same lie in
  // the other direction: it would tell a shop not to bother.
  assert.ok(
    !/href: "\/jobs",[^}]*shell: true/.test(nav),
    "/jobs is still labelled a shell after its write path was built",
  );
});

test("neither shell instructs the machinist to press a control that does not exist", () => {
  // The worse failure than an unlabelled shell: "Open a part's Cost panel to
  // produce one, then attach it to a quote" sent someone looking for two
  // buttons that were never built.
  const quoting = readFileSync("src/app/(app)/quoting/page.tsx", "utf8");
  assert.ok(!/then attach it to a quote/.test(quoting), "the empty state still describes an action nobody can take");
  assert.ok(/not built yet/.test(quoting), "the empty state does not say the section is unbuilt");

  // Jobs no longer needs that guard — the actions exist. What it needs
  // instead is that its empty state does not claim to be unbuilt, and that
  // the entry point it names is one that now exists.
  const jobs = readFileSync("src/app/(app)/jobs/page.tsx", "utf8");
  assert.ok(!/not built yet/.test(jobs), "Jobs still says it is unbuilt after its write path was built");
  assert.match(jobs, /createJob/, "the Jobs page names no way to raise a job");
  assert.match(jobs, /released/i, "the Jobs page no longer says what a job is raised against");
});
