"use server";

import { revalidatePath } from "next/cache";
import { requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { loadRevision } from "@/lib/data";
import { validateMethod } from "@/lib/engines/inspection-method";
import type { Instrument } from "@/lib/engines/inspection-capability";

/**
 * ASSIGNING AN INSPECTION METHOD
 *
 * The "Critical tolerance strategy" gate asked for this and nothing could
 * write it. See `engines/inspection-method.ts` for why a human choosing here
 * is a decision rather than a confirm button, and why the choice narrows what
 * the capability gate will then judge.
 *
 * Tenancy: a Feature carries no organizationId, so it is reached through its
 * revision's part. A feature id posted in a form is one another shop could
 * name.
 */

const instrumentsFor = async (organizationId: string): Promise<Instrument[]> =>
  (
    await db.metrologyDevice.findMany({ where: { organizationId } })
  ).map((d) => ({
    id: d.id,
    deviceType: d.deviceType,
    description: d.description,
    resolution: d.resolution,
    uncertainty: d.uncertainty,
    rangeMin: d.rangeMin,
    rangeMax: d.rangeMax,
    calibrated: d.calibrated,
  }));

export async function assignInspectionMethod(partId: string, formData: FormData) {
  const user = await requireWrite();
  const featureId = String(formData.get("featureId") ?? "");
  const deviceType = String(formData.get("deviceType") ?? "").trim();

  const owned = await db.feature.findFirst({
    where: { id: featureId, partRevision: { part: { id: partId, organizationId: user.organizationId } } },
    select: { id: true, label: true, inspectionMethod: true },
  });
  if (!owned) return;

  const revision = await loadRevision(user.organizationId, partId);
  const feature = revision?.features.find((f) => f.id === featureId);
  if (!feature) return;

  /* ---- Clearing is a decision too, and is recorded as one ---- */
  if (deviceType === "") {
    await db.feature.update({
      where: { id: owned.id },
      data: {
        inspectionMethod: null,
        inspectionDeviceType: null,
        inspectionMethodBy: null,
        inspectionMethodAt: null,
      },
    });
    await audit({
      organizationId: user.organizationId,
      userId: user.id,
      entityType: "Feature",
      entityId: owned.id,
      action: "UPDATE",
      actorType: "HUMAN",
      reason: `Inspection method cleared on ${owned.label}. The critical tolerance strategy gate is open again.`,
    });
    revalidatePath(`/parts/${partId}`, "layout");
    return;
  }

  const instruments = await instrumentsFor(user.organizationId);
  const verdict = validateMethod(feature, instruments, deviceType);
  // A refused method leaves the feature exactly as it was. The gate stays
  // open, which is the honest outcome — the alternative is a method stored
  // that the shop cannot carry out.
  if (!verdict.ok) return;

  await db.feature.update({
    where: { id: owned.id },
    data: {
      inspectionMethod: verdict.method,
      inspectionDeviceType: verdict.deviceType,
      inspectionMethodBy: user.name || user.email,
      inspectionMethodAt: new Date(),
    },
  });

  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "Feature",
    entityId: owned.id,
    action: "UPDATE",
    actorType: "HUMAN",
    // The verdict is recorded with the choice. A method assigned while the
    // capability was MARGINAL is a different decision from one assigned while
    // it was CAPABLE, and six months later the difference is the whole story.
    reason: `Inspection method for ${owned.label} set to ${verdict.method}. Capability with that method: ${verdict.verdict}.`,
  });

  revalidatePath(`/parts/${partId}`, "layout");
}
