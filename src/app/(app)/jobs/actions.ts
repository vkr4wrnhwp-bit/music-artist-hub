"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { canTransition, validateOutcome, type OutcomeDraft } from "@/lib/engines/jobs";
import { audit } from "@/lib/audit";

/**
 * THE JOBS WRITE PATH
 *
 * Nothing in the application could create a Job or a JobOutcome. The page
 * described job outcomes as the most valuable data a shop generates and then
 * showed rows only the seed had written.
 *
 * Rules that hold across all four actions:
 *
 *   - Organisation comes from the session. Every row is re-resolved against
 *     it before it is touched; a job id in a form is one another shop's
 *     session could name.
 *   - Status changes go through the transition table. A job cannot jump from
 *     PLANNED to COMPLETE: the actuals recorded against it would be
 *     describing a setup and a run that never happened.
 *   - Nothing is invented. An actual that was not entered is stored null and
 *     the job reports it as not recorded, rather than inheriting the estimate.
 */

/* ---------------- Raise a job against a released revision ---------------- */

export async function createJob(formData: FormData) {
  const user = await requireWrite();

  const partId = String(formData.get("partId") ?? "");
  const jobNumber = String(formData.get("jobNumber") ?? "").trim().slice(0, 60);
  const quantity = Number(formData.get("quantity") ?? 0);
  const dueRaw = String(formData.get("dueDate") ?? "").trim();

  if (jobNumber === "" || !Number.isInteger(quantity) || quantity < 1) return;

  /*
   * A job is raised against a RELEASED revision, which is what the page has
   * always said. The revision is found here rather than posted: the released
   * one for this part in this organisation, or nothing.
   */
  const revision = await db.partRevision.findFirst({
    where: { partId, status: "RELEASED", part: { organizationId: user.organizationId } },
    orderBy: { releasedAt: "desc" },
    select: { id: true, revision: true },
  });
  if (!revision) return;

  const due = dueRaw === "" ? null : new Date(dueRaw);
  const job = await db.job.create({
    data: {
      organizationId: user.organizationId,
      partId,
      revision: revision.revision,
      jobNumber,
      quantity,
      dueDate: due && !Number.isNaN(due.getTime()) ? due : null,
      status: "PLANNED",
    },
  });

  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    actorType: "HUMAN",
    entityType: "Job",
    entityId: job.id,
    action: "CREATE",
    reason: `Job ${jobNumber} raised against revision ${revision.revision}, quantity ${quantity}.`,
  });

  revalidatePath("/jobs");
  redirect(`/jobs/${job.id}`);
}

/* ---------------- Move it along ---------------- */

export async function advanceJob(jobId: string, formData: FormData) {
  const user = await requireWrite();
  const to = String(formData.get("to") ?? "");

  const job = await db.job.findFirst({ where: { id: jobId, organizationId: user.organizationId } });
  if (!job) return;
  if (!canTransition(job.status, to)) return;

  await db.job.update({
    where: { id: job.id },
    data: {
      status: to,
      // Stamped when the job actually starts running and when it finishes, so
      // elapsed time is a fact rather than something re-derived later.
      startedAt: to === "RUNNING" && job.startedAt === null ? new Date() : job.startedAt,
      completedAt: to === "COMPLETE" ? new Date() : job.completedAt,
    },
  });

  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    actorType: "HUMAN",
    entityType: "Job",
    entityId: job.id,
    action: "UPDATE",
    field: "status",
    oldValue: job.status,
    newValue: to,
  });

  revalidatePath(`/jobs/${jobId}`);
  revalidatePath("/jobs");
}

/* ---------------- What it actually did ---------------- */

export async function recordActuals(jobId: string, formData: FormData) {
  const user = await requireWrite();
  const job = await db.job.findFirst({ where: { id: jobId, organizationId: user.organizationId } });
  if (!job) return;

  /*
   * A blank field stays null. It does NOT fall back to the estimate: the
   * whole purpose of this row is to compare what was estimated against what
   * happened, and an actual quietly seeded from the estimate makes that
   * comparison agree with itself.
   */
  const num = (name: string): number | null => {
    const raw = String(formData.get(name) ?? "").trim();
    if (raw === "") return null;
    const v = Number(raw);
    return Number.isFinite(v) && v >= 0 ? v : null;
  };
  const scrapRaw = String(formData.get("scrapCount") ?? "").trim();
  const scrap = scrapRaw === "" ? null : Number(scrapRaw);

  await db.job.update({
    where: { id: job.id },
    data: {
      actualCycleMinutes: num("actualCycleMinutes"),
      actualSetupHours: num("actualSetupHours"),
      scrapCount: Number.isInteger(scrap) && scrap! >= 0 ? scrap! : job.scrapCount,
      notes: String(formData.get("notes") ?? "").trim().slice(0, 2000) || job.notes,
    },
  });

  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    actorType: "HUMAN",
    entityType: "Job",
    entityId: job.id,
    action: "UPDATE",
    field: "actuals",
    reason: "Recorded what the job actually did.",
  });

  revalidatePath(`/jobs/${jobId}`);
  revalidatePath("/jobs");
}

/* ---------------- What happened, structurally ---------------- */

export async function recordOutcome(jobId: string, formData: FormData) {
  const user = await requireWrite();
  const job = await db.job.findFirst({
    where: { id: jobId, organizationId: user.organizationId },
    include: { part: { include: { revisions: { include: { setups: true } } } } },
  });
  if (!job) return;

  const draft: OutcomeDraft = {
    code: String(formData.get("code") ?? ""),
    cause: String(formData.get("cause") ?? ""),
    correctiveAction: String(formData.get("correctiveAction") ?? "").trim().slice(0, 2000),
    partsAffected: Number(formData.get("partsAffected") ?? 0),
    operationId: String(formData.get("operationId") ?? "") || null,
    toolNumber: String(formData.get("toolNumber") ?? "") === "" ? null : Number(formData.get("toolNumber")),
    notes: String(formData.get("notes") ?? "").trim().slice(0, 2000),
  };

  // A mislabelled outcome is worse than a rejected one: it will be counted as
  // something it is not, by everything downstream that counts outcomes.
  if (validateOutcome(draft).length > 0) return;

  /*
   * The scope, captured now. Read back through the setup later it would
   * silently start describing whatever machine the setup names by then.
   * Whatever is not recorded stays null, and a null matches nothing.
   */
  const revision = job.part.revisions.find((r) => r.revision === job.revision);
  const setup = revision?.setups[0] ?? null;
  const materialName = revision ? (JSON.parse(revision.intentJson).material?.value ?? null) : null;

  await db.jobOutcome.create({
    data: {
      jobId: job.id,
      code: draft.code,
      operationId: draft.operationId,
      toolNumber: Number.isInteger(draft.toolNumber) ? draft.toolNumber : null,
      cause: draft.cause,
      correctiveAction: draft.correctiveAction,
      partsAffected: Number.isInteger(draft.partsAffected) ? draft.partsAffected : 0,
      notes: draft.notes,
      recordedBy: user.name ?? user.email,
      machineId: setup?.machineId ?? null,
      workholdingId: setup?.workholdingId ?? null,
      materialName: typeof materialName === "string" ? materialName : null,
    },
  });

  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    actorType: "HUMAN",
    entityType: "Job",
    entityId: job.id,
    action: "CREATE",
    field: "outcome",
    newValue: draft.code,
    reason: draft.cause,
  });

  revalidatePath(`/jobs/${jobId}`);
  revalidatePath("/jobs");
  revalidatePath(`/parts/${job.partId}/setups`);
}
