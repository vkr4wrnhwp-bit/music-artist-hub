/**
 * DISAGREEMENT AND SHOP-KNOWLEDGE VOCABULARY, AND THE SCOPING RULE
 *
 * Split out of disagreement.ts, which is server-only because it touches the
 * database. None of this needs a database: it is the vocabulary a machinist
 * picks from and the rule deciding where an observation applies. Keeping it
 * here means the rule can be exercised directly, and that a page rendering a
 * label does not pull the Prisma client in behind it.
 */

export const DISAGREEMENT_SUBJECTS = [
  "READINESS_GATE",
  "WORKHOLDING",
  "TOOL_CHOICE",
  "FEED_SPEED",
  "PROCESS",
  "NOMINAL",
  "COST",
  "OTHER",
] as const;
export type DisagreementSubject = (typeof DISAGREEMENT_SUBJECTS)[number];

export const SUBJECT_LABEL: Record<DisagreementSubject, string> = {
  READINESS_GATE: "Readiness gate",
  WORKHOLDING: "Workholding",
  TOOL_CHOICE: "Tool choice",
  FEED_SPEED: "Feeds and speeds",
  PROCESS: "Process",
  NOMINAL: "Nominal dimension",
  COST: "Cost",
  OTHER: "Other",
};

/**
 * The scope a piece of shop knowledge was recorded against — only the axes
 * that matter for matching.
 */
export interface KnowledgeScope {
  machineId: string | null;
  toolId: string | null;
  materialId: string | null;
}

export interface KnowledgeContext {
  machineId?: string | null;
  toolIds?: string[];
  materialId?: string | null;
}

/**
 * Does this observation apply here?
 *
 * The schema says of the scope columns: "Any subset may be set; the more that
 * are, the narrower and more trustworthy the claim." So an axis a machinist
 * left blank is one they did not scope the observation to, and an axis they
 * filled in is one they did — the observation applies only where every axis
 * they named is satisfied.
 *
 * The query used to OR the three axes together, which does the opposite. An
 * observation recorded against VF-2 #2 AND tool T5 was returned for VF-2 #1
 * whenever T5 was in the crib, because the tool clause matched on its own.
 * The more carefully a machinist scoped what they saw, the more places it
 * turned up — and disagreement.ts's own comment says knowledge about VF-2 #2
 * is not evidence about VF-2 #1.
 *
 * The OR failed in the opposite direction too: a row with no machine, tool or
 * material set is knowledge about the shop itself, and no clause could ever
 * match it, so it was invisible everywhere.
 */
export function knowledgeApplies(scope: KnowledgeScope, context: KnowledgeContext): boolean {
  if (scope.machineId !== null && scope.machineId !== (context.machineId ?? null)) return false;
  if (scope.toolId !== null && !(context.toolIds ?? []).includes(scope.toolId)) return false;
  if (scope.materialId !== null && scope.materialId !== (context.materialId ?? null)) return false;
  return true;
}
