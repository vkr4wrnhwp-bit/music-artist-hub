import { NextResponse } from "next/server";
import { requireUser } from "@/lib/auth";
import { loadRevision, getTools, getMachines, getMaterials } from "@/lib/data";
import { parseNC } from "@/lib/nc/parse";
import { analyzeNC } from "@/lib/nc/analyze";
import { analyzeLoad, type LoadContext } from "@/lib/nc/load";

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

  const [tools, machines, materials] = await Promise.all([
    getTools(user.organizationId),
    getMachines(user.organizationId),
    getMaterials(user.organizationId),
  ]);
  const toolDiameters: Record<number, number> = {};
  const loadTools: LoadContext["tools"] = {};
  for (const t of tools) {
    toolDiameters[t.toolNumber] = t.diameter;
    loadTools[t.toolNumber] = { diameter: t.diameter, flutes: t.flutes, chiploadMin: t.chiploadMin, chiploadMax: t.chiploadMax };
  }
  // Material by name match against the recorded intent — no match, no energy.
  const materialName = revision.intent.material.value ?? "";
  const material = materials.find((m) => materialName.toLowerCase().includes(m.name.toLowerCase().split(" ")[0]) || m.name.toLowerCase().includes(materialName.toLowerCase().split(" ")[0] ?? "∅"));

  const preset = (new URL(request.url).searchParams.get("preset") ?? "BALANCED") as LoadContext["preset"];
  const stock = revision.stock ? { x: revision.stock.x, y: revision.stock.y, z: revision.stock.z } : null;

  const parsed = parseNC(await file.text());
  const analysis = analyzeNC(parsed, {
    stock,
    toolDiameters,
    rapidRate: machines[0]?.maxRapid ?? 600,
    axisAccel: machines[0]?.axisAccel ?? null,
  });
  const load = analyzeLoad(parsed, {
    stock,
    tools: loadTools,
    specificEnergy: material?.specificEnergy ?? null,
    machineMaxFeed: machines[0]?.maxFeed ?? 300,
    preset: ["CONSERVATIVE", "BALANCED", "AGGRESSIVE", "LIGHTS_OUT"].includes(preset) ? preset : "BALANCED",
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
    load: {
      bands: load.segments.map((s) => s.band),
      proposals: load.proposals,
      totalProposedSecondsSaved: load.totalProposedSecondsSaved,
      gaps: load.gaps,
      developmentAnalysis: load.developmentAnalysis,
    },
    context: {
      stockBound: Boolean(revision.stock),
      toolsKnown: Object.keys(toolDiameters).length,
      rapidRate: machines[0]?.maxRapid ?? 600,
      machine: machines[0] ? `${machines[0].manufacturer} ${machines[0].model}` : null,
    },
  });
}

const r = (v: number) => Number(v.toFixed(4));
