"use client";

import { useState } from "react";
import { DevLabel, Notice, Panel, StatusChip, type Tone } from "@/components/ui";
import type { LatheNCSegment, LatheParseRefusal, LatheNCFinding } from "@/lib/manufacturing/turn/nc-parse";

/**
 * LATHE NC REVIEW — upload/paste a 2-axis program, get the honest report:
 * X/Z backplot (rapids dashed, cuts solid, CSS regions tinted), refusals by
 * line, findings with verdicts, ESTIMATED cycle with stated assumptions.
 * Analysis only: nothing here rewrites, exports or certifies anything.
 */

interface Report {
  parse: {
    lineCount: number;
    segments: LatheNCSegment[];
    refusals: LatheParseRefusal[];
    warnings: string[];
    toolCalls: { line: number; station: string }[];
    cssRegions: number;
    sawG50: boolean;
    units: string;
  };
  analysis: {
    cutMinutes: number;
    rapidMinutes: number;
    unknownSegments: number;
    totalMinutes: number;
    findings: LatheNCFinding[];
    assumptions: string[];
    perTool: { station: string; cutMinutes: number; segments: number }[];
  };
  chuckMaxRpm: number | null;
}

const VERDICT_TONE: Record<string, Tone> = { CONFIDENT: "risk", REVIEW: "review", INSUFFICIENT_DATA: "unknown" };

export function LatheNcReview({ partId }: { partId: string }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);

  async function analyze() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/lathe/${partId}/nc-analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const json = await res.json();
      if (!res.ok) setError(json.error ?? "Analysis failed.");
      else setReport(json as Report);
    } catch {
      setError("Analysis failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <Panel title="Program" meta={<DevLabel>Analysis only — nothing is rewritten or exported</DevLabel>}>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={8}
          placeholder="Paste a Fanuc/Haas-style 2-axis lathe program…"
          className="w-full border border-line-strong bg-void px-2 py-1.5 font-mono text-[11.5px] text-platinum"
        />
        <div className="mt-2 flex items-center gap-3">
          <button
            onClick={analyze}
            disabled={busy || !text.trim()}
            className="border border-precision/50 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-precision-dim hover:bg-precision/10 disabled:opacity-40"
          >
            {busy ? "Reading…" : "Run it past CANVAS"}
          </button>
          {error && <span className="text-[12px] text-risk">{error}</span>}
        </div>
      </Panel>

      {report && (
        <>
          <Panel
            title="Backplot — X/Z"
            meta={
              <span className="font-mono text-[10.5px] text-muted tabular-nums">
                {report.parse.segments.length} moves · {report.parse.toolCalls.length} tool calls · {report.parse.cssRegions} CSS region{report.parse.cssRegions === 1 ? "" : "s"}
              </span>
            }
          >
            <Backplot segments={report.parse.segments} />
          </Panel>

          {report.parse.refusals.length > 0 && (
            <Panel title={`Refused blocks — ${report.parse.refusals.length}`} dense>
              <ul>
                {report.parse.refusals.map((r, i) => (
                  <li key={i} className="flex gap-3 border-b border-line/60 px-4 py-1.5 font-mono text-[11.5px] last:border-0">
                    <span className="text-muted">line {r.line}</span>
                    <span className="text-risk">{r.code}</span>
                    <span className="min-w-0 flex-1 text-platinum-dim">{r.reason}</span>
                  </li>
                ))}
              </ul>
            </Panel>
          )}

          <Panel title={`Findings — ${report.analysis.findings.length}`} dense>
            {report.analysis.findings.length === 0 ? (
              <p className="px-4 py-2 text-[12px] text-muted">Nothing to raise within what the parser understands.</p>
            ) : (
              <ul>
                {report.analysis.findings.map((f, i) => (
                  <li key={i} className="flex items-start gap-3 border-b border-line/60 px-4 py-2 last:border-0">
                    <StatusChip tone={VERDICT_TONE[f.verdict]}>{f.verdict.replace(/_/g, " ")}</StatusChip>
                    <span className="min-w-0 flex-1">
                      <span className="block font-mono text-[11px] text-muted">{f.kind.replace(/_/g, " ")} · line {f.line}</span>
                      <span className="block text-[12px] leading-relaxed text-platinum-dim">{f.detail}</span>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel title="Cycle estimate" meta={<DevLabel>ESTIMATED</DevLabel>}>
            <p className="font-mono text-[16px] text-platinum tabular-nums">
              {report.analysis.totalMinutes.toFixed(2)} min
              <span className="ml-3 text-[11px] text-muted">
                cut {report.analysis.cutMinutes.toFixed(2)} · rapid {report.analysis.rapidMinutes.toFixed(2)}
                {report.analysis.unknownSegments > 0 && ` · ${report.analysis.unknownSegments} segments untimed (missing context)`}
              </span>
            </p>
            <ul className="mt-2 space-y-0.5">
              {report.analysis.assumptions.map((a, i) => (
                <li key={i} className="text-[11px] leading-relaxed text-muted">{a}</li>
              ))}
            </ul>
            {report.analysis.perTool.length > 0 && (
              <table className="mt-2 border-collapse">
                <tbody>
                  {report.analysis.perTool.map((t) => (
                    <tr key={t.station}>
                      <td className="pr-4 font-mono text-[11px] text-precision-dim">T{t.station}</td>
                      <td className="pr-4 font-mono text-[11px] text-muted tabular-nums">{t.cutMinutes.toFixed(2)} min</td>
                      <td className="font-mono text-[11px] text-muted tabular-nums">{t.segments} segments</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>

          {report.parse.warnings.length > 0 && (
            <Notice tone="review" title="Parser notes">
              {report.parse.warnings.join(" ")}
            </Notice>
          )}
        </>
      )}
    </div>
  );
}

/** X/Z backplot on light paper. X is diameter; drawn as radius above the centerline. */
function Backplot({ segments }: { segments: LatheNCSegment[] }) {
  if (segments.length === 0) return <p className="text-[12px] text-muted">No motion parsed.</p>;
  const zs = segments.flatMap((s) => [s.z0, s.z1]);
  const xs = segments.flatMap((s) => [Math.abs(s.x0) / 2, Math.abs(s.x1) / 2]);
  const zMin = Math.min(...zs), zMax = Math.max(...zs);
  const rMax = Math.max(...xs, 0.1);
  const W = 860, H = 300, pad = 34;
  const sx = (W - 2 * pad) / Math.max(0.001, zMax - zMin);
  const sy = (H - 2 * pad) / rMax;
  const sc = Math.min(sx, sy * 2);
  const px = (zz: number) => pad + (zz - zMin) * sc;
  const py = (r: number) => H - pad - r * Math.min(sy, sc);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ background: "#fafaf8" }} className="w-full border border-line" role="img" aria-label="Lathe NC backplot">
      <line x1={pad - 10} y1={py(0)} x2={W - pad + 10} y2={py(0)} stroke="#0b72ff" strokeWidth={1} strokeDasharray="14 4 3 4" opacity={0.6} />
      {segments.map((s, i) => (
        <line
          key={i}
          x1={px(s.z0)}
          y1={py(Math.abs(s.x0) / 2)}
          x2={px(s.z1)}
          y2={py(Math.abs(s.x1) / 2)}
          stroke={s.kind === "RAPID" ? "#a8aeb6" : s.css ? "#0b72ff" : "#14181c"}
          strokeWidth={s.kind === "RAPID" ? 0.8 : 1.5}
          strokeDasharray={s.kind === "RAPID" ? "4 3" : undefined}
          opacity={s.kind === "RAPID" ? 0.65 : 0.9}
        />
      ))}
      <text x={W - pad} y={H - 8} fontSize={9} fill="#5a616b" fontFamily="monospace" textAnchor="end">
        blue = CSS cut · black = fixed-RPM cut · dashed = rapid
      </text>
    </svg>
  );
}
