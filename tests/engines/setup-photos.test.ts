import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

/**
 * A photograph of how a setup was actually built.
 *
 * The last person who ran the job is the only record of which parallels went
 * under the part, which stop it was pushed to, which way the stock faced. That
 * leaves the shop when they do.
 *
 * It is a RECORD, not a verification, and the two halves of that sentence are
 * what these tests hold.
 */

const ROUTE = readFileSync("src/app/api/assets/route.ts", "utf8");
const TABLET = readFileSync("src/app/(app)/parts/[id]/tablet/page.tsx", "utf8");

/** Source with comments stripped — a note about a rule is not the rule. */
function code(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

test("a setup id is resolved through the part's organisation, never trusted", () => {
  // Setup carries no organizationId of its own. It is reached through its
  // revision's part, and that chain is what keeps one shop's photograph off
  // another shop's setup.
  assert.ok(
    /db\.setup\.findFirst\(\{[\s\S]{0,240}?partRevision: \{ part: \{ organizationId: user\.organizationId/.test(code(ROUTE)),
    "the setup id is not resolved against the session's organisation",
  );
  assert.ok(/status: 404/.test(ROUTE), "a setup that does not resolve is not refused");
});

test("the part id comes from the resolved setup, not from the form", () => {
  // Honouring a posted part id here would let a caller pair another shop's
  // setup with a part of their own.
  const body = code(ROUTE);
  assert.ok(/partId = owned\.partRevision\.partId/.test(body), "the part id is not taken from the resolved setup");
  assert.ok(
    !/setupId,[\s\S]{0,60}?partId: postedPartId/.test(body),
    "a client-supplied part id is stored alongside a setup photograph",
  );
});

test("a setup photograph has to be a photograph", () => {
  // The general validator accepts STEP and octet-stream, which are not
  // pictures of a vise.
  assert.ok(
    /setupId && !file\.type\.startsWith\("image\/"\)/.test(code(ROUTE)),
    "a non-image can be stored as a setup photograph",
  );
});

test("a photograph never clears a gate or satisfies the checklist", () => {
  // A photograph of a correct-looking setup is not evidence that the grip
  // depth is what the workholding engine was told. This is the principle-2
  // bite: the sign-off and the failing-gate computation must not learn about
  // photographs at all.
  const regions: [string, RegExp][] = [
    // A const expression, terminated by its own `);`.
    ["failingGates", /const failingGates = [\s\S]{0,600}?\n  \);/],
    // A server action, terminated by its closing brace at function indent.
    ["signOff", /async function signOff\([\s\S]{0,2000}?\n  \}/],
  ];
  for (const [name, re] of regions) {
    const m = re.exec(code(TABLET));
    assert.ok(m, `${name} moved — this test cannot check it any more`);
    for (const token of ["photo", "Photo", "asset", "Asset", "Uploaded"]) {
      assert.ok(!m![0].includes(token), `${name} references ${token} — a photograph is being treated as evidence`);
    }
  }
});

test("the page says a photograph is a record and not a verification", () => {
  assert.ok(/It is not verification that it is correct/.test(TABLET), "the page lets a photo read as proof");
  assert.ok(/clears no gate/.test(TABLET), "the page does not say the photograph clears nothing");
});

test("nothing claims to have read the photograph", () => {
  // No OCR, no dimension extraction, no "CANVAS checked your setup". The
  // stored kind is read by no engine.
  const body = code(TABLET) + code(ROUTE);
  for (const claim of ["ocr", "OCR", "recognise", "recognize", "detected", "analysed", "analyzed"]) {
    assert.ok(!body.includes(claim), `something claims to have interpreted the photograph: ${claim}`);
  }
});

test("ephemeral storage is declared, not discovered later", () => {
  // Without this a shop-floor photograph disappears on the next redeploy with
  // nothing said.
  assert.ok(/storageIsEphemeral/.test(TABLET), "the tablet does not surface whether storage survives a redeploy");
  assert.ok(/lost on the next redeploy/.test(TABLET), "the warning does not say what actually happens");
});

test("a setup photograph survives its setup being re-planned", () => {
  // Approving a new approach deletes and rewrites the setups. SetNull rather
  // than Cascade: re-planning must not destroy the record of how the job was
  // held on the run that already happened.
  const schema = readFileSync("prisma/schema.prisma", "utf8");
  assert.ok(
    /setup\s+Setup\?\s+@relation\(fields: \[setupId\], references: \[id\], onDelete: SetNull\)/.test(schema),
    "a setup photograph is cascade-deleted when the setup is re-planned",
  );
});

test("a setup photograph does not land in the reverse-engineering photo set", () => {
  // That page queries kind: "PHOTO" and its six labelled views mean something
  // specific. A vise photograph appearing there would be read as a part view.
  assert.ok(/"SETUP_PHOTO"/.test(ROUTE), "setup photographs are not given their own kind");
  const re = readFileSync("src/app/(app)/reverse-engineer/[id]/page.tsx", "utf8");
  assert.ok(/kind: "PHOTO"/.test(re), "the reverse-engineering query changed — check it still excludes setup photos");
});

test("both migration trees gained the column", () => {
  // One schema file serves sqlite and postgres; a migration written for only
  // one of them fails on deploy rather than in CI.
  const sqlite = readFileSync("prisma/migrations/20260902110000_setup_photos/migration.sql", "utf8");
  const pg = readFileSync("prisma/migrations-postgres/20260902110010_setup_photos/migration.sql", "utf8");
  for (const [name, sql] of [["sqlite", sqlite], ["postgres", pg]] as const) {
    assert.ok(/ADD COLUMN "setupId"/.test(sql), `${name} migration does not add the column`);
    assert.ok(/UploadedAsset_setupId_idx/.test(sql), `${name} migration does not index it`);
    assert.ok(/ON DELETE SET NULL/.test(sql), `${name} migration does not preserve the photo when a setup is replaced`);
  }
});
