"use server";

import { revalidatePath } from "next/cache";
import { requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { loadRevision } from "@/lib/data";
import { FEATURE_FIELDS, coerceFeatureParameters, validateFeatureParameters } from "@/lib/domain/feature-input";
import { FEATURE_KINDS, FUNCTIONAL_ROLES, type FeatureKind } from "@/lib/domain/features";
import { audit } from "@/lib/audit";
import { PATTERN_KINDS, expandPattern, offStock, patternable, type PatternKind, type PatternSpec } from "@/lib/domain/pattern";
import { randomUUID } from "node:crypto";

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

/**
 * TURNING ONE FEATURE INTO THE PATTERN THE DRAWING DESCRIBES.
 *
 * Every hole in a bolt circle had to be typed in by hand with its coordinates
 * worked out off the machine. Six holes on a 3.000" circle is twelve numbers to
 * compute and twelve to mistype, on the most common thing there is on a plate —
 * and a hole entered at the wrong angle gets drilled in the wrong place and
 * measures perfectly on its own diameter.
 *
 * The source feature BECOMES the first instance rather than being copied
 * alongside it, so nothing is duplicated and everything already recorded
 * against it — tolerance, inspection method, mating component — is what the
 * rest of the pattern inherits. It is one feature the machinist already
 * described, placed the number of times the drawing says.
 */
export async function patternFeature(partId: string, formData: FormData) {
  const user = await requireWrite();
  const revision = await loadRevision(user.organizationId, partId);
  if (!revision) return { error: "Part not found." };

  const featureId = String(formData.get("featureId") ?? "");
  const source = await db.feature.findFirst({ where: { id: featureId, partRevisionId: revision.revisionId } });
  if (!source) return { error: "Feature not found." };
  if (source.patternId) return { error: "This feature is already part of a pattern. Remove it from that one first." };

  const domain = revision.features.find((f) => f.id === source.id);
  if (!domain || !patternable(domain)) {
    return { error: `A ${source.kind} has no centre to place, so it cannot be patterned. Patterns place holes, bores and pockets.` };
  }

  const num = (name: string) => Number(String(formData.get(name) ?? "").trim());
  const kindRaw = String(formData.get("patternKind") ?? "");
  if (!(PATTERN_KINDS as readonly string[]).includes(kindRaw)) return { error: "Unknown pattern kind." };
  const kind = kindRaw as PatternKind;

  const spec: PatternSpec =
    kind === "BOLT_CIRCLE"
      ? { kind, centerX: num("centerX"), centerY: num("centerY"), diameter: num("diameter"), count: num("count"), startAngle: num("startAngle") }
      : kind === "GRID"
        ? { kind, originX: num("originX"), originY: num("originY"), columns: num("columns"), rows: num("rows"), pitchX: num("pitchX"), pitchY: num("pitchY") }
        : { kind, originX: num("originX"), originY: num("originY"), count: num("count"), pitch: num("pitch"), angle: num("angle") };

  if (Object.values(spec).some((v) => typeof v === "number" && !Number.isFinite(v))) {
    return { error: "Every number in the pattern has to be a number. A blank is not a zero." };
  }

  const positions = expandPattern(spec);
  if ("error" in positions) return { error: `${positions.error.reason} ${positions.error.recommendations[0]}.` };

  /*
   * A pattern that runs off the stock is a transposed diameter or a datum
   * mistake, and it is far easier to see here — before the features exist —
   * than as one hole in the middle of a rapid.
   */
  if (revision.stock) {
    const off = offStock(positions, revision.stock);
    if (off.length > 0) {
      return {
        error: `${off.length} of ${positions.length} would sit off the ${revision.stock.x.toFixed(3)} × ${revision.stock.y.toFixed(3)} stock — the first at X${off[0].x.toFixed(4)} Y${off[0].y.toFixed(4)}. Check the diameter and the centre against the drawing's datum.`,
      };
    }
  }

  const params = JSON.parse(source.parametersJson) as Record<string, unknown>;
  const base = source.label.replace(/\s+\d+$/, "");
  const patternId = randomUUID();
  const patternJson = JSON.stringify(spec);
  const count = await db.feature.count({ where: { partRevisionId: revision.revisionId } });

  await db.$transaction(async (tx) => {
    // The source becomes instance 1, moved onto the pattern rather than left
    // wherever it was typed.
    await tx.feature.update({
      where: { id: source.id },
      data: {
        label: `${base} 1`,
        parametersJson: JSON.stringify({ ...params, centerX: positions[0].x, centerY: positions[0].y }),
        patternId,
        patternIndex: 1,
        patternJson,
      },
    });
    for (const pos of positions.slice(1)) {
      await tx.feature.create({
        data: {
          partRevisionId: revision.revisionId,
          kind: source.kind,
          label: `${base} ${pos.index}`,
          functionalRole: source.functionalRole,
          critical: source.critical,
          parametersJson: JSON.stringify({ ...params, centerX: pos.x, centerY: pos.y }),
          // Everything the machinist already said about the first one applies
          // to the rest: it is one feature, placed N times.
          tolerancePlus: source.tolerancePlus,
          toleranceMinus: source.toleranceMinus,
          surfaceFinish: source.surfaceFinish,
          matingComponent: source.matingComponent,
          matingDesignation: source.matingDesignation,
          matingDesignationSource: source.matingDesignationSource,
          interfaceSide: source.interfaceSide,
          rotatingUnderLoad: source.rotatingUnderLoad,
          fitClass: source.fitClass,
          notes: source.notes,
          // The inspection method is NOT inherited. It is a decision about how
          // one feature gets verified, recorded against a name and a time, and
          // copying it would put a person's signature on five decisions they
          // did not make.
          orderIndex: count + pos.index - 1,
          patternId,
          patternIndex: pos.index,
          patternJson,
        },
      });
    }
  });

  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    actorType: "HUMAN",
    entityType: "Feature",
    entityId: source.id,
    action: "CREATE",
    field: "pattern",
    newValue: patternJson,
    reason: `Placed "${base}" ${positions.length} times as a ${kind.replace(/_/g, " ").toLowerCase()}.`,
  });

  revalidatePath(`/parts/${partId}`);
  revalidatePath(`/parts/${partId}/features`);
  revalidatePath(`/parts/${partId}/readiness`);
  return { ok: true as const, created: positions.length };
}
