import type { NCSegment } from "./parse";

/**
 * WHICH WAY THE CUT PUSHES THE PART
 *
 * This check was declared unbuildable and listed in `checksSkipped`: "the
 * check needs a cutting-force vector and a jaw axis, and CANVAS records
 * neither." Half of that is no longer true — `Setup.jawAxis` records which
 * axis the jaws close on, added for the fixture-collision work — and the other
 * half turns out not to be needed for the question a machinist actually asks.
 *
 * The question is not "how many pounds". `holding-margin.ts` answers that, and
 * says DEVELOPMENT ANALYSIS while it does. The question here is WHICH WAY, and
 * that is in the program itself: every cutting segment has a feed direction,
 * exactly, from its own coordinates.
 *
 * What the direction decides, in a vise:
 *
 *   - A cut pushing the part ALONG the jaw axis drives it into a jaw. The jaw
 *     body reacts that directly — it is the direction a vise is for.
 *   - A cut pushing ACROSS the jaw axis slides the part along the jaw faces.
 *     Nothing reacts that but friction, unless there is a positive stop. This
 *     is how a part walks out of a vise while every clamping number looks fine.
 *
 * Stated limits, because this is a direction check and not a force solve:
 *
 *   - The force direction is taken as the FEED direction. A real cutting force
 *     has a radial component that rotates with engagement and reverses between
 *     climb and conventional; none of that is modelled here.
 *   - It says which way the load pushes, not whether the grip holds. Those are
 *     different questions and the second one has its own engine.
 */

export type LoadDirection = "ALONG_JAWS" | "ACROSS_JAWS" | "VERTICAL";

/**
 * How much of a segment's feed is across the jaws rather than into them.
 *
 * Returned as a fraction of the segment's own XY length so segments can be
 * summed by distance — a long slot across the jaws matters more than a short
 * one, and counting segments would say they matter the same.
 */
export function classifySegment(
  seg: Pick<NCSegment, "x0" | "y0" | "x1" | "y1" | "z0" | "z1" | "feed">,
  jawAxis: "X" | "Y",
): { direction: LoadDirection; xyLength: number; acrossFraction: number } | null {
  // A rapid cuts nothing, so it pushes nothing.
  if (seg.feed === null) return null;

  const dx = seg.x1 - seg.x0;
  const dy = seg.y1 - seg.y0;
  const xyLength = Math.hypot(dx, dy);

  // A plunge has no XY direction to classify. It pushes the part down into
  // the parallels, which is the one direction a vise never struggles with.
  if (xyLength < 1e-9) return { direction: "VERTICAL", xyLength: 0, acrossFraction: 0 };

  const along = Math.abs(jawAxis === "X" ? dx : dy);
  const across = Math.abs(jawAxis === "X" ? dy : dx);
  const acrossFraction = across / xyLength;

  return {
    direction: across > along ? "ACROSS_JAWS" : "ALONG_JAWS",
    xyLength,
    acrossFraction,
  };
}

export interface LoadDirectionSummary {
  /** Total cutting distance in XY, inches. */
  cuttingLength: number;
  /** Of that, how much is pushed across the jaw faces rather than into a jaw. */
  acrossLength: number;
  /** acrossLength / cuttingLength, or null when nothing cuts in XY. */
  acrossShare: number | null;
  /** The single worst segment, for somewhere to point. */
  worst: { line: number; acrossFraction: number; length: number } | null;
}

export function summariseLoadDirection(
  segments: Pick<NCSegment, "x0" | "y0" | "x1" | "y1" | "z0" | "z1" | "feed" | "line">[],
  jawAxis: "X" | "Y",
): LoadDirectionSummary {
  let cuttingLength = 0;
  let acrossLength = 0;
  let worst: LoadDirectionSummary["worst"] = null;

  for (const seg of segments) {
    const c = classifySegment(seg, jawAxis);
    if (!c || c.xyLength === 0) continue;
    cuttingLength += c.xyLength;
    // Weighted by how across it is, not counted as all-or-nothing: a cut at
    // 30° pushes partly into the jaw and partly along it, and rounding that
    // to one or the other overstates whichever way it rounded.
    acrossLength += c.xyLength * c.acrossFraction;

    const weight = c.xyLength * c.acrossFraction;
    if (!worst || weight > worst.length * worst.acrossFraction) {
      worst = { line: seg.line, acrossFraction: c.acrossFraction, length: c.xyLength };
    }
  }

  return {
    cuttingLength,
    acrossLength,
    acrossShare: cuttingLength > 0 ? acrossLength / cuttingLength : null,
    worst,
  };
}

/**
 * The share above which the direction is worth raising.
 *
 * Not a safety threshold and not derived from a force: it is the point at
 * which most of the cutting is relying on friction rather than on a jaw, which
 * is a thing to look at rather than a thing that is wrong. A positive stop
 * changes the answer entirely, so the caller checks that first.
 */
export const ACROSS_SHARE_THRESHOLD = 0.5;
