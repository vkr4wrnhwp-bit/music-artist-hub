"use client";

import { useEffect, useMemo, useState } from "react";
import {
  VIEW_PRESETS,
  parseHexColor,
  semanticConflicts,
  shellLegibilityProblems,
  recommendPresetFor,
  loadSavedPresets,
  saveNamedPreset,
  deleteNamedPreset,
  fetchServerPreferences,
  pushServerPreferences,
  type ViewEnvironment,
  type LineMode,
  type LineWeight,
  type AnnotationSize,
  type ViewMode,
} from "@/lib/view-environment";

/**
 * VIEW ENVIRONMENT — the viewport's inspection lamp.
 *
 * Everything in this drawer changes how the scene is drawn, never what it
 * shows. The copy holds to that line: a preset "improves visibility" or
 * "improves contrast" — it never certifies, verifies or improves a
 * measurement. The brand shell and the semantic status colours are not
 * customisable from here, on purpose: a shop that can repaint its own
 * blocking-red into invisibility has been handed a footgun, not a feature.
 *
 * Persistence is the per-user server row, with localStorage as the fast
 * cache, and the footer says so.
 */

const label = "text-[9px] font-semibold uppercase tracking-[0.14em] text-muted";
const btn = (on: boolean) =>
  `border px-1.5 py-1 text-[9px] font-semibold uppercase tracking-[0.1em] transition-colors ${
    on ? "border-precision/60 text-precision-dim" : "border-line-strong text-muted hover:text-platinum"
  }`;

export function ViewEnvironmentDrawer({
  env,
  onChange,
  material,
  onApplyViewMode,
  onClose,
  quality = "AUTO",
  onQuality,
}: {
  env: ViewEnvironment;
  onChange: (env: ViewEnvironment) => void;
  material: string | null;
  /** Applies a view mode's visibility defaults in the workspace. */
  onApplyViewMode: (mode: ViewMode) => void;
  onClose: () => void;
  quality?: "AUTO" | "HIGH" | "PERFORMANCE";
  onQuality?: (q: "AUTO" | "HIGH" | "PERFORMANCE") => void;
}) {
  const [saved, setSaved] = useState(loadSavedPresets);
  const [presetName, setPresetName] = useState("");
  // The server list wins when it exists — presets follow the user, not the
  // browser. An empty server list with local entries means this browser has
  // presets the account does not; push them up rather than losing either.
  useEffect(() => {
    let cancelled = false;
    void fetchServerPreferences().then(({ saved: serverSaved }) => {
      if (cancelled) return;
      if (serverSaved.length > 0) setSaved(serverSaved);
      else {
        const local = loadSavedPresets();
        if (local.length > 0) pushServerPreferences({ saved: local });
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);
  const conflicts = useMemo(() => semanticConflicts(env.background), [env.background]);
  const shellProblems = useMemo(
    () => (env.shellBackground ? shellLegibilityProblems(env.shellBackground) : []),
    [env.shellBackground],
  );
  const recommendation = useMemo(() => recommendPresetFor(material), [material]);

  // Any change that is not itself a preset choice leaves the preset. Only
  // three keys used to count, so altering the selected-feature colour, the
  // shell ground, a line mode or the floor left the chip still lit on
  // "Studio White" — and clicking that lit chip threw the work away without
  // warning, because the environment behind it was no longer that preset.
  const set = (patch: Partial<ViewEnvironment>) =>
    onChange({ ...env, ...patch, preset: "preset" in patch ? (patch.preset ?? env.preset) : "CUSTOM" });

  function screenshot() {
    const canvas = document.querySelector<HTMLCanvasElement>("canvas");
    if (!canvas) return;
    const a = document.createElement("a");
    a.href = canvas.toDataURL("image/png");
    a.download = "canvas-viewport.png";
    a.click();
  }

  return (
    <div className="no-scrollbar max-h-full w-[248px] overflow-y-auto border border-line-strong bg-card/95 backdrop-blur">
      <div className="flex items-center justify-between border-b border-line-strong px-3 py-2">
        <span className="instrument-label">View environment</span>
        <button onClick={onClose} className="text-[11px] text-muted hover:text-platinum" aria-label="Close">
          ✕
        </button>
      </div>

      <div className="space-y-4 px-3 py-3">
        {recommendation && env.preset !== recommendation.preset && (
          <div className="border border-precision/40 bg-precision/5 px-2 py-1.5">
            <p className={label}>Recommended view</p>
            <p className="mt-0.5 text-[10.5px] leading-snug text-platinum-dim">{recommendation.reason}</p>
            <button className={`${btn(false)} mt-1.5`} onClick={() => onChange(VIEW_PRESETS[recommendation.preset].env)}>
              Apply {VIEW_PRESETS[recommendation.preset].label}
            </button>
          </div>
        )}

        {/* ---- Presets ---- */}
        <section>
          <p className={label}>Presets</p>
          <div className="mt-1.5 grid grid-cols-2 gap-1">
            {Object.entries(VIEW_PRESETS).map(([id, p]) => (
              <button
                key={id}
                title={p.note}
                onClick={() => onChange(p.env)}
                className={`flex items-center gap-1.5 border px-1.5 py-1.5 text-left ${
                  env.preset === id ? "border-precision/60" : "border-line-strong hover:border-line"
                }`}
              >
                <span aria-hidden className="h-4 w-4 shrink-0 border border-line-strong" style={{ background: p.env.background }} />
                <span className="text-[9.5px] leading-tight text-platinum-dim">{p.label}</span>
              </button>
            ))}
          </div>
        </section>

        {/* ---- Custom colours ---- */}
        {/*
          * The chrome, separated from the work window on purpose.
          *
          * "Background" below repaints the 3D window the part sits in. It
          * always has, and picking a colour there while the rail and header
          * stayed near-black reads as the control doing nothing. They are
          * two different grounds; the panel now says which is which.
          */}
        <section>
          <p className={label}>Application chrome</p>
          <div className="mt-1 flex items-center justify-between gap-2">
            <span className="text-[10.5px] text-platinum-dim">Shell ground</span>
            <span className="flex items-center gap-1">
              <input
                type="color"
                value={env.shellBackground ?? "#06111c"}
                onChange={(e) => set({ shellBackground: e.target.value })}
                className="h-5 w-7 cursor-pointer border border-line-strong bg-transparent p-0"
                aria-label="Application chrome colour"
              />
              <button
                onClick={() => set({ shellBackground: null })}
                disabled={env.shellBackground === null}
                className="border border-line-strong px-1.5 py-0.5 text-[9.5px] uppercase tracking-[0.1em] text-muted enabled:hover:text-platinum disabled:opacity-40"
              >
                Default
              </button>
            </span>
          </div>
          {shellProblems.map((p) => (
            <p key={p} className="mt-1.5 border border-review/50 bg-review/5 px-2 py-1 text-[10px] leading-snug text-review">
              {p}
            </p>
          ))}
          <p className="mt-1 text-[9.5px] leading-snug text-muted">
            The rail, header and panels — not the 3D window below.
          </p>
        </section>

        <section>
          <p className={label}>Work window colours</p>
          {(
            [
              ["Background", "background"],
              ["Floor", "floorColor"],
              ["Grid", "gridColor"],
              ["Selected feature", "selectedFeatureColor"],
            ] as const
          ).map(([name, key]) => (
            <div key={key} className="mt-1 flex items-center justify-between gap-2">
              <span className="text-[10.5px] text-platinum-dim">{name}</span>
              <span className="flex items-center gap-1">
                <input
                  type="color"
                  value={env[key]}
                  onChange={(e) => set({ [key]: e.target.value } as Partial<ViewEnvironment>)}
                  className="h-5 w-7 cursor-pointer border border-line-strong bg-transparent p-0"
                  aria-label={`${name} colour`}
                />
                <HexField
                  label={`${name} hex`}
                  value={env[key]}
                  onCommit={(hex) => set({ [key]: hex } as Partial<ViewEnvironment>)}
                />
              </span>
            </div>
          ))}
          {conflicts.length > 0 && (
            <p className="mt-1.5 border border-review/50 bg-review/5 px-2 py-1 text-[10px] leading-snug text-review">
              This background drowns the locked {conflicts.join(", ")} status colour{conflicts.length === 1 ? "" : "s"}.
              Status markers may stop reading at a glance — pick a ground with more contrast.
            </p>
          )}
          <p className="mt-1 text-[9.5px] leading-snug text-muted">
            Status colours are locked: blue selected, green pass, orange review, red blocking.
          </p>
        </section>

        {/* ---- Surface ---- */}
        <section>
          <p className={label}>Surface</p>
          {(
            [
              ["Gradient ground", "backgroundGradient"],
              ["Grid", "gridVisible"],
              ["Floor plane", "floorVisible"],
            ] as const
          ).map(([name, key]) => (
            <div key={key} className="mt-1 flex items-center justify-between">
              <span className="text-[10.5px] text-platinum-dim">{name}</span>
              <button className={btn(Boolean(env[key]))} onClick={() => set({ [key]: !env[key] } as Partial<ViewEnvironment>)}>
                {env[key] ? "On" : "Off"}
              </button>
            </div>
          ))}
          {(
            [
              ["Grid intensity", "gridIntensity"],
              ["Shadow", "shadowStrength"],
              ["Reflection", "reflectionStrength"],
              ["Floor reflectivity", "floorReflectivity"],
              ["Ambient", "ambientLevel"],
              ["Highlight", "highlightLevel"],
            ] as const
          ).map(([name, key]) => (
            <div key={key} className="mt-1 flex items-center justify-between gap-2">
              <span className="shrink-0 text-[10.5px] text-platinum-dim">{name}</span>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={env[key]}
                onChange={(e) => set({ [key]: Number(e.target.value) } as Partial<ViewEnvironment>)}
                className="h-1 w-24 accent-[color:var(--c-blue)]"
                aria-label={name}
              />
            </div>
          ))}
          <p className="mt-1 text-[9.5px] leading-snug text-muted">
            Ambient is the fill, Highlight is the key. Lighting changes how the surface reads. It does not change the
            surface.
          </p>
        </section>

        {/* ---- Line detail ---- */}
        <section>
          <p className={label}>View detail</p>
          <ModeRow name="Edges" value={env.edgeMode} onPick={(v) => set({ edgeMode: v })} />
          <ModeRow name="Datum lines" value={env.datumLineMode} onPick={(v) => set({ datumLineMode: v })} />
          <WeightRow name="Measurement" value={env.measurementLineWeight} onPick={(v) => set({ measurementLineWeight: v })} />
          <WeightRow name="Toolpath" value={env.toolpathLineWeight} onPick={(v) => set({ toolpathLineWeight: v })} />
          <div className="mt-1 flex items-center justify-between">
            <span className="text-[10.5px] text-platinum-dim">Feature ring</span>
            <button className={btn(env.featureRingHighContrast)} onClick={() => set({ featureRingHighContrast: !env.featureRingHighContrast })}>
              {env.featureRingHighContrast ? "High contrast" : "Normal"}
            </button>
          </div>
          <div className="mt-1 flex items-center justify-between gap-1">
            <span className="text-[10.5px] text-platinum-dim">Text</span>
            <span className="flex gap-1">
              {(["COMPACT", "STANDARD", "LARGE"] as AnnotationSize[]).map((s) => (
                <button key={s} className={btn(env.annotationSize === s)} onClick={() => set({ annotationSize: s })}>
                  {s[0]}
                </button>
              ))}
            </span>
          </div>
        </section>

        {/* ---- View modes ---- */}
        <section>
          <p className={label}>View mode</p>
          <div className="mt-1.5 grid grid-cols-2 gap-1">
            {(
              [
                ["PROGRAMMING", "Programming"],
                ["INSPECTION", "Inspection"],
                ["PRESENTATION", "Presentation"],
                ["SHOP_FLOOR", "Shop floor"],
              ] as [ViewMode, string][]
            ).map(([m, name]) => (
              <button key={m} className={btn(env.viewMode === m)} onClick={() => onApplyViewMode(m)}>
                {name}
              </button>
            ))}
          </div>
          <p className="mt-1 text-[9.5px] leading-snug text-muted">
            Modes change visibility emphasis. Nothing is removed — everything stays one toggle away.
          </p>
        </section>

        {/* ---- Saved presets ---- */}
        <section>
          <p className={label}>Saved presets</p>
          <div className="mt-1.5 flex gap-1">
            <input
              value={presetName}
              onChange={(e) => setPresetName(e.target.value)}
              placeholder="Name — e.g. Aluminum inspection"
              className="min-w-0 flex-1 border border-line-strong bg-surface px-1.5 py-1 text-[10px] text-platinum-dim placeholder:text-muted"
            />
            <button
              className={btn(false)}
              onClick={() => {
                if (!presetName.trim()) return;
                const list = saveNamedPreset(presetName.trim(), env);
                setSaved(list);
                pushServerPreferences({ saved: list });
                setPresetName("");
              }}
            >
              Save
            </button>
          </div>
          {saved.length > 0 && (
            <ul className="mt-1.5 space-y-0.5">
              {saved.map((p) => (
                <li key={p.name} className="flex items-center justify-between gap-2">
                  <button className="min-w-0 flex-1 truncate text-left text-[10.5px] text-platinum-dim hover:text-platinum" onClick={() => onChange(p.env)}>
                    {p.name}
                  </button>
                  <button
                    className="text-[10px] text-muted hover:text-risk"
                    onClick={() => {
                      const list = deleteNamedPreset(p.name);
                      setSaved(list);
                      pushServerPreferences({ saved: list });
                    }}
                    aria-label={`Delete ${p.name}`}
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          )}
          <p className="mt-1 text-[9.5px] leading-snug text-muted">Saved to your account — presets follow you across devices.</p>
        </section>

        {/* ---- Quality ---- */}
        {onQuality && (
          <section>
            <p className={label}>Viewport quality</p>
            <div className="mt-1.5 flex gap-1">
              {(["AUTO", "HIGH", "PERFORMANCE"] as const).map((q) => (
                <button key={q} className={btn(quality === q)} onClick={() => onQuality(q)}>
                  {q === "PERFORMANCE" ? "PERF" : q}
                </button>
              ))}
            </div>
            <p className="mt-1 text-[9.5px] leading-snug text-muted">
              Performance lowers pixel ratio, shadows and reflections for frame rate. Geometry, toolpaths, datums and warnings are never removed.
            </p>
          </section>
        )}

        {/* ---- Reset ---- */}
        <section>
          <p className={label}>Reset</p>
          <div className="mt-1.5 grid grid-cols-2 gap-1">
            <button
              className={btn(false)}
              title="Default camera, orientation, background and visibility. Manufacturing data is untouched."
              onClick={() => {
                onChange(VIEW_PRESETS.STUDIO_WHITE.env);
                window.dispatchEvent(new CustomEvent("canvas:reset-view"));
              }}
            >
              Reset view
            </button>
            <button
              className={btn(false)}
              title="Restore the approved default panel layout — collapsed drawer, compact runway, closed drawers."
              onClick={() => {
                try {
                  for (const k of Object.keys(window.localStorage)) {
                    if (k.startsWith("canvas.") && (k.includes("Width") || k.includes("Drawer") || k.includes("View") || k.includes("runway") || k.includes("panel"))) {
                      window.localStorage.removeItem(k);
                    }
                  }
                } catch {
                  /* fine */
                }
                window.location.reload();
              }}
            >
              Reset workspace
            </button>
          </div>
          <p className="mt-1 text-[9.5px] leading-snug text-muted">
            Reset view restores the default scene; reset workspace restores the default panel layout. Neither touches manufacturing data.
          </p>
        </section>

        {/* ---- Export view ---- */}
        <section>
          <p className={label}>Export view</p>
          <button className={`${btn(false)} mt-1.5 w-full`} onClick={screenshot}>
            Screenshot (PNG)
          </button>
          <ul className="mt-1 space-y-0.5">
            {["Annotated image", "Setup sheet", "Inspection view", "Customer-safe view"].map((x) => (
              <li key={x} className="flex items-center justify-between text-[10px] text-muted">
                <span>{x}</span>
                <span className="border border-line-strong px-1 text-[8px] font-semibold uppercase tracking-[0.1em]">Development</span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}

/**
 * A hex field that only hands over a colour it can read.
 *
 * Typing is a sequence of invalid states — "#", "#0", "#0b" — and writing
 * each one into the environment persisted them, to this browser and to the
 * server. Worse, a value the contrast maths cannot parse returns null from
 * every check, so an unreadable ground sailed past the semantic-conflict
 * warning by never being evaluated at all. The draft stays local until it
 * parses; until then the field says so rather than accepting it quietly.
 */
function HexField({ label: name, value, onCommit }: { label: string; value: string; onCommit: (hex: string) => void }) {
  const [draft, setDraft] = useState<string | null>(null);
  const shown = draft ?? value;
  const valid = parseHexColor(shown) !== null;
  return (
    <input
      value={shown}
      onChange={(e) => {
        setDraft(e.target.value);
        const hex = parseHexColor(e.target.value);
        if (hex) onCommit(hex);
      }}
      onBlur={() => setDraft(null)}
      aria-label={name}
      aria-invalid={!valid}
      title={valid ? undefined : "Six hex digits, e.g. #1b2530 — not applied until it reads as a colour"}
      className={`w-16 border bg-surface px-1 py-0.5 font-mono text-[9.5px] ${
        valid ? "border-line-strong text-platinum-dim" : "border-review text-review"
      }`}
    />
  );
}

function ModeRow({ name, value, onPick }: { name: string; value: LineMode; onPick: (v: LineMode) => void }) {
  return (
    <div className="mt-1 flex items-center justify-between gap-1">
      <span className="text-[10.5px] text-platinum-dim">{name}</span>
      <span className="flex gap-1">
        {(["OFF", "LIGHT", "MEDIUM", "STRONG"] as LineMode[]).map((m) => (
          <button key={m} className={btn(value === m)} onClick={() => onPick(m)} title={m.toLowerCase()}>
            {m === "OFF" ? "0" : m[0]}
          </button>
        ))}
      </span>
    </div>
  );
}

function WeightRow({ name, value, onPick }: { name: string; value: LineWeight; onPick: (v: LineWeight) => void }) {
  return (
    <div className="mt-1 flex items-center justify-between gap-1">
      <span className="text-[10.5px] text-platinum-dim">{name}</span>
      <span className="flex gap-1">
        {(["THIN", "MEDIUM", "HEAVY"] as LineWeight[]).map((m) => (
          <button key={m} className={btn(value === m)} onClick={() => onPick(m)} title={m.toLowerCase()}>
            {m[0]}
          </button>
        ))}
      </span>
    </div>
  );
}
