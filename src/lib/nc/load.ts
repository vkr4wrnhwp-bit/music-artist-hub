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
  /**
   * Finish-pass protection, built deterministically from the part's own
   * critical features (bearing bores, seal surfaces, tight tolerances,
   * fine finishes). Cutting inside a region is NEVER given a proposal —
   * raise or reduce — automatically. Override is a separate human act.
   */
  protectedRegions?: ProtectedRegion[];
}

export interface ProtectedRegion {
  label: string;
  reason: string;
  centerX: number;
  centerY: number;
  /** Protection radius around the feature, inches (feature radius + tool allowance). */
  radius: number;
  /** Z span of the finish-critical material, program coordinates (top ≥ bottom). */
  zTop: number;
  zBottom: number;
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
  /** RAISE = light engagement, feed up. REDUCE = engagement spike, feed down. */
  kind: "RAISE" | "REDUCE";
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

export interface ProtectedHit {
  label: string;
  reason: string;
  lines: [number, number];
  segments: number;
}

export interface LoadAnalysis {
  segments: SegmentLoad[];
  proposals: FeedProposal[];
  totalProposedSecondsSaved: number;
  /** Finish-protected regions the program actually cuts in — reported, never modified. */
  protectedHits: ProtectedHit[];
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

  // Finish protection: a cut segment is protected when its endpoint lands
  // inside a region's XY circle within the region's Z span (small epsilon —
  // the finish allowance sits just above the final dimension).
  const regions = ctx.protectedRegions ?? [];
  const Z_EPS = 0.02;
  // XY distance from the SEGMENT to the region center — endpoints alone
  // would let a pass that crosses straight through a bore escape protection.
  const segDist = (x0: number, y0: number, x1: number, y1: number, cx: number, cy: number): number => {
    const dx = x1 - x0, dy = y1 - y0;
    const len2 = dx * dx + dy * dy;
    if (len2 < 1e-12) return Math.hypot(x0 - cx, y0 - cy);
    const t = Math.max(0, Math.min(1, ((cx - x0) * dx + (cy - y0) * dy) / len2));
    return Math.hypot(x0 + t * dx - cx, y0 + t * dy - cy);
  };
  const isProtected = (s: NCSegment): ProtectedRegion | null => {
    if (s.feed === null) return null;
    for (const r of regions) {
      const inXY = segDist(s.x0, s.y0, s.x1, s.y1, r.centerX, r.centerY) <= r.radius;
      // Z is tested as a SPAN, for the same reason XY is tested as a segment
      // above. Matching s.z1 alone protected a plunge that stopped inside the
      // region and let an identical one that carried on past the bottom of it
      // go free — a drill continuing through a protected bore, or a pass
      // stepping below the feature it just cut, escaped by finishing lower
      // than the region it travelled through.
      const zLo = Math.min(s.z0, s.z1);
      const zHi = Math.max(s.z0, s.z1);
      const inZ = zLo <= r.zTop + Z_EPS && zHi >= r.zBottom - Z_EPS;
      if (inXY && inZ) return r;
    }
    return null;
  };
  const protectedIdx = new Set<number>();
  const hitBy = new Map<string, ProtectedHit>();
  cuts.forEach((s, i) => {
    const r = isProtected(s);
    if (!r) return;
    protectedIdx.add(i);
    const h = hitBy.get(r.label) ?? { label: r.label, reason: r.reason, lines: [s.line, s.line] as [number, number], segments: 0 };
    h.segments++;
    h.lines = [Math.min(h.lines[0], s.line), Math.max(h.lines[1], s.line)];
    hitBy.set(r.label, h);
  });
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
      kind: "RAISE",
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
      load.band === "LIGHT" && s.feed !== null && !s.tapping && !s.comped && !protectedIdx.has(i) && ctx.tools[s.toolNumber] !== undefined;
    if (eligible && run && cuts[run.segs[run.segs.length - 1]].toolNumber === s.toolNumber && cuts[run.segs[0]].feed === s.feed) {
      run.segs.push(i);
    } else {
      flush();
      if (eligible) run = { segs: [i], s };
    }
  });
  flush();

  /* ---- REDUCE proposals: engagement spikes inside same-tool, same-feed runs ----
     A corner does not change chipload (F and S are constant) — what spikes is
     radial engagement, which the stock replay sees as MRR. Within each run,
     segments whose replayed MRR exceeds SPIKE_RATIO × the run median form a
     spike; the proposal brings the feed down in proportion, floored so the
     chip never thins below the insert's minimum. Hysteresis rules stop feed
     chatter: a spike must be long enough to matter and the delta big enough
     to be worth a word. CONTROLLED LOAD, NOT MAXIMUM LOAD. */
  const SPIKE_RATIO = 2.0;
  const MIN_SPIKE_LENGTH_IN = 0.08; // shorter than this, lookahead eats the change
  const MIN_DELTA = 0.12; // <12% feed change is chatter, not control
  {
    // Runs group same-tool, same-feed CUTTING segments; rapids and dwells
    // between passes are transparent — a multi-pass pocket is one run.
    const runs: number[][] = [];
    let cur: number[] = [];
    cuts.forEach((s, i) => {
      if (s.feed === null) return; // rapid — transparent
      const eligible = !s.tapping && !s.comped && ctx.tools[s.toolNumber] !== undefined;
      const continues =
        cur.length > 0 && cuts[cur[0]].toolNumber === s.toolNumber && cuts[cur[0]].feed === s.feed;
      if (eligible && continues) cur.push(i);
      else {
        if (cur.length > 0) runs.push(cur);
        cur = eligible ? [i] : [];
      }
    });
    if (cur.length > 0) runs.push(cur);

    for (const idxs of runs) {
      if (idxs.length < 3) continue;
      const first = cuts[idxs[0]];
      const tool = ctx.tools[first.toolNumber];
      if (!tool || first.feed === null) continue;
      // Plunges are excluded from spike analysis on both sides: a vertical
      // entry legitimately removes material fast and is not an XY engagement
      // spike — comparing wall cuts against plunges would hide real corners.
      const lateral = idxs.filter((k) => {
        const sg = cuts[k];
        return Math.abs(sg.z1 - sg.z0) < Math.hypot(sg.x1 - sg.x0, sg.y1 - sg.y0) * 3;
      });
      const mrrs = lateral.map((k) => segments[k].mrr).filter((v): v is number => v !== null && v > 1e-6);
      if (mrrs.length < 3) continue; // no replay data — never guess a spike
      const median = [...mrrs].sort((a, b) => a - b)[Math.floor(mrrs.length / 2)];
      if (median <= 1e-6) continue;

      let spike: number[] = [];
      const flushStretch = () => {
        if (spike.length === 0) return;
        const spikeIdxs = spike;
        spike = [];
        const segs = spikeIdxs.map((k) => cuts[k]);
        const length = segs.reduce((t, sg) => t + Math.hypot(sg.x1 - sg.x0, sg.y1 - sg.y0, sg.z1 - sg.z0), 0);
        if (length < MIN_SPIKE_LENGTH_IN) return;
        if (spikeIdxs.some((k) => protectedIdx.has(k))) return; // protection wins
        const peak = Math.max(...spikeIdxs.map((k) => segments[k].mrr ?? 0));
        const factor = Math.max(0.4, median / peak);
        const feed0 = segs[0].feed!;
        // Floor: never thin the chip below the insert minimum.
        const feedFloor = tool.chiploadMin * segs[0].spindleRPM * tool.flutes;
        const proposed = Math.max(Math.floor(feed0 * factor), Math.ceil(feedFloor));
        if (proposed >= feed0 * (1 - MIN_DELTA)) return; // hysteresis
        proposals.push({
          kind: "REDUCE",
          lines: [segs[0].line, segs[segs.length - 1].line],
          toolNumber: segs[0].toolNumber,
          originalFeed: Math.round(feed0),
          proposedFeed: proposed,
          estimatedSecondsSaved: 0, // control costs a little time; it buys the tool and the part
          reason: `Replayed removal rate spikes to ${(peak / median).toFixed(1)}× the run's median through this stretch — an engagement spike, corner or entry. Reducing feed here holds the load band instead of riding the spike.`,
          risk: "REVIEW",
          assumptions: [
            "Engagement from the height-field replay at its cell resolution — DEVELOPMENT load estimate.",
            `Floor at the insert's minimum chipload (${tool.chiploadMin.toFixed(4)}\"/tooth) — the chip never thins below cutting.`,
            `Controller lookahead not modelled; stretches shorter than ${MIN_SPIKE_LENGTH_IN}\" are never proposed.`,
          ],
          requiredEvidence: "Verify in simulation; listen to the corner on the first article. Spindle-load telemetry would make this measured.",
          geometryChanges: false,
        });
      };
      const lateralSet = new Set(lateral);
      for (const k of idxs) {
        const v = segments[k].mrr;
        if (lateralSet.has(k) && v !== null && v > median * SPIKE_RATIO) spike.push(k);
        else flushStretch();
      }
      flushStretch();
    }
  }

  return {
    segments,
    proposals: proposals.sort((a, b) => b.estimatedSecondsSaved - a.estimatedSecondsSaved),
    totalProposedSecondsSaved: Number(proposals.filter((p) => p.kind === "RAISE").reduce((t, p) => t + p.estimatedSecondsSaved, 0).toFixed(1)),
    protectedHits: [...hitBy.values()],
    gaps: [...gaps],
    developmentAnalysis: true,
  };
}
