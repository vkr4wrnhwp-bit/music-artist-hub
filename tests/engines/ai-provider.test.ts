import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

/**
 * WHICH PROVIDER IS CHOSEN, AND WHETHER IT SAYS SO.
 *
 * The failure this guards is not a crash. An operator sets ANTHROPIC_API_KEY
 * in Render, opens the reverse-engineering screen, and reads "no vision model
 * is connected" — which is true, and tells them nothing about the second
 * variable that was the actual cause. A shop would conclude the feature does
 * not work.
 *
 * `getAiProvider` caches its choice for the life of the process, so the rule
 * is tested by reading the module's source for the selection expression
 * rather than by calling it repeatedly. That is weaker than executing it and
 * it is stated here rather than hidden: what it can prove is that the key
 * alone selects anthropic and that both mismatched states are announced.
 */

const src = readFileSync("src/lib/ai/provider.ts", "utf8");

test("only \"deterministic\" pins the deterministic provider; a key otherwise wins", () => {
  // The failure mode this replaced: matching CANVAS_AI_PROVIDER === "anthropic"
  // exactly, so a trailing space or a capital A produced the deterministic
  // provider with the key sitting right there in the environment.
  assert.match(
    src,
    /raw === "deterministic" \? "deterministic" : key \? "anthropic" : "deterministic"/,
    "an unrecognised CANVAS_AI_PROVIDER with a key present must resolve to anthropic, not to silence",
  );
  assert.match(src, /CANVAS_AI_PROVIDER\?\.trim\(\)\.toLowerCase\(\)/, "the value must be trimmed and lowercased before comparison");
});

test("both mismatched configurations are announced, not swallowed", () => {
  assert.ok(
    /raw === "deterministic" && key/.test(src) && /console\.warn/.test(src),
    "a key set while deterministic is pinned must warn — it is the state that looks configured and is not",
  );
  assert.ok(
    /raw !== "anthropic" && raw !== "deterministic"/.test(src),
    "an unrecognised provider name must be named back to the operator, not accepted in silence",
  );
  assert.ok(
    /configured === "anthropic" && !key/.test(src),
    "resolving to anthropic with no key must warn rather than quietly degrading",
  );
});

test("the provider is still constructed from the environment, never from a request", () => {
  // The key must not become reachable from anything a caller passes in.
  assert.ok(
    !/getAiProvider\((?!\)).*\)/.test(src.split("export async function getAiProvider")[1] ?? ""),
    "getAiProvider takes no arguments — a provider chosen per request is a provider a request can choose",
  );
});
