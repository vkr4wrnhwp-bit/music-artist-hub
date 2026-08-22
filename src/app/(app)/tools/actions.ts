"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit, auditChanges } from "@/lib/audit";
import { TOOL_CLASSES } from "@/lib/domain/shop";
import { FormReader, rejectionQuery } from "@/lib/shop-form";
import { TOOL_CONDITIONS, TOOL_COOLANTS } from "./tool-fields";

/**
 * Tool crib writes.
 *
 * Organisation id comes from the session on every path, never from the form
 * — a posted organizationId is how one shop reads another shop's crib.
 * The tool id is likewise re-checked against the session's organisation
 * before an update touches anything.
 *
 * Every write records an audit row with `actorType: "HUMAN"`. The actor is
 * typed, not inferred: a person filled this form in, and the log has to be
 * able to say so later without guessing.
 */

function parse(formData: FormData) {
  const f = new FormReader(formData);

  const chipMin = f.number("chiploadMin", "Chipload min", { min: 0 });
  const chipMax = f.number("chiploadMax", "Chipload max", { min: 0 });
  const sfmMin = f.number("sfmMin", "Surface speed min", { min: 0 });
  const sfmMax = f.number("sfmMax", "Surface speed max", { min: 0 });
  const fluteLength = f.number("fluteLength", "Flute length", { min: 0 });
  const overallLength = f.number("overallLength", "Overall length", { min: 0 });

  const data = {
    toolNumber: f.integer("toolNumber", "Tool number", { min: 1 }),
    toolClass: f.choice("toolClass", "Class", TOOL_CLASSES),
    description: f.text("description", "Description"),
    manufacturer: f.optionalText("manufacturer"),
    product: f.optionalText("product"),

    diameter: f.number("diameter", "Diameter", { min: 0 }),
    cornerRadius: f.number("cornerRadius", "Corner radius", { min: 0 }),
    flutes: f.integer("flutes", "Flutes", { min: 1 }),
    helixAngle: f.optionalNumber("helixAngle", "Helix angle", { min: 0, max: 90 }),
    fluteLength,
    overallLength,
    stickout: f.number("stickout", "Stickout", { min: 0 }),
    holderId: f.optionalText("holderId"),

    material: f.text("material", "Tool material"),
    coating: f.optionalText("coating"),
    chiploadMin: chipMin,
    chiploadMax: chipMax,
    sfmMin,
    sfmMax,
    maxRPM: f.integer("maxRPM", "Maximum RPM", { min: 1 }),
    coolant: f.choice("coolant", "Coolant", TOOL_COOLANTS),
    recommendedMaterials: f.jsonList("recommendedMaterials"),

    condition: f.choice("condition", "Condition", TOOL_CONDITIONS),
    lifeRemaining: f.number("lifeRemaining", "Life remaining", { min: 0, max: 1 }),
    actualStickout: f.optionalNumber("actualStickout", "Measured stickout", { min: 0 }),
    measuredRunout: f.optionalNumber("measuredRunout", "Measured runout", { min: 0 }),
    expectedLifeMinutes: f.number("expectedLifeMinutes", "Expected life", { min: 0 }),
    costPerTool: f.number("costPerTool", "Cost per tool", { min: 0 }),
    notes: f.optionalText("notes"),
    shopNotes: f.optionalText("shopNotes"),
  };

  f.requireOrder(chipMin, chipMax, "Chipload");
  f.requireOrder(sfmMin, sfmMax, "Surface speed");
  // A cutter cannot have more flute than tool. This is geometry, not taste.
  f.requireOrder(fluteLength, overallLength, "Flute length against overall length");
  f.done();
  return data;
}

/** A one-line summary for the audit row — what changed, in machinist terms. */
function summarize(d: ReturnType<typeof parse>): string {
  return `T${d.toolNumber} · ${d.description} · ⌀${d.diameter} R${d.cornerRadius} · ${d.flutes}FL · stickout ${d.stickout}`;
}

export async function createTool(formData: FormData): Promise<void> {
  const user = await requireUser();

  let data;
  try {
    data = parse(formData);
  } catch (err) {
    redirect(`/tools/new${rejectionQuery(err)}`);
  }

  // The crib's uniqueness rule is per organisation, and colliding on it is a
  // user mistake rather than an exception — say which number is taken.
  const clash = await db.tool.findFirst({
    where: { organizationId: user.organizationId, toolNumber: data.toolNumber },
    select: { id: true, description: true },
  });
  if (clash) {
    redirect(
      `/tools/new?problem=${encodeURIComponent(`T${data.toolNumber} is already in the crib — ${clash.description}`)}`,
    );
  }

  const holderId = data.holderId ? ((await db.toolHolder.findUnique({ where: { id: data.holderId } })) ? data.holderId : null) : null;

  const row = await db.tool.create({
    data: { ...data, holderId, organizationId: user.organizationId },
  });

  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "Tool",
    entityId: row.id,
    action: "CREATE",
    actorType: "HUMAN",
    field: "tool",
    newValue: summarize(data),
    reason: "Tool added to the crib.",
  });

  revalidatePath("/tools");
  redirect("/tools");
}

export async function updateTool(formData: FormData): Promise<void> {
  const user = await requireUser();
  const id = String(formData.get("id") ?? "");

  // Org from the session, id checked against it. Never trust the posted id.
  const existing = await db.tool.findFirst({ where: { id, organizationId: user.organizationId } });
  if (!existing) redirect("/tools");

  let data;
  try {
    data = parse(formData);
  } catch (err) {
    redirect(`/tools/${id}/edit${rejectionQuery(err)}`);
  }

  if (data.toolNumber !== existing.toolNumber) {
    const clash = await db.tool.findFirst({
      where: { organizationId: user.organizationId, toolNumber: data.toolNumber, NOT: { id } },
      select: { description: true },
    });
    if (clash) {
      redirect(
        `/tools/${id}/edit?problem=${encodeURIComponent(`T${data.toolNumber} is already in the crib — ${clash.description}`)}`,
      );
    }
  }

  const holderId = data.holderId ? ((await db.toolHolder.findUnique({ where: { id: data.holderId } })) ? data.holderId : null) : null;

  await db.tool.update({ where: { id }, data: { ...data, holderId } });

  // Field-level audit: one row per changed field, so the crib's history reads
  // as "stickout went from 1.250 to 2.000" rather than "tool edited".
  const tracked = Object.keys(data) as (keyof typeof data)[];
  await auditChanges(
    {
      organizationId: user.organizationId,
      userId: user.id,
      entityType: "Tool",
      entityId: id,
      actorType: "HUMAN",
      reason: "Tool crib record edited.",
    },
    Object.fromEntries(tracked.map((k) => [k, (existing as Record<string, unknown>)[k]])),
    Object.fromEntries(tracked.map((k) => [k, data[k]])),
  );

  revalidatePath("/tools");
  redirect("/tools");
}

export async function deleteTool(formData: FormData): Promise<void> {
  const user = await requireUser();
  const id = String(formData.get("id") ?? "");
  const existing = await db.tool.findFirst({ where: { id, organizationId: user.organizationId } });
  if (!existing) redirect("/tools");

  // A tool that operations already reference is not deletable — removing it
  // would silently strip the tooling from a planned operation and leave a
  // plan that looks complete. Say so instead.
  const used = await db.operation.count({ where: { toolId: id } });
  if (used > 0) {
    redirect(
      `/tools/${id}/edit?problem=${encodeURIComponent(
        `T${existing.toolNumber} is used by ${used} planned operation${used === 1 ? "" : "s"} — remove it from those operations first.`,
      )}`,
    );
  }

  await db.tool.delete({ where: { id } });
  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "Tool",
    entityId: id,
    action: "DELETE",
    actorType: "HUMAN",
    field: "tool",
    oldValue: `T${existing.toolNumber} · ${existing.description}`,
    reason: "Tool removed from the crib.",
  });

  revalidatePath("/tools");
  redirect("/tools");
}
