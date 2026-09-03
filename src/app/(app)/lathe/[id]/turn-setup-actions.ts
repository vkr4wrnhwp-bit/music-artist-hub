"use server";

import { revalidatePath } from "next/cache";
import { requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit, auditChanges } from "@/lib/audit";
import { confirmedBy } from "@/lib/provenance";

/**
 * RECORDING HOW A TURNED PART IS SET UP
 *
 * A rotational part carries the lathe it runs on, the chuck holding it, how
 * much of it is inside the jaws, how far it stands out and the RPM the program
 * clamps to. Nothing in the application could write any of them.
 *
 * The seed sets them, so the demo shaft looked fine. Every part created through
 * the reverse-engineering flow — the one path a shop actually uses to get a
 * turned part into CANVAS — arrived with all five null and no way to fill them
 * in, reporting five blocking gates for ever. `latheMachineId`,
 * `workholdingId`, `gripLength`, `stickout` and `maxRpmClamp` had no writer
 * anywhere in `src/`.
 *
 * The rules, the same ones the mill's setup form follows:
 *
 *   - A blank field is null, not zero. "Not recorded" is a state the turning
 *     analyses handle by naming the missing input; a zero is a measurement
 *     nobody took, and it used to be reported as a computed 0.00× grip ratio.
 *   - Machine and chuck ids are re-resolved against the session's
 *     organisation. A RotationalPart carries its own organizationId, but an id
 *     posted in a form is one another shop could name.
 *   - Every change is audited field by field, because these five decide
 *     whether the holding analysis is worth anything.
 */

/** A positive number, or null for a field left blank. */
const num = (formData: FormData, name: string): number | null => {
  const raw = String(formData.get(name) ?? "").trim();
  if (raw === "") return null;
  const v = Number(raw);
  return Number.isFinite(v) && v > 0 ? v : null;
};

export async function recordTurnSetup(partId: string, formData: FormData) {
  const user = await requireWrite();

  const revision = await db.partRevision.findFirst({
    where: { part: { id: partId, organizationId: user.organizationId } },
    orderBy: { createdAt: "desc" },
    select: { id: true },
  });
  if (!revision) return;
  const rot = await db.rotationalPart.findFirst({
    where: { partRevisionId: revision.id, organizationId: user.organizationId },
  });
  if (!rot) return;

  const latheRaw = String(formData.get("latheMachineId") ?? "");
  const latheMachineId = latheRaw
    ? (await db.latheMachine.findFirst({ where: { id: latheRaw, organizationId: user.organizationId }, select: { id: true } }))?.id ?? null
    : null;
  const holdingRaw = String(formData.get("workholdingId") ?? "");
  const workholdingId = holdingRaw
    ? (await db.latheWorkholding.findFirst({ where: { id: holdingRaw, organizationId: user.organizationId }, select: { id: true } }))?.id ?? null
    : null;

  const gripLength = num(formData, "gripLength");
  const stickout = num(formData, "stickout");
  const maxRpmClamp = num(formData, "maxRpmClamp");

  await db.rotationalPart.update({
    where: { id: rot.id },
    data: {
      latheMachineId,
      workholdingId,
      gripLength,
      stickout,
      maxRpmClamp: maxRpmClamp != null ? Math.round(maxRpmClamp) : null,
    },
  });

  await auditChanges(
    {
      organizationId: user.organizationId,
      userId: user.id,
      entityType: "RotationalPart",
      entityId: rot.id,
      actorType: "HUMAN",
      reason: "Turning setup recorded on the workspace.",
    },
    {
      latheMachineId: rot.latheMachineId,
      workholdingId: rot.workholdingId,
      gripLength: rot.gripLength,
      stickout: rot.stickout,
      maxRpmClamp: rot.maxRpmClamp,
    },
    { latheMachineId, workholdingId, gripLength, stickout, maxRpmClamp },
  );

  revalidatePath(`/lathe/${partId}`);
}

/**
 * The material, which lives on the revision's intent rather than on the
 * rotational part.
 *
 * Recorded as a USER value confirmed by a named human, the same shape the
 * responsibility interview writes — not as an inferred one. A machinist typing
 * what is on the rack is stating a fact about their own stock, and the
 * turning speeds and the cost both read it.
 */
export async function recordTurnMaterial(partId: string, formData: FormData) {
  const user = await requireWrite();
  const material = String(formData.get("material") ?? "").trim();

  const revision = await db.partRevision.findFirst({
    where: { part: { id: partId, organizationId: user.organizationId } },
    orderBy: { createdAt: "desc" },
    select: { id: true, intentJson: true },
  });
  if (!revision) return;

  let intent: Record<string, unknown>;
  try {
    intent = JSON.parse(revision.intentJson) as Record<string, unknown>;
  } catch {
    // An unparseable intent is not overwritten with a fresh object — that
    // would discard whatever else the record holds to record one field.
    return;
  }

  const before = (intent.material as { value?: unknown } | undefined)?.value ?? null;
  if (material === "") {
    delete intent.material;
  } else {
    intent.material = confirmedBy(material, user.name || user.email, new Date(), "Recorded on the turning workspace");
  }

  await db.partRevision.update({ where: { id: revision.id }, data: { intentJson: JSON.stringify(intent) } });

  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "PartRevision",
    entityId: revision.id,
    action: "UPDATE",
    actorType: "HUMAN",
    field: "material",
    oldValue: before == null ? null : String(before),
    newValue: material === "" ? null : material,
    reason: "Material recorded on the turning workspace.",
  });

  revalidatePath(`/lathe/${partId}`);
}
