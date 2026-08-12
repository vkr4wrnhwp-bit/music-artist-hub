"use client";

import dynamic from "next/dynamic";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { Feature, Stock } from "@/lib/domain/features";
import type { Move } from "@/lib/engines/cam/types";
import type { ViewMode, FixtureInfo } from "@/components/viewport/scene";
import { holdMeasurements } from "@/components/viewport/hold-measurements";
import { DevLabel } from "@/components/ui";
import { Copilot } from "./copilot";
import { InteractionProvider, useInteraction, type Context } from "./interaction";
import { ContextRail, sceneFlagsFor } from "./context-rail";
import { FeatureLens } from "./feature-lens";
import { FeaturePanel } from "./feature-panel";
import { OperationRunway } from "./operation-runway";
import { DimensionCard } from "./dimension-card";
import { SimTransport } from "./sim-transport";
import { ViewEnvironmentDrawer } from "./view-environment-drawer";
import { CinematicDrawer } from "./cinematic-drawer";
import type { CinematicInput } from "@/lib/cinematic";
import {
  DEFAULT_ENVIRONMENT,
  fetchServerPreferences,
  loadEnvironment,
  pushServerPreferences,
  saveEnvironment,
  viewModeDefaults,
  type ViewEnvironment,
  type ViewMode as EnvViewMode,
} from "@/lib/view-environment";
import { StockRemovalSimulator, type SimOperation } from "@/lib/sim/stock-removal";
import type { SimHandle } from "@/components/viewport/sim-view";
import type { DatumInfo, FeatureDetail, NextActionInfo, RunwayData, RunwayOperation } from "./panel-data";
import { useResizableWidth, RESIZE_HANDLE_CLASS } from "@/lib/use-resizable";

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
  /** Structured operations for the CUT stock-removal simulation. */
  simOps: SimOperation[];
  /** Server action recording a watched-to-completion simulation run. */
  recordSimulation?: (payload: { removedVolume: number; totalTime: number; collisions: number }) => Promise<void>;
  /** True when a Simulation row already exists for this revision. */
  simulationRecorded: boolean;
  /** Recorded material, for the view-environment recommendation. */
  material: string | null;
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
  const { state, hover, select, setDisplayMode, setOperation, setContext, escape } = useInteraction();
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

  // View environment — how the viewport is drawn. The localStorage cache
  // renders immediately after mount (SSR renders the default); the per-user
  // server copy is fetched and wins when present, so preferences follow the
  // user across devices. Changes save to both.
  const [viewEnv, setViewEnv] = useState<ViewEnvironment>(DEFAULT_ENVIRONMENT);
  // One right-side drawer at a time — env settings or the cinematic panel.
  const [drawer, setDrawer] = useState<"env" | "film" | null>(null);
  const envOpen = drawer === "env";
  const setEnvOpen = (v: boolean) => setDrawer(v ? "env" : null);
  useEffect(() => {
    setViewEnv(loadEnvironment());
    let cancelled = false;
    void fetchServerPreferences().then(({ env }) => {
      if (!cancelled && env) {
        setViewEnv(env);
        saveEnvironment(env);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);
  const updateEnv = (e: ViewEnvironment) => {
    setViewEnv(e);
    saveEnvironment(e);
    pushServerPreferences({ env: e });
  };
  const applyViewMode = (m: EnvViewMode) => {
    const d = viewModeDefaults(m);
    setOverrides((o) => ({ ...o, ...d.flags }));
    updateEnv({ ...viewEnv, ...d.env, viewMode: m });
  };

  // Cinematic prompt input — real state only. Values the workspace does not
  // hold are null and the generator writes them as unspecified or omits them.
  const cinematicInput = useMemo<CinematicInput>(
    () => ({
      partName: props.partName,
      partNumber: null,
      material: props.material,
      stock: props.stock ? { x: props.stock.x, y: props.stock.y, z: props.stock.z } : null,
      setupName: props.runway.setups[0]?.name ?? null,
      workholding: props.runway.workholding.device,
      hasSoftJaws: props.fixture?.jawSurface === "SOFT_MACHINED",
      readiness: null,
      operations: props.runway.operations
        .filter((o) => !o.isPlaceholder)
        .map((o) => ({
          id: o.id,
          label: o.label,
          type: o.type,
          toolDescription: o.toolDescription,
          cycleMinutes: o.cycleMinutes,
        })),
    }),
    [props.partName, props.material, props.stock, props.runway, props.fixture],
  );

  // Stock-removal simulation. The simulator is built once from the real
  // toolpaths (the constructor runs the full deterministic pass, so every
  // collision is known before playback starts); the handle is the mutable
  // playback state shared between the transport and the render rig.
  const simHandle = useMemo<SimHandle | null>(() => {
    if (!props.stock || props.simOps.length === 0) return null;
    const sim = new StockRemovalSimulator(
      { x: props.stock.x, y: props.stock.y, z: props.stock.z },
      props.simOps,
    );
    return { sim, time: 0, playing: false, speed: 1, followTool: false, scrubbed: 0 };
  }, [props.stock, props.simOps]);
  const simActive = state.activeContext === "CUT" && simHandle !== null;
  const [simRecorded, setSimRecorded] = useState(props.simulationRecorded);

  // A runway click during simulation jumps the playhead to that operation.
  useEffect(() => {
    if (!simActive || !simHandle || !state.activeOperation) return;
    const idx = props.simOps.findIndex((o) => o.operationId === state.activeOperation);
    if (idx >= 0) {
      simHandle.playing = false;
      simHandle.time = simHandle.sim.opStartTimes[idx];
      simHandle.scrubbed++;
    }
  }, [simActive, simHandle, state.activeOperation, props.simOps]);

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
      // Selecting a feature is the request for its detail — the docked
      // panel opens to answer it (transient; the stored preference is
      // untouched, and Focus keeps everything closed).
      setPanelCollapsed(false);
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

  // Feature panel dock state — layout preference, persisted per browser.
  const [panelCollapsed, setPanelCollapsed] = useState(false);
  // Resizable feature panel — drag the left edge, double-click resets.
  const panelResize = useResizableWidth({ storageKey: "canvas.panelWidth", defaultWidth: 356, min: 280, max: 560, edge: "start" });
  useEffect(() => {
    try {
      const stored = window.localStorage.getItem("canvas.panelCollapsed");
      // The panel starts docked away at every width; selecting a feature is
      // what earns it the width. An explicit choice always wins.
      setPanelCollapsed(stored === null ? true : stored === "1");
    } catch {
      /* fine */
    }
  }, []);
  const togglePanel = () => {
    setPanelCollapsed((c) => {
      try {
        window.localStorage.setItem("canvas.panelCollapsed", c ? "0" : "1");
      } catch {
        /* fine */
      }
      return !c;
    });
  };

  const blocking = props.nextActions.filter((a) => a.severity === "BLOCKING");

  // The view-control stack floats behind one VIEW button by default — the
  // viewport owns the left edge unless the controls are asked for.
  const [controlsOpen, setControlsOpen] = useState(false);
  useEffect(() => {
    try {
      setControlsOpen(window.localStorage.getItem("canvas.viewControls") === "open");
    } catch {
      /* fine */
    }
  }, []);
  const toggleControls = () => {
    setControlsOpen((c) => {
      try {
        window.localStorage.setItem("canvas.viewControls", c ? "closed" : "open");
      } catch {
        /* fine */
      }
      return !c;
    });
  };

  // FOCUS WORKSPACE — one keystroke hands the screen to the part: the
  // context drawer, feature panel, control stack, drawers and the plan body
  // all collapse. It simplifies the interface; it never conceals risk — a
  // compact critical-status chip stays over the viewport while focused.
  const [focus, setFocus] = useState(false);
  const toggleFocus = () => {
    setFocus((f) => {
      const on = !f;
      setPanelCollapsed(on);
      if (on) {
        setDrawer(null);
        setControlsOpen(false);
      }
      window.dispatchEvent(new CustomEvent("canvas:focus", { detail: on }));
      window.dispatchEvent(new CustomEvent("canvas:timeline-minimize", { detail: on }));
      return on;
    });
  };

  // Workspace shortcuts. Never while typing — a machinist entering "5" into
  // a dimension field is not asking for the cost view.
  useEffect(() => {
    const typing = (t: EventTarget | null) => {
      const el = t as HTMLElement | null;
      return Boolean(
        el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable),
      );
    };
    const onKey = (e: KeyboardEvent) => {
      if (typing(e.target) || e.metaKey || e.ctrlKey || e.altKey) return;
      const contexts: Record<string, Context> = { "1": "PART", "2": "HOLD", "3": "CUT", "4": "VERIFY", "5": "COST" };
      if (e.key === "f" || e.key === "F") toggleFocus();
      else if (e.key === "v" || e.key === "V") setDrawer((d) => (d === "env" ? null : "env"));
      else if (contexts[e.key]) setContext(contexts[e.key]);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-work">
      {/* ================= ACTION BANNER =================
          The worst blocking work, full width, before anything else — the
          refactor-spec banner. "Fix Now" routes to the evidence screen that
          could change the first gate; nothing here clears anything in place,
          because a banner control that cleared a gate would be a click
          standing in for evidence. Absent entirely when nothing blocks. */}
      {blocking.length > 0 && !focus && (
        <details className="group/banner shrink-0 border-b border-risk/40 bg-risk/10">
          <summary className="flex cursor-pointer list-none flex-wrap items-center gap-x-3 gap-y-1 px-3 py-1.5">
            <span className="shrink-0 text-[10px] font-semibold uppercase tracking-[0.14em] text-risk">
              {blocking.length} blocking — action required
            </span>
            <span className="min-w-0 flex-1 truncate text-[11.5px] text-platinum-dim">{blocking[0].action}</span>
            {blocking[0]?.href && (
              <a
                href={blocking[0].href}
                onClick={(e) => e.stopPropagation()}
                className="shrink-0 border border-risk/50 px-2.5 py-[3px] text-[9.5px] font-semibold uppercase tracking-[0.12em] text-risk transition-colors hover:bg-risk/15"
              >
                Fix →
              </a>
            )}
            <span className="shrink-0 text-[9px] font-semibold uppercase tracking-[0.12em] text-muted">
              <span className="group-open/banner:hidden">All {blocking.length} ▸</span>
              <span className="hidden group-open/banner:inline">Hide ▾</span>
            </span>
          </summary>
          {/* Each blocker is a pill routing to its evidence screen. Nothing
              here clears a gate in place. */}
          <div className="flex flex-wrap gap-1.5 px-3 pb-2">
            {blocking.map((a, i) => (
              <a
                key={i}
                href={a.href ?? "#"}
                title={a.reason}
                className="border border-risk/40 px-2 py-[3px] text-[10px] font-semibold uppercase tracking-[0.1em] text-platinum-dim transition-colors hover:bg-risk/15 hover:text-platinum"
              >
                {a.action}
              </a>
            ))}
          </div>
        </details>
      )}
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
          {/* The five views onto the object, at the top of the object's own
              window. This lived behind the right panel's DATA tab, which meant
              HOLD, CUT and VERIFY existed but could not be found — you had to
              already know they were there to go looking. A view of the part
              belongs on the part, not two clicks into a sibling panel. */}
          <ContextRail className="shrink-0 border-b border-line" />

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
              simHandle={simActive ? simHandle : null}
              env={viewEnv}
              datums={props.datums}
              verify={Object.fromEntries(
                Object.entries(props.featureDetails).map(([id, d]) => [id, d.verify.state]),
              )}
            />

            {/* MEASUREMENT STRIP — HOLD's computed values, docked to the
                viewport edge and numbered to the balloons in the scene. The
                values used to float over the model; now they hold still where
                an operator can read them, and a row whose value is missing
                says "not recorded" instead of disappearing. */}
            {state.activeContext === "HOLD" && showFixture && props.fixture && !simActive && (
              <div className="absolute bottom-3 right-3 z-20 w-[300px] border border-line-strong bg-surface/95 backdrop-blur-sm">
                <p className="instrument-label border-b border-line px-2.5 py-1.5">Workholding — measured on the setup</p>
                <ul>
                  {holdMeasurements(props.fixture, props.stock!).map((m) => (
                    <li key={m.n} className="flex items-baseline gap-2 border-b border-line/60 px-2.5 py-1 last:border-0">
                      <span
                        className={`flex h-[15px] w-[15px] shrink-0 translate-y-[2px] items-center justify-center rounded-full border font-mono text-[8.5px] font-bold leading-none ${
                          m.tone === "pass"
                            ? "border-pass text-pass"
                            : m.tone === "review"
                              ? "border-review text-review"
                              : m.tone === "risk"
                                ? "border-risk text-risk"
                                : "border-precision/70 text-precision-dim"
                        }`}
                      >
                        {m.n}
                      </span>
                      <span className="min-w-0 flex-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted">
                        {m.label}
                        {m.dev && <DevLabel>Dev</DevLabel>}
                      </span>
                      <span
                        className={`shrink-0 text-right font-mono text-[11px] tabular-nums ${
                          m.tone === "pass"
                            ? "text-pass"
                            : m.tone === "review"
                              ? "text-review"
                              : m.tone === "risk"
                                ? "text-risk"
                                : "text-platinum"
                        }`}
                      >
                        {m.value}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* VERIFY legend — only while the INSPECTION view mode colours the
                rings. The states come from measurement records; the legend
                only names the colours. */}
            {viewEnv.viewMode === "INSPECTION" && !simActive && state.activeContext !== "HOLD" && (
              <div className="pointer-events-none absolute bottom-3 left-3 z-20 flex items-center gap-3 border border-line bg-surface/95 px-3 py-1.5">
                <span className="text-[9px] font-semibold uppercase tracking-[0.14em] text-muted">Verify</span>
                {[
                  ["#17754e", "In tolerance"],
                  ["#c22a1e", "Out of tolerance"],
                  ["#7d838b", "Not measured / cannot determine"],
                ].map(([c, l]) => (
                  <span key={l} className="flex items-center gap-1.5 text-[10px] text-platinum-dim">
                    <span className="inline-block h-2 w-2 rounded-full" style={{ background: c }} />
                    {l}
                  </span>
                ))}
              </div>
            )}

            {/* Right-edge drawers, one at a time, over the viewport. */}
            {drawer === "env" && (
              <div className="absolute inset-y-3 right-3 z-30 flex">
                <ViewEnvironmentDrawer
                  env={viewEnv}
                  onChange={updateEnv}
                  material={props.material}
                  onApplyViewMode={applyViewMode}
                  onClose={() => setDrawer(null)}
                />
              </div>
            )}
            {drawer === "film" && (
              <div className="absolute inset-y-3 right-3 z-30 flex">
                <CinematicDrawer
                  input={cinematicInput}
                  activeOperationId={state.activeOperation}
                  onClose={() => setDrawer(null)}
                />
              </div>
            )}

            {/* FOCUS-mode critical status: the interface simplifies, the risk
                stays stated. Click-through to the evidence. */}
            {focus && (
              <div className="absolute right-3 top-3 z-30 flex items-center gap-3 border border-line-strong bg-surface/95 px-3 py-1.5 backdrop-blur-sm">
                {blocking.length > 0 ? (
                  <a
                    href={blocking[0]?.href ?? "#"}
                    className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-risk hover:underline"
                  >
                    Not ready · {blocking.length} blocking
                  </a>
                ) : (
                  <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-pass">No blocking gates</span>
                )}
                {props.nextActions[0] && (
                  <span className="max-w-[280px] truncate text-[10.5px] text-platinum-dim">
                    Next: {props.nextActions[0].action}
                  </span>
                )}
                <button onClick={toggleFocus} className="text-[10px] font-semibold uppercase tracking-[0.12em] text-precision-dim hover:text-precision">
                  Exit focus
                </button>
              </div>
            )}

            {/* Floating VIEW toggle + FOCUS — the control stack costs viewport
                width only while it is asked for. */}
            <div className="pointer-events-none absolute left-3 top-3 z-20 flex gap-1.5">
              <button
                type="button"
                onClick={toggleControls}
                aria-expanded={controlsOpen}
                title="View, display, show and scene controls"
                className={`pointer-events-auto border px-2.5 py-1.5 text-[9.5px] font-semibold uppercase tracking-[0.12em] transition-colors ${
                  controlsOpen
                    ? "border-precision/60 bg-card/92 text-precision-dim"
                    : "border-line-strong bg-card/92 text-muted hover:text-platinum"
                }`}
              >
                View {controlsOpen ? "▾" : "▸"}
              </button>
              <button
                type="button"
                onClick={toggleFocus}
                aria-pressed={focus}
                title="Focus workspace — collapse everything but the part (F)"
                className={`pointer-events-auto border px-2.5 py-1.5 text-[9.5px] font-semibold uppercase tracking-[0.12em] transition-colors ${
                  focus
                    ? "border-precision/60 bg-card/92 text-precision-dim"
                    : "border-line-strong bg-card/92 text-muted hover:text-platinum"
                }`}
              >
                Focus
              </button>
            </div>

            {/* Compact controls, left edge, behind the VIEW toggle. */}
            <div className={`pointer-events-none absolute inset-y-0 left-0 ${controlsOpen ? "flex" : "hidden"} items-center pl-3 pt-10`}>
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
                <ControlGroup heading="Scene">
                  <ControlButton
                    title="Background, grid, shadows, line weight and text size — visibility, not accuracy"
                    on={envOpen}
                    onClick={() => setDrawer(envOpen ? null : "env")}
                  >
                    View env
                  </ControlButton>
                  <ControlButton
                    title="Generate a cinematic video prompt from selected operations — a film, not a verification"
                    on={drawer === "film"}
                    onClick={() => setDrawer(drawer === "film" ? null : "film")}
                  >
                    Cinematic
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

            {/* Simulation transport — the CUT context's whole reason to
                exist. Falls back to the static-path scrubber elsewhere. */}
            {simActive && simHandle && (
              <SimTransport
                handle={simHandle}
                recorded={simRecorded}
                onRecordRun={
                  props.recordSimulation
                    ? async (payload) => {
                        await props.recordSimulation!(payload);
                        setSimRecorded(true);
                      }
                    : undefined
                }
              />
            )}

            {/* Toolpath transport. Present only while a path is on screen —
                a scrub bar with nothing to scrub is chrome for its own sake. */}
            {!simActive && showTransport && (
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

        {/* ================= RIGHT — the feature panel =================
            Dockable: collapsing it hands the full width to the viewport
            (the spec's ≥75% target). The collapsed rail keeps a visible way
            back — a panel that vanishes without a handle is a panel lost. */}
        {panelCollapsed && (
          <button
            type="button"
            onClick={togglePanel}
            aria-label="Expand the feature panel"
            className="hidden w-9 shrink-0 flex-col items-center gap-2 border-l border-line-strong bg-panel pt-3 text-muted transition-colors hover:text-platinum lg:flex"
          >
            <span aria-hidden>◂</span>
            <span className="text-[9px] font-semibold uppercase tracking-[0.14em] [writing-mode:vertical-rl]">
              Feature panel
            </span>
          </button>
        )}
        <aside
          className={`${mobilePane === "panel" ? "flex" : "hidden"} relative min-h-0 flex-1 flex-col bg-panel ${
            panelCollapsed ? "lg:hidden" : "lg:flex"
          } lg:w-[var(--panel-w)] lg:flex-none`}
          style={{ borderLeft: "1px solid var(--canvas-border-strong)", ["--panel-w" as string]: `${panelResize.width}px` }}
        >
          {/* Resize handle on the panel's canvas edge. Double-click resets. */}
          <div
            role="separator"
            aria-orientation="vertical"
            aria-label="Resize the feature panel"
            title="Drag to resize · double-click to reset"
            onPointerDown={panelResize.onPointerDown}
            onDoubleClick={panelResize.reset}
            className={`${RESIZE_HANDLE_CLASS} left-[-3px] ${panelResize.dragging ? "bg-precision/60" : ""}`}
          />
          <div className="flex shrink-0 items-stretch gap-px border-b border-line bg-line">
            <button
              type="button"
              onClick={togglePanel}
              aria-label="Collapse the feature panel"
              className="hidden w-7 shrink-0 items-center justify-center bg-panel text-muted transition-colors hover:text-platinum lg:flex"
            >
              <span aria-hidden>▸</span>
            </button>
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
