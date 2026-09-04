import type { Move } from "./types";

/**
 * ARCS.
 *
 * Every circular path in this engine used to be walked in straight chords —
 * `max(24, radius * 60)` of them around a circle, eight around a corner. The
 * `ARC` move type existed in the vocabulary and nothing ever emitted one.
 *
 * What that costs, in the units a machinist works in: the tool-centre path of a
 * Ø1.000" bore was a thirty-sided polygon, and at the middle of each chord the
 * cutter sat one sagitta closer to the axis than nominal —
 *
 *     sagitta = r · (1 − cos(π / segments))
 *
 * which is 0.0027" on that bore. Five times the whole band on a ±0.0005"
 * bearing seat, and a FORM error rather than a size error, so no offset dials
 * it out. The part measures round across the flats on a two-point mic and is
 * not round. It also made programs ten to fifty times longer than they need to
 * be, which is what makes a control's look-ahead stumble on short blocks.
 *
 * THE CONVENTION, STATED ONCE
 *
 * An ARC move ends at (x, y, z). `i` and `j` are the offsets from the arc's
 * START point — the previous move's endpoint — to the arc centre. That is the
 * incremental I/J convention every Fanuc-family control uses, so the post
 * writes them out with no conversion and no chance of a sign error in
 * translation. `cw` is the direction in the XY plane seen from +Z looking down,
 * which is what G2 means. A different Z on the end point makes it helical.
 *
 * FULL CIRCLES ARE EMITTED AS TWO HALVES, ON PURPOSE
 *
 * A single block with I/J and no endpoint means "full circle" on Haas and
 * Fanuc, and means something else or nothing at all elsewhere. Two 180° arcs
 * are unambiguous on every control in the world and cost one extra block. The
 * engine never produces a zero-sweep arc for that reason; `arcGeometry` still
 * reads one as a full turn, because that is what a control would do with it.
 */

/** Chord tolerance used when an arc has to be flattened, inches. */
export const CHORD_TOLERANCE = 0.0005;

export interface ArcGeometry {
  centerX: number;
  centerY: number;
  radius: number;
  startAngle: number;
  endAngle: number;
  /** Signed sweep, radians. Negative clockwise. */
  sweep: number;
  /** True length including the helical rise. */
  length: number;
}

/** Builds an ARC move from its start point, its centre and its end point. */
export function arcMove(
  type: Move["type"],
  from: { x: number; y: number },
  centerX: number,
  centerY: number,
  to: { x: number; y: number; z: number },
  cw: boolean,
  feed: number,
): Move {
  return { type, x: to.x, y: to.y, z: to.z, feed, i: centerX - from.x, j: centerY - from.y, cw };
}

export function isArc(m: Move): boolean {
  return m.i !== undefined && m.j !== undefined;
}

export function arcGeometry(prev: Move, m: Move): ArcGeometry | null {
  if (m.i === undefined || m.j === undefined) return null;
  const centerX = prev.x + m.i;
  const centerY = prev.y + m.j;
  const radius = Math.hypot(m.i, m.j);
  if (radius <= 1e-9) return null;

  const startAngle = Math.atan2(prev.y - centerY, prev.x - centerX);
  const endAngle = Math.atan2(m.y - centerY, m.x - centerX);

  let sweep = endAngle - startAngle;
  if (m.cw) {
    // Clockwise sweeps are negative. Normalise into (−2π, 0].
    while (sweep > 0) sweep -= 2 * Math.PI;
    while (sweep <= -2 * Math.PI) sweep += 2 * Math.PI;
  } else {
    while (sweep < 0) sweep += 2 * Math.PI;
    while (sweep >= 2 * Math.PI) sweep -= 2 * Math.PI;
  }
  // Start and end coincident: a control reads that as a full circle, so this
  // does too. The engine never emits one — see the header.
  if (Math.abs(sweep) < 1e-9) sweep = m.cw ? -2 * Math.PI : 2 * Math.PI;

  const planar = Math.abs(sweep) * radius;
  const rise = m.z - prev.z;
  return {
    centerX,
    centerY,
    radius,
    startAngle,
    endAngle,
    sweep,
    length: rise === 0 ? planar : Math.hypot(planar, rise),
  };
}

/**
 * Segments needed to hold an arc within `tolerance` of true.
 *
 * Inverted from the sagitta relation above: with n segments over a sweep θ the
 * worst deviation is r(1 − cos(θ/2n)), so n is the smallest integer for which
 * that falls under the tolerance. A tolerance no chord count can satisfy —
 * an arc smaller than the tolerance itself — bottoms out at one segment, which
 * is the straight line the arc already is at that scale.
 */
export function arcSegments(radius: number, sweep: number, tolerance = CHORD_TOLERANCE): number {
  const abs = Math.abs(sweep);
  if (radius <= tolerance) return 1;
  const halfAngle = Math.acos(Math.max(-1, 1 - tolerance / radius));
  if (halfAngle <= 0) return 1;
  return Math.max(1, Math.ceil(abs / (2 * halfAngle)));
}

/**
 * Straight-line moves that follow the same path.
 *
 * Every consumer that has to walk the path as segments — the simulator's height
 * field, the viewport's line geometry, a post whose dialect cannot express the
 * arc — calls this rather than writing its own tessellation. Three copies of
 * this arithmetic would be three chances to disagree with the program about
 * where the tool actually went, and the simulator disagreeing with the program
 * is the failure this whole layer exists to prevent.
 *
 * Non-arc moves pass through untouched, and the move `type` is carried onto
 * every segment so a caller colouring by type still sees a lead-in as a lead-in.
 */
export function flattenArcs(moves: Move[], tolerance = CHORD_TOLERANCE): Move[] {
  const out: Move[] = [];
  for (let idx = 0; idx < moves.length; idx++) {
    const m = moves[idx];
    const prev = idx > 0 ? moves[idx - 1] : null;
    const geo = prev ? arcGeometry(prev, m) : null;
    if (!geo || !prev) {
      out.push(m);
      continue;
    }
    const n = arcSegments(geo.radius, geo.sweep, tolerance);
    for (let k = 1; k <= n; k++) {
      const a = geo.startAngle + (geo.sweep * k) / n;
      out.push({
        type: m.type,
        x: geo.centerX + geo.radius * Math.cos(a),
        y: geo.centerY + geo.radius * Math.sin(a),
        z: prev.z + ((m.z - prev.z) * k) / n,
        feed: m.feed,
      });
    }
    // The last segment lands on the arc's stated endpoint exactly, rather than
    // on the cosine of an angle that is the same point to within rounding.
    // A path that does not close is a path the simulator and the control
    // disagree about.
    const last = out[out.length - 1];
    last.x = m.x;
    last.y = m.y;
    last.z = m.z;
  }
  return out;
}

/** Path length of a move list, arcs measured along the arc. */
export function pathLength(moves: Move[]): { total: number; cutting: number } {
  let total = 0;
  let cutting = 0;
  for (let i = 1; i < moves.length; i++) {
    const a = moves[i - 1];
    const b = moves[i];
    const geo = arcGeometry(a, b);
    const d = geo ? geo.length : Math.hypot(b.x - a.x, b.y - a.y, b.z - a.z);
    if (d === 0) continue;
    total += d;
    if (b.feed !== null) cutting += d;
  }
  return { total, cutting };
}
