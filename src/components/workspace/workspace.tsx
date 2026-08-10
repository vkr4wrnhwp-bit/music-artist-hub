"use client";

import dynamic from "next/dynamic";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { Feature, Stock } from "@/lib/domain/features";
import type { Move } from "@/lib/engines/cam/types";
import type { ViewMode, FixtureInfo } from "@/components/viewport/scene";
import { Copilot } from "./copilot";
import { InteractionProvider, useInteraction, type Context } from "./interaction";
import { ContextRail, sceneFlagsFor } from "./context-rail";
import { FeatureLens } from "./feature-lens";
import { FeaturePanel } from "./feature-panel";
import { OperationRunway } from "./operation-runway";
import { DimensionCard } from "./dimension-card";
import type { DatumInfo, FeatureDetail, NextActionInfo, RunwayData, RunwayOperation } from "./panel-data";

/**
 * THE PART WORKSPACE — THREE ZONES
 *
 *   CENTRE   the work window. Warm white, and the part is the only thing in
 *            it. Every control that used to sit in a horizontal bar above or
 *            below the viewport is now a compact stack on the left edge or a
 *            floating card, so the component gets the space.
 *   RIGHT    the feature panel. A metrology instrument: what is selected,
 *            what is known about its size, and the evidence behind it.
 *   BOTTOM   the operation runway. The plan, in sequence.
 *
 * The two dividers — centre/right and centre/bottom — are the same 1px
 * `--canvas-border-strong` rule, because they are the same kind of edge.
 *
 * The nine data panels the page builds, the context rail and the copilot all
 * still exist; they live behind the right panel's Data and Copilot tabs rather
 * than in a third column, which is what freed the width for the part.
 */

const Viewport = dynamic(() => import("@/components/viewport/scene").then((m) => m.Viewport), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center bg-work">
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
  fixture: FixtureInfo | null;
  copilotContext: Record<string, unknown>;
  panels: Record<string, React.ReactNode>;
  /** Per-feature capability, measurements and inspection line, precomputed server-side. */
  featureDetails: Record<string, FeatureDetail>;
  /** Datum rows for this revision. Empty is a legitimate state and is treated as one. */
  datums: DatumInfo[];
  runway: RunwayData;
  /** The whole ordered queue from `nextActions()`, head first. */
  nextActions: NextActionInfo[];
  hasInspectionPlan: boolean;
  measurementSessionId: string | null;
}

/**
 * Panels grouped by the question they answer.
 *
 * The old workspace showed ten equal-weight tabs, which taught the operator
 * that they were ten separate things to fill in. They are not — they are
 * answers to five questions about one part, and grouping them that way means
 * choosing a context already narrows what is on screen to what bears on the
 * decision being made.
 */
const PANELS_BY_CONTEXT: Record<Context, readonly string[]> = {
  PART: ["part", "stock"],
  HOLD: ["setups", "workholding"],
  CUT: ["tools", "operations"],
  VERIFY: ["inspection", "history"],
  COST: ["cost"],
};

const PANEL_LABEL: Record<string, string> = {
  part: "Part",
  stock: "Stock",
  setups: "Setups",
  workholding: "Workholding",
  tools: "Tools",
  operations: "Operations",
  inspection: "Inspection",
  cost: "Cost",
  history: "History",
};

/**
 * View presets, in WORLD space.
 *
 * The scene authors geometry Z-up and rotates the whole group once, which maps
 * part (x, y, z) onto world (x, z, -y). The part's top face is therefore world
 * +Y, not world +Z — these were previously written as though it were world +Z,
 * which put "Top" on the front of the part and "Front" underneath it.
 *
 * The distances match the scene's tightened default framing, so ISO returns
 * the camera to where it started rather than pulling back from it.
 */
const VIEWS: { label: string; title: string; position: [number, number, number] }[] = [
  { label: "Iso", title: "Isometric view", position: [5.4, 4.7, 7.15] },
  { label: "Top", title: "Top view", position: [0, 11, 0.001] },
  { label: "Bottom", title: "Bottom view", position: [0, -11, 0.001] },
  { label: "Front", title: "Front view", position: [0, 0, 11] },
  { label: "Rear", title: "Rear view", position: [0, 0, -11] },
  { label: "Left", title: "Left view", position: [-11, 0, 0] },
  { label: "Right", title: "Right view", position: [11, 0, 0] },
];

const MODES: { mode: ViewMode; label: string; title: string }[] = [
  { mode: "SHADED", label: "Shaded", title: "Shaded" },
  { mode: "WIREFRAME", label: "Wireframe", title: "Wireframe" },
  { mode: "TRANSPARENT", label: "Ghost", title: "Ghost — see through the solid" },
];

type SidePane = "feature" | "data" | "copilot";
type MobilePane = "model" | "panel";

export function Workspace(props: WorkspaceProps) {
  // The plan's own first operation, in sequence order. Real ordering, not a
  // status: it is where the runway starts reading, so it is what the runway
  // shows as its subject before the user has picked anything.
  const first =
    props.runway.setups
      .slice()
      .sort((a, b) => a.sequence - b.sequence)
      .flatMap((s) =>
        props.runway.operations.filter((o) => o.setupId === s.id).sort((a, b) => a.sequence - b.sequence),
      )[0] ?? null;

  return (
    <InteractionProvider initialOperation={first?.id ?? null}>
      <WorkspaceInner {...props} />
    </InteractionProvider>
  );
}

function WorkspaceInner(props: WorkspaceProps) {
  const { state, hover, select, setDisplayMode, setOperation, escape } = useInteraction();
  const [panel, setPanel] = useState<string>("part");
  const [side, setSide] = useState<SidePane>("feature");
  const [mobilePane, setMobilePane] = useState<MobilePane>("model");
  // Distinguishes "the plan starts here" from "you chose this". The card looks
  // the same either way; only the marker changes, because the two are
  // different claims.
  const [operationChosen, setOperationChosen] = useState(false);
  const selectedFeature = state.selectedFeature;
  const mode = state.displayMode as ViewMode;

  // The context decides what is drawn around the part. These stay overridable
  // from the canvas stack, because a machinist who wants the fixture visible
  // while looking at the toolpath should not have to argue with the software.
  const contextFlags = sceneFlagsFor(state.activeContext);
  const [overrides, setOverrides] = useState<Partial<ReturnType<typeof sceneFlagsFor>>>({});
  const flags = { ...contextFlags, ...overrides };
  const { showStock, showFixture, showToolpath, showTool } = flags;
  const setFlag = (k: keyof typeof contextFlags) => (v: boolean) => setOverrides((o) => ({ ...o, [k]: v }));
  const [playhead, setPlayhead] = useState(1);
  const [playing, setPlaying] = useState(false);

  const selected = useMemo(
    () => props.features.find((f) => f.id === selectedFeature) ?? null,
    [props.features, selectedFeature],
  );

  const hovered = useMemo(
    () => props.features.find((f) => f.id === state.hoveredFeature) ?? null,
    [props.features, state.hoveredFeature],
  );

  // Switching context resets the inspector to that context's first panel, and
  // clears any scene overrides so the context means what it says again.
  const panels = PANELS_BY_CONTEXT[state.activeContext];
  useEffect(() => {
    setPanel(panels[0]);
    setOverrides({});
  }, [state.activeContext]); // eslint-disable-line react-hooks/exhaustive-deps

  // HOLD is about the setup, not the component, and the vise is wider and
  // deeper than the part. Entering it without reframing leaves the jaws cut
  // off at the edges of the canvas — the one thing the view exists to show.
  useEffect(() => {
    if (state.activeContext !== "HOLD") return;
    const span = props.stock ? Math.max(props.stock.x, props.stock.y, props.stock.z) : 6;
    setView([span * 1.5, span * 1.15, span * 1.85]);
  }, [state.activeContext]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") escape();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [escape]);

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

  /** Selecting geometry always brings the feature panel forward. */
  const selectFeature = (id: string | null) => {
    select(id);
    if (id) {
      setSide("feature");
      setMobilePane("model");
    }
  };

  /**
   * Choosing an operation is the one place `activeOperation` is written, and it
   * is what makes the runway more than a picture: the operation you pick also
   * selects the feature it cuts, so the model and the feature panel follow it.
   */
  const selectOperation = (op: RunwayOperation | null) => {
    setOperationChosen(true);
    setOperation(op ? op.id : null);
    if (op?.featureId) {
      select(op.featureId);
      setSide("feature");
    }
  };

  const showTransport = showToolpath && props.moves.length > 1;

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-work">
      {/* ---------------- Mobile pane switcher ---------------- */}
      <div className="flex shrink-0 gap-px border-b border-line bg-line lg:hidden">
        {(
          [
            ["model", "Model"],
            ["panel", "Panel"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            onClick={() => setMobilePane(id)}
            className={`flex-1 bg-work py-2 text-[10px] font-semibold uppercase tracking-[0.16em] transition-colors ${
              mobilePane === id ? "text-precision-dim" : "text-muted"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        {/* ================= CENTRE — the work window ================= */}
        <section
          className={`${mobilePane === "model" ? "flex" : "hidden"} relative min-h-0 min-w-0 flex-1 flex-col bg-work lg:flex`}
        >
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
              hoveredFeatureId={state.hoveredFeature}
              onSelectFeature={selectFeature}
              onHoverFeature={hover}
              fixture={props.fixture}
              showHoldCallouts={state.activeContext === "HOLD"}
            />

            {/* Compact controls, left edge. Nothing here is wider than the
                buttons it holds — the viewport keeps the rest. */}
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
              <div className="no-scrollbar pointer-events-auto max-h-full overflow-y-auto">
                <ControlGroup heading="View">
                  {VIEWS.map((v) => (
                    <ControlButton key={v.label} title={v.title} onClick={() => setView(v.position)}>
                      {v.label}
                    </ControlButton>
                  ))}
                </ControlGroup>
                <ControlGroup heading="Display">
                  {MODES.map((m) => (
                    <ControlButton
                      key={m.mode}
                      title={m.title}
                      on={mode === m.mode}
                      onClick={() => setDisplayMode(m.mode)}
                    >
                      {m.label}
                    </ControlButton>
                  ))}
                </ControlGroup>
                <ControlGroup heading="Show">
                  {/* `showStock` gates the part solid itself, so this reads
                      PART. It used to say Stock, which hid the component. */}
                  <ControlButton title="Show the part solid" on={showStock} onClick={() => setFlag("showStock")(!showStock)}>
                    Part
                  </ControlButton>
                  <ControlButton title="Show the vise and jaws" on={showFixture} onClick={() => setFlag("showFixture")(!showFixture)}>
                    Fixture
                  </ControlButton>
                  <ControlButton
                    title="Show the toolpath"
                    on={showToolpath}
                    onClick={() => setFlag("showToolpath")(!showToolpath)}
                  >
                    Toolpath
                  </ControlButton>
                  <ControlButton title="Show the cutter" on={showTool} onClick={() => setFlag("showTool")(!showTool)}>
                    Tool
                  </ControlButton>
                </ControlGroup>
              </div>
            </div>

            {/* Feature lens — appears on hover, no click required. The
                measurability row in the lens was dead UI because nothing ever
                passed a verdict; it now carries the real capability result. */}
            {hovered && !selected && (
              <FeatureLens
                feature={hovered}
                pointer={state.pointer}
                capability={props.featureDetails[hovered.id]?.capability ?? null}
              />
            )}

            {/* The dimension card. The model value only — nothing called live,
                no confidence figure, and no second copy of the evidence the
                feature panel already carries three inches to the right. */}
            {selected && <DimensionCard feature={selected} onDismiss={() => selectFeature(null)} />}

            {!props.stock && (
              <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                <div className="border border-dashed border-line-strong px-6 py-4 text-center">
                  <p className="font-mono text-[12px] uppercase tracking-[0.16em] text-platinum-dim">
                    Stock not defined
                  </p>
                  <p className="mt-1.5 max-w-xs text-[12px] text-muted">
                    Define stock dimensions before CANVAS can show the part in its material.
                  </p>
                </div>
              </div>
            )}

            {/* Toolpath transport. Present only while a path is on screen —
                a scrub bar with nothing to scrub is chrome for its own sake. */}
            {showTransport && (
              <div className="absolute bottom-3 left-16 z-20 flex items-center gap-2 border border-line-strong bg-card/95 px-2 py-1.5 backdrop-blur">
                <button
                  onClick={() => setPlaying((p) => !p)}
                  className="border border-line-strong px-2 py-0.5 font-mono text-[9.5px] uppercase tracking-[0.14em] text-platinum-dim transition-colors hover:text-platinum"
                >
                  {playing ? "Pause" : "Play"}
                </button>
                <button
                  onClick={() => {
                    setPlaying(false);
                    setPlayhead((p) => Math.min(1, p + 1 / Math.max(props.moves.length, 1)));
                  }}
                  className="border border-transparent px-1.5 py-0.5 font-mono text-[9.5px] uppercase tracking-[0.14em] text-muted transition-colors hover:text-platinum"
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
                  className="h-1 w-[140px] accent-[color:var(--c-blue)]"
                />
                <span className="tech-value shrink-0 text-[10px] text-muted tabular-nums">
                  {Math.floor(props.moves.length * playhead)} / {props.moves.length}
                </span>
              </div>
            )}
          </div>
        </section>

        {/* ================= RIGHT — the feature panel ================= */}
        <aside
          className={`${mobilePane === "panel" ? "flex" : "hidden"} min-h-0 flex-1 flex-col bg-panel lg:flex lg:w-[356px] lg:flex-none`}
          style={{ borderLeft: "1px solid var(--canvas-border-strong)" }}
        >
          <div className="flex shrink-0 gap-px border-b border-line bg-line">
            {(
              [
                ["feature", "Feature"],
                ["data", "Data"],
                ["copilot", "Copilot"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                onClick={() => setSide(id)}
                aria-pressed={side === id}
                className={`relative flex-1 bg-panel py-2 text-[10px] font-semibold uppercase tracking-[0.14em] transition-colors ${
                  side === id ? "text-precision-dim" : "text-muted hover:text-platinum"
                }`}
              >
                {side === id && <span aria-hidden className="absolute inset-x-0 top-0 h-[2px] bg-precision" />}
                {label}
              </button>
            ))}
          </div>

          {side === "feature" && (
            <FeaturePanel
              partId={props.partId}
              features={props.features}
              selectedId={selectedFeature}
              onSelect={selectFeature}
              stock={props.stock}
              details={props.featureDetails}
              datums={props.datums}
              hasInspectionPlan={props.hasInspectionPlan}
              measurementSessionId={props.measurementSessionId}
            />
          )}

          {side === "data" && (
            <>
              <ContextRail compact className="shrink-0 border-b border-line" />
              <div className="flex shrink-0 flex-wrap gap-px border-b border-line bg-line">
                {panels.map((p) => (
                  <button
                    key={p}
                    onClick={() => setPanel(p)}
                    className={`flex-1 bg-panel px-2 py-1.5 text-[9px] font-semibold uppercase tracking-[0.1em] transition-colors ${
                      panel === p ? "text-precision-dim" : "text-muted hover:text-platinum"
                    }`}
                  >
                    {PANEL_LABEL[p]}
                  </button>
                ))}
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto p-3">
                {props.panels[panel] ?? <p className="tech-label">No data</p>}
              </div>
            </>
          )}

          {side === "copilot" && (
            <Copilot partId={props.partId} partName={props.partName} context={props.copilotContext} />
          )}
        </aside>
      </div>

      {/* ================= BOTTOM — the operation runway ================= */}
      <OperationRunway
        partId={props.partId}
        data={props.runway}
        nextActions={props.nextActions}
        activeOperation={state.activeOperation}
        operationChosenByUser={operationChosen}
        selectedFeature={selectedFeature}
        onSelectOperation={selectOperation}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Canvas controls                                                     */
/* ------------------------------------------------------------------ */

/**
 * A stack of viewport controls.
 *
 * These used to be three-letter abbreviations — ISO / BOT / FRT / REA / SHD /
 * WIR / GST / PRT / FIX / PTH / TL — which are compact and unreadable. "REA"
 * and "GST" are not words, and a machinist should not have to hover a control
 * to find out what it does. Words cost about thirty pixels of a nine-hundred
 * pixel canvas, which is the cheapest trade in the interface.
 */
function ControlGroup({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <div className="mb-2 flex w-[74px] flex-col border border-line-strong bg-card/92 backdrop-blur last:mb-0">
      <p className="border-b border-line px-2 py-1 text-[8.5px] font-semibold uppercase leading-none tracking-[0.12em] text-muted">
        {heading}
      </p>
      {children}
    </div>
  );
}

function ControlButton({
  children,
  title,
  on,
  onClick,
}: {
  children: React.ReactNode;
  title: string;
  on?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      aria-pressed={on}
      onClick={onClick}
      className={`border-b border-line px-2 py-[5px] text-left text-[11px] font-medium leading-tight transition-colors last:border-b-0 ${
        on ? "bg-precision/10 text-precision" : "text-platinum-dim hover:bg-panel hover:text-platinum"
      }`}
    >
      {children}
    </button>
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
