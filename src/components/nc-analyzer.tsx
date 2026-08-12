"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Button, Notice, Panel, StatusChip } from "@/components/ui";

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
    extents: { minX: number; maxX: number; minY: number; maxY: number };
  };
  context: { stockBound: boolean; toolsKnown: number; rapidRate: number; machine: string | null; machineRatePerHour: number | null };
}

export function NcAnalyzer({ partId }: { partId: string }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [preset, setPreset] = useState("BALANCED");
  const [state, setState] = useState<{ busy: boolean; error: string | null; report: Report | null }>({
    busy: false, error: null, report: null,
  });
  const [accepted, setAccepted] = useState<Set<number>>(new Set());
  // SHOW ME selection: a source-line range that the backplot frames and
  // highlights and the code viewer scrolls to — one selection, two scenes.
  const [sel, setSel] = useState<[number, number] | null>(null);
  const [plotMode, setPlotMode] = useState<"ORIGINAL" | "PROPOSED">("ORIGINAL");
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
    const res = await fetch(`/api/parts/${partId}/nc-analyze?preset=${preset}`, { method: "POST", body });
    const json = await res.json().catch(() => null);
    if (!res.ok || !json?.analysis) { setState({ busy: false, error: json?.error ?? "Analysis failed.", report: null }); return; }
    setState({ busy: false, error: null, report: json as Report });
  }

  async function run() {
    const file = fileRef.current?.files?.[0];
    if (!file) { setState((s) => ({ ...s, error: "Choose an .nc / .txt program first." })); return; }
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
            {r.parse.warnings.length > 0 && (
              <ul className="border-t border-line px-4 py-2">
                {r.parse.warnings.map((w) => (
                  <li key={w} className="text-[11.5px] leading-relaxed text-review">— {w}</li>
                ))}
              </ul>
            )}
          </Panel>

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

          <Panel title={`Operations — ${r.operations.length} group(s)`} meta={<StatusChip tone="neutral">Deterministic motion evidence only</StatusChip>} dense>
            <ul>
              {r.operations.map((op, i) => (
                <li key={i} className="flex items-start gap-3 border-b border-line/60 px-4 py-1.5 last:border-0">
                  <StatusChip tone={op.kind === "UNKNOWN" ? "unknown" : op.kind === "LINKING" ? "neutral" : "precision"}>{op.kind}</StatusChip>
                  <span className="min-w-0 flex-1">
                    <span className="block font-mono text-[11px] text-muted">
                      T{op.toolNumber} · L{op.lines[0]}–{op.lines[1]} · {op.cutSegments} cutting segment(s)
                      <button
                        onClick={() => setSel(op.lines)}
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
            <NcCodeViewer code={r.code} sel={sel} onSelect={(line) => setSel([line, line])} />
          </Panel>

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
                {r.load.gaps.map((g) => (
                  <li key={g} className="text-[11.5px] leading-relaxed text-review">— {g}</li>
                ))}
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
                        onClick={() => setSel(p.lines)}
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
                          onClick={() => setSel(h.lines)}
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

          {accepted.size > 0 && (
            <Panel title={`Original vs proposed — ${accepted.size} accepted change(s)`} meta={<StatusChip tone="neutral">Feed words only · geometry identical by masked diff</StatusChip>} dense>
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
          )}

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

          <Panel
            title={`Findings — ${r.analysis.findings.length}`}
            meta={<StatusChip tone="neutral">Analysis only — no proposals yet</StatusChip>}
            dense
          >
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
                        onClick={() => setSel([f.line, f.line])}
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
}: {
  segments: [number, number, number, number, number, number][];
  bands: string[];
  extents: { minX: number; maxX: number; minY: number; maxY: number };
  sel: [number, number] | null;
  onSelect: (line: number) => void;
  proposedRanges: [number, number][];
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

  return (
    <div className="overflow-x-auto px-4 py-3">
      <svg width={w} height={h} style={{ background: "#fafaf8" }} className="border border-line">
        {segments.map(([cut, line, x0, y0, x1, y1], i) => {
          const selected = inSel(line);
          const proposed = inProposed(line);
          return (
            <line
              key={i}
              x1={X(x0)} y1={Y(y0)} x2={X(x1)} y2={Y(y1)}
              stroke={
                selected
                  ? "#b86a0a"
                  : proposed
                    ? "#0b72ff"
                    : cut
                      ? (BAND_COLOR[bands[i]] ?? "#0b72ff")
                      : "#a8aeb6"
              }
              strokeWidth={selected ? 3 : proposed ? 2.4 : cut ? 1.6 : 0.8}
              strokeDasharray={cut ? undefined : "3 3"}
              opacity={sel && !selected ? 0.25 : cut ? 0.95 : 0.4}
              style={{ cursor: "pointer" }}
              onClick={() => onSelect(line)}
            />
          );
        })}
      </svg>
      <p className="mt-1.5 text-[10.5px] text-muted">
        Load bands from chipload + replay: gray/dashed rapid · blue light (rubbing) · green target · orange high ·
        red review. Estimates, not measurements — no spindle telemetry exists.
      </p>
    </div>
  );
}

/**
 * BLOCK-SYNCED NC VIEWER — the immutable original, read-only. Selecting a
 * line here highlights its motion; selecting motion scrolls here. Line
 * numbers are 1-indexed and match every finding and proposal.
 */
function NcCodeViewer({ code, sel, onSelect }: { code: string; sel: [number, number] | null; onSelect: (line: number) => void }) {
  const boxRef = useRef<HTMLDivElement>(null);
  const lines = useMemo(() => code.split(/\r?\n/), [code]);
  useEffect(() => {
    if (!sel || !boxRef.current) return;
    const el = boxRef.current.querySelector<HTMLElement>(`[data-nc-line="${sel[0]}"]`);
    el?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [sel]);
  return (
    <div className="border-t border-line">
      <div className="flex items-center justify-between px-4 py-1.5">
        <span className="instrument-label">Original program — immutable, read-only</span>
        <span className="font-mono text-[10px] text-muted tabular-nums">{lines.length} lines</span>
      </div>
      <div ref={boxRef} className="max-h-[260px] overflow-y-auto bg-void font-mono text-[11.5px] leading-[1.5]">
        {lines.map((text, i) => {
          const n = i + 1;
          const hit = sel !== null && n >= sel[0] && n <= sel[1];
          return (
            <div
              key={n}
              data-nc-line={n}
              onClick={() => onSelect(n)}
              className={`flex cursor-pointer gap-3 px-3 ${hit ? "bg-precision/15 text-platinum" : "text-platinum-dim hover:bg-panel"}`}
            >
              <span className={`w-10 shrink-0 select-none text-right tabular-nums ${hit ? "text-precision-dim" : "text-muted"}`}>{n}</span>
              <span className="whitespace-pre">{text || " "}</span>
            </div>
          );
        })}
      </div>
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
