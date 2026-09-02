"use server";

import { revalidatePath } from "next/cache";
import { requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { JAW_SURFACES } from "@/lib/engines/holding-margin";

/**
 * RECORDING WHAT WAS ACTUALLY SET
 *
 * Grip depth, projection, machine and workholding could only be written by the
 * approach generator on the Machinist page. A machinist who planned 0.250" of
 * grip and actually set 0.400" had no way to say so — and the holding margin,
 * the jaw-clearance check, the fixture model in the simulator and the release
 * snapshot are all computed from numbers they could not correct.
 *
 * The rules:
 *
 *   - Saving this form marks the geometry MEASURED and records who and when.
 *     The plan generator marks it PLANNED. The arithmetic downstream is
 *     identical; what it is entitled to claim is not, and the pages say which
 *     they are looking at.
 *   - A blank field is null, not zero and not the planned value. "Not
 *     recorded" is a state the workholding engine already handles by naming
 *     the missing input; a zero would be a measurement nobody took.
 *   - Machine and workholding are re-resolved against the session's
 *     organisation. Setup carries no organizationId of its own, so it is
 *     reached through its revision's part, and an id posted in a form is one
 *     another shop could name.
 */

const num = (formData: FormData, name: string): number | null => {
  const raw = String(formData.get(name) ?? "").trim();
  if (raw === "") return null;
  const v = Number(raw);
  return Number.isFinite(v) && v >= 0 ? v : null;
};

export async function recordSetupGeometry(partId: string, formData: FormData) {
  const user = await requireWrite();

  const setupId = String(formData.get("setupId") ?? "");
  const owned = await db.setup.findFirst({
    where: { id: setupId, partRevision: { part: { id: partId, organizationId: user.organizationId } } },
    select: { id: true, gripDepth: true, stockProjection: true },
  });
  if (!owned) return;

  // Both are optional, and both are verified to belong to this shop before
  // they are stored. An unknown id clears the field rather than being kept.
  const machineIdRaw = String(formData.get("machineId") ?? "");
  const machineId = machineIdRaw
    ? (await db.machine.findFirst({ where: { id: machineIdRaw, organizationId: user.organizationId }, select: { id: true } }))?.id ?? null
    : null;
  const workholdingIdRaw = String(formData.get("workholdingId") ?? "");
  const workholdingId = workholdingIdRaw
    ? (await db.workholdingDevice.findFirst({ where: { id: workholdingIdRaw, organizationId: user.organizationId }, select: { id: true } }))?.id ?? null
    : null;

  const jawAxisRaw = String(formData.get("jawAxis") ?? "");
  const jawSurfaceRaw = String(formData.get("jawSurface") ?? "");

  const gripDepth = num(formData, "gripDepth");
  const stockProjection = num(formData, "stockProjection");

  await db.setup.update({
    where: { id: owned.id },
    data: {
      machineId,
      workholdingId,
      gripDepth,
      gripLength: num(formData, "gripLength"),
      stockProjection,
      parallelHeight: num(formData, "parallelHeight"),
      // Only values in the vocabulary are stored. An unrecognised one is
      // cleared rather than filed, because a stored value is one the
      // workholding engine will trust.
      jawAxis: jawAxisRaw === "X" || jawAxisRaw === "Y" ? jawAxisRaw : null,
      jawSurface: (JAW_SURFACES as readonly string[]).includes(jawSurfaceRaw) ? jawSurfaceRaw : null,
      workOffset: String(formData.get("workOffset") ?? "").trim().slice(0, 10) || "G54",
      datumNote: String(formData.get("datumNote") ?? "").trim().slice(0, 500) || null,
      geometrySource: "MEASURED",
      geometryRecordedBy: user.name ?? user.email,
      geometryRecordedAt: new Date(),
    },
  });

  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    actorType: "HUMAN",
    entityType: "Setup",
    entityId: owned.id,
    action: "UPDATE",
    field: "geometry",
    oldValue: `grip ${owned.gripDepth ?? "—"}, projection ${owned.stockProjection ?? "—"} (planned)`,
    newValue: `grip ${gripDepth ?? "—"}, projection ${stockProjection ?? "—"} (measured)`,
    reason: "Recorded the setup as actually built.",
  });

  revalidatePath(`/parts/${partId}/setups`);
  revalidatePath(`/parts/${partId}`);
  revalidatePath(`/parts/${partId}/readiness`);
}
