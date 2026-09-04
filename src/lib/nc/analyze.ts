import { HeightField, type StockDims } from "@/lib/sim/stock-removal";
import type { NCSegment, ParsedNC } from "./parse";
import { timePath } from "./time";
import { REACH_CLEARANCE, reachesDepth } from "@/lib/domain/shop";
import { ACROSS_SHARE_THRESHOLD, summariseLoadDirection } from "./load-direction";
import { PROGRAM_ORIGIN } from "@/lib/program-origin";

/** Stated fallback when a part names no machine. Never presented as machine data. */
export const DEFAULT_RAPID_IPM = 600;

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
  kind:
    | "AIR_CUTTING"
    | "EXCESSIVE_RETRACT"
    | "SLOW_LINKING_MOVE"
    | "UNKNOWN_CONTEXT"
    | "TOOL_REACH_REVIEW"
    | "SEQUENCING_OPPORTUNITY"
    | "WORKHOLDING_LOAD_DIRECTION_REVIEW";
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
  /**
   * Checks CANVAS did NOT run, and why. A check that is silently absent reads
   * as a check that passed — the same shape `ReviewResult` uses.
   */
  checksSkipped: { check: string; reason: string }[];
  /** Extents of the parsed motion, for the backplot. */
  extents: { minX: number; maxX: number; minY: number; maxY: number; minZ: number; maxZ: number };
}

export interface AnalysisContext {
  /** Stock bound from the part. Absent → air-cut is heuristic only. */
  stock: StockDims | null;
  /** Tool diameters by T number, from the shop's tool table. */
  toolDiameters: Record<number, number>;
  /**
   * Stickout and flute length by T number, from the crib. Optional: a caller
   * that has no crib gets no reach findings rather than invented ones.
   */
  toolGeometry?: Record<number, { description: string; fluteLength: number; stickout: number; source?: "CRIB" | "TOOL_LIST" }>;
  /**
   * Rapid traverse, in/min, from the machine record. Null when this part
   * names no machine — the analysis still runs, on a stated default, and
   * says so rather than attributing the number to a machine.
   */
  /**
   * How the part is held, when the setup records it. `jawAxis` is the datum
   * the load-direction check needs; without it the check reports that it did
   * not run rather than assuming an orientation.
   */
  workholding?: { jawAxis: string | null; hasPositiveStop: boolean; deviceDescription: string | null };
  rapidRate: number | null;
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
  const rapid = ctx.rapidRate ?? DEFAULT_RAPID_IPM;
  const assumptions = [
    accel !== null
      ? `Trapezoidal acceleration model at ${accel} in/s² (machine record) with cos-scaled junction velocities — DEVELOPMENT ANALYSIS, not validated against this machine's control. Jerk, per-axis limits and look-ahead are not modelled; dense 3D paths run slower than this estimate.`
      : "No axis acceleration recorded for this machine: times are distance over feed and overstate savings on short segments. Record axisAccel on the machine to enable the trapezoidal model.",
    // Stated from one place. This sentence and the setup sheet's and the post
    // header's used to be three separately-written strings describing the one
    // assumption that decides whether the part is cut in the right place.
    PROGRAM_ORIGIN.prose,
  ];
  if (ctx.rapidRate === null) {
    assumptions.push(
      `No machine record bound to this part: rapid traverse assumed at ${DEFAULT_RAPID_IPM} in/min. Rapid time, and therefore every savings figure below, is computed from that assumption and not from a machine.`,
    );
  }
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
    return dist / Math.max(1, s.feed === null ? rapid : s.feed);
  };
  const segMinutes: number[] =
    accel !== null
      ? timePath(parsed.segments, accel, rapid).seconds.map((s) => s / 60)
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
  /*
   * Declared here rather than assembled at the end, because a check that
   * decides at the point of running whether it could run has to be able to
   * say so there. The list used to be a fixed block at the bottom, which is
   * how it came to carry an entry claiming the load-direction check was
   * impossible after it had been built.
   */
  const checksSkipped: { check: string; reason: string }[] = [];
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
        const rapidT = (Math.hypot(s.x1 - s.x0, s.y1 - s.y0, s.z1 - s.z0) / rapid) * 60;
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
      const saved = (excess / rapid) * 60 * 2; // up and back down
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

  /* ---------------- Can the tool reach the depth it is asked to cut? ----
   *
   * CANVAS refuses a CAM operation whose depth beats the tool, and ran no such
   * check on a program a shop hands it — which is the program most likely to
   * have come from somebody else's post with somebody else's tool lengths.
   *
   * The stickout is the crib's record of the tool, not a measurement of what
   * is in the holder right now, and the holder body is not modelled. This is
   * the stickout-against-depth check, not a collision solve, and it says so.
   */
  const geometry = ctx.toolGeometry;
  if (geometry) {
    const deepest = new Map<number, { depth: number; line: number }>();
    for (const seg of parsed.segments) {
      if (seg.feed === null || seg.toolNumber === 0) continue;
      const depth = -Math.min(seg.z0, seg.z1);
      const held = deepest.get(seg.toolNumber);
      if (!held || depth > held.depth) deepest.set(seg.toolNumber, { depth, line: seg.line });
    }
    for (const [toolNumber, { depth, line }] of [...deepest].sort((a, b) => a[0] - b[0])) {
      if (depth <= 0) continue;
      const g = geometry[toolNumber];
      // No crib record: already covered by UNKNOWN_CONTEXT. Nothing invented.
      if (!g) continue;
      // Each value is checked on its own. A tool list commonly carries a
      // stickout and no flute length, or the reverse, and a stickout of
      // 1.200 against a 1.500 cut is a reach problem whether or not the
      // flute length is known.
      const where = g.source === "TOOL_LIST" ? "the attached tool list" : "the crib";
      const short = g.stickout > 0 && !reachesDepth(g.stickout, depth);
      const pastFlute = g.fluteLength > 0 && depth > g.fluteLength;
      const unrecorded = [
        g.stickout <= 0 ? "stickout" : null,
        g.fluteLength <= 0 ? "flute length" : null,
      ].filter((x): x is string => x !== null);

      if (!short && !pastFlute) {
        if (unrecorded.length === 2) {
          findings.push({
            kind: "TOOL_REACH_REVIEW",
            verdict: "INSUFFICIENT_DATA",
            line,
            toolNumber,
            seconds: 0,
            detail: `T${toolNumber} ${g.description} has no stickout or flute length recorded — reach was not checked against the ${depth.toFixed(3)}″ it is programmed to cut.`,
            assumptions: [],
          });
        } else if (unrecorded.length === 1) {
          findings.push({
            kind: "TOOL_REACH_REVIEW",
            verdict: "INSUFFICIENT_DATA",
            line,
            toolNumber,
            seconds: 0,
            detail: `T${toolNumber} ${g.description} clears the ${depth.toFixed(3)}″ cut on the one figure ${where} carries, but its ${unrecorded[0]} is not recorded — half the reach check ran.`,
            assumptions: [],
          });
        }
        continue;
      }

      findings.push({
        kind: "TOOL_REACH_REVIEW",
        verdict: "REVIEW",
        line,
        toolNumber,
        seconds: 0,
        detail:
          `T${toolNumber} ${g.description} is programmed ${depth.toFixed(3)}″ deep. ` +
          (short
            ? `${where === "the crib" ? "The crib records" : "The attached tool list records"} ${g.stickout.toFixed(3)}″ of stickout, which leaves less than the ${REACH_CLEARANCE.toFixed(3)}″ clearance this shop works to. `
            : "") +
          (pastFlute ? `The cut is deeper than the ${g.fluteLength.toFixed(3)}″ flute length. ` : "") +
          (unrecorded.length === 1 ? `Its ${unrecorded[0]} is not recorded, so that half of the check did not run. ` : ""),
        assumptions: [
          "Depth is measured from program Z0, taken as the top of the stock.",
          g.source === "TOOL_LIST"
            ? `Stickout and flute length are the attached tool list's figures for T${toolNumber} — the programmer's intent, not a measurement of the tool now in the holder.`
            : `Stickout and flute length are the crib record for T${toolNumber}, not a measurement of the tool now in the holder.`,
          "The holder body is not modelled as geometry — this is the stickout-against-depth check, not a collision solve.",
        ],
      });
    }
  }

  /* ---------------- Which way does the cut push the part? ---------------- */

  /*
   * Direction, not magnitude. holding-margin.ts answers how many pounds and
   * says DEVELOPMENT ANALYSIS while it does; this answers which way, and the
   * program states that exactly in its own coordinates.
   *
   * A cut pushing along the jaw axis drives the part into a jaw, which is what
   * a vise is for. A cut pushing across it slides the part along the jaw faces
   * with nothing but friction resisting — which is how a part walks out of a
   * vise while every clamping number looks fine.
   */
  const jawAxisRaw = ctx.workholding?.jawAxis;
  if (jawAxisRaw === "X" || jawAxisRaw === "Y") {
    const summary = summariseLoadDirection(parsed.segments, jawAxisRaw);
    if (summary.acrossShare !== null && summary.worst) {
      if (ctx.workholding?.hasPositiveStop) {
        // A positive stop reacts exactly this. Saying nothing would leave the
        // operator unsure whether the check ran.
        checksSkipped.push({
          check: "Cut direction against the jaws",
          reason: `${(summary.acrossShare * 100).toFixed(0)}% of the cutting pushes across the jaw faces, and this setup records a positive stop, which reacts that. Nothing raised.`,
        });
      } else if (summary.acrossShare > ACROSS_SHARE_THRESHOLD) {
        findings.push({
          kind: "WORKHOLDING_LOAD_DIRECTION_REVIEW",
          verdict: "REVIEW",
          line: summary.worst.line,
          toolNumber: 0,
          // Nothing is saved by changing which way a cut runs, and pricing it
          // would put a number on a decision about holding the part.
          seconds: 0,
          detail:
            `${(summary.acrossShare * 100).toFixed(0)}% of the cutting distance pushes the part across the jaw faces rather than into a jaw. ` +
            `The jaws close on ${jawAxisRaw}, and this setup records no positive stop, so friction is the only thing resisting that. ` +
            `The longest such move is at line ${summary.worst.line}.`,
          assumptions: [
            "The force direction is taken as the feed direction. A real cutting force has a radial component that rotates with engagement and reverses between climb and conventional; none of that is modelled.",
            "This says which way the load pushes, not whether the grip holds — the holding margin answers that, and answers it as a development analysis.",
            `The jaws are taken to close on ${jawAxisRaw} because the setup records it. Nothing here checks that against the fixture.`,
            "Plunges are excluded: they push the part down onto the parallels, which is the one direction a vise does not struggle with.",
          ],
        });
      }
    }
  } else {
    checksSkipped.push({
      check: "Cut direction against the jaws",
      reason:
        "The setup does not record which axis the jaws close on, so there is no way to tell a cut that drives the part into a jaw from one that slides it along the jaw faces. Record it on the setups page.",
    });
  }

  /* ---------------- Is a tool loaded more than once? ---------------- */
  if (parsed.toolChanges.length >= 2) {
    const loads = new Map<number, number[]>();
    for (const tc of parsed.toolChanges) {
      loads.set(tc.toolNumber, [...(loads.get(tc.toolNumber) ?? []), tc.line]);
    }
    const distinct = loads.size;
    for (const [toolNumber, lines] of [...loads].sort((a, b) => a[0] - b[0])) {
      if (lines.length < 2) continue;
      findings.push({
        kind: "SEQUENCING_OPPORTUNITY",
        verdict: "REVIEW",
        line: lines[1],
        toolNumber,
        // No tool-change time is recorded for this machine, so no saving is
        // claimed. Reporting a figure would be inventing one.
        seconds: 0,
        detail: `T${toolNumber} is loaded ${lines.length} times (lines ${lines.join(", ")}). The program makes ${parsed.toolChanges.length} tool changes for ${distinct} distinct tool${distinct === 1 ? "" : "s"}.`,
        assumptions: [
          "Detected from M6 tool calls only. An uploaded program carries no feature model, so CANVAS cannot tell a wasteful return from a deliberate one — rough then finish, or chamfer after tapping, are both correct.",
          "Reordering motion is outside this optimizer and is never emitted.",
          "No tool-change time is recorded for this machine, so no saving is claimed.",
        ],
      });
    }
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
    checksSkipped,
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
