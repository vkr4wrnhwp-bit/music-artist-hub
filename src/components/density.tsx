"use client";

import { useEffect, useState } from "react";

/**
 * DENSITY — COMFORTABLE (default) or COMPACT.
 *
 * One root attribute governs the whole instrument; CSS in globals.css
 * overrides only the shared primitives' density hooks (panel chrome,
 * data rows, table cells). Type hierarchy, color and page structure are
 * untouched — density is spacing, not a different design.
 */

export type Density = "COMFORTABLE" | "COMPACT";
const KEY = "canvas.density";

function apply(d: Density) {
  if (d === "COMPACT") document.documentElement.dataset.density = "compact";
  else delete document.documentElement.dataset.density;
}

function stored(): Density {
  try {
    return window.localStorage.getItem(KEY) === "COMPACT" ? "COMPACT" : "COMFORTABLE";
  } catch {
    return "COMFORTABLE";
  }
}

/** Mounted once in the app layout: applies the saved density on load. */
export function DensityApplier() {
  useEffect(() => {
    apply(stored());
    const onChange = () => apply(stored());
    window.addEventListener("canvas:density", onChange);
    return () => window.removeEventListener("canvas:density", onChange);
  }, []);
  return null;
}

export function DensityToggle() {
  const [density, setDensity] = useState<Density>("COMFORTABLE");
  useEffect(() => setDensity(stored()), []);

  const set = (d: Density) => {
    setDensity(d);
    try {
      window.localStorage.setItem(KEY, d);
    } catch {
      /* session-only is fine */
    }
    apply(d);
    window.dispatchEvent(new CustomEvent("canvas:density"));
  };

  return (
    <div className="flex items-center gap-2">
      {(["COMFORTABLE", "COMPACT"] as const).map((d) => (
        <button
          key={d}
          onClick={() => set(d)}
          aria-pressed={density === d}
          className={`border px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] transition-colors ${
            density === d
              ? "border-precision/60 text-precision-dim"
              : "border-line-strong text-muted hover:text-platinum"
          }`}
        >
          {d}
        </button>
      ))}
    </div>
  );
}
