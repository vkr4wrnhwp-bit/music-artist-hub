import { HeightField, type StockDims } from "@/lib/sim/stock-removal";
import type { NCSegment, ParsedNC } from "./parse";
import { timePath } from "./time";

/**
 * NC ANALYSIS — Phase 4B: cycle-time breakdown and air-cut detection
 *
 * Timing is distance over feed, rapids at the machine rapid rate, dwells at
 * face value — the same arithmetic the CAM engine uses, and it carries the
 * same stated limit: no acceleration model exists, so figures overstate on
 * short-segment paths and every total says so.
 *
 * Air cutting is REPLAY-PROVEN when stock and tool diameters are bound: the
 * parsed motion runs through the same height field the simulator uses, and
 * a feed move that removes zero material is air by construction — verdict
 * CONFIDENT. Without stock, only geometry heuristics remain and nothing
 * rises above REVIEW. Without a tool diameter for a T number, the replay
 * cannot run that tool's motion and says INSUFFICIENT DATA rather than
 * assuming a cutter.
 */

export type FindingVerdict = "CONFIDENT" | "REVIEW" | "INSUFFICIENT_DATA";

export interface NCFinding {
  kind: "AIR_CUTTING" | "EXCESSIVE_RETRACT" | "SLOW_LINKING_MOVE" | "UNKNOWN_CONTEXT";
  verdict: FindingVerdict;
  line: number;
  toolNumber: number;
  seconds: number;
  detail: string;
  assumptions: string[];
}

export interface ToolTimeBreakdown {
  toolNumber: number;
  cutMinutes: number;
  rapidMinutes: number;
  dwellMinutes: number;
  segments: number;
}

export interface NCAnalysis {
  totalMinutes: number;
  cutMinutes: number;
  rapidMinutes: number;
  dwellMinutes: number;
  perTool: ToolTimeBreakdown[];
  findings: NCFinding[];
  /** Findings grand total of recoverable seconds (sum of finding.seconds). */
  recoverableSeconds: number;
  assumptions: string[];
  /** Extents of the parsed motion, for the backplot. */
  extents: { minX: number; maxX: number; minY: number; maxY: number; minZ: number; maxZ: number };
}

export interface AnalysisContext {
  /** Stock bound from the part. Absent → air-cut is heuristic only. */
  stock: StockDims | null;
  /** Tool diameters by T number, from the shop's tool table. */
  toolDiameters: Record<number, number>;
  rapidRate: number;
  /**
   * Axis acceleration in in/s², from the machine record. Null means not
   * recorded: timing falls back to distance-over-feed and the assumptions
   * say so — the value is never guessed.
   */
  axisAccel?: number | null;
}

const AIR_MIN_SECONDS = 0.5; // below this a finding is noise, not a saving

export function analyzeNC(parsed: ParsedNC, ctx: AnalysisContext): NCAnalysis {
  const accel = ctx.axisAccel ?? null;
  const assumptions = [
    accel !== null
      ? `Trapezoidal acceleration model at ${accel} in/s² (machine record) with cos-scaled junction velocities — DEVELOPMENT ANALYSIS, not validated against this machine's control. Jerk, per-axis limits and look-ahead are not modelled; dense 3D paths run slower than this estimate.`
      : "No axis acceleration recorded for this machine: times are distance over feed and overstate savings on short segments. Record axisAccel on the machine to enable the trapezoidal model.",
    "Work-offset origin taken as program zero with Z0 at the stock top.",
  ];
  if (parsed.workOffsetsSeen.length > 1) assumptions.push("Multiple work offsets — spatial findings downgraded to REVIEW.");
  const multiOffset = parsed.workOffsetsSeen.length > 1;

  /* ---- timing ---- */
  const perTool = new Map<number, ToolTimeBreakdown>();
  let cutMin = 0, rapidMin = 0, dwellMin = 0;
  const ext = { minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity, minZ: Infinity, maxZ: -Infinity };

  // With a recorded acceleration the whole path is timed as one motion
  // profile; without one, each segment is distance over feed. Both paths
  // produce a per-segment minutes array so the findings below can price a
  // segment consistently with the totals.
  const flatSegTime = (s: NCSegment): number => {
    if (s.kind === "DWELL") return (s.dwellSeconds ?? 0) / 60;
    const dist = Math.hypot(s.x1 - s.x0, s.y1 - s.y0, s.z1 - s.z0);
    if (dist === 0) return 0;
    return dist / Math.max(1, s.feed === null ? ctx.rapidRate : s.feed);
  };
  const segMinutes: number[] =
    accel !== null
      ? timePath(parsed.segments, accel, ctx.rapidRate).seconds.map((s) => s / 60)
      : parsed.segments.map(flatSegTime);

  for (const [si, s] of parsed.segments.entries()) {
    const t = segMinutes[si];
    const row = perTool.get(s.toolNumber) ?? { toolNumber: s.toolNumber, cutMinutes: 0, rapidMinutes: 0, dwellMinutes: 0, segments: 0 };
    row.segments++;
    if (s.kind === "DWELL") { dwellMin += t; row.dwellMinutes += t; }
    else if (s.feed === null) { rapidMin += t; row.rapidMinutes += t; }
    else { cutMin += t; row.cutMinutes += t; }
    perTool.set(s.toolNumber, row);
    for (const [px, py, pz] of [[s.x0, s.y0, s.z0], [s.x1, s.y1, s.z1]] as const) {
      ext.minX = Math.min(ext.minX, px); ext.maxX = Math.max(ext.maxX, px);
      ext.minY = Math.min(ext.minY, py); ext.maxY = Math.max(ext.maxY, py);
      ext.minZ = Math.min(ext.minZ, pz); ext.maxZ = Math.max(ext.maxZ, pz);
    }
  }

  /* ---- findings ---- */
  const findings: NCFinding[] = [];
  const stockTop = 0; // by the stated Z0-at-stock-top assumption

  // Replay for air-cut proof, when context allows.
  let field: HeightField | null = null;
  const missingTools = new Set<number>();
  if (ctx.stock) {
    field = new HeightField(ctx.stock, 200);
  } else {
    assumptions.push("No stock bound — air cutting cannot be proven, retract findings are heuristic.");
  }

  for (const [si, s] of parsed.segments.entries()) {
    const t = segMinutes[si] * 60; // seconds
    if (s.kind === "DWELL") continue;

    if (s.feed !== null && !s.tapping) {
      // Feed move fully above the stock top: a linking move at cutting feed.
      if (s.z0 >= stockTop - 1e-9 && s.z1 >= stockTop - 1e-9) {
        const rapidT = (Math.hypot(s.x1 - s.x0, s.y1 - s.y0, s.z1 - s.z0) / ctx.rapidRate) * 60;
        const saved = t - rapidT;
        if (saved > AIR_MIN_SECONDS) {
          findings.push({
            kind: "SLOW_LINKING_MOVE",
            verdict: multiOffset ? "REVIEW" : ctx.stock ? "CONFIDENT" : "REVIEW",
            line: s.line, toolNumber: s.toolNumber, seconds: round1(saved),
            detail: `Feed move at F${s.feed.toFixed(0)} entirely above the stock top — a rapid does the same job.`,
            assumptions: ["Z0 is the stock top."],
          });
        }
      } else if (field) {
        // Replay: does this feed move remove anything?
        const dia = ctx.toolDiameters[s.toolNumber];
        if (dia === undefined) {
          missingTools.add(s.toolNumber);
        } else {
          const before = field.removedVolume;
          replayCut(field, s, dia / 2, ctx.stock!);
          if (field.removedVolume - before < 1e-9 && t > AIR_MIN_SECONDS) {
            findings.push({
              kind: "AIR_CUTTING",
              verdict: multiOffset || s.comped ? "REVIEW" : "CONFIDENT",
              line: s.line, toolNumber: s.toolNumber, seconds: round1(t * 0.8),
              detail: `Feed move removes no material in the stock replay — ${t.toFixed(1)}s of cutting feed in air.`,
              assumptions: ["Replay-proven against the bound stock at the height-field resolution.", "80% of the segment time counted as recoverable."],
            });
          }
        }
      }
    }

    // Excessive retract: rapids climbing far above the stock.
    if (s.feed === null && s.z1 > stockTop + 0.5 && s.z1 > s.z0) {
      const excess = s.z1 - (stockTop + 0.25);
      const saved = (excess / ctx.rapidRate) * 60 * 2; // up and back down
      if (saved > AIR_MIN_SECONDS) {
        findings.push({
          kind: "EXCESSIVE_RETRACT",
          verdict: ctx.stock ? "REVIEW" : "REVIEW",
          line: s.line, toolNumber: s.toolNumber, seconds: round1(saved),
          detail: `Retract to Z${s.z1.toFixed(3)} — ${excess.toFixed(2)}" above a 0.25" clearance plane. REVIEW: clamps or obstacles may require it.`,
          assumptions: ["A 0.25\" clearance plane clears this setup — verify against fixtures."],
        });
      }
    }
  }

  if (missingTools.size > 0) {
    findings.push({
      kind: "UNKNOWN_CONTEXT",
      verdict: "INSUFFICIENT_DATA",
      line: 0,
      toolNumber: [...missingTools][0],
      seconds: 0,
      detail: `No tool diameter for T${[...missingTools].join(", T")} — their motion cannot be replayed against stock, so air-cut findings for these tools do not exist rather than being guessed.`,
      assumptions: [],
    });
  }

  return {
    totalMinutes: round3(cutMin + rapidMin + dwellMin),
    cutMinutes: round3(cutMin),
    rapidMinutes: round3(rapidMin),
    dwellMinutes: round3(dwellMin),
    perTool: [...perTool.values()].sort((a, b) => a.toolNumber - b.toolNumber),
    findings: findings.sort((a, b) => b.seconds - a.seconds),
    recoverableSeconds: round1(findings.reduce((s, f) => s + f.seconds, 0)),
    assumptions,
    extents: ext,
  };
}

/** Sampled flat-bottom cut along a segment — same arithmetic as the simulator. */
function replayCut(field: HeightField, s: NCSegment, radius: number, stock: StockDims): void {
  const len = Math.hypot(s.x1 - s.x0, s.y1 - s.y0, s.z1 - s.z0);
  const steps = Math.max(1, Math.ceil(len / (field.cell * 0.5)));
  for (let k = 0; k <= steps; k++) {
    const f = k / steps;
    field.cut(
      s.x0 + (s.x1 - s.x0) * f,
      s.y0 + (s.y1 - s.y0) * f,
      s.z0 + (s.z1 - s.z0) * f + stock.z, // Z0-at-top → field measures from the base
      radius,
    );
  }
}

const round1 = (v: number) => Number(v.toFixed(1));
const round3 = (v: number) => Number(v.toFixed(3));
