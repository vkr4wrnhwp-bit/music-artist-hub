import { z } from "zod";
import type { Chain, ChainPoint, ChainSegment } from "@/lib/engines/cam/chain";

/**
 * UNORDERED SEGMENTS INTO A CLOSED, ORDERED, CORRECTLY-WOUND LOOP.
 *
 * `Feature.chain` is read by the contour engine and the chamfer engine, typed
 * in the domain — and was written by nothing. Every profile CANVAS posted was
 * `rectangleChain(width, length, cornerRadius)`: a rounded rectangle from three
 * numbers. A part that is an L, or a D, or a plate with a flat on one side was
 * cut as a rectangle and nothing said so.
 *
 * This is the shared middle. A DXF gives lines and arcs in file order, which is
 * whatever the CAD wrote; a sketch drawn in CANVAS gives them in click order,
 * which is whatever the hand did. Neither is a toolpath boundary until the ends
 * are joined into one closed loop and the loop is wound the right way. Doing
 * that once means the drawn part and the imported part are the same part, and
 * both get the same refusals.
 *
 * WINDING IS NOT COSMETIC
 *
 * `contourToolpath` compensates `side: "RIGHT"` — G42 — and `rectangleChain` is
 * counter-clockwise. Cut counter-clockwise with the tool on the right of
 * travel, the tool is OUTSIDE the boundary, which is what profiling a part
 * means. Feed a clockwise loop through unchanged and the same G42 puts the
 * cutter on the inside: it climbs straight into the part and takes the profile
 * off undersize by a full tool diameter, with a program that reads correctly
 * on the screen. A DXF carries no intent about direction and CAD writes both,
 * so orientation is established here rather than trusted.
 *
 * WHAT IT REFUSES, BY NAME
 *
 * An open end, a branch, a gap wider than CAD noise. A drawing that does not
 * close is a drawing with a mistake in it, and the mistake has coordinates —
 * so the message carries them. Nothing is nudged shut silently: the gap that
 * WAS closed is reported too, because a 0.0005" gap a CAD wrote by accident is
 * worth a machinist knowing about before the part is cut.
 */

export interface RawLine {
  kind: "LINE";
  a: ChainPoint;
  b: ChainPoint;
}

export interface RawArc {
  kind: "ARC";
  a: ChainPoint;
  b: ChainPoint;
  center: ChainPoint;
  /** True when travelling a→b goes clockwise about the centre. */
  cw: boolean;
}

export type RawSegment = RawLine | RawArc;

/**
 * The same shape, checked at a trust boundary.
 *
 * A DXF is read from a file this code wrote the parser for; a drawing arrives
 * as JSON from a browser, which is a place values come from rather than a
 * place they are computed. A coordinate that is not a finite number is not a
 * place on the part, and it reaches the offset arithmetic as a silent NaN.
 */
const pointSchema = z.object({ x: z.number().finite(), y: z.number().finite() });

export const rawSegmentSchema: z.ZodType<RawSegment> = z.discriminatedUnion("kind", [
  z.object({ kind: z.literal("LINE"), a: pointSchema, b: pointSchema }),
  z.object({ kind: z.literal("ARC"), a: pointSchema, b: pointSchema, center: pointSchema, cw: z.boolean() }),
]);

export interface LoopRefusal {
  reason: string;
  recommendations: string[];
}

export interface AssembledLoop {
  chain: Chain;
  /** Enclosed area, square inches. Positive; winding is normalised. */
  area: number;
  /** The widest endpoint gap this loop had to close, inches. */
  largestGapClosed: number;
  /** True when the source was a single closed entity, e.g. a DXF CIRCLE. */
  fromClosedEntity: boolean;
}

export interface LoopAssembly {
  loops: AssembledLoop[];
  /** Segments that could not be joined into any closed loop, and why. */
  refusals: LoopRefusal[];
}

/*
 * CAD writes endpoints that agree to eight or nine places and sometimes to
 * four. A tenth of a thou is wider than any rounding a CAD does and narrower
 * than any gap a person draws on purpose, so it separates noise from mistake —
 * and whatever is closed inside it is still reported.
 */
export const JOIN_TOLERANCE = 0.0001;

const near = (a: ChainPoint, b: ChainPoint, tol: number) => Math.hypot(a.x - b.x, a.y - b.y) <= tol;
const dist = (a: ChainPoint, b: ChainPoint) => Math.hypot(a.x - b.x, a.y - b.y);
const fmt = (p: ChainPoint) => `(${p.x.toFixed(4)}, ${p.y.toFixed(4)})`;

/** Length of a raw segment, for dropping the degenerate ones. */
function segLength(s: RawSegment): number {
  if (s.kind === "LINE") return dist(s.a, s.b);
  const r = dist(s.center, s.a);
  const a0 = Math.atan2(s.a.y - s.center.y, s.a.x - s.center.x);
  const a1 = Math.atan2(s.b.y - s.center.y, s.b.x - s.center.x);
  let sweep = s.cw ? a0 - a1 : a1 - a0;
  while (sweep <= 0) sweep += Math.PI * 2;
  return r * sweep;
}

/**
 * Twice the signed area a segment contributes, by the shoelace rule with an
 * exact correction for the circular cap an arc adds over its chord.
 *
 * Positive total is counter-clockwise. This is what decides whether the loop
 * gets reversed, so it is computed rather than inferred from the order the
 * segments happened to arrive in.
 */
function signedAreaContribution(from: ChainPoint, seg: RawSegment): number {
  const chord = from.x * seg.b.y - seg.b.x * from.y;
  if (seg.kind === "LINE") return chord;

  const r = dist(seg.center, from);
  const a0 = Math.atan2(from.y - seg.center.y, from.x - seg.center.x);
  const a1 = Math.atan2(seg.b.y - seg.center.y, seg.b.x - seg.center.x);
  let sweep = seg.cw ? a0 - a1 : a1 - a0;
  while (sweep <= 0) sweep += Math.PI * 2;
  // Circular segment between the arc and its chord: (r²/2)(θ − sin θ), signed
  // by travel direction. Twice it, to match the shoelace convention above.
  const cap = r * r * (sweep - Math.sin(sweep));
  return chord + (seg.cw ? -cap : cap);
}

/** The same segment walked the other way. */
function reverseSegment(s: RawSegment): RawSegment {
  return s.kind === "LINE"
    ? { kind: "LINE", a: s.b, b: s.a }
    : { kind: "ARC", a: s.b, b: s.a, center: s.center, cw: !s.cw };
}

function toChainSegment(s: RawSegment): ChainSegment {
  return s.kind === "LINE"
    ? { kind: "LINE", to: s.b }
    : { kind: "ARC", to: s.b, center: s.center, cw: s.cw };
}

/**
 * Assemble every closed loop the segments form.
 *
 * A DXF of a plate is the profile and the holes in one file, so finding more
 * than one loop is the normal case rather than an error. What is an error is a
 * segment that belongs to no closed loop at all, and that is named with its
 * coordinates instead of being dropped.
 */
export function assembleLoops(segments: RawSegment[], tol = JOIN_TOLERANCE): LoopAssembly {
  const refusals: LoopRefusal[] = [];

  // A zero-length line is a duplicated point, which every CAD emits sooner or
  // later. It is not geometry and it is not a mistake worth reporting.
  const live = segments.filter((s) => segLength(s) > tol);

  const used = new Array<boolean>(live.length).fill(false);
  const loops: AssembledLoop[] = [];

  for (let seed = 0; seed < live.length; seed++) {
    if (used[seed]) continue;

    const walk: RawSegment[] = [live[seed]];
    used[seed] = true;
    const start = live[seed].a;
    let head = live[seed].b;
    let largestGap = 0;
    let closed = near(head, start, tol);
    if (closed) largestGap = dist(head, start);

    while (!closed) {
      /*
       * Exactly one unused end may fall inside the window. Two is a duplicated
       * edge, a centreline left in the export, or a genuine branch — and which
       * way the boundary goes from there is not something to guess, so it is
       * refused rather than resolved by whichever came first in file order.
       */
      let best = -1;
      let bestFlip = false;
      let bestGap = Infinity;
      let contenders = 0;
      for (let i = 0; i < live.length; i++) {
        if (used[i]) continue;
        const da = dist(head, live[i].a);
        const db = dist(head, live[i].b);
        const g = Math.min(da, db);
        if (g > tol) continue;
        contenders++;
        bestGap = g;
        best = i;
        bestFlip = db < da;
      }

      if (contenders > 1) {
        refusals.push({
          reason: `More than one edge meets at ${fmt(head)}. A boundary that branches is not a single closed profile, and which way it goes is not something to guess.`,
          recommendations: [
            "Check for a duplicated edge on top of another in the drawing",
            "Delete construction lines and centrelines before exporting",
            "Export only the profile layer",
          ],
        });
        break;
      }

      if (best < 0) {
        const gap = live
          .map((s, i) => (used[i] ? Infinity : Math.min(dist(head, s.a), dist(head, s.b))))
          .reduce((m, v) => Math.min(m, v), Infinity);
        refusals.push({
          reason:
            `The boundary stops at ${fmt(head)} and nothing continues from there` +
            (Number.isFinite(gap) ? ` — the nearest other end is ${gap.toFixed(4)}" away.` : "."),
          recommendations: [
            `Close the gap in CAD, or join the edges within ${tol}"`,
            "A profile has to be a closed loop before it can be cut as one",
          ],
        });
        break;
      }

      used[best] = true;
      largestGap = Math.max(largestGap, bestGap);
      walk.push(bestFlip ? reverseSegment(live[best]) : live[best]);
      head = walk[walk.length - 1].b;
      closed = near(head, start, tol);
      if (closed) largestGap = Math.max(largestGap, dist(head, start));
    }

    if (!closed) continue;

    /*
     * Winding, established rather than trusted. Cut counter-clockwise with the
     * tool on the right, the tool is outside the boundary — which is what
     * profiling a part means. A clockwise loop through the same G42 climbs
     * into the part.
     */
    let twiceArea = 0;
    let from = start;
    for (const s of walk) {
      twiceArea += signedAreaContribution(from, s);
      from = s.b;
    }
    const ordered = twiceArea >= 0 ? walk : walk.slice().reverse().map(reverseSegment);

    loops.push({
      chain: { start: ordered[0].a, segments: ordered.map(toChainSegment) },
      area: Math.abs(twiceArea) / 2,
      largestGapClosed: largestGap,
      fromClosedEntity: walk.length === 1,
    });
  }

  return { loops, refusals };
}

/**
 * The outer profile and everything inside it.
 *
 * The largest loop by enclosed area is the part's outside; the rest are holes,
 * pockets and windows in it. Nothing here decides what those interiors ARE — a
 * circle could be a drilled hole, a bored hole or a circular pocket, and that
 * is a manufacturing question a drawing does not answer. They are handed back
 * named and counted so a person can say.
 */
export function splitProfile(loops: AssembledLoop[]): {
  profile: AssembledLoop | null;
  interior: AssembledLoop[];
} {
  if (loops.length === 0) return { profile: null, interior: [] };
  const sorted = loops.slice().sort((a, b) => b.area - a.area);
  return { profile: sorted[0], interior: sorted.slice(1) };
}
