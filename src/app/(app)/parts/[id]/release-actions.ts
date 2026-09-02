"use server";

import { revalidatePath } from "next/cache";
import { requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { buildPackage } from "@/lib/package";
import { acknowledgementsSatisfied, evaluateRelease, releaseSnapshot } from "@/lib/engines/jobs";
import { audit } from "@/lib/audit";

/**
 * RELEASING A REVISION TO THE FLOOR
 *
 * The Jobs page said jobs are created from a released part revision, and
 * nothing anywhere set a revision to RELEASED. This is that act.
 *
 * The rules that must not vary:
 *
 *   - The gates are re-evaluated HERE, server-side, from the package. A
 *     release decided on what the client happened to be showing is a release
 *     decided on a stale page.
 *   - A blocking gate that is not PASS refuses the release, and the refusal
 *     names the gates. This is principle 1 applied to a second surface, not a
 *     new rule: the aggregate is the worst unresolved required gate, and one
 *     blocking failure is a refusal however many others pass.
 *   - Releasing clears nothing. No gate is written, no severity lowered. What
 *     is written is a decision and the readiness picture it was taken against.
 *   - The actor is a signed-in writer and is typed HUMAN explicitly.
 */

export async function releaseRevision(partId: string, formData: FormData) {
  const user = await requireWrite();
  const pkg = await buildPackage(user.organizationId, partId);
  if (!pkg) return;

  const revisionId = String(formData.get("revisionId") ?? "");
  // The revision comes from the package built for THIS organisation, never
  // from the form: a form that can name a revision can name another shop's.
  if (revisionId !== pkg.revision.revisionId) return;

  const verdict = evaluateRelease(pkg.readiness.gates);

  /*
   * Acknowledgements, checked against the gates evaluated HERE. A blocking
   * gate at REVIEW needs a named human to take responsibility for it — one
   * acknowledgement per gate, never a single blanket accept, because one
   * click standing for several separate engineering judgements is the shape
   * of the problem this split exists to avoid.
   *
   * Gates with no evidence behind them are not in this list at all and cannot
   * be reached by adding ids to the form: verdict.acknowledgeable is derived
   * server-side from the package, and anything not in it is ignored.
   */
  const acknowledged = formData
    .getAll("acknowledge")
    .map(String)
    .filter((id) => verdict.acknowledgeable.some((a) => a.id === id));
  if (!acknowledgementsSatisfied(verdict, acknowledged)) return;

  await db.partRevision.update({
    where: { id: pkg.revision.revisionId },
    data: {
      status: "RELEASED",
      releasedAt: new Date(),
      releasedBy: user.name ?? user.email,
      releaseSnapshotJson: JSON.stringify({
        ...releaseSnapshot(pkg.readiness.gates, acknowledged),
        acknowledgedBy: user.name ?? user.email,
        reservations: verdict.reservations,
        cycleMinutes: pkg.cycleMinutes,
      }),
    },
  });

  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    actorType: "HUMAN",
    entityType: "PartRevision",
    entityId: pkg.revision.revisionId,
    action: "APPROVE",
    field: "status",
    oldValue: "DRAFT",
    newValue: "RELEASED",
    reason: `Released to the floor, acknowledging ${acknowledged.length} blocking gate(s) under review and ${verdict.reservations.length} open reservation(s). No gate was cleared.`,
  });

  revalidatePath(`/parts/${partId}`);
  revalidatePath("/jobs");
}
