import { db } from "@/lib/db";
import { outcomeApplies, type OutcomeScope } from "@/lib/engines/jobs";
import type { JobOutcomeCode } from "@/lib/engines/network";

/**
 * WHAT PAST JOBS TAUGHT, WHERE IT APPLIES
 *
 * The Jobs page said outcomes exist so they "can teach the workholding and
 * process models rather than living in someone's memory", and nothing read
 * them. This is the read.
 *
 * Principle 11 governs the whole file: shop knowledge is scoped to the shop,
 * machine, tool and material it was observed on, and is never promoted into a
 * published engineering fact. So:
 *
 *   - Nothing here changes an engine's answer. It returns observations for a
 *     person to read beside the recommendation. A holding margin is not
 *     adjusted because a previous job moved in the vise; the machinist is
 *     shown that it did.
 *   - An observation applies only where machine, workholding and material all
 *     match. A null on either side matches nothing — an unrecorded machine is
 *     a missing fact, not a wildcard.
 *   - Only this organisation's jobs are read. Another shop's outcomes are not
 *     this shop's knowledge, and the anonymous network path is a separate
 *     opt-in thing entirely.
 */

export interface PriorObservation {
  code: JobOutcomeCode;
  cause: string;
  correctiveAction: string;
  partsAffected: number;
  recordedAt: Date;
  jobNumber: string;
  partName: string;
  /** True when this came from the same part, rather than merely the same scope. */
  samePart: boolean;
  toolNumber: number | null;
}

export async function observationsForScope(
  organizationId: string,
  here: OutcomeScope,
  currentPartId: string,
): Promise<PriorObservation[]> {
  // Nothing to match against: every observation would fail the scope test, so
  // do not go to the database to be told so.
  if (here.machine == null && here.material == null && here.workholding == null) return [];

  const rows = await db.jobOutcome.findMany({
    where: { code: { not: "SUCCESS" }, job: { organizationId } },
    orderBy: { recordedAt: "desc" },
    take: 200,
    include: { job: { include: { part: { select: { id: true, name: true } } } } },
  });

  return rows
    .filter((r) =>
      outcomeApplies(
        { machine: r.machineId, material: r.materialName, workholding: r.workholdingId, toolNumber: r.toolNumber },
        here,
      ),
    )
    .map((r) => ({
      code: r.code as JobOutcomeCode,
      cause: r.cause,
      correctiveAction: r.correctiveAction,
      partsAffected: r.partsAffected,
      recordedAt: r.recordedAt,
      jobNumber: r.job.jobNumber,
      partName: r.job.part.name,
      samePart: r.job.part.id === currentPartId,
      toolNumber: r.toolNumber,
    }));
}
