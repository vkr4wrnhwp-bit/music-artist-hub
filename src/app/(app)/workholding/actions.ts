"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit, auditChanges } from "@/lib/audit";
import { WORKHOLDING_TYPES } from "@/lib/domain/shop";
import { FormReader, rejectionQuery } from "@/lib/shop-form";
import { title } from "./device-fields";

function parse(formData: FormData) {
  const f = new FormReader(formData);
  const jawHeight = f.number("jawHeight", "Jaw height", { min: 0 });
  const fixtureHeight = f.number("fixtureHeight", "Fixture height", { min: 0 });

  const data = {
    type: f.choice("type", "Type", WORKHOLDING_TYPES),
    manufacturer: f.optionalText("manufacturer"),
    model: f.optionalText("model"),
    description: f.text("description", "Description"),
    jawWidth: f.number("jawWidth", "Jaw width", { min: 0 }),
    jawHeight,
    maxOpening: f.number("maxOpening", "Maximum opening", { min: 0 }),
    clampForce: f.optionalNumber("clampForce", "Clamp force", { min: 0 }),
    fixtureHeight,
    mountingGeometry: f.optionalText("mountingGeometry"),
    notes: f.optionalText("notes"),
  };

  // The jaws sit on top of the base, so the whole fixture cannot be shorter
  // than its own jaw face. Recorded the wrong way round, the Z envelope check
  // is computed against a stack that cannot exist.
  f.requireOrder(jawHeight, fixtureHeight, "Jaw height against fixture height");
  f.done();
  return data;
}

const summary = (d: ReturnType<typeof parse>) =>
  `${title(d.type)} · ${d.description} · jaw ${d.jawWidth}×${d.jawHeight}`;

export async function createDevice(formData: FormData): Promise<void> {
  const user = await requireUser();
  let data;
  try {
    data = parse(formData);
  } catch (err) {
    redirect(`/workholding/new${rejectionQuery(err)}`);
  }
  const row = await db.workholdingDevice.create({ data: { ...data, organizationId: user.organizationId } });
  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "WorkholdingDevice",
    entityId: row.id,
    action: "CREATE",
    actorType: "HUMAN",
    field: "workholding device",
    newValue: summary(data),
    reason: "Workholding device added to the shop.",
  });
  revalidatePath("/workholding");
  redirect("/workholding");
}

export async function updateDevice(formData: FormData): Promise<void> {
  const user = await requireUser();
  const id = String(formData.get("id") ?? "");
  const existing = await db.workholdingDevice.findFirst({ where: { id, organizationId: user.organizationId } });
  if (!existing) redirect("/workholding");

  let data;
  try {
    data = parse(formData);
  } catch (err) {
    redirect(`/workholding/${id}/edit${rejectionQuery(err)}`);
  }

  await db.workholdingDevice.update({ where: { id }, data });

  const keys = Object.keys(data) as (keyof typeof data)[];
  await auditChanges(
    {
      organizationId: user.organizationId,
      userId: user.id,
      entityType: "WorkholdingDevice",
      entityId: id,
      actorType: "HUMAN",
      reason: "Workholding device edited.",
    },
    Object.fromEntries(keys.map((k) => [k, (existing as Record<string, unknown>)[k]])),
    Object.fromEntries(keys.map((k) => [k, data[k]])),
  );

  revalidatePath("/workholding");
  redirect("/workholding");
}

export async function deleteDevice(formData: FormData): Promise<void> {
  const user = await requireUser();
  const id = String(formData.get("id") ?? "");
  const existing = await db.workholdingDevice.findFirst({ where: { id, organizationId: user.organizationId } });
  if (!existing) redirect("/workholding");

  /*
   * Setups and generated soft jaws both point at the device with
   * onDelete: SetNull. Deleting would leave a setup with no workholding and
   * a jaw set with nothing to bolt to, while both would still read as
   * planned. Refuse and name what is holding it.
   */
  const [setups, jaws] = await Promise.all([
    db.setup.count({ where: { workholdingId: id } }),
    db.jaw.count({ where: { deviceId: id } }),
  ]);
  if (setups > 0 || jaws > 0) {
    const parts = [
      setups > 0 ? `${setups} setup${setups === 1 ? "" : "s"}` : null,
      jaws > 0 ? `${jaws} generated soft jaw${jaws === 1 ? "" : "s"}` : null,
    ].filter(Boolean);
    redirect(
      `/workholding/${id}/edit?problem=${encodeURIComponent(
        `${parts.join(" and ")} reference this device. Removing it would leave them planned against nothing.`,
      )}`,
    );
  }

  await db.workholdingDevice.delete({ where: { id } });
  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "WorkholdingDevice",
    entityId: id,
    action: "DELETE",
    actorType: "HUMAN",
    field: "workholding device",
    oldValue: existing.description,
    reason: "Workholding device removed from the shop.",
  });
  revalidatePath("/workholding");
  redirect("/workholding");
}
