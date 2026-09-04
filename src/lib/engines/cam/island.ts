import type { Feature } from "@/lib/domain/features";

/**
 * WHAT A POCKET WOULD MACHINE AWAY.
 *
 * A pocket toolpath sweeps its whole area. Put a boss in the middle of one and
 * the rings run straight over it: on a 3.000 × 2.000 pocket with a ⌀0.750
 * locating boss at its centre, 66 of the 188 moves were inside the boss, and
 * the helical entry started at the boss's own centre. The boss was machined
 * away, the program reported real motion, and nothing said a word.
 *
 * The coverage gate caught the wrong half of it. A BOSS with no operation reads
 * as "not cut" — and a machinist looking at a feature they want LEFT STANDING
 * could reasonably record it as not made by this program, which clears the gate
 * and leaves the program still cutting it away.
 *
 * WHAT IS AND IS NOT IMPLEMENTED
 *
 * Machining a pocket around an island is island avoidance: offsetting a region
 * bounded by an outer loop and inner loops, and clipping every ring against
 * every island. That is a real piece of computational geometry and this engine
 * does not have it.
 *
 * One case needs none of it. A circular island CONCENTRIC in a circular pocket
 * is an annulus, and concentric rings between the two radii are exactly right
 * with nothing to clip — a sealing land, a relief around a spigot, a counterbored
 * face. That case is cut. Every other arrangement is refused by name.
 */

export interface Footprint {
  kind: "RECT" | "CIRCLE";
  centerX: number;
  centerY: number;
  /** RECT only. */
  width?: number;
  length?: number;
  /** CIRCLE only. */
  diameter?: number;
}

/** Features that have to survive the cut. */
export function standing(features: Feature[]): Feature[] {
  return features.filter((f) => f.kind === "BOSS");
}

export function footprintOf(f: Feature): Footprint | null {
  if (f.kind === "BOSS" || f.kind === "CIRC_POCKET" || f.kind === "BORE") {
    return { kind: "CIRCLE", centerX: f.centerX, centerY: f.centerY, diameter: f.diameter };
  }
  if (f.kind === "RECT_POCKET") {
    return { kind: "RECT", centerX: f.centerX, centerY: f.centerY, width: f.width, length: f.length };
  }
  return null;
}

/** Whether two footprints share any area at all. */
export function overlaps(a: Footprint, b: Footprint): boolean {
  if (a.kind === "CIRCLE" && b.kind === "CIRCLE") {
    return Math.hypot(a.centerX - b.centerX, a.centerY - b.centerY) < (a.diameter! + b.diameter!) / 2;
  }
  if (a.kind === "RECT" && b.kind === "RECT") {
    return (
      Math.abs(a.centerX - b.centerX) < (a.width! + b.width!) / 2 &&
      Math.abs(a.centerY - b.centerY) < (a.length! + b.length!) / 2
    );
  }
  const rect = a.kind === "RECT" ? a : b;
  const circ = a.kind === "RECT" ? b : a;
  // Nearest point of the rectangle to the circle's centre. Corner radii make
  // the rectangle slightly smaller than this, which errs toward reporting an
  // overlap — the safe direction for a check that stops a cut.
  const nx = Math.max(rect.centerX - rect.width! / 2, Math.min(circ.centerX, rect.centerX + rect.width! / 2));
  const ny = Math.max(rect.centerY - rect.length! / 2, Math.min(circ.centerY, rect.centerY + rect.length! / 2));
  return Math.hypot(circ.centerX - nx, circ.centerY - ny) < circ.diameter! / 2;
}

/** Concentric to within a machining thou; past that it is not an annulus. */
const CONCENTRIC_TOLERANCE = 0.001;

export interface Annulus {
  centerX: number;
  centerY: number;
  outerDiameter: number;
  innerDiameter: number;
}

/**
 * The one arrangement that needs no clipping: a circular island concentric in
 * a circular pocket. Anything else — off centre, or either one not round —
 * returns null and is refused by the caller.
 */
export function annulusOf(pocket: Feature, island: Feature): Annulus | null {
  const p = footprintOf(pocket);
  const i = footprintOf(island);
  if (!p || !i || p.kind !== "CIRCLE" || i.kind !== "CIRCLE") return null;
  if (Math.hypot(p.centerX - i.centerX, p.centerY - i.centerY) > CONCENTRIC_TOLERANCE) return null;
  if (i.diameter! >= p.diameter!) return null;
  return { centerX: p.centerX, centerY: p.centerY, outerDiameter: p.diameter!, innerDiameter: i.diameter! };
}

/** Everything standing inside this pocket's own footprint. */
export function islandsIn(pocket: Feature, features: Feature[]): Feature[] {
  const p = footprintOf(pocket);
  if (!p) return [];
  return standing(features).filter((f) => {
    const i = footprintOf(f);
    return i !== null && overlaps(p, i);
  });
}
