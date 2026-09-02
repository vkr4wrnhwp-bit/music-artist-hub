import "server-only";
import { db } from "./db";
import { knowledgeApplies } from "./disagreement-scope";
import type { DisagreementSubject } from "./disagreement-scope";
import { audit } from "./audit";

/**
 * "I DISAGREE"
 *
 * CANVAS is allowed to be wrong, and the person standing at the machine is the
 * most likely one to know it. A machinist who has run four hundred of these
 * knows things the model does not, and the worst possible response to that is a
 * dialog that makes them click "acknowledge" and moves on.
 *
 * So disagreement is recorded as evidence. Two rules govern what happens next,
 * and neither is negotiable:
 *
 *   1. RECORDING A DISAGREEMENT NEVER CLEARS A GATE.
 *      A gate reflects the state of the evidence. Disagreeing with it is a
 *      claim about the evidence, not a change to it. The gate moves when the
 *      underlying facts move — a measurement taken with a better instrument, a
 *      clamping force recorded, a comparable job produced.
 *
 *   2. SHOP KNOWLEDGE IS NOT UNIVERSAL KNOWLEDGE.
 *      "This cutter chatters above .450 on VF-2 #2" is true and useful and
 *      belongs to this shop, this machine, this tool. It is scoped that way in
 *      the data model and never promoted into a general engineering fact.
 *
 * What disagreement does buy is weight. A disagreement backed by a comparable
 * job that ran successfully is a different kind of claim from one backed by
 * nothing, and CANVAS records which it is rather than treating them alike.
 */

export {
  DISAGREEMENT_SUBJECTS,
  SUBJECT_LABEL,
  knowledgeApplies,
  type DisagreementSubject,
  type KnowledgeScope,
  type KnowledgeContext,
} from "./disagreement-scope";

export interface RecordDisagreementInput {
  organizationId: string;
  userId: string;
  subjectType: DisagreementSubject;
  subjectId?: string | null;
  partRevisionId?: string | null;
  setupId?: string | null;
  /** What CANVAS said, captured verbatim so the record survives a recompute. */
  canvasPosition: string;
  reasoning: string;
  hasRunComparable: boolean;
  comparableJobId?: string | null;
  proposedValue?: string | null;
}

export async function recordDisagreement(input: RecordDisagreementInput) {
  const row = await db.disagreement.create({
    data: {
      organizationId: input.organizationId,
      userId: input.userId,
      subjectType: input.subjectType,
      subjectId: input.subjectId ?? null,
      partRevisionId: input.partRevisionId ?? null,
      setupId: input.setupId ?? null,
      canvasPosition: input.canvasPosition,
      reasoning: input.reasoning,
      hasRunComparable: input.hasRunComparable,
      comparableJobId: input.comparableJobId ?? null,
      proposedValue: input.proposedValue ?? null,
      // A disagreement with evidence behind it is worth reviewing; one without
      // is worth recording but is not yet a claim on anything.
      status: input.hasRunComparable ? "OPEN" : "EVIDENCE_REQUESTED",
      // Never, under any circumstance, on creation.
      gateCleared: false,
    },
  });

  await audit({
    organizationId: input.organizationId,
    userId: input.userId,
    entityType: "Disagreement",
    entityId: row.id,
    action: "CREATE",
    actorType: "HUMAN",
    field: input.subjectType,
    oldValue: input.canvasPosition,
    newValue: input.proposedValue ?? null,
    reason: input.reasoning,
  });

  return row;
}

/**
 * Promotes a reviewed disagreement into scoped shop knowledge.
 *
 * Deliberately a separate, explicit step rather than something that happens
 * when the disagreement is filed. One machinist's objection is not yet
 * something CANVAS should reason from; it becomes that when somebody with the
 * authority to say so decides it has earned it.
 */
export async function promoteToShopKnowledge(input: {
  organizationId: string;
  userId: string;
  disagreementId: string;
  category: string;
  observation: string;
  machineId?: string | null;
  toolId?: string | null;
  materialId?: string | null;
  parameter?: string | null;
  thresholdValue?: number | null;
  thresholdUnit?: string | null;
  direction?: "ABOVE" | "BELOW" | null;
}) {
  const disagreement = await db.disagreement.findFirst({
    where: { id: input.disagreementId, organizationId: input.organizationId },
  });
  if (!disagreement) return null;

  const knowledge = await db.shopKnowledge.create({
    data: {
      organizationId: input.organizationId,
      category: input.category,
      observation: input.observation,
      machineId: input.machineId ?? null,
      toolId: input.toolId ?? null,
      materialId: input.materialId ?? null,
      parameter: input.parameter ?? null,
      thresholdValue: input.thresholdValue ?? null,
      thresholdUnit: input.thresholdUnit ?? null,
      direction: input.direction ?? null,
      origin: "DISAGREEMENT",
      jobCount: disagreement.hasRunComparable ? 1 : 0,
      recordedById: input.userId,
      // One person's experience, recorded once. It earns higher confidence by
      // being borne out across jobs, not by being asserted firmly.
      confidence: disagreement.hasRunComparable ? "LOW" : "UNKNOWN",
    },
  });

  await db.disagreement.update({
    where: { id: disagreement.id },
    data: {
      status: "ACCEPTED_AS_KNOWLEDGE",
      shopKnowledgeId: knowledge.id,
      resolution: "Recorded as shop knowledge. The gate it related to is unchanged.",
      // Restated here because it is the single most important property of this
      // whole flow: accepting the objection does not clear the gate.
      gateCleared: false,
    },
  });

  await audit({
    organizationId: input.organizationId,
    userId: input.userId,
    entityType: "ShopKnowledge",
    entityId: knowledge.id,
    action: "CREATE",
    actorType: "HUMAN",
    field: input.category,
    newValue: input.observation,
    reason: `Promoted from disagreement ${disagreement.id}`,
  });

  return knowledge;
}

/**
 * Shop knowledge that applies to a given context. Scoping is a filter, not a
 * ranking: knowledge about VF-2 #2 is not evidence about VF-2 #1, and offering
 * it as though it were is how a shop-specific observation quietly becomes a
 * universal claim.
 *
 * The organisation is filtered in the query — one shop's observations must
 * never be reachable from another's, and that is not a rule to enforce in
 * application code. The scope rule is applied in memory instead of as a
 * where-clause so that knowledgeApplies is the single statement of it, rather
 * than a Prisma expression that has to be read as one. A shop's knowledge
 * base is its own observations; this is tens of rows, not a table scan.
 */
export async function relevantKnowledge(params: {
  organizationId: string;
  machineId?: string | null;
  toolIds?: string[];
  materialId?: string | null;
}) {
  const all = await db.shopKnowledge.findMany({
    where: { organizationId: params.organizationId, active: true },
    include: { machine: true, tool: true, material: true },
    orderBy: [{ jobCount: "desc" }, { lastObservedAt: "desc" }],
  });

  return all.filter((k) => knowledgeApplies(k, params));
}

/**
 * Jobs this shop has run, for naming the comparable setup behind a
 * disagreement.
 *
 * One home, because the select for this was dead once already: `Disagree`'s
 * `jobs` prop defaulted to `[]` and its only call site passed none, so
 * "have you successfully run a comparable setup?" was asked with no way to
 * answer it. Six mount points each fetching their own list is six chances to
 * repeat that.
 *
 * COMPLETE only — a job still on the machine has not demonstrated anything.
 */
export async function comparableJobs(organizationId: string): Promise<{ id: string; label: string }[]> {
  const jobs = await db.job.findMany({
    where: { organizationId, status: "COMPLETE" },
    orderBy: { completedAt: "desc" },
    take: 50,
    include: { part: { select: { partNumber: true } } },
  });
  return jobs.map((j) => ({
    id: j.id,
    label: `${j.jobNumber} — ${j.part.partNumber} rev ${j.revision}, qty ${j.quantity}`,
  }));
}
