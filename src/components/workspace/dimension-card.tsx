"use client";

import type { Feature } from "@/lib/domain/features";
import { featureSummary, fmtTol } from "@/lib/domain/features";
import { primaryDimension } from "./dimension";
import { StatusChip } from "@/components/ui";

/**
 * THE FLOATING DIMENSION CARD
 *
 * The reference design calls this "LIVE DIMENSION". It is not live, and
 * saying so would be the most consequential lie on the screen: there is no
 * machine connection, no probe feed and no streaming data path anywhere in
 * CANVAS. `MACHINE_PROBE` is a row in the metrology list, not a socket.
 *
 * WHAT IT CARRIES, AND WHY SO LITTLE
 * It used to repeat the feature panel almost verbatim — the same ⌀, the same
 * tolerance, the same recorded reading with its instrument and its deviation
 * line — 30px from the panel already saying all of it, in a 268 x 360 block
 * pinned over the top-right of the work window. Two large duplicate numbers
 * side by side split attention and cost the part 17.6% of its canvas.
 *
 * So it is now only what the 3D view uniquely adds: which feature the geometry
 * under the cursor IS, its one primary dimension, its tolerance, and whether
 * it is critical. The evidence — the recorded reading, the instrument, the
 * deviation, the datum — belongs to the panel, which owns it and owns it
 * better. Nothing has been dropped from the product; it has been dropped from
 * the duplicate.
 *
 * There is no confidence row. `Measurement.suggestionConfidence` exists, but
 * it scores how well a reading matches a published standard nominal — not
 * confidence in the measurement, the feature or the part — and it is null on
 * every seeded row. A percentage beside a dimension is exactly the pattern
 * principle 1 forbids.
 */
export function DimensionCard({ feature, onDismiss }: { feature: Feature; onDismiss: () => void }) {
  const model = primaryDimension(feature);

  return (
    /* Bottom-left, over the empty ground plane, rather than pinned to the top
       right where it forced the camera back to keep the part clear of it. */
    <div className="pointer-events-auto absolute bottom-3 right-3 z-20 w-[230px] border border-line-strong bg-card/95 shadow-[0_10px_30px_rgba(16,20,24,0.10)] backdrop-blur">
      <div className="flex items-start justify-between gap-2 border-b border-line px-3 py-1.5">
        <div className="min-w-0">
          <p className="instrument-label">Selected feature</p>
          <p className="mt-0.5 truncate text-[12.5px] leading-tight text-platinum">{feature.label}</p>
        </div>
        <button
          onClick={onDismiss}
          aria-label="Clear selection"
          className="-mr-1 -mt-0.5 shrink-0 p-1 text-muted transition-colors hover:text-platinum"
        >
          <svg width="11" height="11" viewBox="0 0 11 11" aria-hidden="true">
            <g stroke="currentColor" strokeWidth="1.1">
              <line x1="1.5" y1="1.5" x2="9.5" y2="9.5" />
              <line x1="9.5" y1="1.5" x2="1.5" y2="9.5" />
            </g>
          </svg>
        </button>
      </div>

      {/* MODEL — what the plan cuts. Not a measurement, and labelled so. */}
      <div className="px-3 py-2">
        <div className="flex items-baseline justify-between gap-2">
          <span className="instrument-label">Model</span>
          {feature.critical && <StatusChip tone="review">Critical</StatusChip>}
        </div>
        {model ? (
          <p className="mt-1 font-mono text-[24px] leading-none tracking-tight text-platinum tabular-nums">
            {model.prefix}
            {model.value.toFixed(4)}
            <span className="ml-1.5 text-[12px] text-muted">in</span>
          </p>
        ) : (
          <p className="mt-1 text-[12px] text-muted">{featureSummary(feature)}</p>
        )}
        <div className="mt-1 flex items-baseline justify-between gap-2">
          <span className="text-[11px] text-muted">{model ? model.name : "Geometry"}</span>
          <span className="font-mono text-[11px] text-platinum-dim tabular-nums">
            {feature.tolerance ? fmtTol(feature.tolerance) : "no tolerance stated"}
          </span>
        </div>
        <p className="mt-1.5 border-t border-line pt-1.5 text-[10.5px] leading-snug text-muted">
          Readings, instrument and deviation are in the feature panel.
        </p>
      </div>
    </div>
  );
}
