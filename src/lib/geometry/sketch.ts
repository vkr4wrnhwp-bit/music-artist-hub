import type { RawSegment } from "./loop";

/**
 * TYPED AND CLICKED POINTS INTO LINES AND ARCS.
 *
 * The drawing surface's geometry, out of the component so it can be tested.
 * A corner with a radius is a fillet tangent to both edges, and getting it
 * wrong is wrong geometry on the part — not a rendering bug.
 *
 * This is a DRAWING, not a sketch solver: no constraints, no dimensions
 * driving geometry. A machinist who needs constraint solving needs CAD, and
 * CANVAS reads its DXF.
 */

export interface SketchPoint {
  x: number;
  y: number;
  /** Radius of the corner AT this point. 0 is sharp. */
  r: number;
}

export type SketchResult = { segments: RawSegment[]; error: null } | { segments: []; error: string };

/**
 * A fillet at a corner starts a distance `r / tan(θ/2)` back along the incoming
 * edge and ends the same distance along the outgoing one, with its centre on
 * the bisector at `r / sin(θ/2)`. θ is the angle between the two edges as seen
 * from the corner.
 *
 * A radius bigger than an edge can carry is REFUSED rather than clipped. A
 * clipped fillet is a different shape from the one that was drawn, and it
 * would arrive looking deliberate.
 */
export function sketchToSegments(pts: SketchPoint[]): SketchResult {
  if (pts.length < 3) return { segments: [], error: "A closed outline needs at least three points." };

  const n = pts.length;
  const ends: {
    in: { x: number; y: number };
    out: { x: number; y: number };
    arc: null | { c: { x: number; y: number }; cw: boolean };
  }[] = [];

  for (let i = 0; i < n; i++) {
    const prev = pts[(i - 1 + n) % n];
    const cur = pts[i];
    const next = pts[(i + 1) % n];

    if (!(cur.r > 0)) {
      // Coordinates only. A sketch point carries the corner radius that
      // produced it; a chain segment is geometry and must not, or the radius
      // rides into the stored boundary as a stray field on every point.
      ends.push({ in: { x: cur.x, y: cur.y }, out: { x: cur.x, y: cur.y }, arc: null });
      continue;
    }

    const v1 = { x: prev.x - cur.x, y: prev.y - cur.y };
    const v2 = { x: next.x - cur.x, y: next.y - cur.y };
    const m1 = Math.hypot(v1.x, v1.y);
    const m2 = Math.hypot(v2.x, v2.y);
    if (m1 < 1e-9 || m2 < 1e-9) {
      return { segments: [], error: `Two points at the same place near (${cur.x}, ${cur.y}).` };
    }

    const u1 = { x: v1.x / m1, y: v1.y / m1 };
    const u2 = { x: v2.x / m2, y: v2.y / m2 };
    const theta = Math.acos(Math.max(-1, Math.min(1, u1.x * u2.x + u1.y * u2.y)));
    if (theta < 1e-6 || Math.abs(theta - Math.PI) < 1e-6) {
      return { segments: [], error: `The corner at (${cur.x}, ${cur.y}) is straight, so a radius has nothing to round.` };
    }

    const back = cur.r / Math.tan(theta / 2);
    if (back > m1 - 1e-9 || back > m2 - 1e-9) {
      return {
        segments: [],
        error:
          `R${cur.r} at (${cur.x}, ${cur.y}) needs ${back.toFixed(4)}" of edge either side and the edges are ` +
          `${m1.toFixed(4)}" and ${m2.toFixed(4)}". Use a smaller radius or move the point.`,
      };
    }

    const bis = { x: u1.x + u2.x, y: u1.y + u2.y };
    const bm = Math.hypot(bis.x, bis.y);
    const d = cur.r / Math.sin(theta / 2);
    ends.push({
      in: { x: cur.x + u1.x * back, y: cur.y + u1.y * back },
      out: { x: cur.x + u2.x * back, y: cur.y + u2.y * back },
      arc: {
        c: { x: cur.x + (bis.x / bm) * d, y: cur.y + (bis.y / bm) * d },
        // Travelling in along u1 reversed and out along u2: the turn's sense is
        // the sign of that cross product.
        cw: -u1.x * u2.y + u1.y * u2.x < 0,
      },
    });
  }

  const segments: RawSegment[] = [];
  for (let i = 0; i < n; i++) {
    const a = ends[i];
    const b = ends[(i + 1) % n];
    if (a.arc) segments.push({ kind: "ARC", a: a.in, b: a.out, center: a.arc.c, cw: a.arc.cw });
    // A zero-length edge between two adjacent fillets is dropped by the loop
    // assembler, so it is emitted rather than special-cased here.
    segments.push({ kind: "LINE", a: a.out, b: b.in });
  }

  return { segments, error: null };
}
