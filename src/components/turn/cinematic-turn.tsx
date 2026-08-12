"use client";

import { useState } from "react";
import { CinematicDrawer } from "@/components/workspace/cinematic-drawer";
import type { CinematicInput } from "@/lib/cinematic";

/**
 * Cinematic entry for the turning workspace. The drawer and engine are the
 * shared ones — turning only changes the language the shots speak (bar
 * spins, tool holds) via input.process = "TURN". Communication artifact
 * only; the drawer carries the NOT-NC-VERIFICATION disclaimer on every
 * output.
 */
export function CinematicTurnButton({ input }: { input: CinematicInput }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        onClick={() => setOpen((v) => !v)}
        className="border border-line-strong px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-platinum-dim hover:bg-panel"
      >
        Cinematic
      </button>
      {open && (
        <div className="fixed right-4 top-16 z-40 max-h-[80vh]">
          <CinematicDrawer input={input} activeOperationId={null} onClose={() => setOpen(false)} />
        </div>
      )}
    </>
  );
}
