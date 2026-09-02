"use client";

import type { Feature, Stock } from "@/lib/domain/features";
import { fmt } from "@/lib/domain/features";
import { sectionStroke, type ViewEnvironment } from "@/lib/view-environment";

/**
 * SECTION SKETCH
 *
 * A technical section through the selected feature, drawn from the stored
 * parameters and nothing else.
 *
 * Everything with a number against it — diameter, width, depth, stock
 * thickness, centre offset — comes from the feature or the stock record. The
 * liberties taken are scale: both the vertical and the horizontal are floored
 * (`depthPx`, `halfPx`) so a small feature in a large plate stays legible at
 * panel width. The caption says so.
 *
 * What is deliberately NOT drawn:
 *   - edge breaks, chamfers and fillets. This sketch is built from the same
 *     axis-aligned parameters as `part-solid.ts`, which does not represent a
 *     non-vertical wall, so an edge break drawn here would be drawn from
 *     nothing. It is a limit of the DRAWING, not a statement about the plan:
 *     the deterministic CAM engine does emit a CHAMFER toolpath, and where one
 *     exists it appears in the operation plan below.
 *   - anything for a feature kind whose section CANVAS cannot derive. That
 *     case returns a stated omission rather than a generic rectangle.
 */

const OUTLINE = "var(--c-platinum-dim)";
/* The hatch IS the fill in a section drawing, so `sectionFillColor` is
   literal rather than a near-synonym. It was a persisted setting nothing
   read. */
const DIM = "var(--c-blue)";

// The viewBox is wider than the slab on both sides on purpose: the stock
// thickness sits outside it on the left and the depth callout on the right,
// and both were clipped when the margins were tighter.
const W = 320;
const H = 132;
const SLAB_L = 44;
const SLAB_R = 268;
const SLAB_W = SLAB_R - SLAB_L;
const SLAB_T = 44;
const SLAB_H = 56;
const SLAB_B = SLAB_T + SLAB_H;

interface Section {
  /** Half-width of the removed volume, in inches. */
  halfWidth: number;
  /** Depth below the top face, in inches. Ignored when `through`. */
  depth: number;
  through: boolean;
  /** Centre offset from the stock centre along X, in inches. */
  centerX: number;
  /** Label for the across-the-top dimension. */
  widthLabel: string;
  /** Second, larger opening (counterbore head), when one exists. */
  head?: { halfWidth: number; depth: number; label: string };
}

function sectionFor(f: Feature): Section | null {
  switch (f.kind) {
    case "BORE":
    case "CIRC_POCKET":
      return {
        halfWidth: f.diameter / 2,
        depth: f.depth,
        through: f.through,
        centerX: f.centerX,
        widthLabel: `⌀${fmt(f.diameter)}`,
      };
    case "DRILLED_HOLE":
    case "TAPPED_HOLE":
      return {
        halfWidth: f.diameter / 2,
        depth: f.depth,
        through: f.through,
        centerX: f.centerX,
        widthLabel: f.kind === "TAPPED_HOLE" && f.thread ? f.thread : `⌀${fmt(f.diameter)}`,
      };
    case "COUNTERBORE":
      return {
        halfWidth: f.diameter / 2,
        depth: f.depth,
        through: f.through,
        centerX: f.centerX,
        widthLabel: `⌀${fmt(f.diameter)}`,
        head:
          f.headDiameter != null && f.headDepth != null
            ? { halfWidth: f.headDiameter / 2, depth: f.headDepth, label: `⌀${fmt(f.headDiameter)}` }
            : undefined,
      };
    case "RECT_POCKET":
      return {
        halfWidth: f.width / 2,
        depth: f.depth,
        through: false,
        centerX: f.centerX,
        widthLabel: `${fmt(f.width)} wide`,
      };
    case "SLOT":
      return {
        halfWidth: f.width / 2,
        depth: f.depth,
        through: false,
        centerX: (f.startX + f.endX) / 2,
        widthLabel: `${fmt(f.width)} wide`,
      };
    default:
      return null;
  }
}

export function SectionSketch({ feature, stock, env }: { feature: Feature; stock: Stock | null; env: ViewEnvironment }) {
  const cut = sectionStroke(env.sectionLineMode);
  if (!stock) {
    return (
      <Omission>
        Stock is not defined for this revision, so there is no material section to draw the feature into.
      </Omission>
    );
  }

  if (feature.kind === "FACE") {
    return <FaceSection feature={feature} stock={stock} env={env} />;
  }

  const section = sectionFor(feature);
  if (!section) {
    return (
      <Omission>
        CANVAS does not derive a cross-section for a {feature.kind.replace(/_/g, " ").toLowerCase()}. Drawing one would
        mean inventing geometry the toolpath does not produce.
      </Omission>
    );
  }

  const stockX = stock.form === "ROUND" ? (stock.diameter ?? stock.x) : stock.x;
  // True proportions, floored so a small hole in a wide plate is still legible.
  const halfPx = Math.max(7, (section.halfWidth / stockX) * SLAB_W);
  const cxPx = SLAB_L + SLAB_W / 2 + (section.centerX / stockX) * SLAB_W;
  const depthPx = section.through ? SLAB_H : Math.max(7, Math.min(SLAB_H, (section.depth / stock.z) * SLAB_H));
  const headHalfPx = section.head ? Math.max(halfPx + 5, (section.head.halfWidth / stockX) * SLAB_W) : 0;
  const headDepthPx = section.head ? Math.max(5, (section.head.depth / stock.z) * SLAB_H) : 0;

  const left = cxPx - halfPx;
  const right = cxPx + halfPx;
  const bottom = SLAB_T + depthPx;

  return (
    <figure className="m-0">
      <svg viewBox={`0 0 ${W} ${H}`} className="block w-full" role="img" aria-label={`Section through ${feature.label}`}>
        <defs>
          <pattern id="cs-hatch" width="6" height="6" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
            <line x1="0" y1="0" x2="0" y2="6" stroke={env.sectionFillColor} strokeWidth="1" />
          </pattern>
        </defs>

        {/* Material, sectioned. Hatching is what makes this read as a cut. */}
        <path
          d={
            section.through
              ? `M${SLAB_L} ${SLAB_T} H${left} V${SLAB_B} H${SLAB_L} Z M${right} ${SLAB_T} H${SLAB_R} V${SLAB_B} H${right} Z`
              : `M${SLAB_L} ${SLAB_T} H${section.head ? cxPx - headHalfPx : left} ` +
                (section.head
                  ? `V${SLAB_T + headDepthPx} H${left} V${bottom} H${right} V${SLAB_T + headDepthPx} H${cxPx + headHalfPx} V${SLAB_T} `
                  : `V${bottom} H${right} V${SLAB_T} `) +
                `H${SLAB_R} V${SLAB_B} H${SLAB_L} Z`
          }
          fill="url(#cs-hatch)"
          stroke={OUTLINE}
          strokeWidth={cut.width}
          strokeOpacity={cut.opacity}
          fillRule="evenodd"
        />

        {/* Centreline of the feature — blue, because it is a datum reference. */}
        <line
          x1={cxPx}
          y1={SLAB_T - 16}
          x2={cxPx}
          y2={SLAB_B + 10}
          stroke={DIM}
          strokeWidth="0.75"
          strokeDasharray="7 3 1.5 3"
          opacity="0.85"
        />

        {/* Across-the-top dimension */}
        <g stroke={DIM} strokeWidth="0.9" fill="none">
          <line x1={left} y1={SLAB_T - 22} x2={right} y2={SLAB_T - 22} />
          <line x1={left} y1={SLAB_T - 26} x2={left} y2={SLAB_T - 18} />
          <line x1={right} y1={SLAB_T - 26} x2={right} y2={SLAB_T - 18} />
        </g>
        <text
          x={cxPx}
          y={SLAB_T - 28}
          textAnchor="middle"
          fill={DIM}
          fontSize="10"
          fontFamily="var(--font-mono-tech), ui-monospace, monospace"
        >
          {section.widthLabel}
        </text>

        {/* Depth dimension, on the right */}
        <g stroke={DIM} strokeWidth="0.9" fill="none">
          <line x1={SLAB_R + 10} y1={SLAB_T} x2={SLAB_R + 10} y2={bottom} />
          <line x1={SLAB_R + 6} y1={SLAB_T} x2={SLAB_R + 14} y2={SLAB_T} />
          <line x1={SLAB_R + 6} y1={bottom} x2={SLAB_R + 14} y2={bottom} />
        </g>
        <text
          x={SLAB_R + 16}
          y={(SLAB_T + bottom) / 2 + 3}
          fill={DIM}
          fontSize="9.5"
          fontFamily="var(--font-mono-tech), ui-monospace, monospace"
        >
          {section.through ? "THRU" : fmt(section.depth)}
        </text>

        {/* Stock thickness, on the left */}
        <g stroke="var(--c-muted)" strokeWidth="0.9" fill="none">
          <line x1={SLAB_L - 12} y1={SLAB_T} x2={SLAB_L - 12} y2={SLAB_B} />
          <line x1={SLAB_L - 16} y1={SLAB_T} x2={SLAB_L - 8} y2={SLAB_T} />
          <line x1={SLAB_L - 16} y1={SLAB_B} x2={SLAB_L - 8} y2={SLAB_B} />
        </g>
        <text
          x={SLAB_L - 18}
          y={(SLAB_T + SLAB_B) / 2 + 3}
          textAnchor="end"
          fill="var(--c-muted)"
          fontSize="9.5"
          fontFamily="var(--font-mono-tech), ui-monospace, monospace"
        >
          {fmt(stock.z, 3)}
        </text>
      </svg>
      <Caption />
    </figure>
  );
}

function FaceSection({ feature, stock, env }: { feature: Extract<Feature, { kind: "FACE" }>; stock: Stock; env: ViewEnvironment }) {
  const cut = sectionStroke(env.sectionLineMode);
  const cutPx = Math.max(5, Math.min(SLAB_H - 6, (feature.depth / stock.z) * SLAB_H));
  const finishedTop = SLAB_T + cutPx;

  return (
    <figure className="m-0">
      <svg viewBox={`0 0 ${W} ${H}`} className="block w-full" role="img" aria-label={`Section showing ${feature.label}`}>
        <defs>
          <pattern id="fs-hatch" width="6" height="6" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
            <line x1="0" y1="0" x2="0" y2="6" stroke={env.sectionFillColor} strokeWidth="1" />
          </pattern>
        </defs>

        {/* Material that survives */}
        <rect
          x={SLAB_L}
          y={finishedTop}
          width={SLAB_W}
          height={SLAB_B - finishedTop}
          fill="url(#fs-hatch)"
          stroke={OUTLINE}
          strokeWidth={cut.width}
          strokeOpacity={cut.opacity}
        />
        {/* Material this operation removes */}
        <rect
          x={SLAB_L}
          y={SLAB_T}
          width={SLAB_W}
          height={cutPx}
          fill="none"
          stroke={DIM}
          strokeWidth="0.9"
          strokeDasharray="4 3"
        />

        <g stroke={DIM} strokeWidth="0.9" fill="none">
          <line x1={SLAB_R + 10} y1={SLAB_T} x2={SLAB_R + 10} y2={finishedTop} />
          <line x1={SLAB_R + 6} y1={SLAB_T} x2={SLAB_R + 14} y2={SLAB_T} />
          <line x1={SLAB_R + 6} y1={finishedTop} x2={SLAB_R + 14} y2={finishedTop} />
        </g>
        <text
          x={SLAB_R + 16}
          y={(SLAB_T + finishedTop) / 2 + 3}
          fill={DIM}
          fontSize="9.5"
          fontFamily="var(--font-mono-tech), ui-monospace, monospace"
        >
          {fmt(feature.depth)}
        </text>

        <text
          x={SLAB_L}
          y={SLAB_T - 10}
          fill="var(--c-muted)"
          fontSize="9.5"
          fontFamily="var(--font-mono-tech), ui-monospace, monospace"
        >
          MATERIAL REMOVED
        </text>

        <g stroke="var(--c-muted)" strokeWidth="0.9" fill="none">
          <line x1={SLAB_L - 12} y1={SLAB_T} x2={SLAB_L - 12} y2={SLAB_B} />
          <line x1={SLAB_L - 16} y1={SLAB_T} x2={SLAB_L - 8} y2={SLAB_T} />
          <line x1={SLAB_L - 16} y1={SLAB_B} x2={SLAB_L - 8} y2={SLAB_B} />
        </g>
        <text
          x={SLAB_L - 18}
          y={(SLAB_T + SLAB_B) / 2 + 3}
          textAnchor="end"
          fill="var(--c-muted)"
          fontSize="9.5"
          fontFamily="var(--font-mono-tech), ui-monospace, monospace"
        >
          {fmt(stock.z, 3)}
        </text>
      </svg>
      <Caption />
    </figure>
  );
}

function Caption() {
  return (
    <figcaption className="mt-1.5 text-[11px] leading-relaxed text-muted">
      Drawn from the stored feature parameters. Small features are floored to stay legible, so both scales are
      exaggerated. Edge breaks, chamfers and fillets are not drawn — the solid model does not represent a non-vertical
      wall. Where a chamfer operation exists it appears in the operation plan below.
    </figcaption>
  );
}

function Omission({ children }: { children: React.ReactNode }) {
  return (
    <div className="border border-dashed border-line-strong px-3 py-3">
      <p className="text-[11.5px] leading-relaxed text-muted">{children}</p>
    </div>
  );
}
