"use client";

import { useRef, useState } from "react";
import { Button, Notice, Panel, StatusChip } from "@/components/ui";

/**
 * NC ANALYZER — Phase 4A/4B client
 *
 * Upload → parse report → backplot → cycle breakdown → findings. Analysis
 * only: there are no optimization proposals yet and the screen says so.
 * Every finding carries its verdict — CONFIDENT is replay-proven, REVIEW is
 * a heuristic, INSUFFICIENT_DATA names what is missing.
 */

interface Report {
  fileName: string;
  parse: {
    lineCount: number;
    segments: number;
    refusals: { line: number; reason: string }[];
    warnings: string[];
    units: string;
    workOffsetsSeen: string[];
    toolChanges: { line: number; toolNumber: number }[];
  };
  backplot: [number, number, number, number, number][];
  load: {
    bands: string[];
    proposals: {
      lines: [number, number]; toolNumber: number; originalFeed: number; proposedFeed: number;
      estimatedSecondsSaved: number; reason: string; risk: string; assumptions: string[];
      requiredEvidence: string; geometryChanges: false;
    }[];
    totalProposedSecondsSaved: number;
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
  context: { stockBound: boolean; toolsKnown: number; rapidRate: number; machine: string | null };
}

export function NcAnalyzer({ partId }: { partId: string }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [preset, setPreset] = useState("BALANCED");
  const [state, setState] = useState<{ busy: boolean; error: string | null; report: Report | null }>({
    busy: false, error: null, report: null,
  });
  const [accepted, setAccepted] = useState<Set<number>>(new Set());
  const [optimizing, setOptimizing] = useState(false);
  const [optimized, setOptimized] = useState<{
    programId: string; applied: number; savedSeconds: number;
    originalMinutes: number; optimizedMinutes: number; lintErrors: number;
    unapplied: { lines: [number, number]; reason: string }[];
  } | null>(null);
  const [optError, setOptError] = useState<string | null>(null);

  async function generateOptimized() {
    const file = fileRef.current?.files?.[0];
    const r = state.report;
    if (!file || !r || accepted.size === 0) return;
    setOptimizing(true);
    setOptError(null);
    const body = new FormData();
    body.append("file", file);
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

  async function run() {
    const file = fileRef.current?.files?.[0];
    if (!file) { setState((s) => ({ ...s, error: "Choose an .nc / .txt program first." })); return; }
    setState({ busy: true, error: null, report: null });
    const body = new FormData();
    body.append("file", file);
    const res = await fetch(`/api/parts/${partId}/nc-analyze?preset=${preset}`, { method: "POST", body });
    const json = await res.json().catch(() => null);
    if (!res.ok || !json?.analysis) { setState({ busy: false, error: json?.error ?? "Analysis failed.", report: null }); return; }
    setState({ busy: false, error: null, report: json as Report });
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

          <Panel title="Backplot — load map, top view" meta={<StatusChip tone="review">Development analysis</StatusChip>} dense>
            <Backplot segments={r.backplot} bands={r.load.bands} extents={r.analysis.extents} />
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
                      <span className="text-platinum">F{p.originalFeed} → F{p.proposedFeed}</span>
                      <span className="text-review">~{p.estimatedSecondsSaved}s</span>
                      <StatusChip tone={p.risk === "LOW" ? "pass" : "review"}>{p.risk}</StatusChip>
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

const BAND_COLOR: Record<string, string> = {
  AIR: "var(--c-muted)",
  LIGHT: "#4d97ff",
  TARGET: "var(--c-pass, #17754e)",
  HIGH: "var(--c-review, #96570d)",
  REVIEW: "var(--c-risk, #c22a1e)",
};

function Backplot({
  segments,
  bands,
  extents,
}: {
  segments: [number, number, number, number, number][];
  bands: string[];
  extents: { minX: number; maxX: number; minY: number; maxY: number };
}) {
  const w = 640, h = 400, pad = 20;
  const spanX = Math.max(0.001, extents.maxX - extents.minX);
  const spanY = Math.max(0.001, extents.maxY - extents.minY);
  const k = Math.min((w - pad * 2) / spanX, (h - pad * 2) / spanY);
  const X = (v: number) => pad + (v - extents.minX) * k;
  const Y = (v: number) => h - pad - (v - extents.minY) * k;
  return (
    <div className="overflow-x-auto px-4 py-3">
      <svg width={w} height={h} className="border border-line bg-work">
        {segments.map(([cut, x0, y0, x1, y1], i) => (
          <line
            key={i}
            x1={X(x0)} y1={Y(y0)} x2={X(x1)} y2={Y(y1)}
            stroke={cut ? (BAND_COLOR[bands[i]] ?? "var(--c-blue)") : "var(--c-muted)"}
            strokeWidth={cut ? 1.6 : 0.8}
            strokeDasharray={cut ? undefined : "3 3"}
            opacity={cut ? 0.95 : 0.4}
          />
        ))}
      </svg>
      <p className="mt-1.5 text-[10.5px] text-muted">
        Load bands from chipload + replay: gray/dashed rapid · blue light (rubbing) · green target · orange high ·
        red review. Estimates, not measurements — no spindle telemetry exists.
      </p>
    </div>
  );
}
