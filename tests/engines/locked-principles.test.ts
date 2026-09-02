import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

/**
 * The locked principles that are currently true because nobody has broken
 * them yet, as executable checks.
 *
 * This file exists because of what wiring isEngineeringGrade turned up:
 * CLAUDE.md named it as the single home of "AI inference never satisfies a
 * required gate", and it was called by nothing at all. The rule read as
 * enforced and was not. Everything below is in that same position today —
 * correct, load-bearing, and unguarded.
 *
 * Source checks, and coarse on purpose. They cannot prove the architecture
 * is right, only that the shape of a specific documented mistake fails
 * loudly instead of landing quietly in a diff.
 */

const read = (p: string) => readFileSync(p, "utf8");

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const p = join(dir, entry);
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else if (/\.tsx?$/.test(p)) out.push(p);
  }
  return out;
}

/* ------------------------------------------------------------------ */
/* 6. An LLM is never the sole generator or validator of machine motion */
/* ------------------------------------------------------------------ */

test("the CAM engine contains no model calls and cannot acquire any", () => {
  // CLAUDE.md: "The CAM engine (engines/cam/) contains no model calls and
  // must not acquire any." An import is how it would acquire one.
  const files = walk("src/lib/engines/cam");
  assert.ok(files.length >= 4, `precondition: the CAM engine is where it was (${files.length} files)`);
  for (const f of files) {
    const src = read(f);
    for (const forbidden of [/from "@\/lib\/ai\//, /from "@anthropic-ai/, /getAiProvider/, /answerCopilot/]) {
      assert.doesNotMatch(
        src,
        forbidden,
        `${f} reaches the AI layer — the CAM engine is the deterministic generator of machine motion`,
      );
    }
  }
});

test("the deterministic toolpath engines stay free of the model too", () => {
  // The same rule, one level out: the turning operations engine emits motion
  // and is not inside engines/cam.
  // src/lib/nc/* was missing from this list and it parses, analyses and emits
  // machine motion for a program a shop hands CANVAS — the same rule applies.
  for (const f of [
    "src/lib/manufacturing/turn/operations.ts",
    "src/lib/manufacturing/turn/post.ts",
    "src/lib/nc/parse.ts",
    "src/lib/nc/analyze.ts",
    "src/lib/nc/load.ts",
    "src/lib/nc/source.ts",
  ]) {
    assert.doesNotMatch(read(f), /from "@\/lib\/ai\//, `${f} emits machine motion and must not consult a model`);
  }
});

/* ------------------------------------------------------------------ */
/* 13. Never expose AI API keys client-side                            */
/* ------------------------------------------------------------------ */

test("no client component reads the environment or imports the AI layer", () => {
  const clients = walk("src").filter((f) => /^["']use client["']/m.test(read(f)));
  assert.ok(clients.length > 0, "precondition: there are client components");
  for (const f of clients) {
    const src = read(f);
    assert.doesNotMatch(src, /process\.env\.[A-Z_]*(KEY|SECRET|TOKEN|PASSWORD)/, `${f} reads a secret in the browser`);
    assert.doesNotMatch(src, /from "@\/lib\/ai\//, `${f} imports the AI layer into a client bundle`);
  }
});

/* ------------------------------------------------------------------ */
/* 2. Gates are satisfied by evidence, not clicks                      */
/* ------------------------------------------------------------------ */

test("inspection capability cannot be made clearable by a confirmation", () => {
  // Typed as the literal `false` rather than as a boolean, so no caller can
  // set it — the verdict is a property of the instruments the shop owns.
  const src = read("src/lib/engines/inspection-capability.ts");
  assert.match(src, /clearableByConfirmation:\s*false;/, "the field is no longer typed as the literal false");
  assert.doesNotMatch(src, /clearableByConfirmation\??:\s*boolean/, "the field has been widened to a boolean");
});

/* ------------------------------------------------------------------ */
/* 12. Unvalidated models are classified DEVELOPMENT ANALYSIS          */
/* ------------------------------------------------------------------ */

test("models not validated against physical testing keep saying so, non-optionally", () => {
  for (const f of ["src/lib/engines/holding-margin.ts", "src/lib/manufacturing/turn/analysis.ts"]) {
    const src = read(f);
    assert.match(src, /developmentAnalysis:\s*true;/, `${f} no longer declares developmentAnalysis as the literal true`);
    assert.doesNotMatch(src, /developmentAnalysis\?:/, `${f} made developmentAnalysis optional — it can now be omitted`);
  }
});

/* ------------------------------------------------------------------ */
/* 13. The audit actor is typed explicitly, never inferred             */
/* ------------------------------------------------------------------ */

test("every audit entry names its actor as a literal, never a computed one", () => {
  // "actorType is always passed explicitly — it is never inferred, because
  // the whole value of the field is that it is trustworthy." A ternary or a
  // variable is an inference: it makes the field a guess about who acted.
  const audit = read("src/lib/audit.ts");
  assert.match(audit, /actorType: ActorType;/, "actorType is no longer required on an audit entry");
  assert.doesNotMatch(audit, /actorType\?:/, "actorType became optional — an omitted actor is an inferred one");

  const offenders: string[] = [];
  for (const f of walk("src")) {
    if (f.endsWith("audit.ts")) continue; // the sink itself passes the caller's value through
    if (f.startsWith("src/generated/")) continue; // Prisma's own types, not our call sites
    // Comments discuss the rule; only real call sites are being checked.
    const src = read(f).replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
    for (const m of src.matchAll(/actorType:\s*([^,;\n}]+)/g)) {
      const v = m[1].trim();
      if (/^"(HUMAN|AI|SYSTEM)"$/.test(v)) continue;
      // A type declaration — `actorType: ActorType` — states the field, it
      // does not set it. The rule is about values reaching a record.
      if (/^(ActorType|string)$/.test(v)) continue;
      // Carrying a STORED actor through unchanged — `row.actorType` — is not
      // an inference: the decision was made and recorded at the write, and
      // this is reading it back to show it. Anything else (a ternary, a
      // variable, a call) is a guess about who acted. Write sites are held to
      // the stricter rule below, so a carry-through into a database write is
      // still caught.
      if (/^[A-Za-z_$][\w$]*\.actorType(?: as ActorType)?$/.test(v)) continue;
      offenders.push(`${f}: actorType: ${v}`);
    }
  }
  assert.deepEqual(offenders, [], "an audit actor was computed rather than stated");
});

test("no database write decides an actor — every write states one", () => {
  // The read-back exemption above must not become a way to launder an actor
  // into storage. At a write site the actor is a literal or nothing.
  const offenders: string[] = [];
  for (const f of walk("src")) {
    if (f.startsWith("src/generated/")) continue;
    if (f.endsWith("audit.ts")) continue; // the sink writes the actor its caller stated
    const src = read(f).replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
    for (const w of src.matchAll(/db\.\w+\.(create|createMany|update|updateMany|upsert)\(/g)) {
      // To the matching close paren, so the window is the call and not
      // whatever happens to follow it — an overrunning window reports
      // unrelated code and would be worked around by widening the exemption.
      let depth = 0;
      let end = w.index! + w[0].length;
      for (let i = w.index! + w[0].length - 1; i < src.length; i++) {
        if (src[i] === "(") depth++;
        else if (src[i] === ")") { depth--; if (depth === 0) { end = i; break; } }
      }
      const block = src.slice(w.index!, end);
      for (const m of block.matchAll(/actorType:\s*([^,;\n}]+)/g)) {
        const v = m[1].trim();
        if (!/^"(HUMAN|AI|SYSTEM)"$/.test(v)) offenders.push(`${f}: ${w[0]} ... actorType: ${v}`);
      }
    }
  }
  assert.deepEqual(offenders, [], "a database write took its actor from something other than a literal");
});
