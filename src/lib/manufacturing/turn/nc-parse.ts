/**
 * LATHE NC PARSER — Fanuc/Haas-style 2-axis subset, refusals first.
 *
 * Supported: G18, G20/G21, G90/G91, G0/G1/G2/G3 (arcs flattened to chords
 * for timing — flagged), F (per-rev under G99, per-min under G98), S with
 * G96/G97 semantics, G50 spindle clamp, T station calls, M3/M4/M5, M8/M9,
 * G54-G59, comments, block skip.
 *
 * REVIEW-ONLY / REFUSED, by name and line number: G70/G71/G72/G74/G75/G76
 * canned and threading cycles, G73, drilling cycles G83/G84/G85, cutter
 * compensation G41/G42 (tool-nose-radius comp changes the path), macros
 * (#, GOTO, IF, WHILE), subprograms (M98/M97), G10 writes. A block the
 * parser does not understand creates UNSUPPORTED_CONTEXT — it is never
 * silently assumed safe.
 *
 * X words are DIAMETERS (lathe convention). Feed under G99 is per-rev and
 * needs the live S context to become time; where S context is missing the
 * segment is timed as UNKNOWN, not guessed.
 */

export interface LatheNCSegment {
  line: number;
  kind: "RAPID" | "CUT" | "ARC";
  x0: number; // diameter
  z0: number;
  x1: number;
  z1: number;
  /** Feed in effect: per-rev under G99 (in/rev), per-min under G98 (in/min). */
  feed: number | null;
  feedMode: "PER_REV" | "PER_MIN";
  /** Spindle context at this segment. */
  css: boolean;
  sWord: number | null; // SFM under G96, RPM under G97
  maxRpmClamp: number | null; // last G50 S
  station: string | null; // "0101"
  spindleOn: boolean;
  /** G32 single-point threading — the feed IS the pitch. Never retimed, never optimized. */
  thread: boolean;
}

export interface LatheParseRefusal {
  line: number;
  code: string;
  reason: string;
}

export interface ParsedLatheNC {
  segments: LatheNCSegment[];
  refusals: LatheParseRefusal[];
  warnings: string[];
  toolCalls: { line: number; station: string }[];
  cssRegions: number;
  sawG50: boolean;
  units: "IN" | "MM";
  lineCount: number;
}

const REFUSE: { re: RegExp; code: string; reason: string }[] = [
  { re: /\bG7[0-6]\b/, code: "CANNED_CYCLE", reason: "G70-G76 turning cycles expand on the control; the parser does not guess their motion." },
  { re: /\bG73\b/, code: "PATTERN_CYCLE", reason: "G73 pattern repeat is control-dependent." },
  { re: /\bG8[3-9]\b/, code: "DRILL_CYCLE", reason: "Lathe drilling cycles are not expanded." },
  { re: /\bG4[12]\b/, code: "TNR_COMP", reason: "Tool-nose-radius compensation changes the actual path; uncompensated analysis would be wrong." },
  { re: /\bG92\b/, code: "THREAD_CYCLE", reason: "G92 threading cycle is not expanded." },
  { re: /\bM9[78]\b/, code: "SUBPROGRAM", reason: "Subprogram calls are not followed." },
  { re: /#\d|\bGOTO\b|\bIF\b|\bWHILE\b/i, code: "MACRO", reason: "Macro statements make motion data-dependent." },
  { re: /\bG10\b/, code: "OFFSET_WRITE", reason: "G10 writes offsets; analysis must not assume their effect." },
];

export function parseLatheNc(text: string): ParsedLatheNC {
  const lines = text.split(/\r?\n/);
  const segments: LatheNCSegment[] = [];
  const refusals: LatheParseRefusal[] = [];
  const warnings: string[] = [];
  const toolCalls: { line: number; station: string }[] = [];

  let units: "IN" | "MM" = "IN";
  let absolute = true;
  let feedMode: "PER_REV" | "PER_MIN" = "PER_REV"; // lathe default G99
  let css = false;
  let cssRegions = 0;
  let sWord: number | null = null;
  let clamp: number | null = null;
  let sawG50 = false;
  let station: string | null = null;
  let spindleOn = false;
  let feed: number | null = null;
  let x = 0; // diameter
  let z = 0;
  let motionModal: "G0" | "G1" | "G2" | "G3" | null = null;

  lines.forEach((raw, idx) => {
    const line = idx + 1;
    // Strip comments and block-skip.
    let s = raw.replace(/\(.*?\)/g, "").replace(/;.*$/, "").trim();
    if (s.startsWith("/")) s = s.slice(1);
    if (!s || s === "%" || /^O\d+/.test(s)) return;

    for (const r of REFUSE) {
      if (r.re.test(s)) {
        refusals.push({ line, code: r.code, reason: r.reason });
        return;
      }
    }

    if (/\bG20\b/.test(s)) units = "IN";
    if (/\bG21\b/.test(s)) units = "MM";
    if (/\bG90\b/.test(s)) absolute = true;
    if (/\bG91\b/.test(s)) absolute = false;
    if (/\bG98\b/.test(s)) feedMode = "PER_MIN";
    if (/\bG99\b/.test(s)) feedMode = "PER_REV";
    if (/\bG96\b/.test(s)) {
      if (!css) cssRegions++;
      css = true;
    }
    if (/\bG97\b/.test(s)) css = false;

    const g50 = /\bG50\s*S(\d+(?:\.\d+)?)/.exec(s);
    if (g50) {
      clamp = Number(g50[1]);
      sawG50 = true;
      return;
    }
    // Bare G50 without S is a coordinate-system preset on some controls.
    if (/\bG50\b/.test(s)) {
      warnings.push(`Line ${line}: G50 without an S word — treated as a preset, not a clamp.`);
      return;
    }

    const t = /\bT(\d{2,4})\b/.exec(s);
    if (t) {
      station = t[1].padStart(4, "0");
      toolCalls.push({ line, station });
    }
    const sw = /\bS(\d+(?:\.\d+)?)/.exec(s);
    if (sw) sWord = Number(sw[1]);
    if (/\bM0?3\b|\bM0?4\b/.test(s)) spindleOn = true;
    if (/\bM0?5\b/.test(s)) spindleOn = false;

    const f = /\bF(\d*\.?\d+)/.exec(s);
    if (f) feed = Number(f[1]);

    const gMotion = /\bG0?([0-3])\b/.exec(s);
    if (gMotion) motionModal = (`G${gMotion[1]}` as "G0" | "G1" | "G2" | "G3");
    const xw = /\bX(-?\d*\.?\d+)/.exec(s);
    const zw = /\bZ(-?\d*\.?\d+)/.exec(s);
    const g32 = /\bG32\b/.test(s);
    if ((xw || zw) && (motionModal || g32)) {
      const nx = xw ? (absolute ? Number(xw[1]) : x + Number(xw[1])) : x;
      const nz = zw ? (absolute ? Number(zw[1]) : z + Number(zw[1])) : z;
      const kind = g32 ? "CUT" : motionModal === "G0" ? "RAPID" : motionModal === "G2" || motionModal === "G3" ? "ARC" : "CUT";
      if (kind === "ARC") warnings.push(`Line ${line}: arc flattened to a chord for timing — length underestimated.`);
      segments.push({ line, kind, x0: x, z0: z, x1: nx, z1: nz, feed, feedMode, css, sWord, maxRpmClamp: clamp, station, spindleOn, thread: g32 });
      x = nx;
      z = nz;
    }
  });

  // TS narrows `units` to its initializer because the mutations live in the
  // forEach callback; widen before comparing.
  if ((units as string) === "MM") warnings.push("G21 metric program — all values reported in millimetres.");
  return { segments, refusals, warnings, toolCalls, cssRegions, sawG50, units, lineCount: lines.length };
}

/* ------------------------------------------------------------------ */
/* Analysis — cycle estimate + findings                                */
/* ------------------------------------------------------------------ */

export interface LatheNCFinding {
  kind:
    | "MISSING_MAX_RPM_CLAMP"
    | "RPM_LIMIT_REVIEW"
    | "CSS_NOT_USED"
    | "UNKNOWN_SPINDLE_CONTEXT"
    | "UNSUPPORTED_CONTEXT";
  verdict: "CONFIDENT" | "REVIEW" | "INSUFFICIENT_DATA";
  line: number;
  detail: string;
}

export interface LatheNCAnalysis {
  cutMinutes: number;
  rapidMinutes: number;
  unknownSegments: number;
  totalMinutes: number;
  findings: LatheNCFinding[];
  assumptions: string[];
  perTool: { station: string; cutMinutes: number; segments: number }[];
}

const RAPID_IPM = 800; // stated assumption — lathe rapids vary widely

export function analyzeLatheNc(parsed: ParsedLatheNC, chuckMaxRpm: number | null): LatheNCAnalysis {
  const assumptions = [
    `Rapids assumed at ${RAPID_IPM} in/min — machine value not known to the analyzer.`,
    "CSS segments timed at the RPM the mean diameter yields, capped by the G50 clamp.",
    "No acceleration or spindle spin-up model — figures are ESTIMATED and read low.",
  ];
  const findings: LatheNCFinding[] = [];
  let cutMin = 0;
  let rapidMin = 0;
  let unknown = 0;
  const perTool = new Map<string, { cutMinutes: number; segments: number }>();

  for (const r of parsed.refusals) {
    findings.push({ kind: "UNSUPPORTED_CONTEXT", verdict: "INSUFFICIENT_DATA", line: r.line, detail: `${r.code}: ${r.reason}` });
  }

  // G96 without any G50: the classic unclamped-CSS hazard.
  const cssNoClampLine = parsed.segments.find((s) => s.css && s.maxRpmClamp === null);
  if (cssNoClampLine) {
    findings.push({
      kind: "MISSING_MAX_RPM_CLAMP",
      verdict: "CONFIDENT",
      line: cssNoClampLine.line,
      detail: "G96 constant surface speed with no G50 maximum-RPM clamp in effect. As X approaches zero the spindle winds to its limit.",
    });
  }
  if (chuckMaxRpm !== null) {
    const over = parsed.segments.find((s) => s.maxRpmClamp !== null && s.maxRpmClamp > chuckMaxRpm);
    if (over) {
      findings.push({
        kind: "RPM_LIMIT_REVIEW",
        verdict: "CONFIDENT",
        line: over.line,
        detail: `G50 S${over.maxRpmClamp} exceeds the chuck's ${chuckMaxRpm} RPM limit.`,
      });
    }
  }
  // Fixed RPM across a large diameter range: surface speed swings with X.
  const fixedCuts = parsed.segments.filter((s) => s.kind === "CUT" && !s.css && s.spindleOn);
  if (fixedCuts.length > 3) {
    const dias = fixedCuts.flatMap((s) => [Math.abs(s.x0), Math.abs(s.x1)]).filter((d) => d > 0.05);
    if (dias.length > 0 && Math.max(...dias) / Math.max(0.05, Math.min(...dias)) > 2.5) {
      findings.push({
        kind: "CSS_NOT_USED",
        verdict: "REVIEW",
        line: fixedCuts[0].line,
        detail: `Fixed RPM (G97) across a ${Math.min(...dias).toFixed(2)}–${Math.max(...dias).toFixed(2)} diameter range — surface speed varies ${(Math.max(...dias) / Math.max(0.05, Math.min(...dias))).toFixed(1)}×. CSS may cut more consistently; review against interrupted cuts and workholding limits first.`,
      });
    }
  }

  for (const s of parsed.segments) {
    const dx = (s.x1 - s.x0) / 2; // radius travel
    const dz = s.z1 - s.z0;
    const dist = Math.hypot(dx, dz);
    if (dist <= 0) continue;
    if (s.kind === "RAPID") {
      rapidMin += dist / RAPID_IPM;
      continue;
    }
    const key = s.station ?? "----";
    const row = perTool.get(key) ?? { cutMinutes: 0, segments: 0 };
    row.segments++;
    if (s.feed === null || s.sWord === null || !s.spindleOn) {
      unknown++;
      if (s.sWord === null) {
        findings.push({ kind: "UNKNOWN_SPINDLE_CONTEXT", verdict: "INSUFFICIENT_DATA", line: s.line, detail: "Cutting move with no S word in effect — time cannot be computed honestly." });
      }
      perTool.set(key, row);
      continue;
    }
    let minutes: number;
    if (s.feedMode === "PER_MIN") {
      minutes = dist / s.feed;
    } else {
      const meanDia = Math.max(0.05, (Math.abs(s.x0) + Math.abs(s.x1)) / 2);
      const rpm = s.css
        ? Math.min((s.sWord * 12) / (Math.PI * meanDia), s.maxRpmClamp ?? Infinity)
        : s.sWord;
      minutes = rpm > 0 && rpm !== Infinity ? dist / (s.feed * rpm) : 0;
      if (!Number.isFinite(minutes)) minutes = 0;
    }
    cutMin += minutes;
    row.cutMinutes += minutes;
    perTool.set(key, row);
  }

  return {
    cutMinutes: r3(cutMin),
    rapidMinutes: r3(rapidMin),
    unknownSegments: unknown,
    totalMinutes: r3(cutMin + rapidMin),
    findings,
    assumptions,
    perTool: [...perTool.entries()].map(([station, v]) => ({ station, cutMinutes: r3(v.cutMinutes), segments: v.segments })),
  };
}

const r3 = (v: number) => Number(v.toFixed(3));
