import { NextResponse } from "next/server";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { storage } from "@/lib/storage";

/**
 * Asset read. The storage key alone is never sufficient — the asset row must
 * belong to the requesting user's organisation. This is the single place a
 * cross-tenant read could happen, so the check is explicit and unconditional.
 */
export async function GET(_request: Request, ctx: { params: Promise<{ key: string }> }) {
  const user = await requireUser();
  const { key } = await ctx.params;
  const storageKey = decodeURIComponent(key);

  const asset = await db.uploadedAsset.findFirst({
    where: { storageKey, organizationId: user.organizationId },
  });
  if (!asset) return NextResponse.json({ error: "Not found" }, { status: 404 });

  try {
    const data = await storage.get(storageKey);
    return new NextResponse(new Uint8Array(data), {
      headers: {
        "content-type": asset.mimeType,
        "content-length": String(asset.size),
        "cache-control": "private, max-age=3600",
        "content-disposition": `inline; filename="${asset.filename.replace(/"/g, "")}"`,
      },
    });
  } catch {
    return NextResponse.json({ error: "Object missing from storage" }, { status: 410 });
  }
}
