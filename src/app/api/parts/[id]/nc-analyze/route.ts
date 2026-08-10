import { NextResponse } from "next/server";
import { requireUser } from "@/lib/auth";
import { loadRevision, getTools, getMachines } from "@/lib/data";
import { parseNC } from "@/lib/nc/parse";
import { analyzeNC } from "@/lib/nc/analyze";

/**
 * NC ANALYSIS — Phase 4A/4B endpoint
 *
 * Parses an uploaded program and analyzes it against THIS part's context:
 * stock from the revision, tool diameters matched by T number from the
 * shop's tool table, rapid rate from the machine record. Analysis only —
 * no optimization proposals exist yet, nothing is stored, and nothing here
 * touches an NC program row or a gate.
 */

const MAX_BYTES = 5 * 1024 * 1024;

export async function POST(request: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const user = await requireUser();
  const revision = await loadRevision(user.organizationId, id);
  if (!revision) return NextResponse.json({ error: "Part not found" }, { status: 404 });

  const form = await request.formData().catch(() => null);
  const file = form?.get("file");
  if (!(file instanceof File)) return NextResponse.json({ error: "Attach an .nc / .txt program." }, { status: 400 });
  if (file.size > MAX_BYTES) return NextResponse.json({ error: "File exceeds the 5 MB limit." }, { status: 400 });

  const [tools, machines] = await Promise.all([getTools(user.organizationId), getMachines(user.organizationId)]);
  const toolDiameters: Record<number, number> = {};
  for (const t of tools) toolDiameters[t.toolNumber] = t.diameter;

  const parsed = parseNC(await file.text());
  const analysis = analyzeNC(parsed, {
    stock: revision.stock ? { x: revision.stock.x, y: revision.stock.y, z: revision.stock.z } : null,
    toolDiameters,
    rapidRate: machines[0]?.maxRapid ?? 600,
  });

  return NextResponse.json({
    fileName: file.name,
    parse: {
      lineCount: parsed.lineCount,
      segments: parsed.segments.length,
      refusals: parsed.refusals,
      warnings: parsed.warnings,
      units: parsed.units,
      workOffsetsSeen: parsed.workOffsetsSeen,
      toolChanges: parsed.toolChanges,
    },
    // Backplot polylines, decimated for transport: [kind, x0,y0, x1,y1].
    backplot: parsed.segments
      .filter((s) => s.kind !== "DWELL")
      .map((s) => [s.feed === null ? 0 : 1, r(s.x0), r(s.y0), r(s.x1), r(s.y1)]),
    analysis,
    context: {
      stockBound: Boolean(revision.stock),
      toolsKnown: Object.keys(toolDiameters).length,
      rapidRate: machines[0]?.maxRapid ?? 600,
      machine: machines[0] ? `${machines[0].manufacturer} ${machines[0].model}` : null,
    },
  });
}

const r = (v: number) => Number(v.toFixed(4));
