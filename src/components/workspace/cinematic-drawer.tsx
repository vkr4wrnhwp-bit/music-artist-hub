"use client";

import { useMemo, useState } from "react";
import {
  generateCinematic,
  DISCLAIMER,
  STYLE_LABEL,
  type CinematicInput,
  type CinematicOp,
  type CinematicSettings,
} from "@/lib/cinematic";

/**
 * CINEMATIC TOOLPATH — a film prompt, not a verification.
 *
 * Everything rendered here is generated deterministically from structured
 * CANVAS state and labelled CINEMATIC PREVIEW — NOT NC VERIFICATION. The
 * technical toolpath player and the stock-removal simulator are untouched;
 * this drawer only writes text. Copy and download are real; sending to an
 * external generator is a DEVELOPMENT stub behind a privacy notice, because
 * a prompt full of part geometry is proprietary data the moment it leaves.
 */

const label = "text-[9px] font-semibold uppercase tracking-[0.14em] text-muted";
const btn = (on: boolean) =>
  `border px-1.5 py-1 text-[9px] font-semibold uppercase tracking-[0.1em] transition-colors ${
    on ? "border-precision/60 text-precision-dim" : "border-line-strong text-muted hover:text-platinum"
  }`;

type OutputTab = "FULL" | "SHORT" | "SHOTS" | "JSON";

const DEFAULT_INCLUDE: CinematicSettings["include"] = {
  softJaws: true,
  stock: true,
  toolAndHolder: true,
  toolpathTrace: true,
  materialRemoval: true,
  datumLabels: true,
  measurementOverlays: true,
  operationLabels: true,
  coolantChips: false,
  finalReveal: true,
};

export function CinematicDrawer({
  input,
  activeOperationId,
  onClose,
}: {
  input: CinematicInput;
  activeOperationId: string | null;
  onClose: () => void;
}) {
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(activeOperationId ? [activeOperationId] : input.operations.slice(0, 1).map((o) => o.id)),
  );
  const [duration, setDuration] = useState<CinematicSettings["durationSeconds"]>(10);
  const [style, setStyle] = useState<CinematicSettings["style"]>("PREMIUM_PRODUCT_RENDER");
  const [include, setInclude] = useState(DEFAULT_INCLUDE);
  const [customerSafe, setCustomerSafe] = useState(false);
  const [tab, setTab] = useState<OutputTab>("FULL");
  const [copied, setCopied] = useState(false);

  const ops: CinematicOp[] = input.operations.filter((o) => selected.has(o.id));
  const result = useMemo(
    () =>
      ops.length > 0
        ? generateCinematic({ ...input, operations: ops }, { durationSeconds: duration, style, include, customerSafe })
        : null,
    [input, ops, duration, style, include, customerSafe],
  );

  const outputText = !result
    ? ""
    : tab === "FULL"
      ? `${result.title}\n\n${result.prompt}\n\n${DISCLAIMER}`
      : tab === "SHORT"
        ? `${result.shortPrompt}\n\n${DISCLAIMER}`
        : tab === "SHOTS"
          ? result.shots.map((s) => `${s.start}–${s.end}s  ${s.operation}: ${s.visual}`).join("\n") + `\n\n${DISCLAIMER}`
          : JSON.stringify(result.storyboard, null, 2);

  async function copy() {
    await navigator.clipboard.writeText(outputText).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }
  function download() {
    const blob = new Blob([outputText], { type: tab === "JSON" ? "application/json" : "text/plain" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = tab === "JSON" ? "cinematic-storyboard.json" : "cinematic-prompt.txt";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  return (
    <div className="no-scrollbar flex max-h-full w-[300px] flex-col overflow-y-auto border border-line-strong bg-card/95 backdrop-blur">
      <div className="flex items-center justify-between border-b border-line-strong px-3 py-2">
        <span className="instrument-label">Cinematic toolpath</span>
        <button onClick={onClose} className="text-[11px] text-muted hover:text-platinum" aria-label="Close">✕</button>
      </div>
      <p className="border-b border-line bg-review/5 px-3 py-1.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-review">
        Cinematic preview — not NC verification
      </p>

      <div className="space-y-3.5 px-3 py-3">
        <section>
          <p className={label}>Operations</p>
          <ul className="mt-1 space-y-0.5">
            {input.operations.map((o) => (
              <li key={o.id}>
                <label className="flex items-center gap-2 text-[10.5px] text-platinum-dim">
                  <input
                    type="checkbox"
                    checked={selected.has(o.id)}
                    onChange={(e) => {
                      const next = new Set(selected);
                      if (e.target.checked) next.add(o.id);
                      else next.delete(o.id);
                      setSelected(next);
                    }}
                    className="accent-[color:var(--c-blue)]"
                  />
                  <span className="truncate">{o.label}</span>
                </label>
              </li>
            ))}
          </ul>
        </section>

        <section className="flex items-center justify-between">
          <p className={label}>Length</p>
          <span className="flex gap-1">
            {([10, 15, 30] as const).map((d) => (
              <button key={d} className={btn(duration === d)} onClick={() => setDuration(d)}>{d}s</button>
            ))}
          </span>
        </section>

        <section>
          <p className={label}>Style</p>
          <select
            value={style}
            onChange={(e) => setStyle(e.target.value as CinematicSettings["style"])}
            className="mt-1 w-full border border-line-strong bg-surface px-1.5 py-1 text-[10.5px] text-platinum-dim"
          >
            {Object.entries(STYLE_LABEL).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        </section>

        <section>
          <p className={label}>Include</p>
          <div className="mt-1 grid grid-cols-2 gap-x-2 gap-y-0.5">
            {(Object.keys(DEFAULT_INCLUDE) as (keyof typeof DEFAULT_INCLUDE)[]).map((k) => (
              <label key={k} className="flex items-center gap-1.5 text-[9.5px] text-platinum-dim">
                <input
                  type="checkbox"
                  checked={include[k]}
                  onChange={(e) => setInclude({ ...include, [k]: e.target.checked })}
                  className="accent-[color:var(--c-blue)]"
                />
                {k.replace(/([A-Z])/g, " $1").toLowerCase()}
              </label>
            ))}
          </div>
        </section>

        <section className="flex items-center justify-between">
          <span>
            <p className={label}>Customer-safe</p>
            <p className="text-[9px] leading-snug text-muted">Strips part identity, dimensions and tool specifics.</p>
          </span>
          <button className={btn(customerSafe)} onClick={() => setCustomerSafe(!customerSafe)}>
            {customerSafe ? "On" : "Off"}
          </button>
        </section>

        <section>
          <div className="flex gap-1">
            {(["FULL", "SHORT", "SHOTS", "JSON"] as OutputTab[]).map((t) => (
              <button key={t} className={btn(tab === t)} onClick={() => setTab(t)}>
                {t === "SHOTS" ? "Shot list" : t.toLowerCase()}
              </button>
            ))}
          </div>
          {result ? (
            <pre className="mt-1.5 max-h-56 overflow-auto border border-line bg-surface px-2 py-1.5 text-[9.5px] leading-relaxed whitespace-pre-wrap text-platinum-dim">
              {outputText}
            </pre>
          ) : (
            <p className="mt-1.5 text-[10.5px] text-muted">Select at least one operation.</p>
          )}
          <div className="mt-1.5 flex gap-1.5">
            <button className={btn(false)} onClick={copy} disabled={!result}>{copied ? "Copied" : "Copy"}</button>
            <button className={btn(false)} onClick={download} disabled={!result}>Download</button>
          </div>
        </section>

        <section className="border border-line px-2 py-1.5">
          <p className="text-[9.5px] leading-snug text-muted">
            Sending this prompt to an external video generator shares part and process information with that service.
            Use Customer-Safe mode if that matters — and it usually does.
          </p>
          <button className={`${btn(false)} mt-1.5 opacity-60`} disabled>
            Send to video generator — Development
          </button>
        </section>
      </div>
    </div>
  );
}
