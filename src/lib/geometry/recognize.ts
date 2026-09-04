import type { FeatureSuggestion } from "@/lib/domain/features";
import { assembleLoops, splitProfile, type AssembledLoop, type LoopRefusal, type RawSegment } from "./loop";

/**
 * CLOSED LOOPS INTO FEATURE PROPOSALS.
 *
 * The last step shared by a DXF import and a profile drawn in CANVAS. Loops in,
 * suggestions out, and a human accepts every one before it becomes geometry —
 * the same rule the STEP recognizer follows. Zero-click ingest, never
 * zero-click geometry.
 *
 * WHAT A DRAWING DOES NOT SAY
 *
 * A drawing gives shape. It does not say how deep, and it does not say what an
 * interior loop IS — a circle in a DXF could be a drilled hole, a bored hole,
 * or a circular pocket, and those are three different operations with three
 * different tools. Depth and kind are manufacturing decisions, so interior
 * loops are reported with their size and position and left for a person to
 * classify rather than guessed into holes.
 *
 * The outer profile is different: whatever else is true of it, it is the
 * outside of the part, and there is exactly one. That one is proposed.
 */

export interface GeometryRecognition {
  profile: FeatureSuggestion | null;
  /** What the outer loop measures, for the operator to check against the print. */
  profileSize: { width: number; length: number; area: number } | null;
  /** Interior loops, described but not classified. */
  interior: { label: string; kind: "CIRCLE" | "SHAPE"; diameter: number | null; x: number; y: number; area: number }[];
  refusals: LoopRefusal[];
  warnings: string[];
}

/** Axis-aligned extent of a loop, from its own points and arc extremes. */
function extent(loop: AssembledLoop): { minX: number; maxX: number; minY: number; maxY: number } {
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  const see = (x: number, y: number) => {
    minX = Math.min(minX, x);
    maxX = Math.max(maxX, x);
    minY = Math.min(minY, y);
    maxY = Math.max(maxY, y);
  };
  see(loop.chain.start.x, loop.chain.start.y);
  let from = loop.chain.start;
  for (const seg of loop.chain.segments) {
    see(seg.to.x, seg.to.y);
    if (seg.kind === "ARC") {
      /*
       * An arc can reach past both its endpoints. A quarter-round corner whose
       * ends are both inside the bounding box still bulges out to the radius,
       * and a size taken from endpoints alone would report a part smaller than
       * it is — which is a stock size that does not cover the part.
       */
      const r = Math.hypot(from.x - seg.center.x, from.y - seg.center.y);
      const a0 = Math.atan2(from.y - seg.center.y, from.x - seg.center.x);
      const a1 = Math.atan2(seg.to.y - seg.center.y, seg.to.x - seg.center.x);
      for (const q of [0, Math.PI / 2, Math.PI, -Math.PI / 2]) {
        // Is this cardinal direction inside the swept arc?
        const rel = (t: number) => {
          let d = seg.cw ? a0 - t : t - a0;
          while (d < 0) d += Math.PI * 2;
          return d;
        };
        let sweep = seg.cw ? a0 - a1 : a1 - a0;
        while (sweep <= 0) sweep += Math.PI * 2;
        if (rel(q) <= sweep) see(seg.center.x + r * Math.cos(q), seg.center.y + r * Math.sin(q));
      }
    }
    from = seg.to;
  }
  return { minX, maxX, minY, maxY };
}

/** A loop that is one circle: two half-arcs about a common centre. */
function asCircle(loop: AssembledLoop): { x: number; y: number; diameter: number } | null {
  const segs = loop.chain.segments;
  if (segs.length !== 2 || segs.some((s) => s.kind !== "ARC")) return null;
  const [a, b] = segs;
  if (a.kind !== "ARC" || b.kind !== "ARC") return null;
  if (Math.hypot(a.center.x - b.center.x, a.center.y - b.center.y) > 1e-6) return null;
  const r = Math.hypot(loop.chain.start.x - a.center.x, loop.chain.start.y - a.center.y);
  // Area of a circle of that radius, as a check the two arcs really close one.
  if (Math.abs(loop.area - Math.PI * r * r) > 1e-6) return null;
  return { x: a.center.x, y: a.center.y, diameter: r * 2 };
}

export function recognizeGeometry(
  segments: RawSegment[],
  opts: { label?: string; depth?: number | null } = {},
): GeometryRecognition {
  const { loops, refusals } = assembleLoops(segments);
  const { profile, interior } = splitProfile(loops);
  const warnings: string[] = [];

  if (!profile) {
    return { profile: null, profileSize: null, interior: [], refusals, warnings };
  }

  const e = extent(profile);
  const width = e.maxX - e.minX;
  const length = e.maxY - e.minY;

  if (profile.largestGapClosed > 0) {
    warnings.push(
      `The outline was closed across a gap of ${profile.largestGapClosed.toFixed(5)}". That is inside CAD rounding, and it is stated rather than hidden — if the drawing was meant to be exact, check it.`,
    );
  }

  /*
   * Depth is not in the drawing. A profile with no depth is a profile that is
   * not cut, and inventing one would put a Z on the part that nobody chose —
   * so it is left absent and the operator supplies it. The feature form
   * refuses the feature until they do.
   */
  const suggestion: FeatureSuggestion = {
    kind: "OUTSIDE_CONTOUR",
    label: opts.label ?? "Outside profile",
    functionalRole: "NONE",
    critical: false,
    parameters: {
      width: Number(width.toFixed(5)),
      length: Number(length.toFixed(5)),
      cornerRadius: 0,
      ...(opts.depth != null ? { depth: opts.depth } : {}),
    },
    chain: profile.chain.segments,
    chainStart: profile.chain.start,
    rationale:
      `Closed outline from the imported geometry: ${profile.chain.segments.length} segments, ` +
      `${width.toFixed(4)}" × ${length.toFixed(4)}" over ${profile.area.toFixed(4)} sq in. ` +
      `Depth is not in a 2D drawing and has not been guessed.`,
  };

  return {
    profile: suggestion,
    profileSize: { width, length, area: profile.area },
    interior: interior.map((l, i) => {
      const c = asCircle(l);
      const ex = extent(l);
      return c
        ? { label: `Circle ${i + 1}`, kind: "CIRCLE" as const, diameter: c.diameter, x: c.x, y: c.y, area: l.area }
        : {
            label: `Interior shape ${i + 1}`,
            kind: "SHAPE" as const,
            diameter: null,
            x: (ex.minX + ex.maxX) / 2,
            y: (ex.minY + ex.maxY) / 2,
            area: l.area,
          };
    }),
    refusals,
    warnings,
  };
}
