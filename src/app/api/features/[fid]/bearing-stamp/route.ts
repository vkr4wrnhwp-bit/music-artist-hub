import { NextResponse } from "next/server";
import { requireWriteApi } from "@/lib/auth";
import { db } from "@/lib/db";
import { getAiProvider } from "@/lib/ai/provider";
import { resolveStampReadings } from "@/lib/engines/bearing-stamp";
import { audit } from "@/lib/audit";
import { storage } from "@/lib/storage";

/**
 * READ A BEARING STAMP FROM A PHOTOGRAPH
 *
 * What this endpoint deliberately does NOT do is write a designation.
 *
 * A designation is dimensions — 6203 is a 17 mm bore, 6208 is a 40 mm one —
 * and the mating analysis reasons about the fit from it. So a model reading
 * characters off a photograph produces candidates and nothing else; the
 * machinist confirms one against the bearing in their hand, through the
 * ordinary save on the feature page, and only then is anything stored.
 *
 * The photograph is stored either way. Even with no vision model connected it
 * is a record of the actual bearing that the machinist can read themselves,
 * which is worth more than nothing.
 */

const MAX_BYTES = 8 * 1024 * 1024;
const ALLOWED = ["image/jpeg", "image/png", "image/webp"];

export async function POST(request: Request, ctx: { params: Promise<{ fid: string }> }) {
  const { fid } = await ctx.params;
  const gate = await requireWriteApi();
  if ("denied" in gate) return gate.denied;
  const user = gate.user;

  // The feature is resolved through its revision's part, against the session's
  // organisation. Feature carries no organizationId of its own.
  const feature = await db.feature.findFirst({
    where: { id: fid, partRevision: { part: { organizationId: user.organizationId } } },
    select: { id: true, label: true, matingComponent: true, partRevision: { select: { partId: true } } },
  });
  if (!feature) return NextResponse.json({ error: "Feature not found." }, { status: 404 });

  const form = await request.formData().catch(() => null);
  const file = form?.get("photo");
  if (!(file instanceof File)) return NextResponse.json({ error: "Attach a photograph of the bearing." }, { status: 400 });
  if (file.size > MAX_BYTES) return NextResponse.json({ error: "Photograph exceeds the 8 MB limit." }, { status: 400 });
  if (!ALLOWED.includes(file.type)) {
    return NextResponse.json({ error: `Unsupported image type "${file.type}". Use JPEG, PNG or WebP.` }, { status: 400 });
  }

  const data = Buffer.from(await file.arrayBuffer());
  const bytes = new Uint8Array(data);
  const put = await storage.put(user.organizationId, file.name, data);
  const stored = await db.uploadedAsset.create({
    data: {
      organizationId: user.organizationId,
      partId: feature.partRevision.partId,
      kind: "BEARING_STAMP",
      filename: file.name.slice(0, 200),
      mimeType: file.type,
      size: put.size,
      checksum: put.checksum,
      storageKey: put.storageKey,
      uploadedBy: user.id,
      privacy: "PRIVATE",
      processingState: "STORED",
    },
  });

  const provider = await getAiProvider();
  const reading = await provider.readBearingStamp({
    mediaType: file.type,
    base64: Buffer.from(bytes).toString("base64"),
  });

  // Resolved against CANVAS's own catalogue, in code. The model never states a
  // bore, and a designation the catalogue does not hold is reported as unknown
  // rather than given invented dimensions.
  const candidates = resolveStampReadings(reading.readings);

  await audit({
    organizationId: user.organizationId,
    userId: user.id,
    // The model did the reading. That it produced nothing storable is the
    // point: a candidate is not a value until a human accepts one.
    actorType: "AI",
    entityType: "Feature",
    entityId: feature.id,
    action: "GENERATE",
    reason: reading.connected
      ? `Read a bearing stamp photograph: ${candidates.length} candidate(s), none stored.`
      : "Stored a bearing stamp photograph. No vision model is connected, so nothing was read from it.",
  });

  return NextResponse.json({
    photoId: stored.id,
    photoUrl: `/api/assets/${encodeURIComponent(stored.storageKey)}`,
    connected: reading.connected,
    note: reading.note,
    candidates,
  });
}
