/**
 * NC PARSER + INTERPRETER — Phase 4A of the load-aware optimizer
 *
 * Fanuc/Haas-style 3-axis word parser and modal interpreter. Text in,
 * absolute-inch motion segments out, every segment carrying the source line
 * range it came from. Deterministic, dependency-free, and honest about what
 * it refuses: macros, subprograms and off-plane arcs stop interpretation
 * with the line number, and cutter-comp regions are marked rather than
 * silently mis-modelled.
 *
 * Coordinate assumption, stated: the active work offset's origin is the
 * program zero, and Z0 is wherever the program says it is — conventionally
 * the part top. Binding to a part places the stock top at Z0; the analyzer
 * says so in its assumptions.
 *
 * V1 subset (see docs/LOAD_AWARE_NC_OPTIMIZER.md §4): G0/1/2/3, G17,
 * G20/21, G90/91, G54–G59 (multi-offset downgrades spatial findings),
 * G80/81/83 expanded, G84/G74 parsed and flagged NEVER-RETIME, G4 dwell,
 * F/S/T/M6, spindle and coolant M-codes. G41/G42 mark their region comped.
 */

export interface NCSegment {
  /** 1-indexed source lines this segment came from. */
  line: number;
  kind: "RAPID" | "CUT" | "ARC" | "DWELL";
  x0: number; y0: number; z0: number;
  x1: number; y1: number; z1: number;
  /** in/min; null for rapids. */
  feed: number | null;
  /** Dwell only: seconds. */
  dwellSeconds?: number;
  toolNumber: number;
  spindleRPM: number;
  /** Inside a G41/G42 region — findings here are REVIEW at best. */
  comped: boolean;
  /** Part of a tapping cycle — the optimizer must never retime it. */
  tapping: boolean;
}

export interface ParsedNC {
  segments: NCSegment[];
  toolChanges: { line: number; toolNumber: number }[];
  /** Hard stops: line + reason. A refusal ends interpretation there. */
  refusals: { line: number; reason: string }[];
  warnings: string[];
  units: "IN" | "MM";
  /** False when no G20/G21 appeared and inches were assumed. */
  unitsExplicit: boolean;
  workOffsetsSeen: string[];
  lineCount: number;
}

const ARC_CHORD_TOL = 0.001; // inches of chord deviation for tessellation

export function parseNC(text: string): ParsedNC {
  const lines = text.split(/\r?\n/);
  const segments: NCSegment[] = [];
  const toolChanges: { line: number; toolNumber: number }[] = [];
  const refusals: ParsedNC["refusals"] = [];
  const warnings = new Set<string>();
  const offsets = new Set<string>();

  // Modal state.
  let units: "IN" | "MM" = "IN";
  let unitsExplicit = false;
  let absolute = true;
  let motion: number | null = null; // sticky G0/1/2/3 or canned cycle
  let x = 0, y = 0, z = 0;
  let feed: number | null = null;
  let rpm = 0;
  let tool = 0;
  let comped = false;
  let plane: 17 | 18 | 19 = 17;
  let retractR = 0; // canned cycle R plane
  // The cycle's depth is modal too, and used to be re-read from the current
  // Z on every repeat. After the first hole the current Z IS the retract
  // plane, so a repeat position drilled from R to R — nothing — and the
  // program silently lost every hole after the first.
  let cycleZ: number | null = null;
  let cycleQ: number | null = null;
  let retractMode: 98 | 99 = 98;
  let initialZ = 0;

  const scale = () => (units === "MM" ? 1 / 25.4 : 1);

  outer: for (let li = 0; li < lines.length; li++) {
    const lineNo = li + 1;
    // Strip comments (both styles) and whitespace.
    const raw = lines[li].replace(/\(.*?\)/g, "").replace(/;.*$/, "").trim();
    if (!raw || raw === "%") continue;

    // Refusals: macros, control flow, subprograms.
    if (/[#]|IF\b|WHILE\b|GOTO\b/i.test(raw)) {
      refusals.push({ line: lineNo, reason: "Macro or control flow — not supported in V1" });
      break;
    }
    if (/\bM9[78]\b/.test(raw)) {
      refusals.push({ line: lineNo, reason: "Subprogram call — not supported in V1" });
      break;
    }

    // Word scan.
    const words = [...raw.matchAll(/([A-Z])\s*(-?\d*\.?\d+)/gi)].map((m) => ({
      letter: m[1].toUpperCase(),
      value: parseFloat(m[2]),
    }));
    if (words.length === 0) continue;

    let unknownG: number | null = null;
    const gs = words.filter((w) => w.letter === "G").map((w) => w.value);
    const get = (l: string) => words.find((w) => w.letter === l)?.value;

    for (const g of gs) {
      if (g === 20) { units = "IN"; unitsExplicit = true; }
      else if (g === 21) { units = "MM"; unitsExplicit = true; }
      else if (g === 90) absolute = true;
      else if (g === 91) absolute = false;
      else if (g === 17 || g === 18 || g === 19) plane = g as 17;
      else if (g >= 54 && g <= 59) offsets.add(`G${g}`);
      else if (g === 0 || g === 1 || g === 2 || g === 3) motion = g;
      else if (g === 81 || g === 83) motion = g;
      else if (g === 84 || g === 74) motion = 84;
      else if (g === 80) { motion = null; cycleZ = null; cycleQ = null; }
      else if (g === 41 || g === 42) { comped = true; warnings.add("Cutter compensation active (G41/G42) — findings inside comped regions are REVIEW only."); }
      else if (g === 40) comped = false;
      else if (g === 43 || g === 49 || g === 94 || g === 98 || g === 99) {
        if (g === 98) retractMode = 98;
        if (g === 99) retractMode = 99;
      } else if (g === 4) {
        const p = get("P");
        const s = get("X");
        const sec = s !== undefined ? s : p !== undefined ? (p > 100 ? p / 1000 : p) : 0;
        segments.push({ line: lineNo, kind: "DWELL", x0: x, y0: y, z0: z, x1: x, y1: y, z1: z, feed: null, dwellSeconds: sec, toolNumber: tool, spindleRPM: rpm, comped, tapping: false });
      } else if (g === 53) {
        warnings.add("G53 machine-coordinate moves are skipped — machine zero is unknown to the analyzer.");
        continue outer;
      } else if (g === 28 || g === 30) {
        // Reference return. Its coordinates name an intermediate point in
        // MACHINE space, which the analyzer cannot place — but it is
        // housekeeping at a tool change or the end of a program, not
        // cutting. Skip the line outright: neither refuse the program over
        // it, nor let a stale modal motion consume its Z.
        warnings.add(`G${g} reference return skipped — machine zero is unknown to the analyzer.`);
        continue outer;
      } else {
        unknownG = g;
        warnings.add(`G${g} ignored — outside the V1 subset.`);
      }
    }

    const f = get("F");
    if (f !== undefined) feed = f * scale();
    const s = get("S");
    if (s !== undefined) rpm = s;
    const t = get("T");
    if (t !== undefined) tool = Math.round(t);
    if (words.some((w) => w.letter === "M" && w.value === 6)) toolChanges.push({ line: lineNo, toolNumber: tool });

    const hasCoord = ["X", "Y", "Z"].some((l) => get(l) !== undefined);

    /*
     * An unrecognised G-code on a line that also carries coordinates is a
     * REFUSAL, not a warning.
     *
     * Ignoring the word does not ignore the line: the coordinates are still
     * consumed by whatever motion mode happened to be modal, which is
     * usually the G00 that positioned over the hole. A `G82 Z-0.2 R0.1 P100`
     * then became a RAPID from clearance straight down to Z-0.2, and the
     * bare `X2.0` after it a RAPID across the part at that depth — a
     * modelled crash, reported as a warning, with the replay, the cycle time
     * and every air-cutting finding computed over it.
     *
     * The cycles that land here are real and common: G73 high-speed peck,
     * G82 spot/counterbore with dwell, G85/G86/G89 boring and reaming, G76
     * fine boring. CANVAS does not expand them, and the honest response to
     * a motion it cannot model is to stop reading rather than to model a
     * different one.
     */
    if (unknownG !== null && hasCoord) {
      refusals.push({
        line: lineNo,
        reason: `G${unknownG} is not in the analyzer's motion vocabulary, and this line carries coordinates. Reading them under the previous motion mode would invent a move this program does not contain.`,
      });
      break;
    }

    if (!hasCoord || motion === null) continue;

    /*
     * A cutting move with no feed rate anywhere before it.
     *
     * The control would alarm on this; CANVAS used to emit the segment with
     * a null feed, and everything downstream reads null as "rapid" — so a
     * feed move was timed at the machine's rapid rate, the fastest number
     * available. On a two-move program that was 0.004 minutes against 0.22:
     * fifty-five times under, silently, with no assumption naming it.
     *
     * There is no honest number to substitute. The feed is the operator's
     * decision and it is simply not in the file.
     */
    if ((motion === 1 || motion === 2 || motion === 3) && feed === null) {
      refusals.push({
        line: lineNo,
        reason: "Cutting move with no feed rate — no F word on this line and none set earlier in the program. CANVAS will not time a cut at a guessed feed.",
      });
      break;
    }

    if (plane !== 17 && (motion === 2 || motion === 3)) {
      refusals.push({ line: lineNo, reason: "Arc outside G17 (XY) plane — not supported in V1" });
      break;
    }

    const nx = coord(get("X"), x, absolute, scale());
    const ny = coord(get("Y"), y, absolute, scale());
    const nz = coord(get("Z"), z, absolute, scale());

    if (motion === 0 || motion === 1) {
      segments.push({
        line: lineNo, kind: motion === 0 ? "RAPID" : "CUT",
        x0: x, y0: y, z0: z, x1: nx, y1: ny, z1: nz,
        feed: motion === 0 ? null : feed, toolNumber: tool, spindleRPM: rpm, comped, tapping: false,
      });
      x = nx; y = ny; z = nz;
    } else if (motion === 2 || motion === 3) {
      const i = (get("I") ?? 0) * scale();
      const j = (get("J") ?? 0) * scale();
      const r = get("R");
      const pts = tessellateArc(x, y, nx, ny, i, j, r !== undefined ? r * scale() : null, motion === 2);
      if (!pts) {
        refusals.push({ line: lineNo, reason: "Arc geometry could not be resolved (I/J/R inconsistent)" });
        break;
      }
      let px = x, py = y;
      const zStep = (nz - z) / pts.length;
      pts.forEach((p, k) => {
        segments.push({
          line: lineNo, kind: "ARC",
          x0: px, y0: py, z0: z + zStep * k, x1: p[0], y1: p[1], z1: z + zStep * (k + 1),
          feed, toolNumber: tool, spindleRPM: rpm, comped, tapping: false,
        });
        px = p[0]; py = p[1];
      });
      x = nx; y = ny; z = nz;
    } else if (motion === 81 || motion === 83 || motion === 84) {
      // Canned cycle at this XY. R plane and final Z are modal to the cycle.
      const rr = get("R");
      if (rr !== undefined) retractR = rr * scale();
      if (get("Z") !== undefined) cycleZ = nz;
      const qq = get("Q");
      if (qq !== undefined && qq > 0) cycleQ = qq * scale();
      if (cycleZ === null) {
        refusals.push({ line: lineNo, reason: "Canned cycle with no depth — no Z on this line and none modal from a previous cycle" });
        break;
      }
      const finalZ = cycleZ;
      if (initialZ === 0) initialZ = z;
      const tapping = motion === 84;
      const cycleFeed = tapping && feed === null && rpm > 0 ? null : feed;
      // Rapid to XY, rapid to R, feed to depth, retract.
      segments.push({ line: lineNo, kind: "RAPID", x0: x, y0: y, z0: z, x1: nx, y1: ny, z1: z, feed: null, toolNumber: tool, spindleRPM: rpm, comped, tapping: false });
      segments.push({ line: lineNo, kind: "RAPID", x0: nx, y0: ny, z0: z, x1: nx, y1: ny, z1: retractR, feed: null, toolNumber: tool, spindleRPM: rpm, comped, tapping: false });
      if (motion === 83) {
        // Q is modal to the cycle exactly as Z and R are.
        const peck = cycleQ ?? Math.abs(retractR - finalZ);
        let depth = retractR;
        while (depth > finalZ + 1e-9) {
          depth = Math.max(finalZ, depth - peck);
          segments.push({ line: lineNo, kind: "CUT", x0: nx, y0: ny, z0: retractR, x1: nx, y1: ny, z1: depth, feed: cycleFeed, toolNumber: tool, spindleRPM: rpm, comped, tapping });
          segments.push({ line: lineNo, kind: "RAPID", x0: nx, y0: ny, z0: depth, x1: nx, y1: ny, z1: retractR, feed: null, toolNumber: tool, spindleRPM: rpm, comped, tapping: false });
        }
      } else {
        segments.push({ line: lineNo, kind: "CUT", x0: nx, y0: ny, z0: retractR, x1: nx, y1: ny, z1: finalZ, feed: cycleFeed, toolNumber: tool, spindleRPM: rpm, comped, tapping });
        segments.push({ line: lineNo, kind: tapping ? "CUT" : "RAPID", x0: nx, y0: ny, z0: finalZ, x1: nx, y1: ny, z1: retractR, feed: tapping ? cycleFeed : null, toolNumber: tool, spindleRPM: rpm, comped, tapping });
      }
      const back = retractMode === 98 ? initialZ : retractR;
      if (back > retractR) {
        segments.push({ line: lineNo, kind: "RAPID", x0: nx, y0: ny, z0: retractR, x1: nx, y1: ny, z1: back, feed: null, toolNumber: tool, spindleRPM: rpm, comped, tapping: false });
      }
      x = nx; y = ny; z = back;
      if (tapping) warnings.add("Tapping cycle present (G84/G74) — its feed is the thread and will never be retimed.");
    }
  }

  if (!unitsExplicit) warnings.add("No units word (G20/G21) — inches assumed. Verify before trusting any figure.");
  if (offsets.size > 1) warnings.add(`Multiple work offsets (${[...offsets].join(", ")}) — fixture-relative geometry is unknown, spatial findings are REVIEW only.`);

  return {
    segments,
    toolChanges,
    refusals,
    warnings: [...warnings],
    units,
    unitsExplicit,
    workOffsetsSeen: [...offsets],
    lineCount: lines.length,
  };
}

const coord = (v: number | undefined, current: number, absolute: boolean, k: number): number =>
  v === undefined ? current : absolute ? v * k : current + v * k;

/** XY arc → polyline within chord tolerance. Returns null when unresolvable. */
function tessellateArc(
  x0: number, y0: number, x1: number, y1: number,
  i: number, j: number, r: number | null, cw: boolean,
): [number, number][] | null {
  let cx: number, cy: number;
  if (r !== null) {
    // R-form: centre from radius; choose the minor arc for |R|, major for -R.
    const dx = x1 - x0, dy = y1 - y0;
    const d = Math.hypot(dx, dy);
    if (d < 1e-9 || d > Math.abs(r) * 2 + 1e-6) return null;
    const h = Math.sqrt(Math.max(0, r * r - (d / 2) ** 2));
    const sign = (cw ? -1 : 1) * (r >= 0 ? 1 : -1);
    cx = x0 + dx / 2 - (sign * h * dy) / d;
    cy = y0 + dy / 2 + (sign * h * dx) / d;
  } else {
    cx = x0 + i;
    cy = y0 + j;
  }
  const radius = Math.hypot(x0 - cx, y0 - cy);
  if (radius < 1e-9) return null;
  let a0 = Math.atan2(y0 - cy, x0 - cx);
  let a1 = Math.atan2(y1 - cy, x1 - cx);
  if (cw) {
    if (a1 >= a0 - 1e-12) a1 -= Math.PI * 2;
  } else {
    if (a1 <= a0 + 1e-12) a1 += Math.PI * 2;
  }
  const sweep = Math.abs(a1 - a0);
  const maxStep = 2 * Math.acos(Math.max(0.5, 1 - ARC_CHORD_TOL / radius));
  const steps = Math.max(2, Math.ceil(sweep / maxStep));
  const pts: [number, number][] = [];
  for (let k = 1; k <= steps; k++) {
    const a = a0 + ((a1 - a0) * k) / steps;
    pts.push([cx + radius * Math.cos(a), cy + radius * Math.sin(a)]);
  }
  pts[pts.length - 1] = [x1, y1];
  return pts;
}
