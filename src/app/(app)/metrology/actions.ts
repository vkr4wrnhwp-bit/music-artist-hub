"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { requireUser, requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit, auditChanges } from "@/lib/audit";
import { METROLOGY_DEVICES } from "@/lib/domain/shop";
import { FormReader, rejectionQuery } from "@/lib/shop-form";

/**
 * Instrument writes.
 *
 * Organisation id from the session on every path; the instrument id is
 * re-checked against it before an update or a delete touches anything.
 */

function parse(formData: FormData) {
  const f = new FormReader(formData);
  const rangeMin = f.optionalNumber("rangeMin", "Range min", { min: 0 });
  const rangeMax = f.optionalNumber("rangeMax", "Range max", { min: 0 });

  let calibrationDue: Date | null = null;
  const due = f.optionalText("calibrationDue");
  if (due) {
    const d = new Date(due);
    if (Number.isNaN(d.getTime())) f.text("__calibrationDueInvalid", "Calibration due date is not a date");
    else calibrationDue = d;
  }

  const data = {
    deviceType: f.choice("deviceType", "Instrument", METROLOGY_DEVICES),
    description: f.text("description", "Description"),
    rangeMin,
    rangeMax,
    resolution: f.number("resolution", "Resolution", { min: 0 }),
    uncertainty: f.number("uncertainty", "Uncertainty", { min: 0 }),
    calibrated: f.boolean("calibrated"),
    calibrationDue,
  };

  f.requireOrder(rangeMin, rangeMax, "Range");
  // An instrument cannot be more certain than its own smallest division.
  // Recorded the other way round, the capability verdict is computed from a
  // figure the instrument cannot deliver.
  if (data.uncertainty > 0 && data.resolution > 0 && data.uncertainty < data.resolution / 2) {
    f.text(
      "__uncertaintyBelowResolution",
      `Uncertainty ±${data.uncertainty} is below half the ${data.resolution} resolution, which no instrument achieves`,
    );
  }
  f.done();
  return data;
}

const summary = (d: ReturnType<typeof parse>) =>
  `${d.description} · ±${d.uncertainty} · ${d.calibrated ? "calibrated" : "not calibrated"}`;

export async function createInstrument(formData: FormData): Promise<void> {
  const user = await requireWrite();
  let data;
  try {
    data = parse(formData);
  } catch (err) {
    redirect(`/metrology/new${rejectionQuery(err)}`);
  }

  const row = await db.metrologyDevice.create({ data: { ...data, organizationId: user.organizationId } });
  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "MetrologyDevice",
    entityId: row.id,
    action: "CREATE",
    actorType: "HUMAN",
    field: "instrument",
    newValue: summary(data),
    reason: "Instrument added to the shop's metrology list.",
  });
  revalidatePath("/metrology");
  redirect("/metrology");
}

export async function updateInstrument(formData: FormData): Promise<void> {
  const user = await requireWrite();
  const id = String(formData.get("id") ?? "");
  const existing = await db.metrologyDevice.findFirst({ where: { id, organizationId: user.organizationId } });
  if (!existing) redirect("/metrology");

  let data;
  try {
    data = parse(formData);
  } catch (err) {
    redirect(`/metrology/${id}/edit${rejectionQuery(err)}`);
  }

  await db.metrologyDevice.update({ where: { id }, data });

  const keys = Object.keys(data) as (keyof typeof data)[];
  await auditChanges(
    {
      organizationId: user.organizationId,
      userId: user.id,
      entityType: "MetrologyDevice",
      entityId: id,
      actorType: "HUMAN",
      reason: "Instrument record edited.",
    },
    Object.fromEntries(keys.map((k) => [k, (existing as Record<string, unknown>)[k]])),
    Object.fromEntries(keys.map((k) => [k, data[k]])),
  );

  revalidatePath("/metrology");
  redirect("/metrology");
}

export async function deleteInstrument(formData: FormData): Promise<void> {
  const user = await requireWrite();
  const id = String(formData.get("id") ?? "");
  const existing = await db.metrologyDevice.findFirst({ where: { id, organizationId: user.organizationId } });
  if (!existing) redirect("/metrology");

  /*
   * An instrument that measurements cite is the provenance of those readings.
   * The relation is onDelete: SetNull, so deleting would leave the readings
   * in place with nothing recorded about what took them — a measured value
   * whose instrument is gone is no longer evidence, and principle 4 makes
   * provenance first-class data rather than a decoration on it. Refuse.
   */
  const used = await db.measurement.count({ where: { deviceId: id } });
  if (used > 0) {
    redirect(
      `/metrology/${id}/edit?problem=${encodeURIComponent(
        `${used} recorded measurement${used === 1 ? "" : "s"} cite this instrument. Deleting it would strip the provenance from ${
          used === 1 ? "that reading" : "those readings"
        }, so it cannot be removed.`,
      )}`,
    );
  }

  await db.metrologyDevice.delete({ where: { id } });
  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "MetrologyDevice",
    entityId: id,
    action: "DELETE",
    actorType: "HUMAN",
    field: "instrument",
    oldValue: existing.description,
    reason: "Instrument removed from the shop's metrology list.",
  });
  revalidatePath("/metrology");
  redirect("/metrology");
}
