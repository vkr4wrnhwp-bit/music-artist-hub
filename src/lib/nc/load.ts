import { HeightField, type StockDims } from "@/lib/sim/stock-removal";
import type { NCSegment, ParsedNC } from "./parse";

/**
 * LOAD MAP + FEED PROPOSALS — Phase 4D of the optimizer
 *
 * DEVELOPMENT ANALYSIS, like the holding model: the load figures here are
 * estimates from geometry and published tool data, not measurements — no
 * spindle telemetry exists yet, and nothing below claims otherwise.
 *
 * The arithmetic, all of it stated:
 * - Chipload = F / (S × flutes). Exact, from the program's own words and
 *   the tool record. The banding compares it to the tool's published
 *   chipload window.
 * - MRR per segment = replayed removed volume / segment time. Exact at the
 *   height-field resolution.
 * - Spindle power = MRR × material specific energy — the same model the
 *   cutting-force engine uses.
 *
 * Proposals are FEED-ONLY and refuse on principle:
 * - tapping segments: never (the feed is the thread);
 * - comped regions: never (the machine owns the real geometry);
 * - segments already in or above the target band: never;
 * - anything without tool + material context: never — INSUFFICIENT DATA is
 *   a verdict, not an obstacle to route around.
 * A proposal never touches a coordinate word. Geometry preservation in V1
 * is feed-only optimization by construction.
 */

export type LoadBand = "AIR" | "LIGHT" | "TARGET" | "HIGH" | "REVIEW";

export interface LoadToolContext {
  diameter: number;
  flutes: number;
  chiploadMin: number;
  chiploadMax: number;
}

export interface LoadContext {
  stock: StockDims | null;
  tools: Record<number, LoadToolContext>;
  /** hp per in³/min — from the material record. Null = no power estimate. */
  specificEnergy: number | null;
  machineMaxFeed: number;
  preset: "CONSERVATIVE" | "BALANCED" | "AGGRESSIVE" | "LIGHTS_OUT";
}

export interface SegmentLoad {
  index: number;
  line: number;
  band: LoadBand;
  chipload: number | null;
  mrr: number | null;
  spindlePowerHp: number | null;
}

export interface FeedProposal {
  lines: [number, number];
  toolNumber: number;
  originalFeed: number;
  proposedFeed: number;
  estimatedSecondsSaved: number;
  reason: string;
  risk: "LOW" | "REVIEW";
  assumptions: string[];
  requiredEvidence: string;
  geometryChanges: false;
}

export interface LoadAnalysis {
  segments: SegmentLoad[];
  proposals: FeedProposal[];
  totalProposedSecondsSaved: number;
  /** Why parts of the program got no load verdict. */
  gaps: string[];
  developmentAnalysis: true;
}

/** Feed multiplier ceiling per preset. LIGHTS_OUT is the most conservative:
 *  unattended running means nobody hears a bad cut. */
const PRESET_CAP: Record<LoadContext["preset"], number> = {
  CONSERVATIVE: 1.15,
  BALANCED: 1.35,
  AGGRESSIVE: 1.6,
  LIGHTS_OUT: 1.1,
};

export function analyzeLoad(parsed: ParsedNC, ctx: LoadContext): LoadAnalysis {
  const gaps = new Set<string>();
  const segments: SegmentLoad[] = [];
  const field = ctx.stock ? new HeightField(ctx.stock, 200) : null;
  if (!field) gaps.add("No stock bound — engagement cannot be replayed; bands are chipload-only where a tool is known.");
  if (ctx.specificEnergy === null) gaps.add("No material specific energy — spindle power is not estimated.");

  const cuts = parsed.segments.filter((s) => s.kind !== "DWELL");
  cuts.forEach((s, i) => {
    if (s.feed === null) {
      segments.push({ index: i, line: s.line, band: "AIR", chipload: null, mrr: null, spindlePowerHp: null });
      return;
    }
    const tool = ctx.tools[s.toolNumber];
    if (!tool) {
      gaps.add(`No tool record for T${s.toolNumber} — its segments carry no load verdict.`);
      segments.push({ index: i, line: s.line, band: "REVIEW", chipload: null, mrr: null, spindlePowerHp: null });
      return;
    }

    // Replayed removal for this segment.
    let removed: number | null = null;
    if (field && ctx.stock) {
      const before = field.removedVolume;
      const len = Math.hypot(s.x1 - s.x0, s.y1 - s.y0, s.z1 - s.z0);
      const steps = Math.max(1, Math.ceil(len / (field.cell * 0.5)));
      for (let k = 0; k <= steps; k++) {
        const f = k / steps;
        field.cut(s.x0 + (s.x1 - s.x0) * f, s.y0 + (s.y1 - s.y0) * f, s.z0 + (s.z1 - s.z0) * f + ctx.stock.z, tool.diameter / 2);
      }
      removed = field.removedVolume - before;
    }

    const minutes = Math.hypot(s.x1 - s.x0, s.y1 - s.y0, s.z1 - s.z0) / Math.max(1, s.feed);
    const mrr = removed !== null && minutes > 0 ? removed / minutes : null;
    const chipload = s.spindleRPM > 0 && tool.flutes > 0 ? s.feed / (s.spindleRPM * tool.flutes) : null;
    const power = mrr !== null && ctx.specificEnergy !== null ? mrr * ctx.specificEnergy : null;

    let band: LoadBand;
    if (mrr !== null && mrr < 1e-6) band = "AIR";
    else if (chipload === null) band = "REVIEW";
    else if (chipload < tool.chiploadMin * 0.6) band = "LIGHT";
    else if (chipload <= tool.chiploadMax) band = "TARGET";
    else if (chipload <= tool.chiploadMax * 1.3) band = "HIGH";
    else band = "REVIEW";

    segments.push({
      index: i, line: s.line, band,
      chipload: chipload !== null ? Number(chipload.toFixed(5)) : null,
      mrr: mrr !== null ? Number(mrr.toFixed(4)) : null,
      spindlePowerHp: power !== null ? Number(power.toFixed(2)) : null,
    });
  });

  /* ---- proposals: contiguous LIGHT runs, same tool and feed ---- */
  const proposals: FeedProposal[] = [];
  const cap = PRESET_CAP[ctx.preset];
  let run: { segs: number[]; s: NCSegment } | null = null;

  const flush = () => {
    if (!run || run.segs.length === 0) { run = null; return; }
    const first = cuts[run.segs[0]];
    const tool = ctx.tools[first.toolNumber];
    const chip = first.spindleRPM > 0 ? first.feed! / (first.spindleRPM * tool.flutes) : null;
    if (chip === null) { run = null; return; }
    // Target the middle of the published window, capped by preset and machine.
    const targetChip = (tool.chiploadMin + tool.chiploadMax) / 2;
    const proposed = Math.min(first.feed! * cap, first.feed! * (targetChip / chip), ctx.machineMaxFeed);
    if (proposed <= first.feed! * 1.02) { run = null; return; }
    let dist = 0;
    for (const idx of run.segs) {
      const s = cuts[idx];
      dist += Math.hypot(s.x1 - s.x0, s.y1 - s.y0, s.z1 - s.z0);
    }
    const saved = (dist / first.feed! - dist / proposed) * 60;
    if (saved < 0.5) { run = null; return; }
    const capped = proposed < first.feed! * (targetChip / chip) - 1e-9;
    proposals.push({
      lines: [cuts[run.segs[0]].line, cuts[run.segs[run.segs.length - 1]].line],
      toolNumber: first.toolNumber,
      originalFeed: Math.round(first.feed!),
      // Floor, not round: the preset cap is a ceiling, and rounding a feed
      // word up past it would breach the very limit the preset promises.
      proposedFeed: Math.floor(proposed),
      estimatedSecondsSaved: Number(saved.toFixed(1)),
      reason: `Chipload ${chip.toFixed(4)}" is below the tool's ${tool.chiploadMin.toFixed(4)}–${tool.chiploadMax.toFixed(4)}" window; the cut is rubbing more than cutting.`,
      risk: ctx.preset === "AGGRESSIVE" ? "REVIEW" : "LOW",
      assumptions: [
        "Chipload from programmed F and S with the recorded flute count.",
        "Engagement from the height-field replay at its cell resolution.",
        "No acceleration model — savings overstate on short segments.",
        ...(capped ? [`Capped at ${cap}× by the ${ctx.preset} preset, below the chipload-ideal feed.`] : []),
      ],
      requiredEvidence: "Verify in the stock-removal simulation, then prove on the first article — spindle-load telemetry would raise this to measured.",
      geometryChanges: false,
    });
    run = null;
  };

  cuts.forEach((s, i) => {
    const load = segments[i];
    const eligible =
      load.band === "LIGHT" && s.feed !== null && !s.tapping && !s.comped && ctx.tools[s.toolNumber] !== undefined;
    if (eligible && run && cuts[run.segs[run.segs.length - 1]].toolNumber === s.toolNumber && cuts[run.segs[0]].feed === s.feed) {
      run.segs.push(i);
    } else {
      flush();
      if (eligible) run = { segs: [i], s };
    }
  });
  flush();

  return {
    segments,
    proposals: proposals.sort((a, b) => b.estimatedSecondsSaved - a.estimatedSecondsSaved),
    totalProposedSecondsSaved: Number(proposals.reduce((t, p) => t + p.estimatedSecondsSaved, 0).toFixed(1)),
    gaps: [...gaps],
    developmentAnalysis: true,
  };
}
