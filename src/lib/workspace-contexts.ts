/**
 * The workspace's context vocabulary, in a module with no boundary.
 *
 * These lived in `components/workspace/interaction.tsx`, which is a
 * `"use client"` module. Importing them from server code typechecks and then
 * fails at runtime — under the server bundle a client module resolves to a
 * client-reference proxy, so `CONTEXTS.includes` is not a function. The copilot
 * endpoint validates a requested context against this list, and did exactly
 * that.
 *
 * A shared vocabulary that both sides validate against belongs in neither
 * side's bundle. `interaction.tsx` re-exports it so nothing that already
 * imports it has to move.
 */

/** What the user is currently trying to decide. Views onto one object. */
export const CONTEXTS = ["PART", "HOLD", "CUT", "VERIFY", "COST"] as const;
export type Context = (typeof CONTEXTS)[number];

export const CONTEXT_LABEL: Record<Context, string> = {
  PART: "Part",
  HOLD: "Hold",
  CUT: "Cut",
  VERIFY: "Verify",
  COST: "Cost",
};
