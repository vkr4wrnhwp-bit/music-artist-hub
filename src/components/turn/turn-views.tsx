"use client";

import { useEffect, useState, type ReactNode } from "react";

/**
 * TURNING VIEW MODES — PROFILE / 3D / BOTH.
 *
 * Both panels are server-rendered and passed in; this component only
 * chooses what shows. BOTH is a synchronized split — the same ?op=
 * selection drives the highlighted segment in the profile and the
 * playback scope in 3D, so selecting an operation updates both at once.
 * Choice persists per device.
 */
export function TurnViews({ profile, sim }: { profile: ReactNode; sim: ReactNode }) {
  const [mode, setMode] = useState<"PROFILE" | "3D" | "BOTH">("PROFILE");
  useEffect(() => {
    try {
      const stored = window.localStorage.getItem("canvas.turnView");
      if (stored === "3D" || stored === "BOTH") setMode(stored);
    } catch {
      /* fine */
    }
  }, []);
  const set = (m: "PROFILE" | "3D" | "BOTH") => {
    setMode(m);
    try {
      window.localStorage.setItem("canvas.turnView", m);
    } catch {
      /* fine */
    }
  };
  return (
    <div>
      <div className="mb-2 flex items-center gap-1">
        {(["PROFILE", "3D", "BOTH"] as const).map((m) => (
          <button
            key={m}
            onClick={() => set(m)}
            aria-pressed={mode === m}
            className={`border px-2.5 py-1 text-[9.5px] font-semibold uppercase tracking-[0.14em] ${
              mode === m ? "border-precision/60 text-precision-dim" : "border-line-strong text-muted hover:text-platinum"
            }`}
          >
            {m}
          </button>
        ))}
      </div>
      {mode === "BOTH" ? (
        <div className="grid gap-4 xl:grid-cols-2">
          <div>{profile}</div>
          <div>{sim}</div>
        </div>
      ) : mode === "3D" ? (
        sim
      ) : (
        profile
      )}
    </div>
  );
}
