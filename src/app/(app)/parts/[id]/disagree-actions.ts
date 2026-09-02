"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { loadRevision } from "@/lib/data";
import { recordDisagreement } from "@/lib/disagreement";
import { DISAGREEMENT_SUBJECTS, type DisagreementSubject } from "@/lib/disagreement-scope";

/**
 * ONE ACTION FOR EVERY DISAGREEMENT.
 *
 * Principle 11 says every significant recommendation supports WHY / CHANGE /
 * I DISAGREE. It was mounted in exactly one place — non-passing readiness
 * gates — so six of the eight subjects the vocabulary defines were
 * unreachable: a machinist could not disagree with a process recommendation,
 * a workholding assessment, a suggested nominal, a tool choice, a cost
 * verdict or a feed and speed.
 *
 * One action rather than one per page, because the rules that matter here are
 * the ones that must not vary by surface:
 *
 *   - It records evidence and clears nothing. `recordDisagreement` hardcodes
 *     `gateCleared: false`; nothing here writes anything else. A test asserts
 *     this file contains no other write at all.
 *   - Organisation comes from the session. The part, the setup and the job
 *     are re-resolved against it, and the revision id is derived server-side
 *     rather than read off the form — a form that can name a revision can
 *     name another shop's.
 *   - The subject is validated against the vocabulary. An unrecognised
 *     subject is refused rather than filed under OTHER: a mislabelled
 *     disagreement is worse than a rejected one, because the subject is what
 *     scopes the knowledge afterwards.
 */

/** Where the machinist was when they disagreed, and where to put them back. */
const RETURN_PATH: Record<string, (partId: string) => string> = {
  readiness: (p) => `/parts/${p}/readiness`,
  setups: (p) => `/parts/${p}/setups`,
  tooling: (p) => `/parts/${p}/tooling`,
  cost: (p) => `/parts/${p}/cost`,
  part: (p) => `/parts/${p}`,
};

export async function recordPartDisagreement(formData: FormData): Promise<void> {
  const user = await requireWrite();

  const partId = String(formData.get("partId") ?? "");
  const surface = String(formData.get("surface") ?? "part");
  const back = (RETURN_PATH[surface] ?? RETURN_PATH.part)(partId);

  const reasoning = String(formData.get("reasoning") ?? "").trim();
  if (!reasoning) redirect(back);

  const subjectRaw = String(formData.get("subjectType") ?? "");
  const subjectType = DISAGREEMENT_SUBJECTS.find((s) => s === subjectRaw) as DisagreementSubject | undefined;
  if (!subjectType) redirect(`${back}?problem=subject`);

  // The revision comes from the part, scoped to this organisation. Never from
  // the form.
  const revision = await loadRevision(user.organizationId, partId);
  if (!revision) redirect("/parts");

  const setupIdRaw = String(formData.get("setupId") ?? "");
  const setup = setupIdRaw
    ? await db.setup.findFirst({
        where: { id: setupIdRaw, partRevision: { part: { organizationId: user.organizationId } } },
        select: { id: true },
      })
    : null;

  const jobIdRaw = String(formData.get("comparableJobId") ?? "");
  const job = jobIdRaw
    ? await db.job.findFirst({ where: { id: jobIdRaw, organizationId: user.organizationId }, select: { id: true } })
    : null;

  await recordDisagreement({
    organizationId: user.organizationId,
    userId: user.id,
    subjectType,
    subjectId: String(formData.get("subjectId") ?? "") || null,
    partRevisionId: revision.revisionId,
    setupId: setup?.id ?? null,
    canvasPosition: String(formData.get("canvasPosition") ?? ""),
    reasoning,
    hasRunComparable: formData.get("hasRunComparable") === "yes",
    comparableJobId: job?.id ?? null,
    proposedValue: String(formData.get("proposedValue") ?? "") || null,
  });

  // revalidate before redirect — redirect throws to unwind.
  revalidatePath(back);
  redirect(`${back}?recorded=1`);
}
