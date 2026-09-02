"use server";

import { revalidatePath } from "next/cache";
import { requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { loadRevision } from "@/lib/data";
import { FEATURE_FIELDS, coerceFeatureParameters, validateFeatureParameters } from "@/lib/domain/feature-input";
import { FEATURE_KINDS, FUNCTIONAL_ROLES, type FeatureKind } from "@/lib/domain/features";
import { audit } from "@/lib/audit";

/**
 * ADDING A FEATURE BY HAND
 *
 * `db.feature.create` existed in exactly one place: accepting an AI proposal.
 * The empty state said "add features, or accept the proposals from the intake"
 * and no add control existed, so the only route into a part's geometry was to
 * accept something a model proposed.
 *
 * Beyond being unusable for a shop that wants to type in a 40 mm bore, that
 * sat badly against principle 3. A human accepting a proposal is a real act,
 * but making it the *only* way in means every dimension in the system began as
 * an inference.
 *
 * The rules:
 *
 *   - Parameters are validated against the kind's field spec, server-side.
 *     Nothing is defaulted: a missing depth is a refusal, not a zero, because
 *     a zero-depth pocket removes no material and every engine downstream
 *     would treat it as real.
 *   - A hand-entered feature is USER-sourced by construction — it is what the
 *     machinist says the part has. It carries no model score and no rationale.
 *   - Organisation comes from the session and the revision is re-resolved
 *     against it.
 */

export async function createFeature(partId: string, formData: FormData) {
  const user = await requireWrite();
  const revision = await loadRevision(user.organizationId, partId);
  if (!revision) return { error: "Part not found." };

  const kind = String(formData.get("kind") ?? "");
  if (!(FEATURE_KINDS as readonly string[]).includes(kind)) return { error: "Unknown feature kind." };

  const label = String(formData.get("label") ?? "").trim().slice(0, 120);
  if (label === "") return { error: "Give the feature a name a machinist would recognise." };

  const roleRaw = String(formData.get("functionalRole") ?? "NONE");
  const functionalRole = (FUNCTIONAL_ROLES as readonly string[]).includes(roleRaw) ? roleRaw : "NONE";

  const params: Record<string, unknown> = {};
  for (const f of FEATURE_FIELDS[kind as FeatureKind]) {
    params[f.name] = f.type === "boolean" ? formData.get(f.name) === "on" : formData.get(f.name);
  }

  const refusals = validateFeatureParameters(kind, params);
  if (refusals.length > 0) return { error: refusals.map((r) => r.reason).join(" ") };

  const tolPlus = String(formData.get("tolerancePlus") ?? "").trim();
  const tolMinus = String(formData.get("toleranceMinus") ?? "").trim();
  const finish = String(formData.get("surfaceFinish") ?? "").trim();

  const count = await db.feature.count({ where: { partRevisionId: revision.revisionId } });
  const created = await db.feature.create({
    data: {
      partRevisionId: revision.revisionId,
      kind,
      label,
      functionalRole,
      critical: formData.get("critical") === "on",
      parametersJson: JSON.stringify(coerceFeatureParameters(kind as FeatureKind, params)),
      // A blank tolerance is no tolerance, not a zero one: a ±0.0000 band is
      // unmeasurable and would fail every capability check for a reason
      // nobody typed.
      tolerancePlus: tolPlus === "" ? null : Number(tolPlus),
      toleranceMinus: tolMinus === "" ? null : Number(tolMinus),
      surfaceFinish: finish === "" ? null : Number(finish),
      notes: String(formData.get("notes") ?? "").trim().slice(0, 1000) || null,
      orderIndex: count,
    },
  });

  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    actorType: "HUMAN",
    entityType: "Feature",
    entityId: created.id,
    action: "CREATE",
    reason: `Added ${kind} "${label}" by hand.`,
  });

  revalidatePath(`/parts/${partId}`);
  revalidatePath(`/parts/${partId}/readiness`);
  return { ok: true as const };
}

export async function deleteFeature(partId: string, formData: FormData) {
  const user = await requireWrite();
  const revision = await loadRevision(user.organizationId, partId);
  if (!revision) return;

  const featureId = String(formData.get("featureId") ?? "");
  const owned = await db.feature.findFirst({
    where: { id: featureId, partRevisionId: revision.revisionId },
    select: { id: true, label: true, kind: true },
  });
  if (!owned) return;

  // Operations reference the feature. Removing it leaves them pointing at
  // nothing, so they go with it — the plan for a feature that no longer
  // exists is not a plan.
  await db.operation.deleteMany({ where: { featureId: owned.id } });
  await db.feature.delete({ where: { id: owned.id } });

  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    actorType: "HUMAN",
    entityType: "Feature",
    entityId: owned.id,
    action: "DELETE",
    reason: `Removed ${owned.kind} "${owned.label}" and the operations planned for it.`,
  });

  revalidatePath(`/parts/${partId}`);
  revalidatePath(`/parts/${partId}/readiness`);
}
