"use server";

import { revalidatePath } from "next/cache";
import { requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { loadRevision } from "@/lib/data";
import { RESOLUTION_STATUSES, type ResolutionStatus } from "@/lib/review-findings";

/**
 * RECORDING A RESPONSE TO A REVIEW FINDING
 *
 * The rules that must not vary:
 *
 *   - It clears nothing. This file writes one row, to FindingResolution, and
 *     never touches a gate, a severity or a readiness record. A test asserts
 *     the file contains no other write.
 *   - Organisation comes from the session, and the revision is re-resolved
 *     against it. The form names a finding key, never a revision id — a form
 *     that can name a revision can name another shop's.
 *   - The response is bound to the evidence digest the finding carries right
 *     now, read server-side from the stored snapshot rather than posted. A
 *     digest that arrives in a form is a digest a caller can choose, and
 *     choosing it is choosing which engineering condition you are agreeing
 *     to have already answered.
 *   - The actor is typed HUMAN explicitly. This action is only reachable from
 *     a form submission by a signed-in user; nothing infers it.
 */

export async function recordFindingResolution(partId: string, formData: FormData) {
  const user = await requireWrite();
  const revision = await loadRevision(user.organizationId, partId);
  if (!revision) return;

  const findingKey = String(formData.get("findingKey") ?? "");
  const status = String(formData.get("status") ?? "");
  const note = String(formData.get("note") ?? "").trim().slice(0, 2000);
  if (!RESOLUTION_STATUSES.includes(status as ResolutionStatus)) return;

  // A disagreement with no reasoning is not shop knowledge, it is a dismissal.
  if (status === "DISPUTED" && note.length < 10) return;

  const finding = await db.reviewFinding.findFirst({
    where: { partRevisionId: revision.revisionId, findingKey, organizationId: user.organizationId },
  });
  if (!finding) return;

  await db.findingResolution.create({
    data: {
      findingId: finding.id,
      status,
      note,
      actorType: "HUMAN",
      actorId: user.id,
      actorName: user.name ?? user.email,
      evidenceDigest: finding.evidenceDigest,
    },
  });

  revalidatePath(`/parts/${partId}/review`);
}
