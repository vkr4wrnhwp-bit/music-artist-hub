import { NextResponse } from "next/server";
import { z } from "zod";
import { requireSessionApi } from "@/lib/auth";
import { db } from "@/lib/db";
import { getAiProvider, type CopilotContext } from "@/lib/ai/provider";
import { buildPackage } from "@/lib/package";
import { missingEngineeringInput } from "@/lib/domain/part-intent";
import { validateProposals, validateSceneActions } from "@/lib/engines/copilot-actions";
import { audit } from "@/lib/audit";

/**
 * Copilot endpoint.
 *
 * The client's `context` field is advisory only — the authoritative context is
 * rebuilt server-side from the database, scoped to the caller's organisation.
 * A client cannot talk the copilot into reasoning about a machine the shop
 * does not own by putting it in the request body.
 */

const bodySchema = z.object({
  partId: z.string().min(1),
  question: z.string().min(1).max(2000),
});

export async function POST(request: Request) {
  const gate = await requireSessionApi();
  if ("denied" in gate) return gate.denied;
  const user = gate.user;
  const parsed = bodySchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) return NextResponse.json({ error: "Invalid request" }, { status: 400 });

  const { partId, question } = parsed.data;
  const pkg = await buildPackage(user.organizationId, partId);
  if (!pkg) return NextResponse.json({ error: "Part not found" }, { status: 404 });

  const context: CopilotContext = {
    partName: pkg.revision.partName,
    material: pkg.revision.intent.material.value,
    stock: pkg.revision.stock
      ? `${pkg.revision.stock.x} × ${pkg.revision.stock.y} × ${pkg.revision.stock.z} ${pkg.revision.stock.material}`
      : null,
    machine: pkg.primaryMachine ? `${pkg.primaryMachine.manufacturer} ${pkg.primaryMachine.model}` : null,
    tools: pkg.assignedTools.map((t) => `T${t.toolNumber} ${t.description}`),
    workholding: pkg.primaryWorkholding?.description ?? null,
    features: pkg.revision.features.map((f) => `${f.label} (${f.kind})`),
    readiness: pkg.readiness.overall,
    openQuestions: missingEngineeringInput(pkg.revision.intent),
  };

  const ai = await getAiProvider();
  const reply = await ai.answerCopilot(question, context);

  /*
   * Everything the model asked for, checked against the package the SERVER
   * built. A model can name any id; an id that is not on this part is dropped
   * rather than handed to the client as something to press. That mattered
   * less when a reference was a caption and matters now that it is a control.
   */
  const scene = validateSceneActions(reply.sceneActions ?? [], {
    featureIds: pkg.revision.features.map((f) => f.id),
    operationIds: pkg.setups.flatMap((s) => s.operations.map((o) => o.id)),
  });

  /*
   * Proposals do NOT take effect. They are written at PROPOSED into the same
   * queue every other AI suggestion goes through and are accepted by a human
   * on /proposals — the copilot gets no softer second route to the part.
   */
  const proposed = validateProposals(reply.proposals ?? []);
  for (const p of proposed.proposals) {
    await db.aIRecommendation.create({
      data: {
        partRevisionId: pkg.revision.revisionId,
        kind: p.kind,
        summary: p.summary,
        payloadJson: JSON.stringify(p.payload ?? null),
        providerId: ai.id,
        status: "PROPOSED",
      },
    });
  }
  if (proposed.proposals.length > 0) {
    await audit({
      organizationId: user.organizationId,
      userId: user.id,
      // The model proposed it. Nothing has been applied.
      actorType: "AI",
      entityType: "PartRevision",
      entityId: pkg.revision.revisionId,
      action: "GENERATE",
      reason: `The copilot proposed ${proposed.proposals.length} change(s) for review. None applied.`,
    });
  }

  // Conversations are persisted so the reasoning behind a decision survives
  // the session it was made in.
  const conversation =
    (await db.conversation.findFirst({ where: { organizationId: user.organizationId, partId } })) ??
    (await db.conversation.create({
      data: { organizationId: user.organizationId, partId, title: pkg.revision.partName },
    }));

  await db.conversationMessage.createMany({
    data: [
      { conversationId: conversation.id, role: "user", content: question },
      {
        conversationId: conversation.id,
        role: "assistant",
        content: reply.reply,
        referencesJson: JSON.stringify(reply.references ?? []),
        needsJson: JSON.stringify(reply.needs ?? []),
        providerId: ai.id,
      },
    ],
  });

  return NextResponse.json({
    ...reply,
    sceneActions: scene.actions,
    proposals: proposed.proposals.map((p) => ({ kind: p.kind, summary: p.summary })),
    // Dropped on the way through, and why. A silent drop would leave the
    // machinist reading an answer that refers to a control that is not there.
    dropped: [
      ...scene.rejected.map((r) => `${r.kind} ${r.targetId}: ${r.reason}`),
      ...proposed.rejected.map((r) => `${r.kind}: ${r.reason}`),
    ],
  });
}
