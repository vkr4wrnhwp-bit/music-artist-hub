import { NextResponse } from "next/server";
import { requireSessionApi } from "@/lib/auth";
import { db } from "@/lib/db";
import { parseLatheNc, analyzeLatheNc } from "@/lib/manufacturing/turn/nc-parse";
import { optimizeTurnCycle, type TurnPreset } from "@/lib/manufacturing/turn/optimize";

const PRESETS: TurnPreset[] = ["CONSERVATIVE", "BALANCED", "AGGRESSIVE"];

/**
 * RUN IT PAST CANVAS — lathe. Parses an uploaded 2-axis program with the
 * refusal-first parser and returns the honest report: segments for the
 * backplot, refusals by line, findings with verdicts, ESTIMATED times with
 * assumptions. Organisation from the session; the chuck RPM limit for the
 * RPM_LIMIT_REVIEW finding comes from the part's own workholding record.
 */
export async function POST(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const gate = await requireSessionApi();
  if ("denied" in gate) return gate.denied;
  const user = gate.user;

  const part = await db.part.findFirst({ where: { id, organizationId: user.organizationId } });
  if (!part) return NextResponse.json({ error: "Part not found in this organisation" }, { status: 404 });

  const body = (await req.json().catch(() => null)) as { text?: string; preset?: string } | null;
  const preset: TurnPreset = PRESETS.includes(body?.preset as TurnPreset) ? (body!.preset as TurnPreset) : "BALANCED";
  const text = body?.text ?? "";
  if (!text.trim()) return NextResponse.json({ error: "Paste or upload a program first." }, { status: 400 });
  if (text.length > 2 * 1024 * 1024) return NextResponse.json({ error: "Program exceeds the 2 MB analysis limit." }, { status: 400 });

  const revision = await db.partRevision.findFirst({ where: { partId: part.id }, orderBy: { createdAt: "desc" } });
  const rot = revision
    ? await db.rotationalPart.findFirst({ where: { partRevisionId: revision.id, organizationId: user.organizationId } })
    : null;
  const holding = rot?.workholdingId
    ? await db.latheWorkholding.findFirst({ where: { id: rot.workholdingId, organizationId: user.organizationId } })
    : null;

  const parsed = parseLatheNc(text);
  const analysis = analyzeLatheNc(parsed, holding?.maxRPM ?? null);

  // Optimizer context from the shop's own turning tool records.
  const toolRows = await db.turningTool.findMany({ where: { organizationId: user.organizationId } });
  const tools = Object.fromEntries(
    toolRows.map((t) => [
      t.station.padStart(4, "0"),
      {
        station: t.station.padStart(4, "0"),
        description: t.description,
        surfaceSpeedMin: t.surfaceSpeedMin,
        surfaceSpeedMax: t.surfaceSpeedMax,
        feedPerRevMin: t.feedPerRevMin,
        feedPerRevMax: t.feedPerRevMax,
      },
    ]),
  );
  const optimization = optimizeTurnCycle(parsed, { tools, chuckMaxRpm: holding?.maxRPM ?? null, preset });

  return NextResponse.json({
    optimization,
    preset,
    parse: {
      lineCount: parsed.lineCount,
      segments: parsed.segments,
      refusals: parsed.refusals,
      warnings: parsed.warnings,
      toolCalls: parsed.toolCalls,
      cssRegions: parsed.cssRegions,
      sawG50: parsed.sawG50,
      units: parsed.units,
    },
    analysis,
    chuckMaxRpm: holding?.maxRPM ?? null,
  });
}
