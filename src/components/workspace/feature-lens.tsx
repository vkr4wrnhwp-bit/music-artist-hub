"use client";

import type { Feature, FunctionalRole } from "@/lib/domain/features";
import { fmtTol } from "@/lib/domain/features";
import type { FeatureActions } from "./feature-actions";

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

// Typed against the domain union so a renamed or added role fails the build
// instead of silently dropping the Function row from the lens.
const ROLE_LABEL: Record<FunctionalRole, string> = {
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
  COSMETIC: "Cosmetic surface",
  STRUCTURAL_RIB: "Structural rib",
  FIXTURE_PAD: "Fixture pad",
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
  actions,
}: {
  feature: Feature;
  pointer: { x: number; y: number } | null;
  /** Measurement capability verdict for this feature, when one applies. */
  capability?: { verdict: string; reason: string } | null;
  /** DETAIL / MEASURE / MAKE / VERIFY, as availability rather than controls. */
  actions: FeatureActions;
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
        <p className="text-[12px] font-medium leading-tight text-platinum">{feature.label}</p>
        <p className="instrument-label mt-0.5">{KIND_LABEL[feature.kind] ?? feature.kind}</p>
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
            <span className="instrument-label">Function</span>
            <span className="text-[12px] text-platinum-dim">{role}</span>
          </div>
        )}

        {feature.critical && (
          <div className="flex items-baseline justify-between gap-3">
            <span className="instrument-label">Criticality</span>
            <span className="text-[12px] text-review">Critical</span>
          </div>
        )}

        {capability && capability.verdict !== "NOT_REQUIRED" && (
          <div className="flex items-baseline justify-between gap-3">
            <span className="instrument-label">Measurable</span>
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

      {/* The four, as NAMED AVAILABILITY rather than as controls.
          This surface follows the cursor and stays pointer-events-none on
          purpose — a form on hover is a trap, because reaching it means
          dragging the cursor across the part and over other geometry. So the
          lens states what each action would find and the click-through panel
          carries the controls.

          Four independent statements, never a tally. There is no count, no
          score and no colour ramp: an absent operation is an absence, which
          is why it renders muted rather than as a risk. */}
      <div className="grid grid-cols-4 border-t border-line">
        {(
          [
            ["Detail", actions.detail],
            ["Measure", actions.measure],
            ["Make", actions.make],
            ["Verify", actions.verify],
          ] as const
        ).map(([name, a]) => (
          <div key={name} className="min-w-0 border-r border-line px-2 py-1.5 last:border-r-0">
            <p className="instrument-label">{name}</p>
            <p className={`mt-0.5 truncate text-[10px] leading-tight ${a.available ? "text-platinum-dim" : "text-unknown"}`}>
              {a.available ? a.detail : a.reason}
            </p>
          </div>
        ))}
      </div>

      <p className="border-t border-line px-3 py-1.5 text-[9px] font-semibold uppercase tracking-[0.14em] text-muted">
        Click to open the feature panel
      </p>
    </div>
  );
}
