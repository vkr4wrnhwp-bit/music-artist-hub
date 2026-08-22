"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { requireUser, requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit, auditChanges } from "@/lib/audit";
import { FormReader, rejectionQuery } from "@/lib/shop-form";
import { FAMILIES, title } from "./material-fields";

function parse(formData: FormData) {
  const f = new FormReader(formData);
  const sfmMin = f.number("sfmCarbideMin", "Carbide surface speed min", { min: 0 });
  const sfmMax = f.number("sfmCarbideMax", "Carbide surface speed max", { min: 0 });
  const yieldStrength = f.optionalNumber("yieldStrength", "Yield strength", { min: 0 });
  const tensileStrength = f.optionalNumber("tensileStrength", "Tensile strength", { min: 0 });

  const data = {
    name: f.text("name", "Name"),
    family: f.choice("family", "Family", FAMILIES),
    condition: f.text("condition", "Condition"),
    density: f.number("density", "Density", { min: 0 }),
    hardness: f.optionalNumber("hardness", "Hardness", { min: 0 }),
    yieldStrength,
    tensileStrength,
    machinabilityRating: f.number("machinabilityRating", "Machinability rating", { min: 0 }),
    sfmCarbideMin: sfmMin,
    sfmCarbideMax: sfmMax,
    specificEnergy: f.number("specificEnergy", "Specific cutting energy", { min: 0 }),
    costPerPound: f.number("costPerPound", "Cost per pound", { min: 0 }),
    weldable: f.boolean("weldable"),
    castable: f.boolean("castable"),
    notes: f.optionalText("notes"),
  };

  f.requireOrder(sfmMin, sfmMax, "Carbide surface speed");
  // Yield above tensile is not a material, it is a typo. Both are optional,
  // so this only fires when a shop recorded both.
  f.requireOrder(yieldStrength, tensileStrength, "Yield strength against tensile strength");
  f.done();
  return data;
}

const summary = (d: ReturnType<typeof parse>) =>
  `${d.name} (${title(d.family)}, ${d.condition}) · ${d.specificEnergy} hp/in³/min`;

export async function createMaterial(formData: FormData): Promise<void> {
  const user = await requireWrite();
  let data;
  try {
    data = parse(formData);
  } catch (err) {
    redirect(`/materials/new${rejectionQuery(err)}`);
  }
  const row = await db.material.create({ data: { ...data, organizationId: user.organizationId } });
  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "Material",
    entityId: row.id,
    action: "CREATE",
    actorType: "HUMAN",
    field: "material",
    newValue: summary(data),
    reason: "Material added to the shop's list.",
  });
  revalidatePath("/materials");
  redirect("/materials");
}

export async function updateMaterial(formData: FormData): Promise<void> {
  const user = await requireWrite();
  const id = String(formData.get("id") ?? "");
  const existing = await db.material.findFirst({ where: { id, organizationId: user.organizationId } });
  if (!existing) redirect("/materials");

  let data;
  try {
    data = parse(formData);
  } catch (err) {
    redirect(`/materials/${id}/edit${rejectionQuery(err)}`);
  }

  await db.material.update({ where: { id }, data });

  const keys = Object.keys(data) as (keyof typeof data)[];
  await auditChanges(
    {
      organizationId: user.organizationId,
      userId: user.id,
      entityType: "Material",
      entityId: id,
      actorType: "HUMAN",
      reason: "Material record edited.",
    },
    Object.fromEntries(keys.map((k) => [k, (existing as Record<string, unknown>)[k]])),
    Object.fromEntries(keys.map((k) => [k, data[k]])),
  );

  revalidatePath("/materials");
  redirect("/materials");
}

export async function deleteMaterial(formData: FormData): Promise<void> {
  const user = await requireWrite();
  const id = String(formData.get("id") ?? "");
  const existing = await db.material.findFirst({ where: { id, organizationId: user.organizationId } });
  if (!existing) redirect("/materials");

  /*
   * Shop knowledge is scoped to the material it was observed on. The relation
   * is onDelete: SetNull, so deleting would leave observations whose subject
   * is gone — a shop note saying "this runs hot at 900 sfm" with nothing to
   * say what "this" was. That is not knowledge any more.
   */
  const observations = await db.shopKnowledge.count({ where: { materialId: id } });
  if (observations > 0) {
    redirect(
      `/materials/${id}/edit?problem=${encodeURIComponent(
        `${observations} shop knowledge entr${observations === 1 ? "y was" : "ies were"} recorded against this material. Removing it would leave ${
          observations === 1 ? "that observation" : "those observations"
        } with no subject.`,
      )}`,
    );
  }

  await db.material.delete({ where: { id } });
  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "Material",
    entityId: id,
    action: "DELETE",
    actorType: "HUMAN",
    field: "material",
    oldValue: `${existing.name} (${existing.condition})`,
    reason: "Material removed from the shop's list.",
  });
  revalidatePath("/materials");
  redirect("/materials");
}
