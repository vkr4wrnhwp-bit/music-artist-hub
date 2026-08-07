"use client";

import dynamic from "next/dynamic";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { Feature, Stock } from "@/lib/domain/features";
import { featureSummary, fmtTol } from "@/lib/domain/features";
import type { Move } from "@/lib/engines/cam/types";
import type { ViewMode } from "@/components/viewport/scene";
import { Copilot } from "./copilot";
import { buttonClass, Dot, StatusChip, type Tone } from "@/components/ui";

const Viewport = dynamic(() => import("@/components/viewport/scene").then((m) => m.Viewport), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center bg-surface">
      <span className="tech-label">Initialising viewport…</span>
    </div>
  ),
});

export interface WorkspaceProps {
  partId: string;
  partName: string;
  stock: Stock | null;
  features: Feature[];
  moves: Move[];
  fixture: { jawWidth: number; jawHeight: number; gripDepth: number | null } | null;
  copilotContext: Record<string, unknown>;
  panels: Record<string, React.ReactNode>;
  readinessTone: Tone;
  readinessLabel: string;
}

const PANEL_ORDER = [
  "part",
  "features",
  "stock",
  "setups",
  "workholding",
  "tools",
  "operations",
  "inspection",
  "cost",
  "history",
] as const;

const PANEL_LABEL: Record<string, string> = {
  part: "Part",
  features: "Features",
  stock: "Stock",
  setups: "Setups",
  workholding: "Workholding",
  tools: "Tools",
  operations: "Operations",
  inspection: "Inspection",
  cost: "Cost",
  history: "History",
};

const VIEWS: { label: string; position: [number, number, number] }[] = [
  { label: "Iso", position: [8, -10, 8] },
  { label: "Top", position: [0, 0, 16] },
  { label: "Bottom", position: [0, 0, -16] },
  { label: "Front", position: [0, -16, 0] },
  { label: "Rear", position: [0, 16, 0] },
  { label: "Left", position: [-16, 0, 0] },
  { label: "Right", position: [16, 0, 0] },
];

export function Workspace(props: WorkspaceProps) {
  const [panel, setPanel] = useState<string>("part");
  const [selectedFeature, setSelectedFeature] = useState<string | null>(null);
  const [mode, setMode] = useState<ViewMode>("SHADED");
  const [showStock, setShowStock] = useState(true);
  const [showFixture, setShowFixture] = useState(false);
  const [showToolpath, setShowToolpath] = useState(true);
  const [showTool, setShowTool] = useState(false);
  const [playhead, setPlayhead] = useState(1);
  const [playing, setPlaying] = useState(false);
  // Three side-by-side columns cannot work on a phone, so below `lg` exactly
  // one is shown at a time and this chooses which.
  const [mobilePane, setMobilePane] = useState<"model" | "data" | "copilot">("model");

  const selected = useMemo(
    () => props.features.find((f) => f.id === selectedFeature) ?? null,
    [props.features, selectedFeature],
  );

  // Playback is a scrub over the move list, driven by rAF while playing.
  useAnimationLoop(playing, (dt) => {
    setPlayhead((p) => {
      const next = p + dt * 0.12;
      if (next >= 1) {
        setPlaying(false);
        return 1;
      }
      return next;
    });
  });

  const setView = (position: [number, number, number]) =>
    window.dispatchEvent(new CustomEvent("canvas:setview", { detail: { position } }));

  return (
    <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
      {/* ---------------- Mobile pane switcher ---------------- */}
      <div className="flex shrink-0 gap-px border-b border-line bg-line lg:hidden">
        {([
          ["model", "Model"],
          ["data", "Data"],
          ["copilot", "Copilot"],
        ] as const).map(([id, label]) => (
          <button
            key={id}
            onClick={() => setMobilePane(id)}
            className={`flex-1 bg-surface py-2.5 font-mono text-[10px] uppercase tracking-[0.16em] transition-colors ${
              mobilePane === id ? "text-precision" : "text-muted"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ---------------- Left: navigator ---------------- */}
      <aside
        className={`${mobilePane === "data" ? "flex" : "hidden"} min-h-0 flex-1 flex-col border-line bg-surface lg:flex lg:w-72 lg:flex-none lg:border-r`}
      >
        <div className="flex flex-wrap gap-px border-b border-line bg-line">
          {PANEL_ORDER.map((p) => (
            <button
              key={p}
              onClick={() => setPanel(p)}
              className={`flex-1 bg-surface px-2 py-2.5 font-mono text-[9px] uppercase tracking-[0.1em] transition-colors lg:py-1.5 ${
                panel === p ? "text-precision" : "text-muted hover:text-platinum"
              }`}
            >
              {PANEL_LABEL[p]}
            </button>
          ))}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-3">
          {panel === "features" ? (
            <FeatureTree features={props.features} selected={selectedFeature} onSelect={setSelectedFeature} />
          ) : (
            props.panels[panel] ?? <p className="tech-label">No data</p>
          )}
        </div>
      </aside>

      {/* ---------------- Centre: viewport ---------------- */}
      <section className={`${mobilePane === "model" ? "flex" : "hidden"} min-h-0 min-w-0 flex-1 flex-col lg:flex`}>
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line bg-surface px-3 py-1.5">
          <div className="flex items-center gap-1 overflow-x-auto">
            {VIEWS.map((v) => (
              <button key={v.label} onClick={() => setView(v.position)} className={buttonClass("ghost", "sm")}>
                {v.label}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-1">
            {(["SHADED", "WIREFRAME", "TRANSPARENT"] as ViewMode[]).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`${buttonClass(mode === m ? "primary" : "ghost", "sm")}`}
              >
                {m === "TRANSPARENT" ? "Ghost" : m.toLowerCase()}
              </button>
            ))}
          </div>
        </div>

        <div className="relative min-h-0 flex-1">
          <Viewport
            stock={props.stock}
            features={props.features}
            moves={props.moves}
            playhead={playhead}
            showStock={showStock}
            showFixture={showFixture}
            showToolpath={showToolpath}
            showTool={showTool}
            mode={mode}
            selectedFeatureId={selectedFeature}
            onSelectFeature={setSelectedFeature}
            fixture={props.fixture}
          />

          {/* Selected feature readout, overlaid on the viewport */}
          {selected && (
            <div className="pointer-events-none absolute left-4 top-4 border border-line bg-surface/95 px-3.5 py-2.5 backdrop-blur">
              <div className="flex items-center gap-2">
                <Dot tone={selected.critical ? "review" : "precision"} />
                <span className="font-mono text-[12px] text-white">{selected.label}</span>
              </div>
              <div className="tech-label mt-1">{featureSummary(selected)}</div>
              {selected.tolerance && (
                <div className="tech-label mt-0.5 text-precision">{fmtTol(selected.tolerance)}</div>
              )}
              {selected.functionalRole !== "NONE" && (
                <div className="tech-label mt-0.5">{selected.functionalRole.replace(/_/g, " ")}</div>
              )}
            </div>
          )}

          {!props.stock && (
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
              <div className="border border-dashed border-line-strong px-6 py-4 text-center">
                <p className="font-mono text-[12px] uppercase tracking-[0.16em] text-platinum-dim">Stock not defined</p>
                <p className="mt-1.5 max-w-xs text-[12px] text-muted">
                  Define stock dimensions before CANVAS can show the part in its material.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* ---------------- Toolpath transport ---------------- */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-line bg-surface px-3 py-2">
          <button onClick={() => setPlaying((p) => !p)} disabled={props.moves.length === 0} className={buttonClass("default", "sm")}>
            {playing ? "Pause" : "Play"}
          </button>
          <button
            onClick={() => {
              setPlaying(false);
              setPlayhead((p) => Math.min(1, p + 1 / Math.max(props.moves.length, 1)));
            }}
            disabled={props.moves.length === 0}
            className={buttonClass("ghost", "sm")}
          >
            Step
          </button>
          <input
            type="range"
            aria-label="Toolpath position"
            min={0}
            max={1}
            step={0.001}
            value={playhead}
            onChange={(e) => {
              setPlaying(false);
              setPlayhead(Number(e.target.value));
            }}
            className="h-1 min-w-[120px] flex-1 accent-[color:var(--c-blue)]"
          />
          <span className="tech-value w-28 shrink-0 text-right text-[10px] text-muted">
            {Math.floor(props.moves.length * playhead)} / {props.moves.length} moves
          </span>
          <div className="flex items-center gap-1">
            <Toggle label="Stock" on={showStock} set={setShowStock} />
            <Toggle label="Fixture" on={showFixture} set={setShowFixture} />
            <Toggle label="Path" on={showToolpath} set={setShowToolpath} />
            <Toggle label="Tool" on={showTool} set={setShowTool} />
          </div>
        </div>
      </section>

      {/* ---------------- Right: copilot ---------------- */}
      <aside
        className={`${mobilePane === "copilot" ? "flex" : "hidden"} min-h-0 flex-1 flex-col border-line bg-surface lg:flex lg:w-80 lg:flex-none lg:border-l`}
      >
        <Copilot partId={props.partId} partName={props.partName} context={props.copilotContext} />
      </aside>
    </div>
  );
}

function Toggle({ label, on, set }: { label: string; on: boolean; set: (v: boolean) => void }) {
  return (
    <button
      onClick={() => set(!on)}
      className={`border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.12em] transition-colors ${
        on ? "border-precision/50 text-precision" : "border-line-strong text-muted hover:text-platinum"
      }`}
    >
      {label}
    </button>
  );
}

function FeatureTree({
  features,
  selected,
  onSelect,
}: {
  features: Feature[];
  selected: string | null;
  onSelect: (id: string | null) => void;
}) {
  if (features.length === 0) {
    return (
      <div className="border border-dashed border-line-strong px-3 py-4">
        <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-platinum-dim">No features</p>
        <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted">
          A part with no features has no manufacturing plan. Add features, or accept the proposals from the intake.
        </p>
      </div>
    );
  }

  return (
    <ul className="space-y-px">
      {features.map((f) => (
        <li key={f.id}>
          <button
            onClick={() => onSelect(f.id === selected ? null : f.id)}
            className={`w-full border-l-2 px-2 py-1.5 text-left transition-colors ${
              selected === f.id
                ? "border-l-precision bg-raised text-white"
                : "border-l-transparent text-platinum-dim hover:bg-raised hover:text-white"
            }`}
          >
            <span className="flex items-center justify-between gap-2">
              <span className="truncate text-[12px]">{f.label}</span>
              {f.critical && <StatusChip tone="review">Crit</StatusChip>}
            </span>
            <span className="tech-label block truncate">{featureSummary(f)}</span>
            {f.functionalRole !== "NONE" && (
              <span className="tech-label block truncate text-precision/70">
                {f.functionalRole.replace(/_/g, " ").toLowerCase()}
              </span>
            )}
          </button>
        </li>
      ))}
    </ul>
  );
}

/** Minimal rAF loop. Avoids pulling a timing library in for one slider. */
function useAnimationLoop(active: boolean, tick: (deltaSeconds: number) => void) {
  const cb = useLatest(tick);
  useIsomorphicEffect(() => {
    if (!active) return;
    let raf = 0;
    let last = performance.now();
    const loop = (now: number) => {
      const dt = (now - last) / 1000;
      last = now;
      cb.current(dt);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [active]);
}

const useIsomorphicEffect = typeof window !== "undefined" ? useLayoutEffect : useEffect;

function useLatest<T>(value: T) {
  const ref = useRef(value);
  ref.current = value;
  return ref;
}
