import type { Move } from "./types";
import { arcMove } from "./arc";

/**
 * A CLOSED 2D BOUNDARY, AS LINES AND ARCS.
 *
 * `contourToolpath` hard-coded a centred rectangle: `rectMoves(moves, 0, 0, w,
 * l, cr, …)`. An `OUTSIDE_CONTOUR` feature carried width, length and one corner
 * radius and nothing else, so every profiled part in the system was a centred
 * rectangle with four equal corners — and a part that is an L, or a D, or a
 * plate with a flat on one side, was cut as a rectangle with nothing saying so.
 *
 * This is the first piece of actual geometry the system holds, and it is worth
 * having before any kernel decision because 2D chains cover most of what a job
 * shop profiles.
 *
 * OFFSETTING, AND WHAT IT REFUSES
 *
 * The PROGRAM carries the boundary — cutter compensation means the control does
 * the offsetting — so the offset computed here is for the CUTTER CENTRE: the
 * path the simulator sweeps and the collision checks reason about.
 *
 * Most real profiles are tangent-continuous, which is what a fillet is for, and
 * a tangent joint's offsets meet by themselves with nothing to do. The two
 * cases that need work are a sharp CONVEX corner, where the offsets leave a gap
 * that the tool pivots across — filled with an arc of the tool radius about the
 * corner — and a sharp CONCAVE corner, where they overlap and would need
 * trimming.
 *
 * A sharp concave corner is refused, and that is engineering rather than
 * laziness: a round tool cannot produce a sharp inside corner. It leaves a
 * radius, and the drawing has to say so. The same rule that already refuses a
 * pocket whose corner radius is smaller than the cutter is what refuses an
 * inside arc here — the offset radius goes to zero or negative, and the message
 * says which corner and how big a tool would fit.
 */

export interface ChainPoint {
  x: number;
  y: number;
}

export type ChainSegment =
  | { kind: "LINE"; to: ChainPoint }
  | { kind: "ARC"; to: ChainPoint; center: ChainPoint; cw: boolean };

export interface Chain {
  start: ChainPoint;
  /** Closed: the last segment ends where `start` is. */
  segments: ChainSegment[];
  /**
   * Indices in `segments` that this offset INSERTED — the arcs the tool
   * pivots through at a sharp convex corner. They have no counterpart in the
   * boundary, and with cutter compensation active the control performs them
   * itself, so they are motion for the simulator and not blocks for the
   * program. Present only on an offset chain.
   *
   * Without this the caller has to guess which segments are pivots, and the
   * guess was wrong: every profile CANVAS posted came out with its straight
   * edges programmed as impossible arcs and a full circle cut into the last
   * corner.
   */
  pivots?: number[];
}

export interface ChainError {
  reason: string;
  recommendations: string[];
}

const EPS = 1e-7;

const sub = (a: ChainPoint, b: ChainPoint): ChainPoint => ({ x: a.x - b.x, y: a.y - b.y });
const add = (a: ChainPoint, b: ChainPoint): ChainPoint => ({ x: a.x + b.x, y: a.y + b.y });
const scale = (a: ChainPoint, k: number): ChainPoint => ({ x: a.x * k, y: a.y * k });
const norm = (a: ChainPoint): ChainPoint => {
  const m = Math.hypot(a.x, a.y);
  return m < EPS ? { x: 0, y: 0 } : { x: a.x / m, y: a.y / m };
};
/** Right of the direction of travel, which is the G42 side. */
const rightOf = (d: ChainPoint): ChainPoint => ({ x: d.y, y: -d.x });
const cross = (a: ChainPoint, b: ChainPoint) => a.x * b.y - a.y * b.x;
const near = (a: ChainPoint, b: ChainPoint) => Math.hypot(a.x - b.x, a.y - b.y) < 1e-6;

/** The rounded rectangle a width/length/corner-radius feature describes. */
export function rectangleChain(width: number, length: number, cornerRadius: number): Chain {
  const hx = width / 2;
  const hy = length / 2;
  const r = Math.min(cornerRadius, hx, hy);
  if (r <= EPS) {
    // Sharp corners. Still a valid chain; the offset fills each with an arc.
    return {
      start: { x: -hx, y: -hy },
      segments: [
        { kind: "LINE", to: { x: hx, y: -hy } },
        { kind: "LINE", to: { x: hx, y: hy } },
        { kind: "LINE", to: { x: -hx, y: hy } },
        { kind: "LINE", to: { x: -hx, y: -hy } },
      ],
    };
  }
  // Counter-clockwise from the left end of the bottom edge, tangent throughout.
  return {
    start: { x: -hx + r, y: -hy },
    segments: [
      { kind: "LINE", to: { x: hx - r, y: -hy } },
      { kind: "ARC", to: { x: hx, y: -hy + r }, center: { x: hx - r, y: -hy + r }, cw: false },
      { kind: "LINE", to: { x: hx, y: hy - r } },
      { kind: "ARC", to: { x: hx - r, y: hy }, center: { x: hx - r, y: hy - r }, cw: false },
      { kind: "LINE", to: { x: -hx + r, y: hy } },
      { kind: "ARC", to: { x: -hx, y: hy - r }, center: { x: -hx + r, y: hy - r }, cw: false },
      { kind: "LINE", to: { x: -hx, y: -hy + r } },
      { kind: "ARC", to: { x: -hx + r, y: -hy }, center: { x: -hx + r, y: -hy + r }, cw: false },
    ],
  };
}

/** Unit direction of travel entering `seg`'s end point, from `from`. */
function exitDirection(from: ChainPoint, seg: ChainSegment): ChainPoint {
  if (seg.kind === "LINE") return norm(sub(seg.to, from));
  const radial = sub(seg.to, seg.center);
  // Tangent at the end: rotate the radius −90° going clockwise, +90° going
  // counter-clockwise.
  return norm(seg.cw ? { x: radial.y, y: -radial.x } : { x: -radial.y, y: radial.x });
}

/** Unit direction of travel leaving `from` along `seg`. */
function entryDirection(from: ChainPoint, seg: ChainSegment): ChainPoint {
  if (seg.kind === "LINE") return norm(sub(seg.to, from));
  const radial = sub(from, seg.center);
  return norm(seg.cw ? { x: radial.y, y: -radial.x } : { x: -radial.y, y: radial.x });
}

/**
 * The cutter-centre chain, offset to the RIGHT of travel by `radius`.
 *
 * Right of travel is the G42 side, which for a counter-clockwise outside
 * profile puts the cutter outside the part.
 */
export function offsetChain(chain: Chain, radius: number): Chain | { error: ChainError } {
  if (radius <= EPS) return chain;

  interface Offset {
    from: ChainPoint;
    seg: ChainSegment;
    /** The original vertex this segment starts at, for the pivot arc. */
    vertex: ChainPoint;
    entry: ChainPoint;
    exit: ChainPoint;
  }

  const offsets: Offset[] = [];
  let cursor = chain.start;

  for (const seg of chain.segments) {
    const entry = entryDirection(cursor, seg);
    const exit = exitDirection(cursor, seg);

    if (seg.kind === "LINE") {
      const n = scale(rightOf(entry), radius);
      offsets.push({ from: add(cursor, n), seg: { kind: "LINE", to: add(seg.to, n) }, vertex: cursor, entry, exit });
    } else {
      const R = Math.hypot(cursor.x - seg.center.x, cursor.y - seg.center.y);
      // Travelling clockwise the centre is to the right, so offsetting right
      // shrinks the arc. Counter-clockwise it grows.
      const R2 = seg.cw ? R - radius : R + radius;
      if (R2 <= EPS) {
        return {
          error: {
            reason: `An inside radius of ${R.toFixed(4)}" on this profile is smaller than the ⌀${(radius * 2).toFixed(4)}" cutter, so the tool cannot get into it.`,
            recommendations: [
              `Use a tool ⌀${(R * 2).toFixed(4)}" or smaller`,
              `Open the radius to at least R${radius.toFixed(4)}`,
            ],
          },
        };
      }
      const k = R2 / R;
      offsets.push({
        from: add(seg.center, scale(sub(cursor, seg.center), k)),
        seg: { kind: "ARC", to: add(seg.center, scale(sub(seg.to, seg.center), k)), center: seg.center, cw: seg.cw },
        vertex: cursor,
        entry,
        exit,
      });
    }
    cursor = seg.to;
  }

  /* ---- Join the offsets ---- */

  const out: ChainSegment[] = [];
  const pivots: number[] = [];
  for (let i = 0; i < offsets.length; i++) {
    const cur = offsets[i];
    const next = offsets[(i + 1) % offsets.length];
    out.push(cur.seg);

    const endPoint = cur.seg.to;
    if (near(endPoint, next.from)) continue; // tangent: they already meet

    const turn = cross(cur.exit, next.entry);
    if (turn < -EPS) {
      // Concave: the two offsets overlap and would have to be trimmed against
      // each other. A round tool cannot produce a sharp inside corner anyway —
      // it leaves a radius, and the drawing has to say so.
      return {
        error: {
          reason: `This profile has a sharp inside corner at (${next.vertex.x.toFixed(3)}, ${next.vertex.y.toFixed(3)}). A ⌀${(radius * 2).toFixed(4)}" cutter leaves an R${radius.toFixed(4)} radius there and cannot make it sharp.`,
          recommendations: [
            `Add a corner radius of at least R${radius.toFixed(4)} to the drawing`,
            "Use a smaller tool and state the radius it will leave",
            "Relieve the corner",
          ],
        },
      };
    }

    // Convex: the tool pivots around the corner. Same turn direction as the
    // corner itself, which is counter-clockwise on an outside profile.
    pivots.push(out.length);
    out.push({ kind: "ARC", to: next.from, center: next.vertex, cw: false });
  }

  return { start: offsets[0].from, segments: out, pivots };
}

/** Cutting moves along a chain at one depth. */
export function chainMoves(chain: Chain, z: number, feed: number, type: Move["type"] = "CUT"): Move[] {
  const moves: Move[] = [];
  let cursor = chain.start;
  for (const seg of chain.segments) {
    if (seg.kind === "LINE") {
      moves.push({ type, x: seg.to.x, y: seg.to.y, z, feed });
    } else {
      moves.push(arcMove(type, cursor, seg.center.x, seg.center.y, { ...seg.to, z }, seg.cw, feed));
    }
    cursor = seg.to;
  }
  return moves;
}

/** Perimeter, arcs measured along the arc. */
export function chainLength(chain: Chain): number {
  let total = 0;
  let cursor = chain.start;
  for (const seg of chain.segments) {
    if (seg.kind === "LINE") {
      total += Math.hypot(seg.to.x - cursor.x, seg.to.y - cursor.y);
    } else {
      const R = Math.hypot(cursor.x - seg.center.x, cursor.y - seg.center.y);
      const a0 = Math.atan2(cursor.y - seg.center.y, cursor.x - seg.center.x);
      const a1 = Math.atan2(seg.to.y - seg.center.y, seg.to.x - seg.center.x);
      let sweep = a1 - a0;
      if (seg.cw) {
        while (sweep > 0) sweep -= 2 * Math.PI;
      } else {
        while (sweep < 0) sweep += 2 * Math.PI;
      }
      total += Math.abs(sweep) * R;
    }
    cursor = seg.to;
  }
  return total;
}
