import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

/**
 * Locked principle 13, as a property of the repository rather than of one
 * function: "Organisation id always comes from the session, never from a
 * request parameter. One shop's proprietary geometry must never be reachable
 * from another shop's session."
 *
 * Every accessor and every mutating action was read by hand and every one
 * holds the line — the shop-record actions prove ownership with an
 * org-scoped findFirst before updating by id, the measurements API checks the
 * organisation through the relation chain, and getSetups takes an unscoped
 * revision id — the Setup table has no organisation of its own — and every
 * caller resolves that id through loadRevision, which is scoped.
 *
 * That is true today and nothing was keeping it true. These tests are coarse
 * on purpose: they are not trying to prove a given query is correct, only to
 * make the shape of a mistake fail loudly. A new action file that mutates the
 * database with no notion of an organisation in it is that shape.
 */

const APP = "src/app";
const LIB = "src/lib";

/**
 * What counts as changing manufacturing data.
 *
 * `audit(` is in here for a reason. The shop-floor tablet's sign-off — a
 * named human recording APPROVE against a setup at the machine — writes
 * nothing but an audit entry, so a detector that only looked for `db.x.create`
 * walked straight past it and the action sat on `requireUser()`. An audited
 * act is a record; a record is manufacturing data.
 */
const MUTATION = /\bdb\.[a-zA-Z]+\.(create|update|delete|upsert|createMany|updateMany|deleteMany)\b|\bawait audit\(/;

/**
 * Files allowed to mutate without mentioning an organisation, each for a
 * stated reason. Adding to this list should feel like a decision.
 */
const PRE_ORGANISATION: Record<string, string> = {
  "src/app/(auth)/sign-in/page.tsx":
    "Authenticates a user and stamps lastSeenAt on that user's own row. It runs before there is a session to take an organisation from.",
};

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const p = join(dir, entry);
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else if (/\.tsx?$/.test(entry)) out.push(p);
  }
  return out;
}

test("no route or action mutates the database without an organisation in scope", () => {
  const offenders: string[] = [];
  for (const file of walk(APP)) {
    const src = readFileSync(file, "utf8");
    if (!MUTATION.test(src)) continue;
    if (src.includes("organizationId")) continue;
    if (PRE_ORGANISATION[file]) continue;
    offenders.push(file);
  }
  assert.deepEqual(
    offenders,
    [],
    `these write to the database with no notion of which shop they belong to:\n  ${offenders.join("\n  ")}`,
  );
});

test("the pre-organisation exceptions are still the files they were written for", () => {
  // If sign-in stops mutating, the exception should go rather than sit there
  // covering something else that moves into the file later.
  for (const [file, why] of Object.entries(PRE_ORGANISATION)) {
    const src = readFileSync(file, "utf8");
    assert.ok(MUTATION.test(src), `${file} no longer mutates — remove its exception (${why})`);
  }
});

test("every data accessor takes an organisation id, or is reached only through one that does", () => {
  const data = readFileSync(join(LIB, "data.ts"), "utf8");
  const exported = [...data.matchAll(/export async function (\w+)\(([\s\S]*?)\)/g)];
  assert.ok(exported.length > 5, "precondition: the accessors are found");

  const unscoped = exported.filter(([, , args]) => !args.includes("organizationId")).map(([, name]) => name);
  assert.deepEqual(unscoped, ["getSetups"], `accessors taking no organisation id: ${unscoped.join(", ")}`);

  // The Setup table carries no organizationId — it can only ever be scoped
  // through its revision. So the rule is checked as a property of each
  // caller rather than as a list of approved filenames: whoever calls
  // getSetups must have resolved that revision id through the org-scoped
  // loadRevision in the same file. A new caller is fine; a new caller that
  // got its revision id somewhere else is not.
  const callers = walk("src").filter((f) => !f.endsWith("data.ts") && readFileSync(f, "utf8").includes("getSetups("));
  assert.ok(callers.length > 0, "precondition: getSetups has callers");
  for (const f of callers) {
    const src = readFileSync(f, "utf8");
    assert.match(
      src,
      /loadRevision\(\s*(user\.organizationId|organizationId)/,
      `${f} calls getSetups(revisionId) — the Setup table has no organisation of its own, so the revision id must come from an org-scoped loadRevision in this file`,
    );
    // And the id handed over must be the one that load returned.
    assert.match(src, /getSetups\(\s*revision\.revisionId/, `${f}: getSetups must be passed the loaded revision's own id`);
  }
});

test("the session is the only source of an organisation id", () => {
  // The rule stated as its inverse: no route may read an organisation id out
  // of a request. A crafted URL or form field must not be able to name one.
  const offenders: string[] = [];
  for (const file of walk(APP)) {
    const src = readFileSync(file, "utf8");
    for (const pattern of [
      /formData\.get\(\s*["'`]organizationId/,
      /searchParams[^\n]*organizationId/,
      /params[^\n]*\.organizationId/,
      /body\.organizationId/,
    ]) {
      if (pattern.test(src)) offenders.push(`${file} (${pattern.source})`);
    }
  }
  assert.deepEqual(offenders, [], `an organisation id is being read from a request:\n  ${offenders.join("\n  ")}`);
});

/* ---------------- What a signed-in user may DO ---------------- */

/**
 * Files that mutate but are not manufacturing data, each with its reason.
 * A viewer may keep their own UI state and ask the copilot a question; they
 * may not change a machine, a tool, a material or a program.
 */
const NOT_MANUFACTURING_DATA: Record<string, string> = {
  "src/app/(auth)/sign-in/page.tsx": "Runs before there is a session.",
  "src/app/(auth)/sign-up/page.tsx": "Creates the organisation and its first user.",
  "src/app/api/guide/route.ts": "The signed-in user's own guide progress.",
  "src/app/api/guide/events/route.ts": "The signed-in user's own guide telemetry.",
  "src/app/api/view-preferences/route.ts": "The signed-in user's own viewport preferences.",
  "src/app/api/copilot/route.ts": "Logs a conversation. Asking a question is not changing a parameter.",
};

test("every action that changes manufacturing data checks that the user may", () => {
  // canWrite was exported and called by nothing: every mutating action
  // checked that a user was signed in and never what they were allowed to do.
  // Nothing could exploit it, because every account this application creates
  // is an OWNER — but an exported permission that looks enforced is the same
  // shape as an unimplemented feature that looks implemented.
  const offenders: string[] = [];
  for (const file of walk(APP)) {
    const src = readFileSync(file, "utf8");
    if (!MUTATION.test(src)) continue;
    if (NOT_MANUFACTURING_DATA[file]) continue;
    if (/requireWrite\(\)|requireWriteApi\(\)/.test(src)) continue;
    offenders.push(file);
  }
  assert.deepEqual(
    offenders,
    [],
    `these change manufacturing data without checking the user's role:\n  ${offenders.join("\n  ")}`,
  );
});

test("the exemptions are still the files they were written for", () => {
  for (const [file, why] of Object.entries(NOT_MANUFACTURING_DATA)) {
    const src = readFileSync(file, "utf8");
    assert.ok(MUTATION.test(src), `${file} no longer mutates — drop its exemption (${why})`);
  }
});

test("a route handler denies with a status, never a redirect", () => {
  // A fetch() following a 307 to the dashboard and parsing HTML as JSON is a
  // worse failure than a plain 403, so route handlers use requireWriteApi.
  const offenders: string[] = [];
  for (const file of walk(APP)) {
    if (!file.endsWith("route.ts")) continue;
    if (readFileSync(file, "utf8").includes("requireWrite()")) offenders.push(file);
  }
  assert.deepEqual(offenders, [], `route handlers using the redirecting guard:\n  ${offenders.join("\n  ")}`);
});

test("a page still renders for someone who may only read it", () => {
  // requireWrite belongs inside the actions, not at the top of the render.
  // A viewer who cannot open the page cannot see the part they are being
  // asked to run.
  const offenders: string[] = [];
  for (const file of walk(APP)) {
    if (!file.endsWith(".tsx")) continue;
    const lines = readFileSync(file, "utf8").split("\n");
    if (lines[0].trim().replace(/[;"']/g, "") === "use server") continue;
    lines.forEach((line, i) => {
      if (!line.includes("requireWrite()")) return;
      const before = lines.slice(Math.max(0, i - 7), i).join("\n");
      if (!before.includes('"use server"')) offenders.push(`${file}:${i + 1}`);
    });
  }
  assert.deepEqual(offenders, [], `requireWrite outside a server action:\n  ${offenders.join("\n  ")}`);
});

/* ---------------- Nothing the shop did not choose ---------------- */

/**
 * Falling back to the first row of a shop's table is the same mistake in
 * three places: the material a part is force-modelled with, the machine its
 * envelope is validated against, and the vise its soft jaws are cut for. In
 * every case the substitute is a real record that looks chosen and was not.
 *
 * The `[0]` fallbacks that remain are display defaults — which of five plans
 * to show first, which setup a page opens on — and those are named here so a
 * new one has to be looked at rather than blending in.
 */
const DISPLAY_DEFAULTS = [
  'scored.find((s) => s.plan.pattern === approach) ?? scored[0]',
  'pkg.setups.find((s) => s.sequence > 1) ?? pkg.setups[0]',
  'j.outcomes.find((o) => o.code !== "SUCCESS") ?? j.outcomes[0]',
  'matches.find((n) => n > cur) ?? matches[0]',
];

test("no shop record is substituted for one the shop did not choose", () => {
  const offenders: string[] = [];
  for (const file of [...walk(APP), ...walk(LIB)]) {
    if (file.endsWith("package-selectors.ts")) continue;
    const src = readFileSync(file, "utf8");
    for (const line of src.split("\n")) {
      // The fallback may be a dotted path — pkg.workholdingDevices[0] — and the
      // first version of this required a bare identifier, so the vise
      // substitution slipped straight past the guard written for it.
      if (!/\.find\(/.test(line) || !/\?\?\s*[\w.]+\[0\]/.test(line)) continue;
      if (DISPLAY_DEFAULTS.some((d) => line.includes(d.slice(0, 40)))) continue;
      offenders.push(`${file}: ${line.trim()}`);
    }
  }
  assert.deepEqual(
    offenders,
    [],
    `a lookup falls back to the first record in the shop's table:\n  ${offenders.join("\n  ")}`,
  );
});
