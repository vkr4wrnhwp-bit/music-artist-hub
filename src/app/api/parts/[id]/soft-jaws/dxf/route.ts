import { NextResponse } from "next/server";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { buildPackage } from "@/lib/package";
import { generateSoftJaws } from "@/lib/engines/workholding";
import type { JawBlank } from "@/lib/domain/shop";
import { assembleSoftJawRequest } from "@/lib/soft-jaw-request";
import { softJawDxf } from "@/lib/export/soft-jaw-dxf";

/**
 * SOFT JAW DXF DOWNLOAD
 *
 * Regenerates the jaw pair with the same engine and the same assembler the
 * soft-jaws page uses, then draws the requested side. The drawing is never
 * stored — it is derived, so it can never be stale. Fixture geometry, not
 * NC: a plain download is the right transport, and the file carries its own
 * DEVELOPMENT caveats in the header.
 */

export async function GET(request: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const user = await requireUser();
  const pkg = await buildPackage(user.organizationId, id);
  if (!pkg) return NextResponse.json({ error: "Part not found" }, { status: 404 });

  const url = new URL(request.url);
  const side = url.searchParams.get("side") === "RIGHT" ? "RIGHT" : "LEFT";
  const blankRow = await db.jawBlank.findFirst({ where: { organizationId: user.organizationId } });
  const blank = blankRow ? ({ ...blankRow, material: blankRow.material as JawBlank["material"] } as JawBlank) : null;

  const num = (k: string) => {
    const v = url.searchParams.get(k);
    return v === null || v === "" ? null : Number(v);
  };
  const assembled = assembleSoftJawRequest(pkg, blank, {
    setupId: url.searchParams.get("setup"),
    grip: num("grip"),
    allowance: num("allowance"),
    clearance: num("clearance"),
    includeStop: url.searchParams.get("stop") === null ? null : url.searchParams.get("stop") !== "0",
    dir: url.searchParams.get("dir"),
  });
  if (!assembled) {
    return NextResponse.json({ error: "Soft jaws cannot be generated — setup, vise, blank or stock is missing." }, { status: 422 });
  }

  const result = generateSoftJaws(assembled.request);
  const geom = side === "LEFT" ? result.left : result.right;
  if (!result.ok || !geom) {
    return NextResponse.json({ error: result.errors.join(" ") || "Jaw generation failed." }, { status: 422 });
  }

  const dxf = softJawDxf(geom, {
    partName: pkg.revision.partName,
    partNumber: pkg.revision.partNumber,
    setupName: assembled.setupName,
    generatedAtIso: new Date().toISOString(),
  });

  const stem = (pkg.revision.partNumber ?? pkg.revision.partName).replace(/[^A-Za-z0-9-]+/g, "-");
  return new NextResponse(dxf, {
    headers: {
      "content-type": "application/dxf",
      "content-disposition": `attachment; filename="${stem}-soft-jaw-${side.toLowerCase()}.dxf"`,
    },
  });
}
