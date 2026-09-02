import { NextResponse } from "next/server";
import { createHash } from "node:crypto";
import { requireWriteApi } from "@/lib/auth";
import { db } from "@/lib/db";
import { loadRevision, getTools, getMachines, getMaterials, getSetups } from "@/lib/data";
import { selectPrimaryMachine } from "@/lib/package-selectors";
import { parseNC } from "@/lib/nc/parse";
import { analyzeNC } from "@/lib/nc/analyze";
import { analyzeLoad, type LoadContext } from "@/lib/nc/load";
import { buildProtectedRegions } from "@/lib/nc/protection";
import { evaluateAuditGates } from "@/lib/nc/audit-gates";
import { classifyOperations } from "@/lib/nc/classify";
import { inspectSource } from "@/lib/nc/source";

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
  const gate = await requireWriteApi();
  if ("denied" in gate) return gate.denied;
  const user = gate.user;
  const revision = await loadRevision(user.organizationId, id);
  if (!revision) return NextResponse.json({ error: "Part not found" }, { status: 404 });

  const form = await request.formData().catch(() => null);
  const file = form?.get("file");
  if (!(file instanceof File)) return NextResponse.json({ error: "Attach an .nc / .txt program." }, { status: 400 });
  if (file.size > MAX_BYTES) return NextResponse.json({ error: "File exceeds the 5 MB limit." }, { status: 400 });

  const [tools, machines, materials, shop] = await Promise.all([
    getTools(user.organizationId),
    getMachines(user.organizationId),
    getMaterials(user.organizationId),
    db.shop.findFirst({ where: { organizationId: user.organizationId } }),
  ]);
  const toolDiameters: Record<number, number> = {};
  const loadTools: LoadContext["tools"] = {};
  // Stickout and flute length, so the reach check has the crib's record of
  // the tool rather than nothing.
  const toolGeometry: Record<number, { description: string; fluteLength: number; stickout: number }> = {};
  for (const t of tools) {
    toolDiameters[t.toolNumber] = t.diameter;
    loadTools[t.toolNumber] = { diameter: t.diameter, flutes: t.flutes, chiploadMin: t.chiploadMin, chiploadMax: t.chiploadMax };
    toolGeometry[t.toolNumber] = { description: t.description, fluteLength: t.fluteLength, stickout: t.stickout };
  }
  // Material by name match against the recorded intent — no match, no energy.
  const materialName = revision.intent.material.value ?? "";
  const material = materials.find((m) => materialName.toLowerCase().includes(m.name.toLowerCase().split(" ")[0]) || m.name.toLowerCase().includes(materialName.toLowerCase().split(" ")[0] ?? "∅"));

  /*
   * The machine THIS part's setups name — not machines[0]. The audit gate
   * "Machine profile" is written to report INSUFFICIENT_DATA when no
   * machine is bound ("rapid rate and feed ceiling are defaults, not this
   * machine"), and the first-machine fallback defeated it: any shop owning
   * one machine record read as machine-known for every part, and the feed
   * ceiling that caps every raise proposal came from a machine that may
   * not be the one running the program.
   */
  const machine = selectPrimaryMachine(await getSetups(revision.revisionId), machines);

  const preset = (new URL(request.url).searchParams.get("preset") ?? "BALANCED") as LoadContext["preset"];
  const stock = revision.stock ? { x: revision.stock.x, y: revision.stock.y, z: revision.stock.z } : null;

  // The bytes, not a string. `file.text()` decodes as UTF-8 and substitutes
  // U+FFFD for anything that is not — silently losing a character somebody
  // typed into a comment — and says nothing about how the lines end, which is
  // the fact that decides whether the program can be read at all.
  const bytes = new Uint8Array(await file.arrayBuffer());
  const source = inspectSource(bytes);
  const originalText = source.text;
  // Over the bytes, so the receipt is of the file rather than of one decoding
  // of it. Identical to the previous digest for any ASCII program, which is
  // every NC file in practice.
  const digest = createHash("sha256").update(bytes).digest("hex");

  // Immutable original: one row per distinct program text per revision.
  // No code path updates an UPLOADED row — re-uploading the same bytes
  // reuses the row; different bytes are a different original.
  let uploaded = await db.nCProgram.findFirst({
    where: { partRevisionId: revision.revisionId, origin: "UPLOADED", sourceDigest: digest },
  });
  if (!uploaded) {
    uploaded = await db.nCProgram.create({
      data: {
        partRevisionId: revision.revisionId,
        postId: "upload",
        programNumber: /O(\d+)/.exec(originalText)?.[1] ?? "0000",
        code: originalText,
        certified: false,
        origin: "UPLOADED",
        sourceFilename: file.name.slice(0, 200),
        byteLength: file.size,
        sourceDigest: digest,
        sourceEncoding: source.encoding,
        lineEnding: source.lineEnding,
        controllerFamily: source.controllerFamily,
        generatedBy: user.id,
      },
    });
  }

  const parsed = parseNC(originalText);
  const analysis = analyzeNC(parsed, {
    stock,
    toolDiameters,
    toolGeometry,
    rapidRate: machine?.maxRapid ?? null,
    axisAccel: machine?.axisAccel ?? null,
  });
  const load = analyzeLoad(parsed, {
    stock,
    tools: loadTools,
    specificEnergy: material?.specificEnergy ?? null,
    machineMaxFeed: machine?.maxFeed ?? null,
    preset: ["CONSERVATIVE", "BALANCED", "AGGRESSIVE", "LIGHTS_OUT"].includes(preset) ? preset : "BALANCED",
    protectedRegions: buildProtectedRegions(revision.features),
  });

  const toolsInProgram = [...new Set(parsed.segments.map((s) => s.toolNumber).filter((t) => t > 0))];
  const gates = evaluateAuditGates({
    parsed,
    originalStored: true,
    source: { encoding: source.encoding, lineEnding: source.lineEnding, controllerFamily: source.controllerFamily },
    digest,
    toolsInProgram,
    toolsMapped: toolsInProgram.filter((t) => toolDiameters[t] !== undefined),
    machineKnown: machine !== null,
    axisAccelKnown: machine?.axisAccel != null,
    stockBound: Boolean(revision.stock),
    materialMatched: Boolean(material),
    compedSegments: parsed.segments.filter((s) => s.comped).length,
    tappingSegments: parsed.segments.filter((s) => s.tapping).length,
  });

  return NextResponse.json({
    fileName: file.name,
    uploadedProgramId: uploaded.id,
    digest,
    gates,
    source: {
      encoding: source.encoding,
      lineEnding: source.lineEnding,
      controllerFamily: source.controllerFamily,
      controllerEvidence: source.controllerEvidence,
    },
    parse: {
      lineCount: parsed.lineCount,
      segments: parsed.segments.length,
      refusals: parsed.refusals,
      warnings: parsed.warnings,
      units: parsed.units,
      workOffsetsSeen: parsed.workOffsetsSeen,
      toolChanges: parsed.toolChanges,
    },
    // Backplot polylines with source lines: [kind, line, x0,y0, x1,y1] —
    // the line number is what synchronizes scene and code in both directions.
    backplot: parsed.segments
      .filter((s) => s.kind !== "DWELL")
      .map((s) => [s.feed === null ? 0 : 1, s.line, r(s.x0), r(s.y0), r(s.x1), r(s.y1)]),
    // The immutable original's text, for the read-only block-synced viewer.
    code: originalText,
    operations: classifyOperations(parsed),
    analysis,
    load: {
      bands: load.segments.map((s) => s.band),
      proposals: load.proposals,
      totalProposedSecondsSaved: load.totalProposedSecondsSaved,
      protectedHits: load.protectedHits,
      gaps: load.gaps,
      developmentAnalysis: load.developmentAnalysis,
    },
    context: {
      stockBound: Boolean(revision.stock),
      toolsKnown: Object.keys(toolDiameters).length,
      rapidRate: machine?.maxRapid ?? null,
      machine: machine ? `${machine.manufacturer} ${machine.model}` : null,
      machineRatePerHour: shop?.machineRate ?? null,
    },
  });
}

const r = (v: number) => Number(v.toFixed(4));
