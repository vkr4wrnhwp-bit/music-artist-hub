import { NextResponse } from "next/server";
import { z } from "zod";
import { requireSessionApi } from "@/lib/auth";
import { db } from "@/lib/db";
import { getAiProvider, type CopilotContext } from "@/lib/ai/provider";
import { buildPackage } from "@/lib/package";
import { missingEngineeringInput } from "@/lib/domain/part-intent";

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

  return NextResponse.json(reply);
}
