import { NextResponse } from "next/server";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { storage, validateUpload } from "@/lib/storage";

/**
 * Asset upload. Every file is validated, checksummed and scoped to the
 * uploading organisation. Nothing is interpreted here — storage and
 * interpretation are separate steps on purpose, so a stored photograph never
 * implies CANVAS has read geometry from it.
 */

export async function POST(request: Request) {
  const user = await requireUser();
  const form = await request.formData();

  const files = form.getAll("files").filter((f): f is File => f instanceof File);
  if (files.length === 0) return NextResponse.json({ error: "No files supplied." }, { status: 400 });
  if (files.length > 24) return NextResponse.json({ error: "Maximum 24 files per upload." }, { status: 400 });

  const kind = String(form.get("kind") ?? "OTHER");
  const partId = form.get("partId") ? String(form.get("partId")) : null;
  const viewLabel = form.get("viewLabel") ? String(form.get("viewLabel")) : null;
  const scaleReference = form.get("scaleReference") ? String(form.get("scaleReference")) : null;

  // A part id from the client is only honoured after confirming it belongs to
  // this organisation.
  if (partId) {
    const owned = await db.part.findFirst({ where: { id: partId, organizationId: user.organizationId }, select: { id: true } });
    if (!owned) return NextResponse.json({ error: "Part not found." }, { status: 404 });
  }

  const errors: string[] = [];
  const created: string[] = [];

  for (const file of files) {
    const problem = validateUpload(file);
    if (problem) {
      errors.push(problem);
      continue;
    }
    const data = Buffer.from(await file.arrayBuffer());
    const stored = await storage.put(user.organizationId, file.name, data);

    const asset = await db.uploadedAsset.create({
      data: {
        organizationId: user.organizationId,
        partId,
        kind,
        filename: file.name,
        mimeType: file.type || "application/octet-stream",
        size: stored.size,
        checksum: stored.checksum,
        storageKey: stored.storageKey,
        uploadedBy: user.id,
        privacy: "PRIVATE",
        processingState: "STORED",
        viewLabel,
        scaleReference,
      },
    });
    created.push(asset.id);

    await audit({
      organizationId: user.organizationId,
      userId: user.id,
      entityType: "UploadedAsset",
      entityId: asset.id,
      action: "CREATE",
      actorType: "HUMAN",
      newValue: file.name,
      reason: `Uploaded as ${kind}`,
    });
  }

  return NextResponse.json({ count: created.length, assetIds: created, errors }, { status: errors.length && !created.length ? 400 : 200 });
}

export async function GET() {
  const user = await requireUser();
  const assets = await db.uploadedAsset.findMany({
    where: { organizationId: user.organizationId },
    orderBy: { createdAt: "desc" },
    take: 100,
  });
  return NextResponse.json({ assets });
}
