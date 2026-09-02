import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  PROPOSAL_KINDS,
  SCENE_ACTION_KINDS,
  validateProposals,
  validateSceneActions,
} from "@/lib/engines/copilot-actions";
import { CONTEXTS } from "@/lib/workspace-contexts";

/**
 * The copilot's contract was {reply, references, needs} — text plus two string
 * lists — and the client rendered references as a comma-joined line. It could
 * not select geometry, change what the workspace was showing, or put a change
 * in front of anybody.
 *
 * The split that makes this safe: scene actions change what is on screen and
 * nothing else, so a wrong one wastes a click. Proposals change the part, so
 * they do not take effect at all — they go into the queue a human accepts
 * from, which is the path every other AI suggestion already takes.
 */

const TARGETS = { featureIds: ["f1", "f2"], operationIds: ["op1"] };
const act = (kind: string, targetId: string, label = "Look at this") => ({ kind, targetId, label });

test("an action pointing at something on this part is kept", () => {
  const r = validateSceneActions([act("SELECT_FEATURE", "f1"), act("FOCUS_OPERATION", "op1"), act("SET_CONTEXT", "HOLD")], TARGETS);
  assert.deepEqual(r.actions.map((a) => a.targetId), ["f1", "op1", "HOLD"]);
  assert.deepEqual(r.rejected, []);
});

test("an id that is not on this part is dropped, not handed over as a control", () => {
  // A model can name any id. This mattered less when a reference was a
  // caption and matters now that it is a button.
  const r = validateSceneActions([act("SELECT_FEATURE", "f-from-another-part"), act("FOCUS_OPERATION", "op-nope")], TARGETS);
  assert.deepEqual(r.actions, []);
  assert.equal(r.rejected.length, 2);
  assert.ok(r.rejected.every((x) => /does not exist here/.test(x.reason)));
});

test("a context outside the workspace's own list is dropped", () => {
  const r = validateSceneActions([act("SET_CONTEXT", "EVERYTHING")], TARGETS);
  assert.deepEqual(r.actions, []);
  assert.match(r.rejected[0].reason, /not a context the workspace has/);
  // And every real context is accepted, so the list cannot drift.
  for (const c of CONTEXTS) {
    assert.equal(validateSceneActions([act("SET_CONTEXT", c)], TARGETS).actions.length, 1, `${c} was rejected`);
  }
});

test("an action kind the workspace cannot perform is dropped, and says so", () => {
  const r = validateSceneActions([act("DELETE_FEATURE", "f1"), act("RUN_PROGRAM", "f1")], TARGETS);
  assert.deepEqual(r.actions, []);
  assert.equal(r.rejected.length, 2);
  // The reason has to name the real problem. Falling through to the context
  // check would reject it too, for a reason that makes no sense of it.
  assert.ok(
    r.rejected.every((x) => /not an action the workspace has/.test(x.reason)),
    `rejected for the wrong reason: ${r.rejected.map((x) => x.reason).join(" | ")}`,
  );
});

test("an action with no label is dropped — there would be nothing to press", () => {
  const r = validateSceneActions([{ kind: "SELECT_FEATURE", targetId: "f1", label: "   " }], TARGETS);
  assert.deepEqual(r.actions, []);
  assert.match(r.rejected[0].reason, /nothing could be shown to press/);
});

test("a dropped action is reported rather than vanishing", () => {
  // Otherwise the answer refers to a control that is not on the screen.
  const r = validateSceneActions([act("SELECT_FEATURE", "ghost")], TARGETS);
  assert.equal(r.rejected.length, 1);
  assert.equal(r.rejected[0].targetId, "ghost");
});

test("the same action twice appears once, and a wall of buttons is capped", () => {
  const dupes = validateSceneActions([act("SELECT_FEATURE", "f1"), act("SELECT_FEATURE", "f1")], TARGETS);
  assert.equal(dupes.actions.length, 1);
  // Eight DISTINCT valid actions — dedup cannot do the capping for us.
  const distinct = [
    act("SELECT_FEATURE", "f1", "f1"),
    act("SELECT_FEATURE", "f2", "f2"),
    act("FOCUS_OPERATION", "op1", "op1"),
    ...CONTEXTS.map((c) => act("SET_CONTEXT", c, c)),
  ];
  assert.equal(distinct.length, 8, "precondition: more distinct actions than the cap");
  const many = validateSceneActions(distinct, TARGETS);
  assert.ok(many.actions.length <= 6, `${many.actions.length} buttons is a menu, not an answer`);
});

test("junk in the list does not throw", () => {
  const r = validateSceneActions([null, "nope", 42, {}, { kind: "SELECT_FEATURE" }], TARGETS);
  assert.deepEqual(r.actions, []);
});

test("every declared action kind is one the client can actually perform", () => {
  // A kind validated here and not dispatched there is an action that silently
  // does nothing when pressed.
  const src = readFileSync("src/components/workspace/copilot.tsx", "utf8");
  for (const k of SCENE_ACTION_KINDS) {
    assert.ok(new RegExp(`case "${k}":`).test(src), `${k} passes validation and the client does not handle it`);
  }
});

/* ---- proposals ---- */

test("a well-formed proposal is kept", () => {
  const r = validateProposals([{ kind: "PROCESS", summary: "Consider casting at this quantity rather than machining from billet." }]);
  assert.equal(r.proposals.length, 1);
  assert.deepEqual(r.rejected, []);
});

test("a kind the proposals page cannot accept is dropped", () => {
  const r = validateProposals([{ kind: "DELETE_EVERYTHING", summary: "A perfectly reasonable sentence about it." }]);
  assert.deepEqual(r.proposals, []);
  assert.match(r.rejected[0].reason, /not a kind/);
});

test("a proposal nobody could decide on is dropped", () => {
  const r = validateProposals([{ kind: "PROCESS", summary: "do it" }]);
  assert.deepEqual(r.proposals, []);
  assert.match(r.rejected[0].reason, /no summary a person could decide on/);
});

test("a feature proposal is held to the same field spec as the other two doors", () => {
  // Otherwise the copilot introduces a feature through a third route in a
  // shape the engines cannot read.
  const good = validateProposals([{
    kind: "FEATURE",
    summary: "Add the 40 mm bearing bore the drawing calls out.",
    payload: { kind: "BORE", parameters: { centerX: 0, centerY: 0, diameter: 1.5748, depth: 0.75, bottomRadius: 0, top: 0 } },
  }]);
  assert.equal(good.proposals.length, 1);

  const missingDiameter = validateProposals([{
    kind: "FEATURE",
    summary: "Add the 40 mm bearing bore the drawing calls out.",
    payload: { kind: "BORE", parameters: { centerX: 0, centerY: 0, depth: 0.75, bottomRadius: 0, top: 0 } },
  }]);
  assert.deepEqual(missingDiameter.proposals, []);
  assert.match(missingDiameter.rejected[0].reason, /Diameter is required/);

  const noParams = validateProposals([{ kind: "FEATURE", summary: "Add a bore, trust me on the size." }]);
  assert.deepEqual(noParams.proposals, []);
  assert.match(noParams.rejected[0].reason, /no parameters describes nothing buildable/);
});

test("every proposal kind is one the schema already stores", () => {
  const schema = readFileSync("prisma/schema.prisma", "utf8");
  const line = /model AIRecommendation[\s\S]*?kind\s+String\s*\/\/([^\n]*)/.exec(schema)![1];
  for (const k of PROPOSAL_KINDS) {
    assert.ok(line.includes(k), `${k} is not a kind AIRecommendation documents`);
  }
});

/* ---- the copilot cannot apply anything ---- */

const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");

test("the copilot route writes proposals and never touches the part", () => {
  // Principle 3: the model may suggest and may not certify. A second, softer
  // route to the same data is exactly how that gets lost.
  const src = strip(readFileSync("src/app/api/copilot/route.ts", "utf8"));
  const writes = [...src.matchAll(/db\.(\w+)\.(createMany|create|updateMany|update|upsert|deleteMany|delete)/g)].map((m) => `${m[1]}.${m[2]}`);
  assert.deepEqual(
    [...new Set(writes)].sort(),
    ["aIRecommendation.create", "conversation.create", "conversationMessage.createMany"],
    "the copilot writes something other than a proposal and its own conversation",
  );
  assert.ok(!/db\.feature\.|db\.setup\.|db\.operation\.|db\.partRevision\.update/.test(src), "the copilot writes part data directly");
});

test("proposals are written at PROPOSED, never accepted", () => {
  const src = strip(readFileSync("src/app/api/copilot/route.ts", "utf8"));
  assert.match(src, /status: "PROPOSED"/);
  assert.ok(!/status: "ACCEPTED"/.test(src), "the copilot accepts its own proposal");
  assert.ok(!/decidedBy/.test(src), "the copilot records a decision nobody made");
});

test("actions are validated against the package the server built, not the request", () => {
  const src = strip(readFileSync("src/app/api/copilot/route.ts", "utf8"));
  assert.match(src, /featureIds: pkg\.revision\.features\.map/);
  assert.match(src, /operationIds: pkg\.setups\.flatMap/);
});

test("the proposal is audited as the model's work", () => {
  const src = strip(readFileSync("src/app/api/copilot/route.ts", "utf8"));
  assert.match(src, /actorType: "AI"/);
});

test("the panel does not offer to accept a proposal", () => {
  // Accepting an AI suggestion is a decision with its own page and its own
  // record. A button here would be a second, quieter one.
  const src = strip(readFileSync("src/components/workspace/copilot.tsx", "utf8"));
  assert.match(src, /not applied/);
  assert.ok(!/Accept|Apply/.test(src), "the copilot panel offers to apply a proposal");
});

test("the deterministic provider proposes no changes", () => {
  // It is a grammar parser, not a planner. Inventing a proposal would be the
  // failure principle 5 names.
  const src = strip(readFileSync("src/lib/ai/deterministic.ts", "utf8"));
  const say = /const say = \([\s\S]{0,600}?\}\);/.exec(src);
  assert.ok(say, "the deterministic say() moved — this test cannot check it any more");
  assert.match(say![0], /proposals: \[\]/);
});

test("the deterministic provider still offers scene actions", () => {
  // A context switch needs no knowledge of the part, so the copilot's actions
  // work with no API key — which is the state most of CANVAS runs in.
  const src = readFileSync("src/lib/ai/deterministic.ts", "utf8");
  assert.match(src, /const look = \(context: string, label: string\)/);
  const uses = (src.match(/look\("(PART|HOLD|CUT|VERIFY|COST)"/g) ?? []).length;
  assert.ok(uses >= 3, `only ${uses} answers offer somewhere to look`);
});


test("no server-side engine imports a client module", () => {
  // Caught by running it, not by a type. copilot-actions.ts imported CONTEXTS
  // from interaction.tsx, which is "use client": under the server bundle a
  // client module resolves to a client-reference proxy, so CONTEXTS.includes
  // is not a function and the endpoint threw at runtime. It typechecked
  // perfectly.
  const walk = (dir: string): string[] => {
    const { readdirSync, statSync } = require("node:fs") as typeof import("node:fs");
    const { join } = require("node:path") as typeof import("node:path");
    return readdirSync(dir).flatMap((e) => {
      const full = join(dir, e);
      return statSync(full).isDirectory() ? walk(full) : /\.tsx?$/.test(full) ? [full] : [];
    });
  };
  const clientModules = new Set(
    walk("src/components").filter((f) => /^["']use client["']/m.test(readFileSync(f, "utf8"))),
  );
  const offenders: string[] = [];
  for (const f of [...walk("src/lib"), ...walk("src/app/api")]) {
    const src = readFileSync(f, "utf8");
    for (const m of src.matchAll(/from "@\/components\/([^"]+)"/g)) {
      const target = `src/components/${m[1]}`;
      for (const candidate of [`${target}.tsx`, `${target}.ts`, `${target}/index.tsx`]) {
        if (clientModules.has(candidate)) offenders.push(`${f} imports the client module ${candidate}`);
      }
    }
  }
  assert.deepEqual(offenders, [], "server code imports a client module — it will be a proxy at runtime");
});
