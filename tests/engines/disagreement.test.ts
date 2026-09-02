import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import {
  knowledgeApplies,
  DISAGREEMENT_SUBJECTS,
  SUBJECT_LABEL,
  type KnowledgeScope,
  type KnowledgeContext,
} from "@/lib/disagreement-scope";

/**
 * Locked principle 11: "Shop knowledge is not universal knowledge. It is
 * scoped to the shop, machine, tool and material it was observed on, and is
 * never promoted into a published engineering fact."
 *
 * The schema states the same rule from the other end: "Any subset may be set;
 * the more that are, the narrower and more trustworthy the claim."
 *
 * So the tests here are about one thing — that an observation is offered
 * exactly where the machinist said it applies, and nowhere else. Widening it
 * is how "this cutter chatters above .450 on VF-2 #2" quietly becomes "this
 * cutter chatters above .450".
 */

const scope = (o: Partial<KnowledgeScope> = {}): KnowledgeScope => ({
  machineId: null, toolId: null, materialId: null, ...o,
});

const ctx = (o: KnowledgeContext = {}): KnowledgeContext => o;

/* ---------------- Scoping narrows, it never widens ---------------- */

test("an observation about one machine is not evidence about another", () => {
  const onVf2No2 = scope({ machineId: "vf2-2" });
  assert.equal(knowledgeApplies(onVf2No2, ctx({ machineId: "vf2-2" })), true);
  assert.equal(knowledgeApplies(onVf2No2, ctx({ machineId: "vf2-1" })), false);
  assert.equal(knowledgeApplies(onVf2No2, ctx({ machineId: null })), false, "no machine in context is not this machine");
  assert.equal(knowledgeApplies(onVf2No2, ctx()), false);
});

test("every axis a machinist named has to be satisfied, not just one", () => {
  // THE defect. The query ORed the three axes, so an observation recorded
  // against VF-2 #2 AND tool T5 came back for VF-2 #1 whenever T5 was in the
  // crib — the tool clause matched on its own. The more carefully somebody
  // scoped what they saw, the more places it turned up.
  const onThisMachineWithThisTool = scope({ machineId: "vf2-2", toolId: "t5" });

  assert.equal(knowledgeApplies(onThisMachineWithThisTool, ctx({ machineId: "vf2-2", toolIds: ["t5"] })), true);
  assert.equal(
    knowledgeApplies(onThisMachineWithThisTool, ctx({ machineId: "vf2-1", toolIds: ["t5"] })),
    false,
    "same tool, different machine — the observation was about the machine too",
  );
  assert.equal(
    knowledgeApplies(onThisMachineWithThisTool, ctx({ machineId: "vf2-2", toolIds: ["t9"] })),
    false,
    "same machine, different tool",
  );
});

test("a three-axis observation is the narrowest, not the broadest", () => {
  // Under the old OR, adding axes could only ever match MORE contexts. The
  // schema says the opposite: more axes means a narrower claim.
  const narrow = scope({ machineId: "vf2-2", toolId: "t5", materialId: "ti" });
  const broad = scope({ toolId: "t5" });
  const contexts: KnowledgeContext[] = [
    ctx({ machineId: "vf2-2", toolIds: ["t5"], materialId: "ti" }),
    ctx({ machineId: "vf2-1", toolIds: ["t5"], materialId: "ti" }),
    ctx({ machineId: "vf2-2", toolIds: ["t5"], materialId: "al" }),
    ctx({ toolIds: ["t5"] }),
  ];
  const narrowHits = contexts.filter((c) => knowledgeApplies(narrow, c)).length;
  const broadHits = contexts.filter((c) => knowledgeApplies(broad, c)).length;
  assert.ok(narrowHits < broadHits, `the narrower claim matched ${narrowHits} contexts and the broader one ${broadHits}`);
});

test("an axis left blank is not scoped on, so it does not exclude", () => {
  // Blank means "I did not observe this to be about the machine", not "this
  // is about no machine".
  const aboutATool = scope({ toolId: "t5" });
  assert.equal(knowledgeApplies(aboutATool, ctx({ machineId: "vf2-1", toolIds: ["t5"] })), true);
  assert.equal(knowledgeApplies(aboutATool, ctx({ machineId: "anything", toolIds: ["t5"], materialId: "whatever" })), true);
});

test("knowledge about the shop itself is visible, not invisible", () => {
  // The OR had a second failure in the opposite direction: a row with no
  // machine, tool or material set had no clause that could match it, so
  // shop-wide knowledge was returned nowhere at all.
  const shopWide = scope();
  assert.equal(knowledgeApplies(shopWide, ctx()), true);
  assert.equal(knowledgeApplies(shopWide, ctx({ machineId: "vf2-1", toolIds: ["t5"], materialId: "ti" })), true);
});

test("a tool observation matches whichever of the context's tools it names", () => {
  const aboutT5 = scope({ toolId: "t5" });
  assert.equal(knowledgeApplies(aboutT5, ctx({ toolIds: ["t1", "t5", "t9"] })), true);
  assert.equal(knowledgeApplies(aboutT5, ctx({ toolIds: ["t1", "t9"] })), false);
  assert.equal(knowledgeApplies(aboutT5, ctx({ toolIds: [] })), false);
  assert.equal(knowledgeApplies(aboutT5, ctx()), false, "no tools in context is not this tool");
});

test("a material observation is not evidence about another material", () => {
  const aboutTitanium = scope({ materialId: "ti-6al-4v" });
  assert.equal(knowledgeApplies(aboutTitanium, ctx({ materialId: "ti-6al-4v" })), true);
  assert.equal(knowledgeApplies(aboutTitanium, ctx({ materialId: "6061" })), false);
});

test("matching is a filter, never a score", () => {
  // The function returns a boolean by design. A relevance score would let a
  // near-miss surface as weak evidence, which is exactly the promotion of
  // scoped knowledge into general knowledge that principle 11 forbids.
  const r = knowledgeApplies(scope({ machineId: "vf2-2" }), ctx({ machineId: "vf2-1" }));
  assert.equal(typeof r, "boolean");
  assert.equal(r, false);
});

test("the rule is exhaustive over the three axes", () => {
  // Every combination of scoped/unscoped against matching/mismatching, so a
  // future axis added to one side and not the other fails here.
  const ids = { machineId: "m1", toolId: "t1", materialId: "x1" };
  for (const m of [null, "m1"]) {
    for (const t of [null, "t1"]) {
      for (const x of [null, "x1"]) {
        const s = scope({ machineId: m, toolId: t, materialId: x });
        assert.equal(
          knowledgeApplies(s, ctx({ machineId: ids.machineId, toolIds: [ids.toolId], materialId: ids.materialId })),
          true,
          `scope(${m},${t},${x}) should match the context it was recorded in`,
        );
        const mismatched = ctx({ machineId: "other", toolIds: ["other"], materialId: "other" });
        assert.equal(
          knowledgeApplies(s, mismatched),
          m === null && t === null && x === null,
          `scope(${m},${t},${x}) against a wholly different context`,
        );
      }
    }
  }
});

/* ---------------- The vocabulary ---------------- */

test("every disagreement subject has a label", () => {
  for (const s of DISAGREEMENT_SUBJECTS) {
    assert.ok(SUBJECT_LABEL[s], `${s} has no label`);
    assert.ok(SUBJECT_LABEL[s].length > 2);
  }
});

test("the subjects cover what a machinist would actually disagree with", () => {
  // Not exhaustive as a claim about the world — but a machinist who cannot
  // find the thing they object to will pick OTHER, and OTHER is unanalysable.
  for (const expected of ["READINESS_GATE", "WORKHOLDING", "TOOL_CHOICE", "FEED_SPEED", "PROCESS"] as const) {
    assert.ok(DISAGREEMENT_SUBJECTS.includes(expected), `${expected} is not a subject`);
  }
});

test("a disagreement about a readiness gate is a first-class subject", () => {
  // It is the one the whole flow exists for: CANVAS said the gate fails, the
  // machinist says it does not. That has to be recordable without clearing it.
  assert.ok(DISAGREEMENT_SUBJECTS.includes("READINESS_GATE"));
});

/* ---- every significant recommendation can be argued with ---- */

/**
 * Principle 11: every significant recommendation supports WHY / CHANGE / I
 * DISAGREE. It was mounted in exactly one place — non-passing readiness gates
 * — so six of the subjects the vocabulary defines were unreachable. A
 * machinist could not disagree with a process recommendation, a workholding
 * assessment, a suggested nominal, a tool substitution, a make-vs-buy verdict,
 * a feed and speed, or a proposed operation order.
 *
 * The vocabulary existing is not the same as the vocabulary being reachable.
 */

function uiFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) out.push(...uiFiles(full));
    else if (full.endsWith(".tsx")) out.push(full);
  }
  return out;
}

const MOUNTS = [...uiFiles("src/app"), ...uiFiles("src/components")]
  .flatMap((file) => {
    const src = readFileSync(file, "utf8");
    return [...src.matchAll(/<Disagree\b[\s\S]{0,900}?\/>/g)].map((m) => ({ file, jsx: m[0] }));
  })
  .filter((m) => !m.file.endsWith("disagree.tsx"));

test("every mount point passes a part, a surface and a job list", () => {
  assert.ok(MOUNTS.length >= 7, `only ${MOUNTS.length} mount points — the coverage below cannot hold`);
  for (const { file, jsx } of MOUNTS) {
    assert.ok(/partId=\{/.test(jsx), `${file}: a Disagree without a partId — the action cannot find the revision`);
    assert.ok(/surface="/.test(jsx), `${file}: a Disagree without a surface — the machinist is redirected elsewhere`);
    // The exact regression that already happened: jobs defaulted to [] and
    // the form asked "have you run a comparable setup?" with no way to answer.
    assert.ok(/jobs=\{/.test(jsx), `${file}: a Disagree with no jobs — the comparable-job select will not render`);
  }
});

test("every subject in the vocabulary is reachable, except OTHER", () => {
  const mounted = new Set(MOUNTS.map((m) => /subjectType="(\w+)"/.exec(m.jsx)?.[1]).filter(Boolean));
  for (const subject of DISAGREEMENT_SUBJECTS) {
    if (subject === "OTHER") continue; // the catch-all, deliberately not a mount point
    assert.ok(
      mounted.has(subject),
      `${subject} is in the vocabulary and nowhere in the interface — a machinist cannot disagree with it`,
    );
  }
});

test("every mounted subject is one the vocabulary knows", () => {
  for (const { file, jsx } of MOUNTS) {
    const subject = /subjectType="(\w+)"/.exec(jsx)?.[1];
    assert.ok(subject, `${file}: a Disagree with no subject`);
    assert.ok(
      (DISAGREEMENT_SUBJECTS as readonly string[]).includes(subject!),
      `${file}: ${subject} is not a disagreement subject — the record would be unscopeable`,
    );
  }
});

/* ---- the shared action records evidence and clears nothing ---- */

/** The action with comments stripped — a note explaining a rule is not the
  * rule, and asserting over prose only catches the documentation. */
const ACTION = readFileSync("src/app/(app)/parts/[id]/disagree-actions.ts", "utf8")
  .replace(/\/\*[\s\S]*?\*\//g, "")
  .replace(/^\s*\/\/.*$/gm, "");

test("the action takes the subject from the form and validates it", () => {
  assert.ok(/formData\.get\("subjectType"\)/.test(ACTION), "the action does not read the submitted subject");
  assert.ok(
    /DISAGREEMENT_SUBJECTS\.find\(/.test(ACTION),
    "the submitted subject is not checked against the vocabulary",
  );
  // A mislabelled disagreement is worse than a rejected one: the subject is
  // what scopes the knowledge afterwards.
  assert.ok(!/subjectType: "OTHER"/.test(ACTION), "an unrecognised subject is filed under OTHER rather than refused");
  assert.ok(!/subjectType: "READINESS_GATE"/.test(ACTION), "the action hardcodes one subject");
});

test("the action clears nothing", () => {
  // Principle 11 enforced structurally rather than by comment. The only writes
  // permitted here are the ownership lookups and recordDisagreement itself.
  assert.ok(!/gateCleared/.test(ACTION), "the action touches the gate-cleared flag");
  const writes = [...ACTION.matchAll(/db\.\w+\.(\w+)\(/g)].map((m) => m[1]);
  for (const w of writes) {
    assert.equal(w, "findFirst", `the action performs a db.${w} — it may only look things up and record`);
  }
});

test("the action never trusts a revision or an organisation from the form", () => {
  assert.ok(!/formData\.get\("partRevisionId"\)/.test(ACTION), "the form can name a revision");
  assert.ok(!/formData\.get\("organizationId"\)/.test(ACTION), "the form can name an organisation");
  assert.ok(/loadRevision\(user\.organizationId, partId\)/.test(ACTION), "the revision is not derived server-side");
  for (const scoped of ["setup", "job"]) {
    assert.ok(
      new RegExp(`db\\.${scoped}\\.findFirst\\([\\s\\S]{0,220}?organizationId: user\\.organizationId`).test(ACTION),
      `the submitted ${scoped} id is not resolved against this organisation`,
    );
  }
});

test("the machinist is returned somewhere the app chose, not somewhere the form did", () => {
  assert.ok(/RETURN_PATH/.test(ACTION), "the redirect target is not from a fixed map");
  assert.ok(!/formData\.get\("returnTo"\)|formData\.get\("next"\)/.test(ACTION), "the form supplies a redirect target");
});
