import type { LatheNCSegment, ParsedLatheNC } from "./nc-parse";

/**
 * TURNING CYCLE OPTIMIZER — DEVELOPMENT ANALYSIS.
 *
 * Reads a parsed 2-axis program against the shop's own turning tool
 * records and proposes exactly two kinds of change, both feed/speed-word
 * only — a proposal never touches a coordinate:
 *
 * 1. FEED — a contiguous run of cuts on one tool whose feed/rev sits
 *    below the insert's published window is rubbing more than cutting.
 *    Propose the middle of the window, capped by the preset multiplier.
 *
 * 2. CSS_CONVERSION — a G97 fixed-RPM region cutting across a wide
 *    diameter range wastes surface speed at the big end. Propose G96 at
 *    the surface speed the program already runs at its LARGEST diameter
 *    (so no point cuts faster than today), clamped by G50 at the chuck's
 *    recorded RPM limit. Without a recorded chuck limit the proposal is
 *    REFUSED — a clamp value is an engineering input, not a guess.
 *
 * Refused on principle, always:
 * - G32 thread passes (the feed is the pitch);
 * - segments without a tool record, S context, or feed (INSUFFICIENT
 *   DATA is a verdict, not an obstacle);
 * - anything above or inside the insert window already;
 * - per-minute-feed segments without live RPM context.
 *
 * All figures are ESTIMATED from the program's own words and published
 * insert data; nothing here is a measurement, and `developmentAnalysis`
 * says so non-optionally.
 */

export type TurnPreset = "CONSERVATIVE" | "BALANCED" | "AGGRESSIVE";

const PRESET_CAP: Record<TurnPreset, number> = {
  CONSERVATIVE: 1.15,
  BALANCED: 1.35,
  AGGRESSIVE: 1.6,
};

export interface TurnOptTool {
  station: string;
  description: string;
  surfaceSpeedMin: number | null;
  surfaceSpeedMax: number | null;
  feedPerRevMin: number | null;
  feedPerRevMax: number | null;
}

export interface TurnOptContext {
  /** Shop tool records keyed by 4-digit station ("0101"). */
  tools: Record<string, TurnOptTool>;
  /** Chuck's rated max RPM — from the workholding record, never invented. */
  chuckMaxRpm: number | null;
  preset: TurnPreset;
}

export type TurnBand = "LIGHT" | "TARGET" | "HIGH" | "REVIEW" | "UNKNOWN";

export interface TurnSegmentLoad {
  line: number;
  station: string | null;
  band: TurnBand;
  feedPerRev: number | null;
  sfm: number | null;
  note: string | null;
}

export interface TurnProposal {
  kind: "FEED" | "CSS_CONVERSION";
  lines: [number, number];
  station: string;
  detail: string;
  original: string;
  proposed: string;
  estimatedSecondsSaved: number;
  risk: "LOW" | "REVIEW";
  assumptions: string[];
  requiredEvidence: string;
  geometryChanges: false;
}

export interface TurnOptimization {
  segments: TurnSegmentLoad[];
  proposals: TurnProposal[];
  totalProposedSecondsSaved: number;
  gaps: string[];
  developmentAnalysis: true;
}

/** RPM in effect for a per-rev-feed cut, or null where context is missing. */
function rpmOf(s: LatheNCSegment, chuckMaxRpm: number | null): number | null {
  if (s.sWord === null || !s.spindleOn) return null;
  const meanDia = Math.max(0.05, (Math.abs(s.x0) + Math.abs(s.x1)) / 2);
  if (s.css) {
    const clamp = Math.min(s.maxRpmClamp ?? Infinity, chuckMaxRpm ?? Infinity);
    const rpm = Math.min((s.sWord * 12) / (Math.PI * meanDia), clamp);
    return Number.isFinite(rpm) && rpm > 0 ? rpm : null;
  }
  return s.sWord > 0 ? s.sWord : null;
}

function sfmOf(s: LatheNCSegment, chuckMaxRpm: number | null): number | null {
  if (s.css && s.sWord !== null) {
    // CSS: SFM is the S word itself, except where the clamp caps it.
    const rpm = rpmOf(s, chuckMaxRpm);
    if (rpm === null) return s.sWord;
    const meanDia = Math.max(0.05, (Math.abs(s.x0) + Math.abs(s.x1)) / 2);
    return Math.min(s.sWord, (Math.PI * meanDia * rpm) / 12);
  }
  const rpm = rpmOf(s, chuckMaxRpm);
  if (rpm === null) return null;
  const meanDia = Math.max(0.05, (Math.abs(s.x0) + Math.abs(s.x1)) / 2);
  return (Math.PI * meanDia * rpm) / 12;
}

function feedPerRevOf(s: LatheNCSegment, chuckMaxRpm: number | null): number | null {
  if (s.feed === null) return null;
  if (s.feedMode === "PER_REV") return s.feed;
  const rpm = rpmOf(s, chuckMaxRpm);
  return rpm !== null ? s.feed / rpm : null;
}

function cutDist(s: LatheNCSegment): number {
  return Math.hypot((s.x1 - s.x0) / 2, s.z1 - s.z0);
}

/** Minutes for a per-rev cut at a given feed/rev, from the segment's own spindle context. */
function cutMinutesAt(s: LatheNCSegment, feedPerRev: number, chuckMaxRpm: number | null): number | null {
  const rpm = rpmOf(s, chuckMaxRpm);
  if (rpm === null || feedPerRev <= 0) return null;
  return cutDist(s) / (feedPerRev * rpm);
}

export function optimizeTurnCycle(parsed: ParsedLatheNC, ctx: TurnOptContext): TurnOptimization {
  const gaps = new Set<string>();
  const segments: TurnSegmentLoad[] = [];
  const proposals: TurnProposal[] = [];
  const cap = PRESET_CAP[ctx.preset];

  const cuts = parsed.segments.filter((s) => s.kind !== "RAPID");
  if (parsed.refusals.length > 0) {
    gaps.add(`${parsed.refusals.length} refused block(s) — the optimizer sees only what the parser understood.`);
  }

  /* ---- per-segment load bands ---- */
  for (const s of cuts) {
    const station = s.station;
    const tool = station ? ctx.tools[station] : undefined;
    if (s.thread) {
      segments.push({ line: s.line, station, band: "REVIEW", feedPerRev: s.feed, sfm: sfmOf(s, ctx.chuckMaxRpm), note: "Thread pass — the feed is the pitch. Never optimized." });
      continue;
    }
    if (!tool) {
      if (station) gaps.add(`No tool record for T${station} — its cuts carry no verdict and no proposals.`);
      else gaps.add("Cutting moves before any T call carry no verdict.");
      segments.push({ line: s.line, station, band: "UNKNOWN", feedPerRev: null, sfm: null, note: "No tool record." });
      continue;
    }
    const fpr = feedPerRevOf(s, ctx.chuckMaxRpm);
    const sfm = sfmOf(s, ctx.chuckMaxRpm);
    if (fpr === null || sfm === null) {
      segments.push({ line: s.line, station, band: "UNKNOWN", feedPerRev: fpr, sfm, note: "Missing spindle or feed context — not guessed." });
      continue;
    }
    let band: TurnBand;
    let note: string | null = null;
    if (tool.feedPerRevMin === null || tool.feedPerRevMax === null) {
      band = "UNKNOWN";
      note = `T${station} has no published feed/rev window recorded.`;
      gaps.add(note);
    } else if (fpr < tool.feedPerRevMin) {
      band = "LIGHT";
      note = `Feed ${fpr.toFixed(4)}"/rev is below the insert's ${tool.feedPerRevMin.toFixed(4)}–${tool.feedPerRevMax.toFixed(4)}"/rev window.`;
    } else if (fpr <= tool.feedPerRevMax) {
      band = "TARGET";
    } else {
      band = "HIGH";
      note = `Feed ${fpr.toFixed(4)}"/rev exceeds the insert's window — review before running.`;
    }
    if (tool.surfaceSpeedMax !== null && sfm > tool.surfaceSpeedMax * 1.05) {
      band = "REVIEW";
      note = `${Math.round(sfm)} SFM exceeds the insert's rated ${Math.round(tool.surfaceSpeedMax)} SFM.`;
    }
    segments.push({ line: s.line, station, band, feedPerRev: Number(fpr.toFixed(5)), sfm: Number(sfm.toFixed(0)), note });
  }

  /* ---- FEED proposals: contiguous LIGHT runs, same tool + same feed word ---- */
  let run: number[] = [];
  const flushFeed = () => {
    if (run.length === 0) return;
    const first = cuts[run[0]];
    const tool = ctx.tools[first.station!];
    const fpr = feedPerRevOf(first, ctx.chuckMaxRpm)!;
    const target = (tool.feedPerRevMin! + tool.feedPerRevMax!) / 2;
    const proposed = Math.min(fpr * cap, target);
    if (proposed <= fpr * 1.02) { run = []; return; }
    let savedMin = 0;
    let ok = true;
    for (const i of run) {
      const before = cutMinutesAt(cuts[i], fpr, ctx.chuckMaxRpm);
      const after = cutMinutesAt(cuts[i], proposed, ctx.chuckMaxRpm);
      if (before === null || after === null) { ok = false; break; }
      savedMin += before - after;
    }
    const capped = fpr * cap < target - 1e-9;
    if (ok && savedMin * 60 >= 0.5) {
      proposals.push({
        kind: "FEED",
        lines: [cuts[run[0]].line, cuts[run[run.length - 1]].line],
        station: first.station!,
        detail: `Feed ${fpr.toFixed(4)}"/rev is below T${first.station}'s ${tool.feedPerRevMin!.toFixed(4)}–${tool.feedPerRevMax!.toFixed(4)}"/rev insert window — the cut is rubbing more than cutting.`,
        original: `F${fpr.toFixed(4)}`,
        proposed: `F${proposed.toFixed(4)}`,
        estimatedSecondsSaved: Number((savedMin * 60).toFixed(1)),
        risk: ctx.preset === "AGGRESSIVE" ? "REVIEW" : "LOW",
        assumptions: [
          "Feed/rev from the program's own F and S words against the recorded insert window.",
          "Times from the same spindle model the cycle estimate uses — ESTIMATED, no acceleration model.",
          ...(capped ? [`Capped at ${cap}× by the ${ctx.preset} preset, below the window midpoint.`] : []),
        ],
        requiredEvidence: "Prove on the first article; watch surface finish and chip form at the new feed.",
        geometryChanges: false,
      });
    }
    run = [];
  };
  cuts.forEach((s, i) => {
    const load = segments[i];
    const eligible = load.band === "LIGHT" && !s.thread && s.station !== null && s.feed !== null;
    if (eligible && run.length > 0 && cuts[run[run.length - 1]].station === s.station && cuts[run[0]].feed === s.feed && cuts[run[0]].feedMode === s.feedMode) {
      run.push(i);
    } else {
      flushFeed();
      if (eligible) run = [i];
    }
  });
  flushFeed();

  /* ---- CSS_CONVERSION: fixed-RPM regions across a wide diameter range ---- */
  // Group contiguous non-CSS, non-thread cuts by station.
  const regions: number[][] = [];
  let region: number[] = [];
  cuts.forEach((s, i) => {
    const eligible = !s.css && !s.thread && s.spindleOn && s.sWord !== null && s.feed !== null && s.feedMode === "PER_REV" && s.station !== null;
    if (eligible && region.length > 0 && cuts[region[region.length - 1]].station === s.station) region.push(i);
    else {
      if (region.length > 0) regions.push(region);
      region = eligible ? [i] : [];
    }
  });
  if (region.length > 0) regions.push(region);

  for (const reg of regions) {
    const segs = reg.map((i) => cuts[i]);
    const dias = segs.flatMap((s) => [Math.abs(s.x0), Math.abs(s.x1)]).filter((d) => d > 0.05);
    if (dias.length === 0) continue;
    const dMax = Math.max(...dias);
    const dMin = Math.max(0.05, Math.min(...dias));
    if (dMax / dMin < 1.5) continue; // narrow range — fixed RPM is fine
    const station = segs[0].station!;
    const tool = ctx.tools[station];
    const rpm = segs[0].sWord!;
    // SFM the program already accepts at its largest diameter — no point cuts faster.
    const sfm = (Math.PI * dMax * rpm) / 12;
    if (tool?.surfaceSpeedMax != null && sfm > tool.surfaceSpeedMax * 1.05) continue; // already over — not an optimization
    if (ctx.chuckMaxRpm === null) {
      gaps.add(`T${station} G97 region spans ⌀${dMin.toFixed(2)}–⌀${dMax.toFixed(2)} and could run CSS, but the chuck's max RPM is not recorded — CANVAS will not propose G96 without a real clamp value. Record the chuck limit on the workholding.`);
      continue;
    }
    // Retime the region: before at fixed rpm, after at CSS clamped to the chuck.
    let before = 0;
    let after = 0;
    let ok = true;
    for (const s of segs) {
      const fpr = s.feed!;
      const meanDia = Math.max(0.05, (Math.abs(s.x0) + Math.abs(s.x1)) / 2);
      const cssRpm = Math.min((sfm * 12) / (Math.PI * meanDia), ctx.chuckMaxRpm);
      if (rpm <= 0 || cssRpm <= 0) { ok = false; break; }
      before += cutDist(s) / (fpr * rpm);
      after += cutDist(s) / (fpr * cssRpm);
    }
    const savedSec = (before - after) * 60;
    if (!ok || savedSec < 1) continue;
    proposals.push({
      kind: "CSS_CONVERSION",
      lines: [segs[0].line, segs[segs.length - 1].line],
      station,
      detail: `G97 S${rpm} across ⌀${dMin.toFixed(2)}–⌀${dMax.toFixed(2)} leaves surface speed on the table at the small end. G96 at the ${Math.round(sfm)} SFM the program already runs at ⌀${dMax.toFixed(2)} keeps every point at or below today's speed while cutting the small diameters at full speed.`,
      original: `G97 S${rpm}`,
      proposed: `G50 S${ctx.chuckMaxRpm} / G96 S${Math.round(sfm)}`,
      estimatedSecondsSaved: Number(savedSec.toFixed(1)),
      risk: "REVIEW",
      assumptions: [
        `CSS RPM clamped at the chuck's recorded ${ctx.chuckMaxRpm} RPM limit.`,
        "Retimed with the same per-rev spindle model as the cycle estimate — ESTIMATED.",
        "Interrupted cuts, thin walls and workholding behaviour at higher RPM are not modelled — that is what the REVIEW risk means.",
      ],
      requiredEvidence: "Review against interrupted cuts and part geometry; prove on the first article before adopting.",
      geometryChanges: false,
    });
  }

  proposals.sort((a, b) => b.estimatedSecondsSaved - a.estimatedSecondsSaved);
  return {
    segments,
    proposals,
    totalProposedSecondsSaved: Number(proposals.reduce((t, p) => t + p.estimatedSecondsSaved, 0).toFixed(1)),
    gaps: [...gaps],
    developmentAnalysis: true,
  };
}
