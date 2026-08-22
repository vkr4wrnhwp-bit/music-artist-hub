import { NextResponse } from "next/server";
import { z } from "zod";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { getAiProvider } from "@/lib/ai/provider";
import { buildIntakeIntent } from "@/lib/ai/intake-intent";

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

  const { intent, stock } = buildIntakeIntent(prompt, extraction);

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
          // Null rather than a zero-filled record when the extraction gave a
          // form and no dimensions. See stockFromExtraction.
          stockJson: stock ? JSON.stringify(stock) : null,
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
