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
 * revision id but is only ever reached through loadRevision, which is scoped.
 *
 * That is true today and nothing was keeping it true. These tests are coarse
 * on purpose: they are not trying to prove a given query is correct, only to
 * make the shape of a mistake fail loudly. A new action file that mutates the
 * database with no notion of an organisation in it is that shape.
 */

const APP = "src/app";
const LIB = "src/lib";

const MUTATION = /\bdb\.[a-zA-Z]+\.(create|update|delete|upsert|createMany|updateMany|deleteMany)\b/;

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
  // getSetups(revisionId) is the single exception and it is safe by
  // construction: its only caller is buildPackage, which resolves the
  // revision through loadRevision(organizationId, partId) first and passes
  // the id off that result. If a second caller appears, this fails.
  const data = readFileSync(join(LIB, "data.ts"), "utf8");
  const exported = [...data.matchAll(/export async function (\w+)\(([\s\S]*?)\)/g)];
  assert.ok(exported.length > 5, "precondition: the accessors are found");

  const unscoped = exported.filter(([, , args]) => !args.includes("organizationId")).map(([, name]) => name);
  assert.deepEqual(unscoped, ["getSetups"], `accessors taking no organisation id: ${unscoped.join(", ")}`);

  const callers = walk("src").filter((f) => !f.endsWith("data.ts") && readFileSync(f, "utf8").includes("getSetups("));
  assert.deepEqual(
    callers,
    ["src/lib/package.ts"],
    "getSetups is unscoped and safe only because buildPackage resolves the revision through loadRevision first",
  );
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
