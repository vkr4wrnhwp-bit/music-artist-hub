import { NextResponse } from "next/server";
import { z } from "zod";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { getAiProvider } from "@/lib/ai/provider";
import { emptyPartIntent, type PartIntent } from "@/lib/domain/part-intent";
import { inferred, userValue, unknown as unknownField } from "@/lib/provenance";

/**
 * NEW PART INTAKE
 *
 * Natural language in, structured Part Intent Model out. Every field the
 * parser produced is tagged AI_INFERENCE and unconfirmed — the workspace then
 * asks the user to confirm each one. Nothing here is treated as engineering
 * truth just because it parsed cleanly.
 */

const bodySchema = z.object({ prompt: z.string().min(3).max(4000) });

export async function POST(request: Request) {
  const user = await requireUser();

  const parsed = bodySchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ error: "A description of at least 3 characters is required." }, { status: 400 });
  }
  const { prompt } = parsed.data;

  const ai = await getAiProvider();
  const extraction = await ai.interpretPartPrompt(prompt);
  const suggestions = await ai.suggestFeatures(prompt, extraction);

  const intent: PartIntent = emptyPartIntent(extraction.partName ?? "New Part");
  intent.description = inferred(prompt, 1, "Verbatim from the intake request");
  if (extraction.units) intent.units = userValue(extraction.units);
  if (extraction.material) intent.material = inferred(extraction.material, extraction.confidence, "Recognised from the description");
  if (extraction.materialCondition) intent.materialCondition = inferred(extraction.materialCondition, extraction.confidence);
  if (extraction.stock) intent.stock = inferred(extraction.stock, extraction.confidence, "Stock sized from the finished envelope with a facing allowance");
  if (extraction.finishedEnvelope) intent.finishedEnvelope = inferred(extraction.finishedEnvelope, extraction.confidence);
  if (extraction.quantity) intent.quantity = inferred(extraction.quantity, extraction.confidence);
  if (extraction.generalTolerance) intent.generalTolerance = inferred(extraction.generalTolerance, extraction.confidence);
  if (extraction.surfaceFinish) intent.surfaceFinish = inferred(extraction.surfaceFinish, extraction.confidence);
  if (extraction.features?.length) intent.features = inferred(extraction.features, extraction.confidence);
  if (extraction.notes) intent.notes = inferred(extraction.notes, extraction.confidence);

  // Responsibility is never inferred. It is asked.
  intent.loadBearing = unknownField("Requires the Part Responsibility interview");
  intent.safetyCritical = unknownField("Requires the Part Responsibility interview");
  intent.failureConsequence = unknownField("Requires the Part Responsibility interview");
  intent.unknowns = extraction.unknowns;
  intent.confidence = extraction.confidence;

  const part = await db.part.create({
    data: {
      organizationId: user.organizationId,
      name: extraction.partName ?? "New Part",
      description: prompt.slice(0, 500),
      sharing: "PRIVATE",
      revisions: {
        create: {
          revision: "A",
          status: "DRAFT",
          units: extraction.units ?? "IN",
          intentJson: JSON.stringify(intent),
          stockJson: extraction.stock
            ? JSON.stringify({
                form: extraction.stock.form,
                x: extraction.stock.x ?? 0,
                y: extraction.stock.y ?? 0,
                z: extraction.stock.z ?? 0,
                material: extraction.material ?? "Unspecified",
                condition: extraction.materialCondition,
              })
            : null,
          responsibility: { create: {} },
        },
      },
    },
    include: { revisions: true },
  });

  const revision = part.revisions[0];

  // Feature suggestions are stored as proposals, not as geometry. They only
  // become features when a human accepts them in the workspace.
  if (suggestions.length > 0) {
    await db.aIRecommendation.create({
      data: {
        partRevisionId: revision.id,
        kind: "FEATURE",
        summary: `${suggestions.length} features proposed from the description`,
        payloadJson: JSON.stringify(suggestions),
        providerId: ai.id,
        confidence: extraction.confidence,
        status: "PROPOSED",
      },
    });
  }

  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "Part",
    entityId: part.id,
    action: "CREATE",
    actorType: "HUMAN",
    reason: "Created from intake description",
    newValue: part.name,
  });

  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "PartRevision",
    entityId: revision.id,
    action: "GENERATE",
    actorType: "AI",
    reason: `Intent extracted by ${ai.label}`,
    newValue: JSON.stringify({ fields: Object.keys(extraction).length, suggestions: suggestions.length }),
  });

  return NextResponse.json({ partId: part.id, revisionId: revision.id, suggestions: suggestions.length });
}
