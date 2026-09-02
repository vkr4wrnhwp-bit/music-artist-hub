import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { ncVerificationBlockers, verifyNc, type NcVerificationIssue } from "@/lib/engines/cam/post";
import type { MachineProfile } from "@/lib/domain/shop";

const MACHINE = {
  id: "m", manufacturer: "Haas", model: "VF-2", controller: "HAAS_NGC",
  travelsX: 30, travelsY: 16, travelsZ: 20, maxSpindleRPM: 8100, spindleTaper: "CAT40",
  maxFeed: 500, rapidRate: 1000, toolCapacity: 20, hasToolChanger: true, accuracy: 0.0002,
} as unknown as MachineProfile;

/**
 * NC VERIFICATION is a step in the export chain, not a report printed beside
 * it. The locked architecture reads
 *
 *   … → SIMULATION → POST → NC VERIFICATION → HUMAN APPROVAL → EXPORT
 *
 * and it was broken in the middle: verifyNc ran at generation, its issues were
 * stored and rendered, and nothing consulted them — not the export button, and
 * not the authorisation that mints the file. A program the checker itself
 * called an ERROR on could be written to a stick and run.
 */

const issue = (severity: "ERROR" | "WARNING", message: string): NcVerificationIssue => ({
  severity,
  line: 1,
  message,
});

test("an error blocks; a warning does not", () => {
  assert.equal(ncVerificationBlockers([issue("WARNING", "long rapid")]).length, 0);
  assert.equal(ncVerificationBlockers([issue("ERROR", "no units word")]).length, 1);
});

test("one error among warnings still blocks — nothing averages it away", () => {
  const mixed = [issue("WARNING", "a"), issue("WARNING", "b"), issue("ERROR", "c"), issue("WARNING", "d")];
  const blockers = ncVerificationBlockers(mixed);
  assert.equal(blockers.length, 1);
  assert.equal(blockers[0].message, "c");
});

test("a clean program blocks nothing", () => {
  assert.equal(ncVerificationBlockers([]).length, 0);
});

test("a program the checker errors on is refused, end to end", () => {
  // A real program missing its units word — one of the checker's own errors.
  const nc = ["%", "O0001", "G17 G90 G54", "G00 X0 Y0", "G01 Z-0.25 F10.", "M30", "%"].join("\n");
  const issues = verifyNc(nc, MACHINE);
  const blockers = ncVerificationBlockers(issues);
  assert.ok(blockers.length > 0, "the checker found nothing to block on — pick a program it does object to");
  // Every blocker is an ERROR, and every ERROR is a blocker.
  assert.equal(blockers.length, issues.filter((i) => i.severity === "ERROR").length);
});

/* ---- both gates consult it ---- */

test("the export button is disabled by a verification error", () => {
  const src = readFileSync("src/app/(app)/parts/[id]/nc/page.tsx", "utf8");
  assert.ok(
    /canExport =\s*[\s\S]{0,200}?verifyBlockers\.length === 0/.test(src),
    "canExport ignores NC verification — a program with errors offers an enabled export button",
  );
});

test("the mint refuses on a verification error, re-checking the code itself", () => {
  const src = readFileSync("src/app/(app)/parts/[id]/nc/actions.ts", "utf8");
  // The button is a courtesy; the server action is the gate — it is a POST
  // endpoint reachable without the page.
  assert.ok(/ncVerificationBlockers\(/.test(src), "the export mint never consults NC verification");
  assert.ok(
    /verifyNc\(program\.code/.test(src),
    "the mint trusts the verdict stored at generation instead of verifying the text it is about to hand over",
  );
});

test("the mint takes no argument that could wave a verification error through", () => {
  // Structural, not prose: the export authorisation is reachable as a POST, so
  // the guarantee that has to hold is that nothing a caller sends can widen
  // what it will mint. Its whole input is which part.
  const src = readFileSync("src/app/(app)/parts/[id]/nc/actions.ts", "utf8");
  const sig = /export async function mintExport\(([^)]*)\)/.exec(src);
  assert.ok(sig, "mintExport not found");
  assert.equal(
    sig![1].trim(),
    "partId: string",
    "mintExport accepts more than a part id — anything else is a lever on the gate",
  );
});

test("the blocker rule lives in one place", () => {
  // The gate exists twice over — page and action — and both must ask the same
  // function. A second copy of "which severities block" is a second answer.
  for (const file of ["src/app/(app)/parts/[id]/nc/page.tsx", "src/app/(app)/parts/[id]/nc/actions.ts"]) {
    const src = readFileSync(file, "utf8");
    assert.ok(/ncVerificationBlockers\(/.test(src), `${file} does not use the shared rule`);
    // Colouring a row by severity is fine. Filtering on it to decide what
    // blocks is a second copy of the rule.
    assert.ok(
      !/\.filter\([^)]*severity === "ERROR"/.test(src),
      `${file} reimplements which severities block instead of asking ncVerificationBlockers`,
    );
  }
});
