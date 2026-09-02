"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Button, LimitsDisclosure, Notice, Panel, StatusChip } from "@/components/ui";
import {
  CONTROLLER_FAMILY_LABEL,
  ENCODING_LABEL,
  type ControllerFamily,
  type LineEnding,
  type SourceEncoding,
} from "@/lib/nc/source";

/**
 * NC ANALYZER — Phase 4A/4B client
 *
 * Upload → parse report → backplot → cycle breakdown → findings. Analysis
 * only: there are no optimization proposals yet and the screen says so.
 * Every finding carries its verdict — CONFIDENT is replay-proven, REVIEW is
 * a heuristic, INSUFFICIENT_DATA names what is missing.
 */

interface AuditGate {
  id: string;
  label: string;
  status: "PASS" | "REVIEW" | "FAIL" | "INSUFFICIENT_DATA";
  detail: string;
  stage: "AUDIT" | "OPTIMIZATION" | "EXPORT";
}

interface Report {
  fileName: string;
  /** What arrived: how it decoded, how the lines end, what dialect it is. */
  source?: {
    encoding: SourceEncoding;
    lineEnding: LineEnding;
    controllerFamily: ControllerFamily | null;
    controllerEvidence: string | null;
  };
  uploadedProgramId: string;
  digest: string;
  gates: { gates: AuditGate[]; stages: { audit: string; optimization: string; exportPrereqs: string } };
  parse: {
    lineCount: number;
    segments: number;
    refusals: { line: number; reason: string }[];
    warnings: string[];
    units: string;
    workOffsetsSeen: string[];
    toolChanges: { line: number; toolNumber: number }[];
  };
  toolList?: {
    units: "IN" | "MM";
    imported: number;
    applied: number;
    refusals: { row: number; reason: string }[];
    unreadColumns: string[];
    columns: Record<string, string>;
  } | null;
  backplot: [number, number, number, number, number, number][];
  code: string;
  operations: { toolNumber: number; lines: [number, number]; kind: string; method: string; detail: string; cutSegments: number }[];
  load: {
    bands: string[];
    proposals: {
      kind: "RAISE" | "REDUCE";
      lines: [number, number]; toolNumber: number; originalFeed: number; proposedFeed: number;
      estimatedSecondsSaved: number; reason: string; risk: string; assumptions: string[];
      requiredEvidence: string; geometryChanges: false;
    }[];
    totalProposedSecondsSaved: number;
    protectedHits: { label: string; reason: string; lines: [number, number]; segments: number }[];
    gaps: string[];
    developmentAnalysis: true;
  };
  analysis: {
    totalMinutes: number;
    cutMinutes: number;
    rapidMinutes: number;
    dwellMinutes: number;
    perTool: { toolNumber: number; cutMinutes: number; rapidMinutes: number; dwellMinutes: number; segments: number }[];
    findings: { kind: string; verdict: string; line: number; toolNumber: number; seconds: number; detail: string; assumptions: string[] }[];
    recoverableSeconds: number;
    assumptions: string[];
    checksSkipped: { check: string; reason: string }[];
    extents: { minX: number; maxX: number; minY: number; maxY: number };
  };
  context: { stockBound: boolean; toolsKnown: number; rapidRate: number; machine: string | null; machineRatePerHour: number | null };
}

export function NcAnalyzer({ partId }: { partId: string }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const toolListRef = useRef<HTMLInputElement>(null);
  const [toolListUnits, setToolListUnits] = useState("");
  const [preset, setPreset] = useState("BALANCED");
  const [state, setState] = useState<{ busy: boolean; error: string | null; report: Report | null }>({
    busy: false, error: null, report: null,
  });
  const [accepted, setAccepted] = useState<Set<number>>(new Set());
  // SHOW ME selection: a source-line range that the backplot frames and
  // highlights and the code viewer scrolls to — one selection, two scenes.
  const [sel, setSel] = useState<[number, number] | null>(null);
  const [plotMode, setPlotMode] = useState<"ORIGINAL" | "PROPOSED">("ORIGINAL");
  // One workspace mode at a time — the analyzer is an instrument, not a
  // document. SHOW ME from any mode lands in the BACKPLOT scene.
  const [mode, setMode] = useState<"BACKPLOT" | "PROGRAM" | "LOAD" | "TIME" | "FINDINGS" | "COMPARE" | "VERIFY">("BACKPLOT");
  const showMe = (lines: [number, number]) => {
    setSel(lines);
    setMode("BACKPLOT");
  };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setSel(null); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  const [optimizing, setOptimizing] = useState(false);
  const [optimized, setOptimized] = useState<{
    programId: string; applied: number; savedSeconds: number;
    originalMinutes: number; optimizedMinutes: number; lintErrors: number;
    unapplied: { lines: [number, number]; reason: string }[];
  } | null>(null);
  const [optError, setOptError] = useState<string | null>(null);

  async function generateOptimized() {
    const r = state.report;
    if (!r || accepted.size === 0) return;
    setOptimizing(true);
    setOptError(null);
    const body = new FormData();
    // The server derives from the STORED original — the id and digest name
    // the immutable subject; the file itself is never re-sent.
    body.append("uploadedProgramId", r.uploadedProgramId);
    body.append("digest", r.digest);
    body.append("preset", preset);
    body.append(
      "accepted",
      JSON.stringify(
        [...accepted].map((i) => {
          const p = r.load.proposals[i];
          return { lines: p.lines, originalFeed: p.originalFeed, proposedFeed: p.proposedFeed };
        }),
      ),
    );
    const res = await fetch(`/api/parts/${partId}/nc-optimize`, { method: "POST", body });
    const json = await res.json().catch(() => null);
    setOptimizing(false);
    if (!res.ok || !json?.programId) { setOptError(json?.error ?? "Optimization failed — nothing was stored."); return; }
    setOptimized(json);
  }

  async function analyzeFile(file: File) {
    setState({ busy: true, error: null, report: null });
    setAccepted(new Set());
    setSel(null);
    const body = new FormData();
    body.append("file", file);
    const toolListFile = toolListRef.current?.files?.[0];
    if (toolListFile) {
      body.append("toolList", toolListFile);
      body.append("toolListUnits", toolListUnits);
    }
    const res = await fetch(`/api/parts/${partId}/nc-analyze?preset=${preset}`, { method: "POST", body });
    const json = await res.json().catch(() => null);
    if (!res.ok || !json?.analysis) { setState({ busy: false, error: json?.error ?? "Analysis failed.", report: null }); return; }
    setState({ busy: false, error: null, report: json as Report });
  }

  async function run() {
    const file = fileRef.current?.files?.[0];
    if (!file) { setState((s) => ({ ...s, error: "Choose an .nc / .txt program first." })); return; }
    if (toolListRef.current?.files?.[0] && toolListUnits === "") {
      setState((s) => ({ ...s, error: "State the units of the tool list before analyzing. A 6 mm cutter read as 6 inch is a scrapped part." }));
      return;
    }
    await analyzeFile(file);
  }

  // The seeded demo: deliberate mixed results — air cutting, an excessive
  // retract, rubbing passes, an engagement spike, a protected bore pass, a
  // comped region that is review-only. Not artificially perfect.
  async function loadDemo() {
    const res = await fetch("/demo/O2507-DEMO.nc");
    if (!res.ok) { setState((s) => ({ ...s, error: "Demo program not found." })); return; }
    const text = await res.text();
    await analyzeFile(new File([text], "O2507-DEMO.nc", { type: "text/plain" }));
  }

  const r = state.report;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <input
          ref={fileRef}
          type="file"
          accept=".nc,.txt,.tap,.ngc,.prg"
          className="text-[12px] text-muted file:mr-3 file:border file:border-line-strong file:bg-surface file:px-3 file:py-1.5 file:text-[11px] file:font-semibold file:uppercase file:tracking-[0.12em] file:text-platinum-dim hover:file:bg-raised"
        />
        <select
          value={preset}
          onChange={(e) => setPreset(e.target.value)}
          className="border border-line-strong bg-surface px-1.5 py-1.5 text-[11px] text-platinum-dim"
          aria-label="Strategy preset"
          title="Feed proposal ceiling. Lights-out is the most conservative — nobody is there to hear a bad cut."
        >
          <option value="CONSERVATIVE">Conservative (≤1.15×)</option>
          <option value="BALANCED">Balanced (≤1.35×)</option>
          <option value="AGGRESSIVE">Aggressive (≤1.6×, REVIEW risk)</option>
          <option value="LIGHTS_OUT">Lights-out (≤1.1×)</option>
        </select>
        <Button onClick={run} disabled={state.busy} variant="primary">
          {state.busy ? "Analyzing…" : "Analyze program"}
        </Button>
        <Button onClick={loadDemo} disabled={state.busy}>
          Load demo program
        </Button>
        <span className="text-[10.5px] text-muted">Demo: deliberate mixed results — savings, a protected bore, a review-only comped region.</span>
      </div>
      <div className="flex flex-wrap items-center gap-3 border-t border-line pt-3">
        <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-platinum-dim">Tool list (optional)</span>
        <input
          ref={toolListRef}
          type="file"
          accept=".csv,.txt,.tsv"
          aria-label="Tool list (CSV or tab separated)"
          className="text-[12px] text-muted file:mr-3 file:border file:border-line-strong file:bg-surface file:px-3 file:py-1.5 file:text-[11px] file:font-semibold file:uppercase file:tracking-[0.12em] file:text-platinum-dim hover:file:bg-raised"
        />
        <select
          value={toolListUnits}
          onChange={(e) => setToolListUnits(e.target.value)}
          aria-label="Tool list units"
          className="border border-line-strong bg-surface px-1.5 py-1.5 text-[11px] text-platinum-dim"
        >
          <option value="">Units — state them</option>
          <option value="IN">Inch</option>
          <option value="MM">Millimetre</option>
        </select>
        <span className="text-[10.5px] text-muted">
          CSV or tab separated, with a header row. Tool number, diameter and flute count are read; flute length and stickout are used for reach if present.
          Nothing is written to the crib, and a tool known only from the list gets no feed proposal — a tool list carries no chipload window.
        </span>
      </div>
      {state.error && <p className="text-[12px] text-risk">{state.error}</p>}

      {r && (
        <>
          {r.parse.refusals.length > 0 && (
            <Notice tone="risk" title={`Interpretation stopped at line ${r.parse.refusals[0].line}`}>
              {r.parse.refusals[0].reason}. Everything before that line is analyzed; nothing after it is.
            </Notice>
          )}

          <Panel title={`Parse — ${r.fileName}`} dense>
            <div className="flex flex-wrap gap-x-6 gap-y-1 px-4 py-2.5 font-mono text-[11.5px] text-platinum-dim tabular-nums">
              <span>{r.parse.lineCount} lines</span>
              <span>{r.parse.segments} motion segments</span>
              <span>{r.parse.units}</span>
              <span>{r.parse.toolChanges.length} tool changes</span>
              <span>{r.parse.workOffsetsSeen.join(" ") || "no offset word"}</span>
              <span>
                {r.context.stockBound ? "stock bound" : "NO STOCK"} · {r.context.toolsKnown} tools known ·{" "}
                {r.context.machine ?? "no machine"}
              </span>
            </div>
            {/* What arrived, before anything read it. The dialect is null when
                the file carries no marker naming one — not assessed, not
                assumed — and the marker that decided it is shown so the claim
                can be checked. */}
            {r.source && (
              <div className="flex flex-wrap gap-x-6 gap-y-1 border-t border-line px-4 py-2 font-mono text-[11px] text-muted">
                <span>{ENCODING_LABEL[r.source.encoding]}</span>
                <span>{r.source.lineEnding} line endings</span>
                <span>
                  {r.source.controllerFamily
                    ? `${CONTROLLER_FAMILY_LABEL[r.source.controllerFamily]} (${r.source.controllerEvidence})`
                    : "controller family not determinable from the file"}
                </span>
              </div>
            )}
            {r.parse.warnings.length > 0 && (
              <ul className="border-t border-line px-4 py-2">
                {r.parse.warnings.map((w) => (
                  <li key={w} className="text-[11.5px] leading-relaxed text-review">— {w}</li>
                ))}
              </ul>
            )}
          </Panel>

          {r.toolList && (
            <Panel title="Attached tool list" meta={`${r.toolList.imported} tool${r.toolList.imported === 1 ? "" : "s"} read in ${r.toolList.units === "MM" ? "millimetres" : "inches"} — ${r.toolList.applied} used by this program`}>
              <div className="space-y-2 px-4 py-3 text-[11.5px] leading-relaxed">
                <p className="text-muted">
                  Read for this analysis only. Nothing was written to the tool crib, and a tool known only from this
                  list carries no chipload window, so no feed proposal is made against it.
                </p>
                {Object.keys(r.toolList.columns).length > 0 && (
                  <p className="text-muted">
                    Columns read:{" "}
                    {Object.entries(r.toolList.columns).map(([f, h]) => `${f} ← "${h}"`).join(", ")}.
                  </p>
                )}
                {r.toolList.unreadColumns.length > 0 && (
                  <p className="text-review">Not read: {r.toolList.unreadColumns.join(", ")}.</p>
                )}
                {r.toolList.refusals.length > 0 && (
                  <ul>
                    {r.toolList.refusals.map((f) => (
                      <li key={`${f.row}-${f.reason}`} className="text-risk">— Row {f.row}: {f.reason}</li>
                    ))}
                  </ul>
                )}
              </div>
            </Panel>
          )}

          {/* ---------- Workspace modes — one scene at a time ---------- */}
          <div className="flex flex-wrap items-center gap-1 border-b border-line pb-2">
            {(
              [
                ["BACKPLOT", null],
                ["PROGRAM", null],
                ["LOAD", r.load.proposals.length || null],
                ["TIME", null],
                ["FINDINGS", r.analysis.findings.length || null],
                ["COMPARE", accepted.size || null],
                ["VERIFY", null],
              ] as const
            ).map(([m, count]) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                aria-pressed={mode === m}
                className={`border px-2.5 py-1 text-[9.5px] font-semibold uppercase tracking-[0.14em] ${
                  mode === m ? "border-precision/60 bg-precision/10 text-precision" : "border-line-strong text-muted hover:text-platinum"
                }`}
              >
                {m}
                {count ? <span className="ml-1.5 font-mono text-[9px] text-platinum-dim">{count}</span> : null}
              </button>
            ))}
            <span className="ml-auto flex items-center gap-2">
              {(
                [
                  ["AUDIT", r.gates.stages.audit],
                  ["OPT", r.gates.stages.optimization],
                ] as const
              ).map(([label, st]) => (
                <StatusChip key={label} tone={st === "PASS" ? "pass" : st === "REVIEW" ? "review" : st === "FAIL" ? "risk" : "unknown"}>
                  {label}: {st.replace(/_/g, " ")}
                </StatusChip>
              ))}
            </span>
          </div>

          {mode === "VERIFY" && (
          <Panel
            title="Audit gates"
            meta={
              <span className="flex items-center gap-2">
                {(
                  [
                    ["AUDIT", r.gates.stages.audit],
                    ["OPTIMIZATION", r.gates.stages.optimization],
                    ["EXPORT PREREQS", r.gates.stages.exportPrereqs],
                  ] as const
                ).map(([label, st]) => (
                  <StatusChip key={label} tone={st === "PASS" ? "pass" : st === "REVIEW" ? "review" : st === "FAIL" ? "risk" : "unknown"}>
                    {label}: {st.replace(/_/g, " ")}
                  </StatusChip>
                ))}
              </span>
            }
            dense
          >
            <ul>
              {r.gates.gates.map((gate) => (
                <li key={gate.id} className="flex items-start gap-3 border-b border-line/60 px-4 py-1.5 last:border-0">
                  <StatusChip tone={gate.status === "PASS" ? "pass" : gate.status === "REVIEW" ? "review" : gate.status === "FAIL" ? "risk" : "unknown"}>
                    {gate.status.replace(/_/g, " ")}
                  </StatusChip>
                  <span className="min-w-0 flex-1">
                    <span className="block text-[11.5px] font-semibold text-platinum">{gate.label}</span>
                    <span className="block text-[11.5px] leading-relaxed text-platinum-dim">{gate.detail}</span>
                  </span>
                </li>
              ))}
            </ul>
            <p className="border-t border-line/60 px-4 py-2 text-[10.5px] leading-relaxed text-muted">
              Each stage is its worst required gate — never a percentage. Original stored immutably as sha256 {r.digest.slice(0, 16)}…; the optimize step derives from that stored copy, not from re-sent bytes.
            </p>
          </Panel>
          )}

          {mode === "PROGRAM" && (
          <>
          <Panel title={`Operations — ${r.operations.length} group(s)`} meta={<StatusChip tone="neutral">Deterministic motion evidence only</StatusChip>} dense>
            <ul>
              {r.operations.map((op, i) => (
                <li key={i} className="flex items-start gap-3 border-b border-line/60 px-4 py-1.5 last:border-0">
                  <StatusChip tone={op.kind === "UNKNOWN" ? "unknown" : op.kind === "LINKING" ? "neutral" : "precision"}>{op.kind}</StatusChip>
                  <span className="min-w-0 flex-1">
                    <span className="block font-mono text-[11px] text-muted">
                      T{op.toolNumber} · L{op.lines[0]}–{op.lines[1]} · {op.cutSegments} cutting segment(s)
                      <button
                        onClick={() => showMe(op.lines)}
                        className="ml-2 border border-precision/50 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-precision-dim hover:bg-precision/10"
                      >
                        Show me
                      </button>
                    </span>
                    <span className="block text-[11.5px] leading-relaxed text-platinum-dim">{op.detail}</span>
                  </span>
                </li>
              ))}
            </ul>
          </Panel>
          <Panel title="Program" dense>
            <NcCodeViewer code={r.code} sel={sel} onSelect={(line) => setSel([line, line])} toolChanges={r.parse.toolChanges} refusals={r.parse.refusals} />
          </Panel>
          </>
          )}

          {mode === "BACKPLOT" && (
          <Panel title="Backplot — load map, top view" meta={<StatusChip tone="review">Development analysis</StatusChip>} dense>
            <div className="flex items-center gap-2 border-b border-line px-4 py-1.5">
              {(["ORIGINAL", "PROPOSED"] as const).map((mode) => (
                <button
                  key={mode}
                  onClick={() => setPlotMode(mode)}
                  aria-pressed={plotMode === mode}
                  className={`border px-2 py-0.5 text-[9.5px] font-semibold uppercase tracking-[0.12em] ${plotMode === mode ? "border-precision/60 text-precision-dim" : "border-line-strong text-muted hover:text-platinum"}`}
                >
                  {mode}
                </button>
              ))}
              <span className="text-[10px] text-muted">
                {plotMode === "PROPOSED"
                  ? `Accepted feed regions highlighted — geometry identical by construction (masked diff).`
                  : sel
                    ? `Framing L${sel[0]}${sel[1] !== sel[0] ? `–${sel[1]}` : ""} — click the plot or the code to move; Esc clears.`
                    : "Click a path segment to jump to its source block."}
              </span>
              {sel && (
                <button onClick={() => setSel(null)} className="ml-auto text-[9.5px] font-semibold uppercase tracking-[0.12em] text-muted hover:text-platinum">
                  Clear
                </button>
              )}
            </div>
            <Backplot
              segments={r.backplot}
              bands={r.load.bands}
              extents={r.analysis.extents}
              sel={sel}
              onSelect={(line) => setSel([line, line])}
              proposedRanges={plotMode === "PROPOSED" ? [...accepted].map((i) => r.load.proposals[i]?.lines).filter(Boolean) : []}
            />
            <NcCodeViewer code={r.code} sel={sel} onSelect={(line) => setSel([line, line])} toolChanges={r.parse.toolChanges} refusals={r.parse.refusals} />
            <LoadGraph
              segments={r.backplot}
              bands={r.load.bands}
              sel={sel}
              onSelect={(line) => setSel([line, line])}
              proposals={r.load.proposals.map((p) => ({ lines: p.lines, kind: p.kind }))}
              protectedRanges={r.load.protectedHits.map((h) => h.lines)}
              toolChanges={r.parse.toolChanges}
            />
          </Panel>
          )}

          {mode === "LOAD" && (
          <>
          <Panel
            title={`Feed proposals — ${r.load.proposals.length}`}
            meta={
              <span className="flex items-center gap-2">
                {r.load.totalProposedSecondsSaved > 0 && (
                  <span className="font-mono text-[11px] text-review tabular-nums">~{r.load.totalProposedSecondsSaved}s total</span>
                )}
                <StatusChip tone="neutral">Feed-only · geometry never changes</StatusChip>
              </span>
            }
            dense
          >
            {r.load.gaps.length > 0 && (
              <ul className="border-b border-line px-4 py-2">
                {/* Each gap names exactly what is missing — and where to
                    enter it, with a coach mark waiting on arrival. */}
                {r.load.gaps.map((g) => {
                  const fix = /T\d+/.test(g)
                    ? { href: "/tools?guide=tool-crib", label: "Add the tool" }
                    : /stock/i.test(g)
                      ? { href: `/parts/${partId}?guide=define-stock`, label: "Define stock" }
                      : null;
                  return (
                    <li key={g} className="flex items-baseline gap-2 text-[11.5px] leading-relaxed text-review">
                      <span className="min-w-0 flex-1">— {g}</span>
                      {fix && (
                        <a href={fix.href} className="shrink-0 border border-precision/50 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-precision-dim hover:bg-precision/10">
                          {fix.label}
                        </a>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
            {r.load.proposals.length === 0 ? (
              <p className="px-4 py-3 text-[12px] text-muted">
                No feed proposals under this preset — nothing bands LIGHT with enough recoverable time.
              </p>
            ) : (
              <ul>
                {r.load.proposals.map((p, i) => (
                  <li key={i} className="border-b border-line/60 px-4 py-2 last:border-0">
                    <div className="flex flex-wrap items-baseline gap-x-3 font-mono text-[11.5px] tabular-nums">
                      {/* Individual acceptance is the point — there is no
                          accept-all, deliberately. */}
                      <input
                        type="checkbox"
                        aria-label={`Accept proposal at line ${p.lines[0]}`}
                        checked={accepted.has(i)}
                        onChange={(e) => {
                          const next = new Set(accepted);
                          if (e.target.checked) next.add(i);
                          else next.delete(i);
                          setAccepted(next);
                        }}
                        className="mr-1 accent-[color:var(--c-blue)]"
                      />
                      <span className="text-muted">L{p.lines[0]}{p.lines[1] !== p.lines[0] ? `–${p.lines[1]}` : ""}</span>
                      <span className="text-muted">T{p.toolNumber}</span>
                      <StatusChip tone={p.kind === "REDUCE" ? "review" : "precision"}>{p.kind === "REDUCE" ? "REDUCE — load control" : "RAISE"}</StatusChip>
                      <span className="text-platinum">F{p.originalFeed} → F{p.proposedFeed}</span>
                      {p.kind === "RAISE" ? (
                        <span className="text-review">~{p.estimatedSecondsSaved}s</span>
                      ) : (
                        <span className="text-muted">costs a little time; buys the tool and the part</span>
                      )}
                      <StatusChip tone={p.risk === "LOW" ? "pass" : "review"}>{p.risk}</StatusChip>
                      <button
                        onClick={() => showMe(p.lines)}
                        className="border border-precision/50 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-precision-dim hover:bg-precision/10"
                      >
                        Show me
                      </button>
                    </div>
                    <p className="mt-0.5 text-[12px] leading-relaxed text-platinum-dim">{p.reason}</p>
                    <p className="text-[10.5px] leading-relaxed text-muted">
                      Assumes: {p.assumptions.join(" ")} Evidence to raise confidence: {p.requiredEvidence}
                    </p>
                  </li>
                ))}
              </ul>
            )}
            {r.load.proposals.length > 0 && (
              <div className="space-y-2 border-t border-line px-4 py-2.5">
                <div className="flex flex-wrap items-center gap-3">
                  <Button onClick={generateOptimized} disabled={accepted.size === 0 || optimizing} variant="primary">
                    {optimizing ? "Applying…" : `Generate optimized program (${accepted.size} accepted)`}
                  </Button>
                  <span className="text-[11px] leading-relaxed text-muted">
                    Each accepted proposal is re-derived and matched server-side; the emitted program passes a masked
                    geometry diff and a round-trip parse or nothing is stored.
                  </span>
                </div>
                {optError && <p className="text-[12px] text-risk">{optError}</p>}
                {optimized && (
                  <div className="border border-pass/40 bg-pass/5 px-3 py-2">
                    <p className="text-[12px] font-semibold uppercase tracking-[0.1em] text-pass">
                      Optimized program stored — geometry verified identical
                    </p>
                    <p className="mt-1 font-mono text-[11.5px] text-platinum-dim tabular-nums">
                      {optimized.applied} proposal{optimized.applied === 1 ? "" : "s"} applied ·{" "}
                      {optimized.originalMinutes.toFixed(2)} → {optimized.optimizedMinutes.toFixed(2)} min · ~
                      {optimized.savedSeconds}s estimated ·{" "}
                      {optimized.lintErrors === 0 ? "lint clean" : `${optimized.lintErrors} lint errors`}
                    </p>
                    {optimized.unapplied.length > 0 && (
                      <p className="mt-1 text-[11px] text-review">
                        {optimized.unapplied.length} not applied: {optimized.unapplied.map((u) => `L${u.lines[0]} (${u.reason.split(" — ")[0]})`).join("; ")}
                      </p>
                    )}
                    <p className="mt-1 text-[11px] leading-relaxed text-muted">
                      It is now the part&apos;s latest program on the NC output page, behind the same pre-flight and the
                      same export authorization as any other — the gates decide whether it leaves, not this screen.
                    </p>
                  </div>
                )}
              </div>
            )}
          </Panel>

          {r.load.protectedHits.length > 0 && (
            <Panel title={`Finish passes protected — ${r.load.protectedHits.length} region(s)`} dense>
              <ul>
                {r.load.protectedHits.map((h) => (
                  <li key={h.label} className="flex items-start gap-3 border-b border-line/60 px-4 py-2 last:border-0">
                    <StatusChip tone="pass">PROTECTED</StatusChip>
                    <span className="min-w-0 flex-1">
                      <span className="block font-mono text-[11.5px] text-platinum">
                        {h.label} · L{h.lines[0]}–{h.lines[1]} · {h.segments} segment(s)
                        <button
                          onClick={() => showMe(h.lines)}
                          className="ml-2 border border-precision/50 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-precision-dim hover:bg-precision/10"
                        >
                          Show me
                        </button>
                      </span>
                      <span className="block text-[11.5px] leading-relaxed text-platinum-dim">{h.reason}. Cutting inside this feature receives no automatic proposal in either direction — protection is absolute in V1; overriding it is not built.</span>
                    </span>
                  </li>
                ))}
              </ul>
            </Panel>
          )}
          </>
          )}

          {mode === "COMPARE" && (accepted.size === 0 ? (
            <p className="px-1 py-2 text-[12px] text-muted">
              Nothing to compare yet — accept one or more feed proposals under LOAD and the source-level diff appears here.
            </p>
          ) : (() => {
            const acceptedList = [...accepted].map((i) => r.load.proposals[i]).filter(Boolean);
            const savedS = acceptedList.reduce((t, p) => t + (p.kind === "RAISE" ? p.estimatedSecondsSaved : 0), 0);
            const reduceCount = acceptedList.filter((p) => p.kind === "REDUCE").length;
            const proposedMin = Math.max(0, r.analysis.totalMinutes - savedS / 60);
            const mmss = (min: number) => `${Math.floor(min)}:${String(Math.round((min % 1) * 60)).padStart(2, "0")}`;
            return (
            <>
            {/* ---------- The comparison, numbers first ---------- */}
            <div className="grid grid-cols-2 gap-px bg-line sm:grid-cols-5">
              {(
                [
                  ["Original", mmss(r.analysis.totalMinutes), null],
                  ["Proposed", mmss(proposedMin), "ESTIMATED"],
                  ["Savings / part", `${savedS.toFixed(0)} s`, reduceCount > 0 ? `${reduceCount} reduction(s) add a little back — not estimated` : null],
                  ["Geometry changed", "NO", "masked diff enforced at generation"],
                  ["Finish passes changed", "NO", "protection is absolute in V1"],
                ] as const
              ).map(([label, value, note]) => (
                <div key={label} className="bg-surface px-4 py-2.5">
                  <p className="tech-label">{label}</p>
                  <p className="mt-0.5 font-mono text-[18px] text-white tabular-nums">{value}</p>
                  {note && <p className="text-[9.5px] leading-snug text-muted">{note}</p>}
                </div>
              ))}
            </div>

            {/* ---------- Overlay — one scene, changes carried by color ---------- */}
            <Panel title="Overlay — where the program changes" meta={<StatusChip tone="neutral">Same geometry by construction — color shows the feed change</StatusChip>} dense>
              <Backplot
                segments={r.backplot}
                bands={r.load.bands}
                extents={r.analysis.extents}
                sel={sel}
                onSelect={(line) => setSel([line, line])}
                proposedRanges={[]}
                overlay={{
                  raise: acceptedList.filter((p) => p.kind === "RAISE").map((p) => p.lines),
                  reduce: acceptedList.filter((p) => p.kind === "REDUCE").map((p) => p.lines),
                  protected: r.load.protectedHits.map((h) => h.lines),
                }}
              />
              <p className="border-t border-line/60 px-4 py-2 text-[10.5px] leading-relaxed text-muted">
                Ink = unchanged cutting · blue = accepted feed raise · amber = accepted reduction · green = protected finish region (never modified) · dashed gray = rapid. The toolpath is identical in both programs — only feed words differ, which this overlay carries as color instead of drawing the same lines twice.
              </p>
            </Panel>

            <Panel title={`Source diff — ${accepted.size} accepted change(s)`} meta={<StatusChip tone="neutral">Feed words only · geometry identical by masked diff</StatusChip>} dense>
              <ul>
                {[...accepted].map((i) => {
                  const p = r.load.proposals[i];
                  if (!p) return null;
                  return (
                    <DiffRow
                      key={i}
                      codeLines={r.code.split(/\r?\n/)}
                      lines={p.lines}
                      originalFeed={p.originalFeed}
                      proposedFeed={p.proposedFeed}
                      reason={p.reason}
                      saved={p.estimatedSecondsSaved}
                    />
                  );
                })}
              </ul>
              <p className="border-t border-line/60 px-4 py-2 text-[10.5px] leading-relaxed text-muted">
                This preview is derived client-side from the same rule the emitter enforces (F-word replacement on the proposal's own lines). The authoritative diff happens server-side at generation: masked geometry comparison, byte-clean or nothing is stored.
              </p>
            </Panel>
            </>
            );
          })())}

          {mode === "TIME" && (
          <>
          <RoiPanel
            currentMinutes={r.analysis.totalMinutes}
            proposedSeconds={[...accepted].reduce((t, i) => t + (r.load.proposals[i]?.kind === "RAISE" ? r.load.proposals[i].estimatedSecondsSaved : 0), 0)}
            machineRate={r.context.machineRatePerHour}
          />

          <Panel title="Cycle time" dense>
            <div className="flex flex-wrap gap-x-6 gap-y-1 px-4 py-2.5 font-mono text-[12px] text-platinum tabular-nums">
              <span>total {r.analysis.totalMinutes.toFixed(2)} min</span>
              <span className="text-platinum-dim">cutting {r.analysis.cutMinutes.toFixed(2)}</span>
              <span className="text-platinum-dim">rapid {r.analysis.rapidMinutes.toFixed(2)}</span>
              {r.analysis.dwellMinutes > 0 && <span className="text-platinum-dim">dwell {r.analysis.dwellMinutes.toFixed(2)}</span>}
              {r.analysis.recoverableSeconds > 0 && (
                <span className="text-review">~{r.analysis.recoverableSeconds.toFixed(0)}s recoverable (see findings)</span>
              )}
            </div>
            <table className="w-full text-left text-[11.5px]">
              <thead>
                <tr className="border-t border-b border-line-strong">
                  {["Tool", "Cutting", "Rapid", "Segments"].map((h) => (
                    <th key={h} className="instrument-label px-4 py-1.5">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {r.analysis.perTool.map((t) => (
                  <tr key={t.toolNumber} className="border-b border-line/60 font-mono tabular-nums last:border-0">
                    <td className="px-4 py-1.5">T{t.toolNumber}</td>
                    <td className="px-4 py-1.5">{t.cutMinutes.toFixed(2)} min</td>
                    <td className="px-4 py-1.5">{t.rapidMinutes.toFixed(2)} min</td>
                    <td className="px-4 py-1.5 text-muted">{t.segments}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="px-4 py-2 text-[11px] leading-relaxed text-muted">
              {r.analysis.assumptions.join(" ")}
            </p>
          </Panel>
          </>
          )}

          {mode === "FINDINGS" && (
          <Panel
            title={`Findings — ${r.analysis.findings.length}`}
            meta={<StatusChip tone="neutral">Analysis only — no proposals yet</StatusChip>}
            dense
          >
            {/* What CANVAS did NOT check. A silently absent check reads as a
                check that passed, which is the more dangerous of the two. */}
            {r.analysis.checksSkipped.length > 0 && (
              <div className="border-b border-line px-4 py-2.5">
                <LimitsDisclosure label={`Not checked — ${r.analysis.checksSkipped.length}`}>
                  <ul className="space-y-1.5">
                    {r.analysis.checksSkipped.map((c) => (
                      <li key={c.check}>
                        <span className="text-platinum-dim">{c.check}</span> — {c.reason}
                      </li>
                    ))}
                  </ul>
                </LimitsDisclosure>
              </div>
            )}
            {r.analysis.findings.length === 0 ? (
              <p className="px-4 py-3 text-[12px] text-muted">Nothing recoverable found at this phase's sensitivity.</p>
            ) : (
              <ul>
                {r.analysis.findings.map((f, i) => (
                  <li key={i} className="border-b border-line/60 px-4 py-2 last:border-0">
                    <div className="flex flex-wrap items-baseline gap-x-3">
                      <span className="font-mono text-[11px] text-muted">L{f.line}</span>
                      <span className="font-mono text-[11px] text-muted">T{f.toolNumber}</span>
                      <span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-platinum-dim">
                        {f.kind.replace(/_/g, " ").toLowerCase()}
                      </span>
                      <StatusChip tone={f.verdict === "CONFIDENT" ? "pass" : f.verdict === "REVIEW" ? "review" : "unknown"}>
                        {f.verdict.replace("_", " ")}
                      </StatusChip>
                      {f.seconds > 0 && <span className="font-mono text-[11.5px] text-review tabular-nums">~{f.seconds}s</span>}
                      <button
                        onClick={() => showMe([f.line, f.line])}
                        className="border border-precision/50 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-precision-dim hover:bg-precision/10"
                      >
                        Show me
                      </button>
                    </div>
                    <p className="mt-0.5 text-[12px] leading-relaxed text-platinum-dim">{f.detail}</p>
                    {f.assumptions.length > 0 && (
                      <p className="text-[10.5px] leading-relaxed text-muted">Assumes: {f.assumptions.join(" ")}</p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Panel>
          )}
        </>
      )}
    </div>
  );
}

// Drawn for the light work-window ground — fixed inks, not theme tokens.
const BAND_COLOR: Record<string, string> = {
  AIR: "#a8aeb6",
  LIGHT: "#0b72ff",
  TARGET: "#17754e",
  HIGH: "#b86a0a",
  REVIEW: "#c22a1e",
};

function Backplot({
  segments,
  bands,
  extents,
  sel,
  onSelect,
  proposedRanges,
  overlay,
}: {
  segments: [number, number, number, number, number, number][];
  bands: string[];
  extents: { minX: number; maxX: number; minY: number; maxY: number };
  sel: [number, number] | null;
  onSelect: (line: number) => void;
  proposedRanges: [number, number][];
  /** COMPARE overlay: change kind by line range. When set, unchanged
      cutting draws in neutral ink so the changes carry the color. */
  overlay?: { raise: [number, number][]; reduce: [number, number][]; protected: [number, number][] };
}) {
  const w = 640, h = 400, pad = 20;
  // Frame the selection when there is one — SHOW ME changes the scene, it
  // does not just tint a line. Otherwise frame the whole program.
  let fx0 = extents.minX, fx1 = extents.maxX, fy0 = extents.minY, fy1 = extents.maxY;
  if (sel) {
    const hits = segments.filter(([, line]) => line >= sel[0] && line <= sel[1]);
    if (hits.length > 0) {
      fx0 = Math.min(...hits.flatMap(([, , x0, , x1]) => [x0, x1]));
      fx1 = Math.max(...hits.flatMap(([, , x0, , x1]) => [x0, x1]));
      fy0 = Math.min(...hits.flatMap(([, , , y0, , y1]) => [y0, y1]));
      fy1 = Math.max(...hits.flatMap(([, , , y0, , y1]) => [y0, y1]));
      // Context margin: a quarter of the span each side, floor 0.4".
      const mx = Math.max(0.4, (fx1 - fx0) * 0.35);
      const my = Math.max(0.4, (fy1 - fy0) * 0.35);
      fx0 -= mx; fx1 += mx; fy0 -= my; fy1 += my;
    }
  }
  const spanX = Math.max(0.001, fx1 - fx0);
  const spanY = Math.max(0.001, fy1 - fy0);
  const k = Math.min((w - pad * 2) / spanX, (h - pad * 2) / spanY);
  const X = (v: number) => pad + (v - fx0) * k;
  const Y = (v: number) => h - pad - (v - fy0) * k;
  const inSel = (line: number) => sel !== null && line >= sel[0] && line <= sel[1];
  const inProposed = (line: number) => proposedRanges.some(([a, b]) => line >= a && line <= b);
  const inRanges = (line: number, ranges: [number, number][]) => ranges.some(([a, b]) => line >= a && line <= b);

  return (
    <div className="overflow-x-auto px-4 py-3">
      <svg width={w} height={h} style={{ background: "#fafaf8" }} className="border border-line">
        {segments.map(([cut, line, x0, y0, x1, y1], i) => {
          const selected = inSel(line);
          const proposed = inProposed(line);
          let stroke: string;
          let width: number;
          if (selected) {
            stroke = "#b86a0a"; width = 3;
          } else if (overlay && cut) {
            // Change kind carries the color; unchanged cutting is neutral ink.
            stroke = inRanges(line, overlay.raise)
              ? "#0b72ff"
              : inRanges(line, overlay.reduce)
                ? "#b86a0a"
                : inRanges(line, overlay.protected)
                  ? "#17754e"
                  : "#7a828c";
            width = stroke === "#7a828c" ? 1.2 : 2.4;
          } else if (proposed) {
            stroke = "#0b72ff"; width = 2.4;
          } else if (cut) {
            stroke = BAND_COLOR[bands[i]] ?? "#0b72ff"; width = 1.6;
          } else {
            stroke = "#a8aeb6"; width = 0.8;
          }
          return (
            <line
              key={i}
              x1={X(x0)} y1={Y(y0)} x2={X(x1)} y2={Y(y1)}
              stroke={stroke}
              strokeWidth={width}
              strokeDasharray={cut ? undefined : "3 3"}
              opacity={sel && !selected ? 0.25 : cut ? 0.95 : 0.4}
              style={{ cursor: "pointer" }}
              onClick={() => onSelect(line)}
            />
          );
        })}
      </svg>
      {!overlay && (
        <p className="mt-1.5 text-[10.5px] text-muted">
          Load bands from chipload + replay: gray/dashed rapid · blue light (rubbing) · green target · orange high ·
          red review. Estimates, not measurements — no spindle telemetry exists.
        </p>
      )}
    </div>
  );
}

/**
 * BLOCK-SYNCED NC VIEWER — the immutable original, read-only. Selecting a
 * line here highlights its motion; selecting motion scrolls here. Line
 * numbers are 1-indexed and match every finding and proposal.
 *
 * Power features, all read-only: text search with prev/next, go-to-block
 * (type N420 for the block word, 420 alone for the line number), and
 * gutter markers — T<n> at tool changes, a red edge where interpretation
 * refused. Search never edits and never filters: the program always shows
 * whole, matches are jumped to, not extracted.
 */
function NcCodeViewer({
  code,
  sel,
  onSelect,
  toolChanges = [],
  refusals = [],
}: {
  code: string;
  sel: [number, number] | null;
  onSelect: (line: number) => void;
  toolChanges?: { line: number; toolNumber: number }[];
  refusals?: { line: number; reason: string }[];
}) {
  const boxRef = useRef<HTMLDivElement>(null);
  const lines = useMemo(() => code.split(/\r?\n/), [code]);
  const [query, setQuery] = useState("");
  const matches = useMemo(() => {
    const q = query.trim();
    if (!q || /^N?\d+$/i.test(q)) return [];
    const ql = q.toLowerCase();
    const out: number[] = [];
    lines.forEach((t, i) => { if (t.toLowerCase().includes(ql)) out.push(i + 1); });
    return out;
  }, [query, lines]);
  const toolAt = useMemo(() => new Map(toolChanges.map((t) => [t.line, t.toolNumber])), [toolChanges]);
  const refusalAt = useMemo(() => new Set(refusals.map((r) => r.line)), [refusals]);

  const jump = (dir: 1 | -1) => {
    const q = query.trim();
    // Go-to: N420 finds the block carrying that N-word; a bare number is a line number.
    const m = /^N?(\d+)$/i.exec(q);
    if (m) {
      if (/^n/i.test(q)) {
        const re = new RegExp(`^\\s*N0*${m[1]}(?![\\d])`, "i");
        const idx = lines.findIndex((t) => re.test(t));
        if (idx >= 0) onSelect(idx + 1);
      } else {
        const n = Number(m[1]);
        if (n >= 1 && n <= lines.length) onSelect(n);
      }
      return;
    }
    if (matches.length === 0) return;
    const cur = sel?.[0] ?? 0;
    const next =
      dir === 1
        ? matches.find((n) => n > cur) ?? matches[0]
        : [...matches].reverse().find((n) => n < cur) ?? matches[matches.length - 1];
    onSelect(next);
  };

  useEffect(() => {
    if (!sel || !boxRef.current) return;
    const el = boxRef.current.querySelector<HTMLElement>(`[data-nc-line="${sel[0]}"]`);
    el?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [sel]);
  return (
    <div className="border-t border-line">
      <div className="flex flex-wrap items-center gap-3 px-4 py-1.5">
        <span className="instrument-label">Original program — immutable, read-only</span>
        <span className="flex items-center gap-1">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") jump(e.shiftKey ? -1 : 1); }}
            placeholder="search · N420 · line #"
            aria-label="Search program or go to block"
            className="w-40 border border-line-strong bg-void px-2 py-0.5 font-mono text-[10.5px] text-platinum placeholder:text-muted"
          />
          <button onClick={() => jump(-1)} aria-label="Previous match" className="border border-line-strong px-1.5 py-0.5 text-[10px] text-muted hover:text-platinum">↑</button>
          <button onClick={() => jump(1)} aria-label="Next match" className="border border-line-strong px-1.5 py-0.5 text-[10px] text-muted hover:text-platinum">↓</button>
          {query.trim() && !/^N?\d+$/i.test(query.trim()) && (
            <span className="font-mono text-[10px] text-muted tabular-nums">{matches.length} match{matches.length === 1 ? "" : "es"}</span>
          )}
        </span>
        <span className="ml-auto font-mono text-[10px] text-muted tabular-nums">{lines.length} lines</span>
      </div>
      <div ref={boxRef} className="max-h-[260px] overflow-y-auto bg-void font-mono text-[11.5px] leading-[1.5]">
        {lines.map((text, i) => {
          const n = i + 1;
          const hit = sel !== null && n >= sel[0] && n <= sel[1];
          const isMatch = matches.length > 0 && text.toLowerCase().includes(query.trim().toLowerCase());
          const tool = toolAt.get(n);
          const refused = refusalAt.has(n);
          return (
            <div
              key={n}
              data-nc-line={n}
              onClick={() => onSelect(n)}
              className={`flex cursor-pointer gap-3 px-3 ${refused ? "shadow-[inset_2px_0_0_var(--c-red,#c22a1e)]" : ""} ${
                hit ? "bg-precision/15 text-platinum" : isMatch ? "bg-review/10 text-platinum-dim" : "text-platinum-dim hover:bg-panel"
              }`}
            >
              <span className={`w-10 shrink-0 select-none text-right tabular-nums ${hit ? "text-precision-dim" : "text-muted"}`}>{n}</span>
              <span className="w-7 shrink-0 select-none text-[9.5px] leading-[1.8]">
                {tool !== undefined && <span className="text-precision-dim">T{tool}</span>}
                {refused && <span className="text-risk">✕</span>}
              </span>
              <span className="whitespace-pre">{text || " "}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Engagement band → graph level. Order is severity, not value.
const BAND_LEVEL: Record<string, number> = { AIR: 0.5, LIGHT: 1, TARGET: 2, HIGH: 3, REVIEW: 4 };

/**
 * SYNCHRONIZED LOAD GRAPH — the program as an engagement timeline.
 *
 * One bar per motion segment in program order, height and color from the
 * engagement band; rapids draw as thin gray ticks. Overlays: tool-change
 * boundaries, proposal markers (RAISE blue / REDUCE amber), protected
 * finish regions. The same selection state drives the backplot, the code
 * viewer and this graph — click a bar to select its source block, and any
 * SHOW ME lights up the matching span here.
 *
 * Chipload-model estimate, not telemetry — the DEVELOPMENT label stays.
 */
function LoadGraph({
  segments,
  bands,
  sel,
  onSelect,
  proposals,
  protectedRanges,
  toolChanges,
}: {
  segments: [number, number, number, number, number, number][];
  bands: string[];
  sel: [number, number] | null;
  onSelect: (line: number) => void;
  proposals: { lines: [number, number]; kind: "RAISE" | "REDUCE" }[];
  protectedRanges: [number, number][];
  toolChanges: { line: number; toolNumber: number }[];
}) {
  const w = 920, h = 120, padL = 8, padB = 16, padT = 14;
  const n = segments.length;
  if (n === 0) return null;
  const bw = (w - padL * 2) / n;
  const yFor = (lvl: number) => h - padB - (lvl / 4) * (h - padB - padT);
  const inRange = (line: number, ranges: [number, number][]) => ranges.some(([a, b]) => line >= a && line <= b);
  // Tool-change boundaries: first segment index at or past the change line.
  const boundaries = toolChanges
    .map((tc) => ({ tc, idx: segments.findIndex(([, line]) => line >= tc.line) }))
    .filter((b) => b.idx > 0);
  return (
    <div className="border-t border-line px-4 py-2.5">
      <div className="mb-1 flex items-center justify-between">
        <span className="instrument-label">Load along the program — engagement band per segment</span>
        <span className="font-mono text-[9.5px] uppercase tracking-[0.12em] text-review">Development load estimate</span>
      </div>
      <div className="overflow-x-auto">
        <svg width={w} height={h} style={{ background: "#fafaf8" }} className="border border-line">
          {/* Target band reference */}
          <rect x={padL} y={yFor(2.5)} width={w - padL * 2} height={yFor(1.5) - yFor(2.5)} fill="#17754e" opacity={0.06} />
          {segments.map(([cut, line], i) => {
            const selHit = sel !== null && line >= sel[0] && line <= sel[1];
            const lvl = cut ? (BAND_LEVEL[bands[i]] ?? 1) : 0.25;
            const color = cut ? (BAND_COLOR[bands[i]] ?? "#0b72ff") : "#c6ccd2";
            return (
              <rect
                key={i}
                x={padL + i * bw}
                y={yFor(lvl)}
                width={Math.max(0.8, bw - 0.4)}
                height={h - padB - yFor(lvl)}
                fill={selHit ? "#b86a0a" : color}
                opacity={sel && !selHit ? 0.3 : cut ? 0.9 : 0.5}
                style={{ cursor: "pointer" }}
                onClick={() => onSelect(line)}
              />
            );
          })}
          {/* Protected finish regions — hatched span above the bars */}
          {segments.map(([, line], i) =>
            inRange(line, protectedRanges) ? (
              <rect key={`p${i}`} x={padL + i * bw} y={padT - 8} width={Math.max(0.8, bw)} height={4} fill="#17754e" opacity={0.85} />
            ) : null,
          )}
          {/* Proposal markers */}
          {segments.map(([, line], i) => {
            const hit = proposals.find((p) => line >= p.lines[0] && line <= p.lines[1]);
            return hit ? (
              <rect key={`m${i}`} x={padL + i * bw} y={padT - 3} width={Math.max(0.8, bw)} height={4} fill={hit.kind === "RAISE" ? "#0b72ff" : "#b86a0a"} opacity={0.9} />
            ) : null;
          })}
          {/* Tool-change boundaries */}
          {boundaries.map(({ tc, idx }) => (
            <g key={`t${tc.line}`}>
              <line x1={padL + idx * bw} y1={padT - 10} x2={padL + idx * bw} y2={h - padB} stroke="#5a616b" strokeWidth={0.8} strokeDasharray="3 3" />
              <text x={padL + idx * bw + 3} y={h - 5} fontSize={8.5} fill="#5a616b" fontFamily="monospace">T{tc.toolNumber}</text>
            </g>
          ))}
        </svg>
      </div>
      <p className="mt-1 text-[10px] leading-relaxed text-muted">
        Top strips: green = protected finish region (no proposal either direction) · blue = proposed feed raise · amber = proposed reduction. Click a bar to jump to its source block; the backplot and code follow the same selection.
      </p>
    </div>
  );
}

/** One accepted proposal as a source-level diff row — original vs proposed text. */
function DiffRow({ codeLines, lines, originalFeed, proposedFeed, reason, saved }: {
  codeLines: string[];
  lines: [number, number];
  originalFeed: number;
  proposedFeed: number;
  reason: string;
  saved: number;
}) {
  // Find the block in range that carries the matching F-word; show it both ways.
  const feedRe = new RegExp(`F\\s*0*${originalFeed}(?:\\.\\d*)?(?![\\d.])`);
  let shown: { n: number; before: string; after: string } | null = null;
  for (let n = lines[0]; n <= lines[1] && n <= codeLines.length; n++) {
    const text = codeLines[n - 1] ?? "";
    if (feedRe.test(text)) {
      shown = { n, before: text, after: text.replace(feedRe, `F${proposedFeed}.`) };
      break;
    }
  }
  return (
    <li className="border-b border-line/60 px-4 py-2 last:border-0">
      <p className="font-mono text-[10.5px] text-muted">L{lines[0]}{lines[1] !== lines[0] ? `–${lines[1]}` : ""} · {reason}{saved > 0 ? ` · ~${saved}s` : ""}</p>
      {shown ? (
        <div className="mt-1 font-mono text-[11.5px]">
          <p className="text-risk/90"><span className="select-none">− </span>{shown.before}</p>
          <p className="text-pass"><span className="select-none">+ </span>{shown.after}</p>
        </div>
      ) : (
        <p className="mt-1 text-[11px] text-review">Feed is modal here (set on an earlier line) — the emitter will report this proposal unapplied rather than inserting words.</p>
      )}
    </li>
  );
}

/** ROI / capacity — deterministic arithmetic over ESTIMATED inputs, assumptions shown. */
function RoiPanel({ currentMinutes, proposedSeconds, machineRate }: { currentMinutes: number; proposedSeconds: number; machineRate: number | null }) {
  const [batch, setBatch] = useState(100);
  const [annual, setAnnual] = useState(1000);
  const proposedMinutes = Math.max(0, currentMinutes - proposedSeconds / 60);
  const savedMin = currentMinutes - proposedMinutes;
  const batchHours = (savedMin * batch) / 60;
  const annualHours = (savedMin * annual) / 60;
  return (
    <Panel title="ROI / capacity" meta={<StatusChip tone="review">ESTIMATED</StatusChip>} dense>
      <div className="flex flex-wrap items-end gap-4 border-b border-line px-4 py-2.5">
        <label className="block">
          <span className="tech-label mb-1 block">Batch qty</span>
          <input value={batch} onChange={(e) => setBatch(Math.max(1, Number(e.target.value) || 1))} inputMode="numeric" className="w-20 border border-line-strong bg-void px-2 py-1 font-mono text-[12px] text-platinum" />
        </label>
        <label className="block">
          <span className="tech-label mb-1 block">Annual qty</span>
          <input value={annual} onChange={(e) => setAnnual(Math.max(0, Number(e.target.value) || 0))} inputMode="numeric" className="w-24 border border-line-strong bg-void px-2 py-1 font-mono text-[12px] text-platinum" />
        </label>
      </div>
      <div className="grid grid-cols-2 gap-px bg-line px-0 sm:grid-cols-4">
        {[
          ["Save / part", `${(savedMin * 60).toFixed(1)} s`],
          ["Batch", `${batchHours.toFixed(1)} hr`],
          ["Annual capacity", `${annualHours.toFixed(1)} hr`],
          ["Capacity value", machineRate !== null ? `$${(annualHours * machineRate).toFixed(0)}` : "no rate set"],
        ].map(([label, value]) => (
          <div key={label} className="bg-surface px-4 py-2.5">
            <p className="tech-label">{label}</p>
            <p className="mt-0.5 font-mono text-[16px] text-white tabular-nums">{value}</p>
          </div>
        ))}
      </div>
      <p className="px-4 py-2 text-[10.5px] leading-relaxed text-muted">
        From the ACCEPTED raise proposals only — reductions cost a little time and are not counted as savings. Recovered hours are capacity, not revenue; they are worth money only if the spindle time is refilled.{machineRate !== null ? ` Valued at the shop's configured $${machineRate}/hr machine rate.` : " No shop machine rate configured — no dollar figure is shown rather than assuming one."}
      </p>
    </Panel>
  );
}
