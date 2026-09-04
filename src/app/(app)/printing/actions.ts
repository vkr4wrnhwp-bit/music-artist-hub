"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit, auditChanges } from "@/lib/audit";
import { PRINT_TECHNOLOGIES, anisotropyIsPossible } from "@/lib/engines/additive";
import { FormReader, rejectionQuery } from "@/lib/shop-form";

/**
 * Printer and print-material writes.
 *
 * Organisation id from the session on every path; the row id is re-checked
 * against it before an update or a delete touches anything.
 *
 * The optional numbers here are optional on purpose. A printer whose
 * achievable tolerance nobody has measured, and a material whose through-layer
 * strength nobody has pulled a coupon for, are both ordinary states in a real
 * shop — and the additive advisor is built to report those gaps rather than
 * fill them in. Requiring the fields would push somebody into typing a
 * datasheet number, which is exactly the input that makes the advisor wrong.
 */

function parsePrinter(formData: FormData) {
  const f = new FormReader(formData);
  const data = {
    manufacturer: f.text("manufacturer", "Manufacturer"),
    model: f.text("model", "Model"),
    technology: f.choice("technology", "Technology", PRINT_TECHNOLOGIES),
    buildX: f.number("buildX", "Build X", { min: 0 }),
    buildY: f.number("buildY", "Build Y", { min: 0 }),
    buildZ: f.number("buildZ", "Build Z", { min: 0 }),
    achievableTolerance: f.optionalNumber("achievableTolerance", "Achievable tolerance", { min: 0 }),
    achievableRa: f.optionalNumber("achievableRa", "Surface finish", { min: 0 }),
    minLayerHeight: f.optionalNumber("minLayerHeight", "Minimum layer height", { min: 0 }),
    nozzleDiameter: f.optionalNumber("nozzleDiameter", "Nozzle diameter", { min: 0 }),
    notes: f.optionalText("notes"),
  };
  f.done();
  return data;
}

function parseMaterial(formData: FormData) {
  const f = new FormReader(formData);
  const tensileXY = f.optionalNumber("tensileXY", "Tensile strength in plane", { min: 0 });
  const tensileZ = f.optionalNumber("tensileZ", "Tensile strength through Z", { min: 0 });

  /*
   * A material stronger through the layers than within them is not a material,
   * it is a typo — and a bad one, because the anisotropy check would then
   * report the part is fine in the direction it is actually weakest.
   */
  if (!anisotropyIsPossible(tensileXY, tensileZ)) {
    f.problem(
      `Through-layer strength ${tensileZ} psi is above the in-plane ${tensileXY} psi. A printed part is bonded between layers and cannot be stronger across them.`,
    );
  }

  const data = {
    name: f.text("name", "Name"),
    technology: f.choice("technology", "Technology", PRINT_TECHNOLOGIES),
    tensileXY,
    tensileZ,
    maxServiceTempF: f.optionalNumber("maxServiceTempF", "Maximum service temperature"),
    creepDataOnFile: f.boolean("creepDataOnFile"),
    densityLbIn3: f.optionalNumber("densityLbIn3", "Density", { min: 0 }),
    costPerPound: f.optionalNumber("costPerPound", "Cost", { min: 0 }),
    notes: f.optionalText("notes"),
  };
  f.done();
  return data;
}

/* ---------------- Printers ---------------- */

export async function createPrinter(formData: FormData): Promise<void> {
  const user = await requireWrite();
  let data;
  try {
    data = parsePrinter(formData);
  } catch (err) {
    redirect(`/printing/new${rejectionQuery(err)}`);
  }

  const row = await db.printer.create({ data: { ...data, organizationId: user.organizationId } });
  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "Printer",
    entityId: row.id,
    action: "CREATE",
    actorType: "HUMAN",
    field: "printer",
    newValue: `${data.manufacturer} ${data.model} · ${data.technology} · ${
      data.achievableTolerance != null ? `±${data.achievableTolerance}` : "tolerance not measured"
    }`,
    reason: "Printer added to the shop's additive inventory.",
  });
  revalidatePath("/printing");
  redirect("/printing");
}

export async function updatePrinter(formData: FormData): Promise<void> {
  const user = await requireWrite();
  const id = String(formData.get("id") ?? "");
  const existing = await db.printer.findFirst({ where: { id, organizationId: user.organizationId } });
  if (!existing) redirect("/printing");

  let data;
  try {
    data = parsePrinter(formData);
  } catch (err) {
    redirect(`/printing/${id}/edit${rejectionQuery(err)}`);
  }

  await db.printer.update({ where: { id }, data });
  const keys = Object.keys(data) as (keyof typeof data)[];
  await auditChanges(
    {
      organizationId: user.organizationId,
      userId: user.id,
      entityType: "Printer",
      entityId: id,
      actorType: "HUMAN",
      reason: "Printer record edited.",
    },
    Object.fromEntries(keys.map((k) => [k, (existing as Record<string, unknown>)[k]])),
    Object.fromEntries(keys.map((k) => [k, data[k]])),
  );
  revalidatePath("/printing");
  redirect("/printing");
}

export async function deletePrinter(formData: FormData): Promise<void> {
  const user = await requireWrite();
  const id = String(formData.get("id") ?? "");
  const existing = await db.printer.findFirst({ where: { id, organizationId: user.organizationId } });
  if (!existing) redirect("/printing");

  /*
   * A printer holds no readings the way an instrument does — the advisor
   * recomputes from whatever is on file every time — so removing one is safe
   * and simply changes the answer. It is still audited: a part that read
   * NOT SUITABLE last week because this was the only machine on file should be
   * traceable to the machine going away.
   */
  await db.printer.delete({ where: { id } });
  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "Printer",
    entityId: id,
    action: "DELETE",
    actorType: "HUMAN",
    field: "printer",
    oldValue: `${existing.manufacturer} ${existing.model}`,
    reason: "Printer removed from the shop's additive inventory. Additive verdicts are recomputed without it.",
  });
  revalidatePath("/printing");
  redirect("/printing");
}

/* ---------------- Print materials ---------------- */

export async function createPrintMaterial(formData: FormData): Promise<void> {
  const user = await requireWrite();
  let data;
  try {
    data = parseMaterial(formData);
  } catch (err) {
    redirect(`/printing/materials/new${rejectionQuery(err)}`);
  }

  const row = await db.printMaterial.create({ data: { ...data, organizationId: user.organizationId } });
  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "PrintMaterial",
    entityId: row.id,
    action: "CREATE",
    actorType: "HUMAN",
    field: "print material",
    newValue: `${data.name} · ${data.technology} · ${
      data.tensileZ != null ? `${data.tensileZ} psi through Z` : "no through-layer figure"
    }`,
    reason: "Print material added to the shop's additive inventory.",
  });
  revalidatePath("/printing");
  redirect("/printing");
}

export async function updatePrintMaterial(formData: FormData): Promise<void> {
  const user = await requireWrite();
  const id = String(formData.get("id") ?? "");
  const existing = await db.printMaterial.findFirst({ where: { id, organizationId: user.organizationId } });
  if (!existing) redirect("/printing");

  let data;
  try {
    data = parseMaterial(formData);
  } catch (err) {
    redirect(`/printing/materials/${id}/edit${rejectionQuery(err)}`);
  }

  await db.printMaterial.update({ where: { id }, data });
  const keys = Object.keys(data) as (keyof typeof data)[];
  await auditChanges(
    {
      organizationId: user.organizationId,
      userId: user.id,
      entityType: "PrintMaterial",
      entityId: id,
      actorType: "HUMAN",
      reason: "Print material record edited.",
    },
    Object.fromEntries(keys.map((k) => [k, (existing as Record<string, unknown>)[k]])),
    Object.fromEntries(keys.map((k) => [k, data[k]])),
  );
  revalidatePath("/printing");
  redirect("/printing");
}

export async function deletePrintMaterial(formData: FormData): Promise<void> {
  const user = await requireWrite();
  const id = String(formData.get("id") ?? "");
  const existing = await db.printMaterial.findFirst({ where: { id, organizationId: user.organizationId } });
  if (!existing) redirect("/printing");

  await db.printMaterial.delete({ where: { id } });
  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "PrintMaterial",
    entityId: id,
    action: "DELETE",
    actorType: "HUMAN",
    field: "print material",
    oldValue: existing.name,
    reason: "Print material removed from the shop's additive inventory.",
  });
  revalidatePath("/printing");
  redirect("/printing");
}
