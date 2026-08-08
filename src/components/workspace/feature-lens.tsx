"use client";

import type { Feature } from "@/lib/domain/features";
import { fmtTol } from "@/lib/domain/features";

/**
 * FEATURE LENS
 *
 * What appears when the cursor enters a feature. No click required, and
 * deliberately not a form — a form on hover is a trap, because the cursor has
 * to travel through the part to reach it.
 *
 * The content is what a machinist wants in the second before deciding whether
 * to engage: what it is, how big, what it is for, and how much the number in
 * front of them can be trusted. Everything else waits for a click.
 */

const ROLE_LABEL: Record<string, string> = {
  NONE: "",
  BEARING_SEAT: "Bearing seat",
  SEAL_SURFACE: "Seal surface",
  SHAFT_JOURNAL: "Shaft journal",
  LOCATING_SHOULDER: "Locating shoulder",
  PRESS_FIT: "Press fit",
  SLIP_FIT: "Slip fit",
  THREAD: "Thread",
  MOUNTING_HOLE: "Mounting hole",
  DOWEL_HOLE: "Dowel",
  DATUM_FACE: "Datum face",
  INSPECTION_SURFACE: "Inspection surface",
  FLUID_PASSAGE: "Fluid passage",
  STRUCTURAL_RIB: "Structural rib",
  COSMETIC_SURFACE: "Cosmetic surface",
  CLEARANCE: "Clearance",
};

const KIND_LABEL: Record<string, string> = {
  RECT_POCKET: "Rectangular pocket",
  CIRC_POCKET: "Circular pocket",
  BORE: "Bore",
  DRILLED_HOLE: "Drilled hole",
  TAPPED_HOLE: "Tapped hole",
  SLOT: "Slot",
  FACE: "Face",
  OUTSIDE_CONTOUR: "Outside contour",
  CHAMFER: "Chamfer",
  FILLET: "Fillet",
  BOSS: "Boss",
};

export function FeatureLens({
  feature,
  pointer,
  capability,
}: {
  feature: Feature;
  pointer: { x: number; y: number } | null;
  /** Measurement capability verdict for this feature, when one applies. */
  capability?: { verdict: string; reason: string } | null;
}) {
  if (!pointer) return null;

  const size =
    "diameter" in feature
      ? `⌀${feature.diameter.toFixed(4)}″`
      : "width" in feature && "length" in feature
        ? `${feature.width.toFixed(3)} × ${feature.length.toFixed(3)}″`
        : null;

  const role = ROLE_LABEL[feature.functionalRole] || null;

  // Keep the lens clear of the cursor and inside the viewport.
  const style = {
    left: `${Math.min(pointer.x + 20, typeof window === "undefined" ? pointer.x : window.innerWidth - 280)}px`,
    top: `${Math.max(pointer.y - 12, 12)}px`,
  };

  return (
    <div
      style={style}
      className="pointer-events-none fixed z-40 w-[248px] border border-line-strong bg-surface/95 shadow-[0_8px_28px_rgba(20,24,28,0.14)] backdrop-blur-sm"
    >
      <div className="border-b border-line px-3 py-2">
        <p className="font-mono text-[12px] leading-tight text-platinum">{feature.label}</p>
        <p className="tech-label mt-0.5">{KIND_LABEL[feature.kind] ?? feature.kind}</p>
      </div>

      <div className="space-y-1.5 px-3 py-2.5">
        {size && (
          <div className="flex items-baseline justify-between gap-3">
            <span className="font-mono text-[17px] leading-none tracking-tight text-platinum tabular-nums">{size}</span>
            {feature.tolerance && (
              <span className="font-mono text-[11px] text-muted tabular-nums">{fmtTol(feature.tolerance)}</span>
            )}
          </div>
        )}

        {role && (
          <div className="flex items-baseline justify-between gap-3">
            <span className="tech-label">Function</span>
            <span className="text-[12px] text-platinum-dim">{role}</span>
          </div>
        )}

        {feature.critical && (
          <div className="flex items-baseline justify-between gap-3">
            <span className="tech-label">Criticality</span>
            <span className="text-[12px] text-review">Critical</span>
          </div>
        )}

        {capability && capability.verdict !== "NOT_REQUIRED" && (
          <div className="flex items-baseline justify-between gap-3">
            <span className="tech-label">Measurable</span>
            <span
              className={`text-[12px] ${
                capability.verdict === "CAPABLE"
                  ? "text-pass"
                  : capability.verdict === "MARGINAL"
                    ? "text-review"
                    : "text-risk"
              }`}
            >
              {capability.verdict === "CAPABLE"
                ? "Yes"
                : capability.verdict === "MARGINAL"
                  ? "Marginal"
                  : "Not with what you own"}
            </span>
          </div>
        )}
      </div>

      <p className="border-t border-line px-3 py-1.5 font-mono text-[9px] uppercase tracking-[0.14em] text-muted">
        Click to inspect
      </p>
    </div>
  );
}
