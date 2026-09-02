"use client";

import { useEffect, useState } from "react";
import type { SimHandle } from "@/components/viewport/sim-view";

/**
 * CUT transport — playback controls and live readout for the stock-removal
 * simulation.
 *
 * The readout is real arithmetic from the simulator: current feed and rpm
 * come from the segment under the playhead, removed volume from the height
 * field, collisions from the deterministic construction pass. The label says
 * GEOMETRIC SIMULATION because that is what it is — clearance and removal,
 * no forces — and the record button appears only once the playback has
 * actually reached the end.
 */

const SPEEDS = [0.25, 1, 5, 10, 50];

export function SimTransport({
  handle,
  onRecordRun,
  recorded,
}: {
  handle: SimHandle;
  /** Server action recording the completed run; absent when not offered. */
  onRecordRun?: (payload: { removedVolume: number; totalTime: number; collisions: number; fixtureChecked: boolean }) => Promise<void>;
  recorded: boolean;
}) {
  // The handle mutates outside React at frame rate; the HUD samples it at
  // reading speed instead of re-rendering the workspace 60 times a second.
  const [, tick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => tick((t) => t + 1), 150);
    return () => clearInterval(id);
  }, []);
  const [showEvents, setShowEvents] = useState(false);
  const [saving, setSaving] = useState(false);

  const sim = handle.sim;
  const m = sim.metricsAt(handle.time);
  const op = sim.ops[m.opIndex];
  const done = handle.time >= sim.totalTime - 1e-9;
  const pct = sim.totalRemovedVolume > 0 ? (m.removedVolume / sim.totalRemovedVolume) * 100 : 0;

  const btn = "border border-line-strong px-2 py-0.5 font-mono text-[9.5px] uppercase tracking-[0.14em] text-platinum-dim transition-colors hover:text-platinum";

  return (
    <div className="absolute inset-x-3 bottom-3 z-20 space-y-1.5">
      {showEvents && sim.collisions.length > 0 && (
        <div className="max-h-40 overflow-y-auto border border-line-strong bg-card/95 px-3 py-2 backdrop-blur">
          <ul className="space-y-1">
            {sim.collisions.map((c, i) => (
              <li key={i} className="text-[11px] leading-snug text-risk">
                <button className="underline decoration-dotted" onClick={() => { handle.time = Math.max(0, c.time - 0.01); handle.scrubbed++; handle.playing = false; }}>
                  {fmtT(c.time)}
                </button>{" "}
                <span className="text-platinum-dim">{c.detail}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 border border-line-strong bg-card/95 px-3 py-2 backdrop-blur">
        <button className={btn} onClick={() => { if (done && !handle.playing) { handle.time = 0; handle.scrubbed++; } handle.playing = !handle.playing; }}>
          {handle.playing ? "Pause" : done ? "Replay" : "Play"}
        </button>
        <button className={btn} title="Back one move" onClick={() => { handle.playing = false; handle.time = prevBoundary(sim, handle.time); handle.scrubbed++; }}>
          −1
        </button>
        <button className={btn} title="Forward one move" onClick={() => { handle.playing = false; handle.time = nextBoundary(sim, handle.time); handle.scrubbed++; }}>
          +1
        </button>
        <select
          value={handle.speed}
          onChange={(e) => { handle.speed = Number(e.target.value); }}
          className="border border-line-strong bg-surface px-1 py-0.5 font-mono text-[9.5px] text-platinum-dim"
          aria-label="Playback speed"
        >
          {SPEEDS.map((s) => (
            <option key={s} value={s}>{s}×</option>
          ))}
        </select>
        <button className={btn} title="Camera follows the cutter tip" onClick={() => { handle.followTool = !handle.followTool; }}>
          {handle.followTool ? "Unfollow" : "Follow tool"}
        </button>

        {/* Scrub bar with the operation boundaries and collisions marked on it. */}
        <div className="relative min-w-[160px] flex-1">
          <input
            type="range"
            aria-label="Simulation time"
            min={0}
            max={sim.totalTime}
            step={sim.totalTime / 2000}
            value={handle.time}
            onChange={(e) => { handle.playing = false; handle.time = Number(e.target.value); handle.scrubbed++; }}
            className="h-1 w-full accent-[color:var(--c-blue)]"
          />
          {sim.opStartTimes.map((t, i) => (
            <span key={i} aria-hidden className="absolute top-[-2px] h-2 w-px bg-line-strong" style={{ left: `${(t / sim.totalTime) * 100}%` }} />
          ))}
          {sim.collisions.map((c, i) => (
            <span key={`c${i}`} aria-hidden title={c.detail} className="absolute top-[-3px] h-2.5 w-[3px] bg-risk" style={{ left: `${(c.time / sim.totalTime) * 100}%` }} />
          ))}
        </div>

        <span className="tech-value shrink-0 text-[10px] text-muted tabular-nums">
          {fmtT(handle.time)} / {fmtT(sim.totalTime)}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border border-line-strong bg-card/95 px-3 py-1.5 font-mono text-[10.5px] text-platinum-dim backdrop-blur tabular-nums">
        <span className="text-[9px] font-semibold uppercase tracking-[0.14em] text-muted">Geometric simulation — no forces modelled</span>
        <span>{op?.label ?? "—"}</span>
        <span>T{m.toolNumber}</span>
        <span>{m.rapid ? "RAPID" : `F${m.feed.toFixed(0)} ipm`}</span>
        <span>S{m.rpm}</span>
        <span>
          X{m.position.x.toFixed(3)} Y{m.position.y.toFixed(3)} Z{m.position.z.toFixed(3)}
        </span>
        <span>{m.removedVolume.toFixed(3)} in³ removed ({pct.toFixed(0)}%)</span>
        {sim.collisions.length > 0 ? (
          <button onClick={() => setShowEvents((s) => !s)} className="font-semibold text-risk underline decoration-dotted">
            {sim.collisions.length} collision{sim.collisions.length === 1 ? "" : "s"}
          </button>
        ) : (
          /*
           * "No collisions found" on a run that never modelled the fixture is
           * the sentence an operator acts on. What ran is named instead.
           */
          <span className={sim.fixtureChecked ? "text-pass" : "text-review"}>
            {sim.fixtureChecked
              ? "Nothing hit: stock, standing wall and jaws"
              : "Nothing hit in stock or the standing wall — the jaws were not modelled"}
          </span>
        )}
        {!sim.fixtureChecked && (
          <span className="text-review">
            Record which axis the jaws close on in the setup and the cutter is checked against them.
          </span>
        )}
        {done && onRecordRun && !recorded && (
          <button
            className={`${btn} border-precision/50 text-precision-dim`}
            disabled={saving}
            onClick={async () => {
              setSaving(true);
              await onRecordRun({ removedVolume: m.removedVolume, totalTime: sim.totalTime, collisions: sim.collisions.length, fixtureChecked: sim.fixtureChecked });
            }}
          >
            {saving ? "Recording…" : "Record simulation run"}
          </button>
        )}
        {recorded && <span className="text-pass">Run recorded</span>}
      </div>
    </div>
  );
}

function fmtT(minutes: number): string {
  const s = Math.round(minutes * 60);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function prevBoundary(sim: SimHandle["sim"], t: number): number {
  let out = 0;
  for (const s of sim.segments) {
    if (s.t0 < t - 1e-9) out = s.t0;
    else break;
  }
  return out;
}

function nextBoundary(sim: SimHandle["sim"], t: number): number {
  for (const s of sim.segments) if (s.t0 > t + 1e-9) return Math.min(s.t0, sim.totalTime);
  return sim.totalTime;
}
