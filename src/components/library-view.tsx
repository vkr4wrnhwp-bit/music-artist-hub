"use client";

import { useEffect, useState, type ReactNode } from "react";

/**
 * Library view switcher — GRID (visual, default) or TABLE (power users).
 * Both are server-rendered; this only chooses which one shows, and the
 * choice persists per device.
 */
export function LibraryView({ storageKey, grid, table }: { storageKey: string; grid: ReactNode; table: ReactNode }) {
  const [mode, setMode] = useState<"GRID" | "TABLE">("GRID");
  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(storageKey);
      if (stored === "TABLE") setMode("TABLE");
    } catch {
      /* fine */
    }
  }, [storageKey]);
  const set = (m: "GRID" | "TABLE") => {
    setMode(m);
    try {
      window.localStorage.setItem(storageKey, m);
    } catch {
      /* fine */
    }
  };
  return (
    <div>
      <div className="mb-3 flex items-center gap-1">
        {(["GRID", "TABLE"] as const).map((m) => (
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
      {mode === "GRID" ? grid : table}
    </div>
  );
}
