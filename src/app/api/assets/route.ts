import { NextResponse } from "next/server";
import {requireWriteApi, requireSessionApi } from "@/lib/auth";
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
  const gate = await requireWriteApi();
  if ("denied" in gate) return gate.denied;
  const user = gate.user;
  const form = await request.formData();

  const files = form.getAll("files").filter((f): f is File => f instanceof File);
  if (files.length === 0) return NextResponse.json({ error: "No files supplied." }, { status: 400 });
  if (files.length > 24) return NextResponse.json({ error: "Maximum 24 files per upload." }, { status: 400 });

  const setupIdRaw = form.get("setupId") ? String(form.get("setupId")) : null;
  const kind = setupIdRaw ? "SETUP_PHOTO" : String(form.get("kind") ?? "OTHER");
  const postedPartId = form.get("partId") ? String(form.get("partId")) : null;
  const viewLabel = form.get("viewLabel") ? String(form.get("viewLabel")) : null;
  const scaleReference = form.get("scaleReference") ? String(form.get("scaleReference")) : null;

  /*
   * A setup photograph is pinned to a setup, and Setup carries no
   * organizationId of its own — it is reached through its revision's part. So
   * the id is resolved along that chain from the SESSION's organisation, and
   * the part id is then taken FROM THE RESOLVED ROW rather than from the
   * form. Honouring a posted part id here would let a caller pair another
   * shop's setup with a part of their own.
   */
  let setupId: string | null = null;
  let partId = postedPartId;
  if (setupIdRaw) {
    const owned = await db.setup.findFirst({
      where: { id: setupIdRaw, partRevision: { part: { organizationId: user.organizationId } } },
      select: { id: true, partRevision: { select: { partId: true } } },
    });
    if (!owned) return NextResponse.json({ error: "Setup not found." }, { status: 404 });
    setupId = owned.id;
    partId = owned.partRevision.partId;
  } else if (partId) {
    // A part id from the client is only honoured after confirming it belongs
    // to this organisation.
    const owned = await db.part.findFirst({ where: { id: partId, organizationId: user.organizationId }, select: { id: true } });
    if (!owned) return NextResponse.json({ error: "Part not found." }, { status: 404 });
  }

  const errors: string[] = [];
  const created: string[] = [];

  for (const file of files) {
    // A setup photograph is a photograph. validateUpload accepts STEP and
    // octet-stream, which are not pictures of a vise.
    if (setupId && !file.type.startsWith("image/")) {
      errors.push(`${file.name}: a setup photograph must be an image, not ${file.type || "an unnamed type"}.`);
      continue;
    }
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
        setupId,
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
      reason: setupId ? "Setup photograph recorded at the machine" : `Uploaded as ${kind}`,
    });
  }

  return NextResponse.json({ count: created.length, assetIds: created, errors }, { status: errors.length && !created.length ? 400 : 200 });
}

export async function GET() {
  const gate = await requireSessionApi();
  if ("denied" in gate) return gate.denied;
  const user = gate.user;
  const assets = await db.uploadedAsset.findMany({
    where: { organizationId: user.organizationId },
    orderBy: { createdAt: "desc" },
    take: 100,
  });
  return NextResponse.json({ assets });
}
