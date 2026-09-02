import type { ParsedNC } from "./parse";
import {
  CONTROLLER_FAMILY_LABEL,
  ENCODING_LABEL,
  type ControllerFamily,
  type LineEnding,
  type SourceEncoding,
} from "./source";

/**
 * RUN IT PAST CANVAS — AUDIT GATES.
 *
 * A separate gate group for the NC audit, alongside (never replacing) the
 * manufacturing readiness system. Same law: each gate is PASS / REVIEW /
 * FAIL / INSUFFICIENT_DATA, and every stage summary is the WORST required
 * gate — no averages, no percentages, no scores.
 *
 * Three stages, in trust order:
 *
 *   AUDIT             what can honestly be read from the program itself
 *   OPTIMIZATION      what load-aware proposals may be derived from
 *   DERIVED EXPORT    delegated to the existing mint pre-flight — the mint
 *                     re-runs its own gate server-side; this stage reports
 *                     the audit-side prerequisites only and says so.
 *
 * Every gate names the evidence that moves it. A REVIEW gate does not block
 * the audit stage it belongs to — FAIL and INSUFFICIENT_DATA do.
 */

export type AuditGateStatus = "PASS" | "REVIEW" | "FAIL" | "INSUFFICIENT_DATA";

export interface AuditGate {
  id: string;
  label: string;
  status: AuditGateStatus;
  detail: string;
  /** Which stage this gate is required for. */
  stage: "AUDIT" | "OPTIMIZATION" | "EXPORT";
}

export interface AuditGateInput {
  parsed: Pick<ParsedNC, "refusals" | "warnings" | "unitsExplicit" | "units" | "workOffsetsSeen" | "segments" | "lineCount">;
  /** The original was stored immutably and its digest computed server-side. */
  originalStored: boolean;
  /**
   * What arrived: how the bytes decoded, how the lines end, what dialect the
   * file is in. Optional because a program CANVAS generated has no upload to
   * inspect; absent means these gates say nothing rather than assume.
   */
  source?: { encoding: SourceEncoding; lineEnding: LineEnding; controllerFamily: ControllerFamily | null };
  digest: string | null;
  /** T numbers called by the program. */
  toolsInProgram: number[];
  /** T numbers with a matching crib record — measured, and with a chipload window. */
  toolsMapped: number[];
  /**
   * T numbers known only from an attached tool list. Geometry for engagement
   * and reach, no chipload window, and no crib record behind them — so they
   * do not make this gate PASS.
   */
  toolsFromList?: number[];
  machineKnown: boolean;
  axisAccelKnown: boolean;
  stockBound: boolean;
  materialMatched: boolean;
  /** Segment counts the optimizer must exclude. */
  compedSegments: number;
  tappingSegments: number;
}

export interface AuditGateResult {
  gates: AuditGate[];
  /** Worst required gate per stage — the only aggregation permitted. */
  stages: {
    audit: AuditGateStatus;
    optimization: AuditGateStatus;
    /** Audit-side prerequisites only; the export mint runs its own gate. */
    exportPrereqs: AuditGateStatus;
  };
}

const WORST_ORDER: AuditGateStatus[] = ["FAIL", "INSUFFICIENT_DATA", "REVIEW", "PASS"];
const worst = (gates: AuditGate[]): AuditGateStatus => {
  for (const s of WORST_ORDER) if (gates.some((g) => g.status === s)) return s;
  return "PASS";
};

export function evaluateAuditGates(input: AuditGateInput): AuditGateResult {
  const gates: AuditGate[] = [];
  const g = (id: string, label: string, stage: AuditGate["stage"], status: AuditGateStatus, detail: string) =>
    gates.push({ id, label, stage, status, detail });

  /* ---- AUDIT stage ---- */
  g(
    "file-integrity",
    "NC file integrity",
    "AUDIT",
    !input.originalStored || !input.digest
      ? "FAIL"
      : input.source?.encoding === "EIGHT_BIT_UNKNOWN"
        ? "REVIEW"
        : "PASS",
    !input.originalStored || !input.digest
      ? "The original program is not stored — nothing downstream has a fixed subject."
      : input.source
        ? `Original stored immutably, sha256 ${input.digest.slice(0, 12)}… computed server-side. ${ENCODING_LABEL[input.source.encoding]}, ${input.source.lineEnding} line endings.${
            input.source.encoding === "EIGHT_BIT_UNKNOWN"
              ? " Bytes above 0x7F with no codepage declared — a character in a comment may not be what was typed."
              : ""
          }`
        : `Original stored immutably, sha256 ${input.digest.slice(0, 12)}… computed server-side.`,
  );

  const hasRefusals = input.parsed.refusals.length > 0;
  const family = input.source?.controllerFamily ?? null;
  const foreignDialect = family === "HEIDENHAIN" || family === "SIEMENS";
  const mixedEndings = input.source?.lineEnding === "MIXED";
  g(
    "parser-fidelity",
    "Parser fidelity",
    "AUDIT",
    // A dialect this parser does not read is a FAIL, not a note. It reads
    // Fanuc-style word address; run against Heidenhain conversational or
    // Siemens it produces motion that means nothing, and every gate below
    // reasons over that motion.
    foreignDialect
      ? "FAIL"
      : hasRefusals
        ? "FAIL"
        : input.parsed.warnings.length > 0 || mixedEndings
          ? "REVIEW"
          : "PASS",
    foreignDialect
      ? `CANVAS reads Fanuc-style word address. This is a ${CONTROLLER_FAMILY_LABEL[input.source!.controllerFamily!]} program, and nothing the parser produced from it can be trusted.`
      : hasRefusals
        ? `Interpretation stopped at line ${input.parsed.refusals[0].line}: ${input.parsed.refusals[0].reason}. Motion after that line is unknown.`
        : mixedEndings
          ? `${input.parsed.segments.length} motion segments interpreted, but the file mixes line endings — read as ${input.source!.lineEnding}. Check the block count matches the program you sent.`
          : input.parsed.warnings.length > 0
            ? `Parsed with ${input.parsed.warnings.length} note(s) — read them; each names what the parser could not fully trust.`
            : `${input.parsed.segments.length} motion segments interpreted with no reservations.`,
  );

  g(
    "units",
    "Units",
    "AUDIT",
    input.parsed.unitsExplicit ? "PASS" : "REVIEW",
    input.parsed.unitsExplicit
      ? `${input.parsed.units === "IN" ? "G20 inches" : "G21 millimetres"} declared by the program.`
      : "No G20/G21 in the program — inches assumed. Every figure downstream inherits this assumption.",
  );

  g(
    "work-offset",
    "Work offset",
    "AUDIT",
    input.parsed.workOffsetsSeen.length > 1 ? "REVIEW" : "PASS",
    input.parsed.workOffsetsSeen.length > 1
      ? `Multiple offsets (${input.parsed.workOffsetsSeen.join(", ")}) — their relative positions are unknown to CANVAS, so spatial findings are REVIEW at best.`
      : input.parsed.workOffsetsSeen.length === 1
        ? `${input.parsed.workOffsetsSeen[0]} throughout.`
        : "No work offset word seen — program zero is wherever the setup sheet says.",
  );

  /* ---- OPTIMIZATION stage ---- */
  const fromList = input.toolsFromList ?? [];
  const unmapped = input.toolsInProgram.filter((t) => !input.toolsMapped.includes(t) && !fromList.includes(t));
  const listOnly = input.toolsInProgram.filter((t) => fromList.includes(t));
  g(
    "tool-mapping",
    "Tool mapping",
    "OPTIMIZATION",
    input.toolsInProgram.length === 0
      ? "REVIEW"
      : unmapped.length > 0
        ? "INSUFFICIENT_DATA"
        : listOnly.length > 0
          ? "REVIEW"
          : "PASS",
    input.toolsInProgram.length === 0
      ? "No tool calls found in the program."
      : unmapped.length > 0
        ? `T${unmapped.join(", T")} have no crib record and are not in the attached tool list — their cuts carry no load verdict and no proposals. Match, create, or attach the tool(s).`
        : listOnly.length > 0
          ? `T${listOnly.join(", T")} come from the attached tool list, not the crib: diameter and stickout are read for engagement and reach, and no feed proposal is made for them — a tool list carries no chipload window, and one cannot be assumed.`
          : `All ${input.toolsInProgram.length} program tool(s) matched to crib records.`,
  );

  g(
    "machine-profile",
    "Machine profile",
    "OPTIMIZATION",
    !input.machineKnown ? "INSUFFICIENT_DATA" : input.axisAccelKnown ? "PASS" : "REVIEW",
    !input.machineKnown
      ? "No machine selected — rapid rate and feed ceiling are defaults, not this machine."
      : input.axisAccelKnown
        ? "Machine record with recorded axis acceleration — machine-adjusted timing in use."
        : "Machine known but axis acceleration unrecorded — times are ideal motion estimates and say so.",
  );

  g(
    "stock-alignment",
    "Stock / part alignment",
    "OPTIMIZATION",
    input.stockBound ? "REVIEW" : "INSUFFICIENT_DATA",
    input.stockBound
      ? "Stock bound with the stated alignment assumption (program Z0 = stock top, XY zero = stock centre). Confirm against the setup sheet — CANVAS cannot see the vise."
      : "No stock bound — air cutting cannot be proven and engagement cannot be computed. Bind stock to unlock both.",
  );

  g(
    "material",
    "Material",
    "OPTIMIZATION",
    input.materialMatched ? "PASS" : "REVIEW",
    input.materialMatched
      ? "Material matched to a shop record — specific energy available for power estimates."
      : "No material match — spindle-power estimates are absent, not defaulted.",
  );

  g(
    "engagement-model",
    "Engagement model",
    "OPTIMIZATION",
    input.stockBound && input.toolsMapped.length + fromList.length > 0 ? "PASS" : "INSUFFICIENT_DATA",
    input.stockBound && input.toolsMapped.length + fromList.length > 0
      ? "Height-field replay against bound stock with the tool diameters CANVAS has — engagement bands are computed, not guessed."
      : "Engagement needs both bound stock and mapped tools. Bands fall back to chipload-only where a tool is known.",
  );

  const excluded = input.compedSegments + input.tappingSegments;
  g(
    "optimization-scope",
    "Optimization scope",
    "OPTIMIZATION",
    "PASS",
    excluded > 0
      ? `${input.compedSegments} comped and ${input.tappingSegments} tapping segment(s) are excluded from proposals by construction — never retimed.`
      : "No comped or tapping regions — the whole cutting program is inside the feed-only proposal scope.",
  );

  /* ---- EXPORT prerequisites (the mint runs its own gate) ---- */
  g(
    "derived-integrity",
    "Derived NC integrity",
    "EXPORT",
    "PASS",
    "Enforced at emission: feed words only, masked geometry diff must be byte-clean, round-trip re-parse must match segment for segment. The export mint then re-runs the full pre-flight server-side.",
  );

  const stageOf = (stage: AuditGate["stage"]) => gates.filter((x) => x.stage === stage);
  return {
    gates,
    stages: {
      audit: worst(stageOf("AUDIT")),
      optimization: worst([...stageOf("AUDIT"), ...stageOf("OPTIMIZATION")]),
      exportPrereqs: worst(gates),
    },
  };
}
