"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit, auditChanges } from "@/lib/audit";
import { MACHINE_TYPES, CONTROLLERS } from "@/lib/domain/shop";
import { POSTS, defaultPostForController } from "@/lib/engines/cam/post";
import { FormReader, rejectionQuery } from "@/lib/shop-form";

function parse(formData: FormData) {
  const f = new FormReader(formData);
  const controller = f.choice("controller", "Controller", CONTROLLERS);
  const chosenPost = f.optionalText("supportedPostProcessor");

  const data = {
    manufacturer: f.text("manufacturer", "Manufacturer"),
    model: f.text("model", "Model"),
    controller,
    machineType: f.choice("machineType", "Machine type", MACHINE_TYPES),
    axisCount: f.integer("axisCount", "Axis count", { min: 2, max: 9 }),

    travelsX: f.number("travelsX", "X travel", { min: 0 }),
    travelsY: f.number("travelsY", "Y travel", { min: 0 }),
    travelsZ: f.number("travelsZ", "Z travel", { min: 0 }),
    tableX: f.number("tableX", "Table X", { min: 0 }),
    tableY: f.number("tableY", "Table Y", { min: 0 }),

    maxSpindleRPM: f.integer("maxSpindleRPM", "Maximum spindle RPM", { min: 1 }),
    maxSpindlePower: f.number("maxSpindlePower", "Spindle power", { min: 0 }),
    maxSpindleTorque: f.number("maxSpindleTorque", "Spindle torque", { min: 0 }),
    maxFeed: f.number("maxFeed", "Maximum feed", { min: 0 }),
    maxRapid: f.number("maxRapid", "Maximum rapid", { min: 0 }),
    axisAccel: f.optionalNumber("axisAccel", "Axis acceleration", { min: 0 }),

    toolChangerCapacity: f.integer("toolChangerCapacity", "Tool changer capacity", { min: 0 }),
    maxToolDiameter: f.number("maxToolDiameter", "Maximum tool diameter", { min: 0 }),
    maxToolLength: f.number("maxToolLength", "Maximum tool length", { min: 0 }),
    maxToolWeight: f.number("maxToolWeight", "Maximum tool weight", { min: 0 }),

    coolantTypes: f.jsonList("coolantTypes"),
    throughSpindleCoolant: f.boolean("throughSpindleCoolant"),
    probe: f.boolean("probe"),
    toolSetter: f.boolean("toolSetter"),
    fourthAxis: f.boolean("fourthAxis"),
    fifthAxis: f.boolean("fifthAxis"),
    supportedPostProcessor:
      chosenPost && POSTS.some((p) => p.id === chosenPost) ? chosenPost : defaultPostForController(controller).id,
    notes: f.optionalText("notes"),
  };

  // A rapid slower than the cutting feed is a transposition, not a machine.
  f.requireOrder(data.maxFeed, data.maxRapid, "Maximum feed against maximum rapid");
  f.done();
  return data;
}

const summary = (d: ReturnType<typeof parse>) =>
  `${d.manufacturer} ${d.model} · ${d.travelsX}×${d.travelsY}×${d.travelsZ} · ${d.maxSpindleRPM} rpm`;

export async function createMachine(formData: FormData): Promise<void> {
  const user = await requireUser();
  let data;
  try {
    data = parse(formData);
  } catch (err) {
    redirect(`/machines/new${rejectionQuery(err)}`);
  }

  const row = await db.machine.create({
    data: {
      ...data,
      // A machine a shop entered is a machine the shop owns. Reference
      // profiles are seeded example data and are never created from here.
      isReferenceProfile: false,
      organizationId: user.organizationId,
    },
  });
  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "Machine",
    entityId: row.id,
    action: "CREATE",
    actorType: "HUMAN",
    field: "machine",
    newValue: summary(data),
    reason: "Machine added to the shop.",
  });
  revalidatePath("/machines");
  redirect("/machines");
}

export async function updateMachine(formData: FormData): Promise<void> {
  const user = await requireUser();
  const id = String(formData.get("id") ?? "");
  const existing = await db.machine.findFirst({ where: { id, organizationId: user.organizationId } });
  if (!existing) redirect("/machines");

  let data;
  try {
    data = parse(formData);
  } catch (err) {
    redirect(`/machines/${id}/edit${rejectionQuery(err)}`);
  }

  /*
   * Shrinking the changer below what is already loaded would leave tools
   * recorded in pockets the machine no longer has. Name the highest occupied
   * pocket rather than silently orphaning them.
   */
  if (data.toolChangerCapacity < existing.toolChangerCapacity) {
    const highest = await db.tool.findFirst({
      where: { machineId: id, pocket: { not: null } },
      orderBy: { pocket: "desc" },
      select: { pocket: true },
    });
    if (highest?.pocket != null && highest.pocket > data.toolChangerCapacity) {
      redirect(
        `/machines/${id}/edit?problem=${encodeURIComponent(
          `Pocket ${highest.pocket} is loaded, so the changer cannot be reduced to ${data.toolChangerCapacity} pockets. Unload it first.`,
        )}`,
      );
    }
  }

  await db.machine.update({ where: { id }, data });

  const keys = Object.keys(data) as (keyof typeof data)[];
  await auditChanges(
    {
      organizationId: user.organizationId,
      userId: user.id,
      entityType: "Machine",
      entityId: id,
      actorType: "HUMAN",
      reason: "Machine profile edited.",
    },
    Object.fromEntries(keys.map((k) => [k, (existing as Record<string, unknown>)[k]])),
    Object.fromEntries(keys.map((k) => [k, data[k]])),
  );

  revalidatePath("/machines");
  redirect("/machines");
}

export async function deleteMachine(formData: FormData): Promise<void> {
  const user = await requireUser();
  const id = String(formData.get("id") ?? "");
  const existing = await db.machine.findFirst({ where: { id, organizationId: user.organizationId } });
  if (!existing) redirect("/machines");

  /*
   * Setups and NC programs both point at the machine with onDelete: SetNull.
   * Deleting would leave a setup with no machine and a posted program with
   * nothing to say what it was posted for, while both still read as planned.
   * Loaded tools are a different case — SetNull returns them to the crib,
   * which is exactly right, so they do not block.
   */
  const [setups, programs] = await Promise.all([
    db.setup.count({ where: { machineId: id } }),
    db.nCProgram.count({ where: { machineId: id } }),
  ]);
  if (setups > 0 || programs > 0) {
    const parts = [
      setups > 0 ? `${setups} setup${setups === 1 ? "" : "s"}` : null,
      programs > 0 ? `${programs} NC program${programs === 1 ? "" : "s"}` : null,
    ].filter(Boolean);
    redirect(
      `/machines/${id}/edit?problem=${encodeURIComponent(
        `${parts.join(" and ")} reference this machine. Removing it would leave them planned against nothing.`,
      )}`,
    );
  }

  await db.machine.delete({ where: { id } });
  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "Machine",
    entityId: id,
    action: "DELETE",
    actorType: "HUMAN",
    field: "machine",
    oldValue: `${existing.manufacturer} ${existing.model}`,
    reason: "Machine removed from the shop.",
  });
  revalidatePath("/machines");
  redirect("/machines");
}
