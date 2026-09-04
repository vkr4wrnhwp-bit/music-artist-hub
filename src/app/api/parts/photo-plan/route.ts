import { NextResponse } from "next/server";
import { requireWriteApi } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { getAiProvider } from "@/lib/ai/provider";
import { buildGuidedPlan } from "@/lib/engines/photo-plan";
import { getMetrology } from "@/lib/data";

/**
 * "I HAVE THE PART AND A PHONE. WHERE DO I START?"
 *
 * A photograph goes in; an ordered list of things to measure comes back, each
 * one pinned to the spot on that photograph it means, with the instrument this
 * shop actually owns beside it.
 *
 * WHAT THIS ROUTE DOES NOT RETURN IS A DIMENSION.
 *
 * The model is asked what it can see and where. It has nowhere to put a size —
 * the tool schema has no such property — and the prompt tells it not to state
 * one even approximately. A plausible diameter is the most dangerous thing this
 * application could produce, because it would arrive looking exactly like a
 * measured one and somebody would cut to it.
 *
 * The reading is a MEASUREMENT, taken by a person, with a named instrument, to
 * that instrument's uncertainty — recorded through the same measurement session
 * as a reading taken at the bench, because that is what it is. The model's part
 * is over once it has pointed.
 */

const MAX_BYTES = 12 * 1024 * 1024;
const ALLOWED = new Set(["image/jpeg", "image/png", "image/webp"]);

export async function POST(request: Request) {
  const gate = await requireWriteApi();
  if ("denied" in gate) return gate.denied;
  const user = gate.user;

  const form = await request.formData().catch(() => null);
  const file = form?.get("file");
  if (!(file instanceof File)) return NextResponse.json({ error: "Attach a photograph of the part." }, { status: 400 });
  if (file.size > MAX_BYTES) return NextResponse.json({ error: "Photograph is over the 12 MB limit." }, { status: 400 });
  if (!ALLOWED.has(file.type)) {
    return NextResponse.json({ error: "JPEG, PNG or WebP. That is what a phone takes." }, { status: 400 });
  }

  // Part id from the client is only honoured after confirming it is this
  // organisation's — the same rule every other write path follows.
  const partId = String(form?.get("partId") ?? "");
  const part = await db.part.findFirst({
    where: { id: partId, organizationId: user.organizationId },
    select: { id: true },
  });
  if (!part) return NextResponse.json({ error: "Part not found." }, { status: 404 });

  const views = Number(form?.get("views") ?? 1) || 1;

  const base64 = Buffer.from(await file.arrayBuffer()).toString("base64");
  const provider = await getAiProvider();
  const read = await provider.readPartPhoto({ mediaType: file.type, base64 });

  const devices = await getMetrology(user.organizationId);
  const plan = buildGuidedPlan(read, devices, views);

  /*
   * Logged as AI, because it is. The actor is typed rather than inferred, and
   * what it produced is a list of things to go and measure — never a value.
   */
  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    entityType: "Part",
    entityId: part.id,
    action: "GENERATE",
    actorType: "AI",
    reason: `Photograph read for a measurement plan (${provider.label})`,
    newValue: read.connected
      ? `${plan.steps.length} things to measure proposed, ${plan.unmeasurable.length} with no instrument in the library. No dimension was produced.`
      : "No vision model connected — nothing was read from the photograph.",
  });

  return NextResponse.json({ connected: read.connected, plan });
}
