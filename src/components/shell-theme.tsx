"use client";

import { useEffect } from "react";
import { loadEnvironment } from "@/lib/view-environment";

/**
 * SHELL GROUND — the application chrome's background, applied app-wide.
 *
 * The view-environment drawer has always had a "Background" colour, and it
 * has always repainted the 3D work window only. Picking a colour there left
 * the rail, the header and the panels exactly as they were, which reads as
 * the control doing nothing at all.
 *
 * The chrome is one token. `--canvas-bg-shell` is declared on :root and
 * `.canvas-shell` maps `--c-void` to it, so every surface inside the shell
 * re-resolves from a single custom property — the design system was built
 * for this. Setting it on documentElement reaches every `.canvas-shell`
 * element in the app, including the nav rail and header, which live in a
 * different subtree from the workspace that owns the environment state.
 *
 * Null restores the approved near-black. The stylesheet keeps the default;
 * this only ever overrides it, so removing the property is a real reset
 * rather than a second hardcoded colour.
 */
const SHELL_TOKEN = "--canvas-bg-shell";

export function applyShellBackground(color: string | null) {
  const root = document.documentElement;
  if (color) root.style.setProperty(SHELL_TOKEN, color);
  else root.style.removeProperty(SHELL_TOKEN);
}

/** Mounted once in the app layout: applies the saved shell ground on load. */
export function ShellThemeApplier() {
  useEffect(() => {
    const sync = () => {
      try {
        applyShellBackground(loadEnvironment().shellBackground);
      } catch {
        /* a browser that will not give up localStorage keeps the default */
      }
    };
    sync();
    window.addEventListener("canvas:shell-theme", sync);
    return () => window.removeEventListener("canvas:shell-theme", sync);
  }, []);
  return null;
}
