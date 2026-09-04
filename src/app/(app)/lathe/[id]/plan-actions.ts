"use server";

import { revalidatePath } from "next/cache";
import { requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { selectMaterial } from "@/lib/package-selectors";
import { planTurning, type PlannerTool } from "@/lib/manufacturing/turn/planner";
import { materialFromIntent } from "@/lib/manufacturing/turn/derive";
import type { RotationalProfile } from "@/lib/manufacturing/turn/geometry";

/**
 * PLANNING A TURNED PART
 *
 * `planJson` was written by the seed and by nothing else, so a part that
 * arrived through the reverse-engineering flow had no operations, no cycle
 * time and no cost — and the Tooling gate could never pass.
 *
 * The plan is derived server-side from the profile and the crib as they are
 * now. Nothing about the operations comes from the request: a plan posted in a
 * form is machine motion the browser chose, and this is the input to a
 * post processor.
 */

export async function generateTurnPlan(partId: string) {
  const user = await requireWrite();

  const revision = await db.partRevision.findFirst({
    where: { part: { id: partId, organizationId: user.organizationId } },
    orderBy: { createdAt: "desc" },
    select: { id: true, intentJson: true },
  });
  if (!revision) return;
  const rot = await db.rotationalPart.findFirst({
    where: { partRevisionId: revision.id, organizationId: user.organizationId },
  });
  if (!rot) return;

  const [tools, materials, holding] = await Promise.all([
    db.turningTool.findMany({ where: { organizationId: user.organizationId } }),
    db.material.findMany({ where: { organizationId: user.organizationId } }),
    rot.workholdingId
      ? db.latheWorkholding.findFirst({ where: { id: rot.workholdingId, organizationId: user.organizationId } })
      : null,
  ]);

  const materialName = materialFromIntent(revision.intentJson);
  const material = selectMaterial(materials, materialName);

  let profile: RotationalProfile;
  try {
    profile = JSON.parse(rot.profileJson) as RotationalProfile;
  } catch {
    return;
  }

  const plan = planTurning({
    profile,
    tools: tools as unknown as PlannerTool[],
    // Null when the shop holds no record of this material, which stops the
    // planner rather than being filled in. See planner.ts.
    materialSfmMin: material?.sfmCarbideMin ?? null,
    materialSfmMax: material?.sfmCarbideMax ?? null,
    materialName,
    chuckMaxRpm: holding?.maxRPM ?? null,
  });

  // A plan with no operations is not stored. Overwriting a plan a machinist
  // already has with an empty one, because the material record went missing,
  // would delete work to report a gap the page can state on its own.
  if (plan.operations.length === 0) {
    await audit({
      organizationId: user.organizationId,
      userId: user.id,
      entityType: "RotationalPart",
      entityId: rot.id,
      action: "UPDATE",
      actorType: "SYSTEM",
      reason: `Turning plan could not be generated: ${plan.refusals.join(" ")}`,
    });
    revalidatePath(`/lathe/${partId}`);
    return;
  }

  const previous = (() => {
    try {
      return (JSON.parse(rot.planJson) as unknown[]).length;
    } catch {
      return 0;
    }
  })();

  await db.rotationalPart.update({
    where: { id: rot.id },
    data: { planJson: JSON.stringify(plan.operations) },
  });

  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "RotationalPart",
    entityId: rot.id,
    action: "UPDATE",
    actorType: "SYSTEM",
    field: "planJson",
    oldValue: `${previous} operations`,
    newValue: `${plan.operations.length} operations`,
    // The refusals are recorded with the plan. A plan covering four of six
    // operations is a different document from one covering all six, and the
    // audit is where that survives being re-planned.
    reason:
      `Turning plan generated from the profile and the crib.` +
      (plan.refusals.length > 0 ? ` ${plan.refusals.length} not planned: ${plan.refusals.join(" ")}` : ""),
  });

  revalidatePath(`/lathe/${partId}`);
}
