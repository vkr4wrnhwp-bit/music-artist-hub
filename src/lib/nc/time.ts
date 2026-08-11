import type { NCSegment } from "./parse";

/**
 * PATH TIMING — trapezoidal acceleration model. DEVELOPMENT ANALYSIS.
 *
 * Distance-over-feed timing assumes the machine changes velocity instantly,
 * which overstates savings on short-segment paths — the exact paths the
 * optimizer cares about. This model does the standard correction and nothing
 * more exotic:
 *
 * - Each motion segment runs a trapezoidal (or triangular, when the segment
 *   is too short to reach programmed speed) velocity profile at the machine's
 *   recorded axis acceleration.
 * - Velocity carries through a junction scaled by the direction change:
 *   colinear segments blend at full speed, a square corner stops. The factor
 *   is cos θ clamped to zero — a plain geometric junction rule, not a jerk
 *   model or a look-ahead simulation of any particular control.
 * - A forward pass caps each junction by what acceleration can reach from
 *   the previous one; a backward pass caps it by what deceleration needs for
 *   the next. The result is feasible by construction.
 *
 * The acceleration comes from the machine record and is REQUIRED: when the
 * machine has no recorded axisAccel this module is not called, times stay
 * distance-over-feed, and the analysis says so. A guessed acceleration would
 * make every figure look more precise while making it less true.
 *
 * Not modelled, stated plainly: jerk limits, per-axis acceleration
 * differences, control look-ahead depth, corner rounding (G64-style blending)
 * and servo lag. Real machines run slower than this model on dense 3D paths.
 */

export interface PathTiming {
  /** Seconds per segment, aligned with the input array. Dwells at face value. */
  seconds: number[];
  totalSeconds: number;
  /** Count of segments whose time was acceleration-limited (never reached programmed speed). */
  accelLimitedSegments: number;
  developmentAnalysis: true;
}

interface Motion {
  index: number;
  dist: number;
  /** Programmed velocity, in/s. */
  v: number;
  /** Unit direction. */
  ux: number;
  uy: number;
  uz: number;
}

/**
 * Times a parsed segment list under the trapezoidal model.
 *
 * @param accel axis acceleration, in/s² — from the machine record, never a default
 * @param rapidRate in/min, used for segments with no feed word
 */
export function timePath(segments: NCSegment[], accel: number, rapidRate: number): PathTiming {
  const seconds = new Array<number>(segments.length).fill(0);
  let accelLimited = 0;

  // Extract motions; dwells time themselves and break velocity continuity —
  // the machine genuinely stops there.
  const motions: Motion[] = [];
  const breaks = new Set<number>(); // motion indices that start from rest
  for (let i = 0; i < segments.length; i++) {
    const s = segments[i];
    if (s.kind === "DWELL") {
      seconds[i] = s.dwellSeconds ?? 0;
      breaks.add(motions.length); // next motion starts from a stop
      continue;
    }
    const dist = Math.hypot(s.x1 - s.x0, s.y1 - s.y0, s.z1 - s.z0);
    if (dist === 0) continue;
    const feedIpm = s.feed === null ? rapidRate : s.feed;
    motions.push({
      index: i,
      dist,
      v: Math.max(1, feedIpm) / 60,
      ux: (s.x1 - s.x0) / dist,
      uy: (s.y1 - s.y0) / dist,
      uz: (s.z1 - s.z0) / dist,
    });
  }
  if (motions.length === 0) {
    return { seconds, totalSeconds: sum(seconds), accelLimitedSegments: 0, developmentAnalysis: true };
  }

  // Junction velocities: junction[j] is the velocity entering motion j.
  // Start and end of the path are at rest, as is anything after a dwell or a
  // tool change (tool changes parse as separate motions with a gap in
  // continuity only when a dwell intervenes; a change of direction handles
  // the rest).
  const junction = new Array<number>(motions.length + 1).fill(0);
  for (let j = 1; j < motions.length; j++) {
    if (breaks.has(j)) { junction[j] = 0; continue; }
    const a = motions[j - 1];
    const b = motions[j];
    const cos = a.ux * b.ux + a.uy * b.uy + a.uz * b.uz;
    junction[j] = Math.min(a.v, b.v) * Math.max(0, cos);
  }

  // Forward pass: entry velocity limited by what accel can reach across the
  // previous segment. Backward pass: limited by what decel needs for the next.
  for (let j = 1; j <= motions.length; j++) {
    const m = motions[j - 1];
    junction[j] = Math.min(junction[j], Math.sqrt(junction[j - 1] ** 2 + 2 * accel * m.dist));
  }
  for (let j = motions.length - 1; j >= 0; j--) {
    const m = motions[j];
    junction[j] = Math.min(junction[j], Math.sqrt(junction[j + 1] ** 2 + 2 * accel * m.dist));
  }

  for (let j = 0; j < motions.length; j++) {
    const m = motions[j];
    const ve = junction[j];
    const vx = junction[j + 1];
    // Peak velocity reachable inside this segment given entry/exit and accel.
    const vPeak = Math.sqrt((2 * accel * m.dist + ve ** 2 + vx ** 2) / 2);
    const vUsed = Math.min(m.v, vPeak);
    if (vUsed < m.v - 1e-9) accelLimited++;
    const dAccel = (vUsed ** 2 - ve ** 2) / (2 * accel);
    const dDecel = (vUsed ** 2 - vx ** 2) / (2 * accel);
    const dCruise = Math.max(0, m.dist - dAccel - dDecel);
    seconds[m.index] =
      (vUsed - ve) / accel + (vUsed - vx) / accel + (vUsed > 0 ? dCruise / vUsed : 0);
  }

  return {
    seconds,
    totalSeconds: sum(seconds),
    accelLimitedSegments: accelLimited,
    developmentAnalysis: true,
  };
}

const sum = (a: number[]) => a.reduce((t, v) => t + v, 0);
