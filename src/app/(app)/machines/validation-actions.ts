"use server";

import { revalidatePath } from "next/cache";
import { requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { POSTS } from "@/lib/engines/cam/post";

/**
 * RECORDING THAT A POST WAS PROVEN ON A MACHINE.
 *
 * `PostDefinition.certified` is typed as the literal `false` and stays that
 * way. Certification is not a property of the code — it is a property of a post
 * having been run on a specific machine, against a specific control software
 * version, by a named person who watched what happened. That is what this
 * records, and it is what the export gate reads.
 *
 * EVIDENCE IS REQUIRED AND IT IS PROSE
 *
 * "Cut air above the part, single blocked the whole program, first article to
 * print" is what the next person needs to know. A checkbox is a click, and this
 * is the gate that decides whether executable NC leaves the building — the one
 * place in the system where a click would be least defensible.
 *
 * The control version is taken from the MACHINE RECORD rather than typed here,
 * so a validation cannot be recorded against a version the machine does not
 * claim to be running. If somebody updates the control, they update the machine
 * and the proof supersedes itself.
 */

export async function recordPostValidation(machineId: string, formData: FormData): Promise<void> {
  const user = await requireWrite();

  const machine = await db.machine.findFirst({ where: { id: machineId, organizationId: user.organizationId } });
  if (!machine) return;

  const postId = String(formData.get("postId") ?? "");
  if (!POSTS.some((p) => p.id === postId)) return;

  const evidence = String(formData.get("evidence") ?? "").trim().slice(0, 400);
  // No evidence, no validation. This is the gate that releases executable NC.
  if (evidence === "") return;

  const controlVersion = (machine.controlVersion ?? "").trim();
  if (controlVersion === "") return;

  const row = await db.postValidation.create({
    data: {
      organizationId: user.organizationId,
      postId,
      machineId,
      controlVersion,
      validatedByName: user.name,
      evidence,
    },
  });

  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "PostValidation",
    entityId: row.id,
    action: "CREATE",
    actorType: "HUMAN",
    field: "postValidation",
    newValue: `${postId} on ${machine.manufacturer} ${machine.model} at control ${controlVersion}`,
    reason: `Post proven on the machine: ${evidence}`,
  });

  revalidatePath("/machines");
  revalidatePath("/parts", "layout");
}

/**
 * Withdrawing one.
 *
 * Revoked rather than deleted, because the trail is the point: a program
 * exported last month under a validation that was later withdrawn is something
 * a shop needs to be able to find.
 */
export async function revokePostValidation(machineId: string, formData: FormData): Promise<void> {
  const user = await requireWrite();

  const id = String(formData.get("validationId") ?? "");
  const existing = await db.postValidation.findFirst({ where: { id, organizationId: user.organizationId } });
  if (!existing || existing.revokedAt) return;

  const reason = String(formData.get("reason") ?? "").trim().slice(0, 400);
  if (reason === "") return;

  await db.postValidation.update({ where: { id }, data: { revokedAt: new Date(), revokedReason: reason } });

  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "PostValidation",
    entityId: id,
    action: "UPDATE",
    actorType: "HUMAN",
    field: "revokedAt",
    oldValue: "live",
    newValue: "revoked",
    reason: `Post validation withdrawn: ${reason}`,
  });

  revalidatePath("/machines");
  revalidatePath("/parts", "layout");
}
