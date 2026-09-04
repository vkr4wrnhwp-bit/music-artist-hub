"use server";

import { revalidatePath } from "next/cache";
import { requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { auditChanges } from "@/lib/audit";
import { FUNCTIONAL_ROLES } from "@/lib/domain/features";

/**
 * CORRECTING WHAT A FEATURE IS FOR
 *
 * `functionalRole` and `critical` were written at creation and by the
 * accept-a-proposal path, and by nothing else. A machinist who realised the
 * top face was the datum, or that a bore was critical after all, had one
 * option: delete the feature and enter it again — losing its measurements, its
 * assigned inspection method and its history along with the mistake.
 *
 * That is backwards for a product whose ninth principle is function before
 * process. CANVAS asks what the part does and then made the answer permanent,
 * while the geometry it drives could be re-measured at any time.
 *
 * WHAT CHANGES DOWNSTREAM, AND WHY IT IS NOT HIDDEN
 *
 *   - `functionalRole` = DATUM_FACE is what the workholding engine looks for
 *     when it reports "no feature is designated as a datum face". That factor
 *     had a suggestion — "assign a datum face on the part" — with no control
 *     behind it for a feature that already existed.
 *   - `critical` decides whether the critical-tolerance-strategy gate applies
 *     to this feature, and whether it appears in a derived inspection plan.
 *     Turning it on opens a gate. Turning it off closes one, and the page says
 *     so rather than letting a gate quietly disappear.
 *
 * An assigned inspection method is deliberately KEPT when a feature stops
 * being critical. The method is a decision somebody made about how to check
 * this feature, and it stays true whether or not a gate is watching it.
 */

export async function recordFeatureResponsibility(partId: string, formData: FormData) {
  const user = await requireWrite();
  const featureId = String(formData.get("featureId") ?? "");

  const owned = await db.feature.findFirst({
    where: { id: featureId, partRevision: { part: { id: partId, organizationId: user.organizationId } } },
  });
  if (!owned) return;

  const label = String(formData.get("label") ?? "").trim().slice(0, 120);
  const roleRaw = String(formData.get("functionalRole") ?? "");
  const critical = formData.get("critical") === "on";

  const finishRaw = String(formData.get("surfaceFinish") ?? "").trim();
  const finishNum = Number(finishRaw);
  // Blank clears it. A surface finish nobody stated is not a finish of zero,
  // which would read as a mirror.
  const surfaceFinish = finishRaw === "" ? null : Number.isFinite(finishNum) && finishNum > 0 ? finishNum : owned.surfaceFinish;

  const data = {
    // An empty label would leave the feature unnameable everywhere it appears,
    // so the old one stands rather than being cleared.
    label: label === "" ? owned.label : label,
    functionalRole: (FUNCTIONAL_ROLES as readonly string[]).includes(roleRaw) ? roleRaw : owned.functionalRole,
    critical,
    surfaceFinish,
  };

  await db.feature.update({ where: { id: owned.id }, data });

  await auditChanges(
    {
      organizationId: user.organizationId,
      userId: user.id,
      entityType: "Feature",
      entityId: owned.id,
      actorType: "HUMAN",
      // Named for what it is. A change here moves which gates apply to this
      // part, and six months later the reason wants to be legible.
      reason: `What ${owned.label} is for was corrected on the feature page.`,
    },
    {
      label: owned.label,
      functionalRole: owned.functionalRole,
      critical: owned.critical,
      surfaceFinish: owned.surfaceFinish,
    },
    data,
  );

  revalidatePath(`/parts/${partId}`, "layout");
}
