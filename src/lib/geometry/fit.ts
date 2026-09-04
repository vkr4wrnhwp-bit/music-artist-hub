import type { Chain, ChainPoint, ChainSegment } from "@/lib/engines/cam/chain";

/**
 * CHORDS BACK INTO THE LINES AND ARCS SOMEBODY DREW.
 *
 * A slice through a scanned mesh is one chord per triangle: a 4" edge arrives
 * as forty short segments, and a R0.5 fillet as a dozen more. Every one of them
 * is real — they are where the scanner actually found the surface — and cutting
 * them directly gives a program of hundreds of blocks and a wall a hand can
 * feel. The shape somebody designed is a handful of lines and arcs, and this is
 * where it is recovered.
 *
 * THE TOLERANCE IS THE WHOLE ARGUMENT
 *
 * Fitting is deciding that points which are not on a line are close enough to
 * be treated as though they were. That distance is a number a person has to
 * choose, and it is not free: fit loose and the part comes out to the fit
 * rather than to the drawing; fit tight and a scan's own noise becomes fifty
 * segments of geometry.
 *
 * So the tolerance is an input, it is stated on the proposal, and it is never
 * smaller than the scanner's own uncertainty — a fit tighter than the
 * measurement is a claim about the part the measurement cannot support. The
 * caller passes what its metrology record says; nothing here invents one.
 *
 * WHAT IT DOES NOT DO
 *
 * It does not decide that a nearly-square corner was meant to be square, or
 * that a 0.4986 radius was meant to be 0.5. Those are the designer's
 * intentions and this has no access to them — it reports what it fitted and
 * what the worst deviation was, and a human reads it against the print. A
 * scan of a used part carries that part's wear, and rounding it to a nominal
 * would launder wear into design intent.
 */

const EPS = 1e-9;

export interface FitOptions {
  /**
   * How far a point may sit from the fitted line or arc, inches. Never smaller
   * than the scanner's uncertainty — see the note above.
   */
  tolerance: number;
  /** Below this, a run of chords is kept as a line rather than fitted an arc. */
  minArcRadius?: number;
}

export interface FitResult {
  chain: Chain;
  /** How many chords went in and how many segments came out. */
  from: number;
  to: number;
  /** Worst distance between an original point and the fitted geometry. */
  maxDeviation: number;
  arcs: number;
  lines: number;
  notes: string[];
}

const dist = (a: ChainPoint, b: ChainPoint) => Math.hypot(a.x - b.x, a.y - b.y);

/** Perpendicular distance from `p` to the infinite line through a and b. */
function toLine(p: ChainPoint, a: ChainPoint, b: ChainPoint): number {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const m = Math.hypot(dx, dy);
  if (m < EPS) return dist(p, a);
  return Math.abs((p.x - a.x) * dy - (p.y - a.y) * dx) / m;
}

/**
 * The circle through three points. Null when they are collinear — which is not
 * a failure, it is the answer that this run is a line.
 */
function circleThrough(a: ChainPoint, b: ChainPoint, c: ChainPoint): { c: ChainPoint; r: number } | null {
  const d = 2 * (a.x * (b.y - c.y) + b.x * (c.y - a.y) + c.x * (a.y - b.y));
  if (Math.abs(d) < 1e-12) return null;
  const ua = a.x * a.x + a.y * a.y;
  const ub = b.x * b.x + b.y * b.y;
  const uc = c.x * c.x + c.y * c.y;
  const cx = (ua * (b.y - c.y) + ub * (c.y - a.y) + uc * (a.y - b.y)) / d;
  const cy = (ua * (c.x - b.x) + ub * (a.x - c.x) + uc * (b.x - a.x)) / d;
  const centre = { x: cx, y: cy };
  return { c: centre, r: dist(centre, a) };
}

/** Which way a run of points turns about a centre. */
function turnsClockwise(pts: ChainPoint[], centre: ChainPoint): boolean {
  let total = 0;
  for (let i = 1; i < pts.length; i++) {
    const a0 = Math.atan2(pts[i - 1].y - centre.y, pts[i - 1].x - centre.x);
    const a1 = Math.atan2(pts[i].y - centre.y, pts[i].x - centre.x);
    let d = a1 - a0;
    while (d > Math.PI) d -= Math.PI * 2;
    while (d < -Math.PI) d += Math.PI * 2;
    total += d;
  }
  return total < 0;
}

/**
 * Fit a closed chain of chords.
 *
 * Greedy and longest-first: at each point, take the longest run that a single
 * line covers within tolerance, and the longest a single arc covers, and keep
 * whichever reaches further. Longest-first matters — fitting the shortest
 * acceptable piece would leave a straight edge chopped into arbitrary
 * fragments at the join between two tolerable fits.
 */
export function fitChain(chain: Chain, opts: FitOptions): FitResult {
  const tol = opts.tolerance;
  const minArcR = opts.minArcRadius ?? tol * 4;
  const notes: string[] = [];

  // The closed ring of points the chords pass through.
  const pts: ChainPoint[] = [chain.start, ...chain.segments.map((s) => s.to)];
  // A closed chain ends where it started; drop the duplicate for the walk.
  if (pts.length > 1 && dist(pts[0], pts[pts.length - 1]) < 1e-7) pts.pop();
  const n = pts.length;

  if (n < 3) {
    return { chain, from: chain.segments.length, to: chain.segments.length, maxDeviation: 0, arcs: 0, lines: 0, notes: ["Too few points to fit."] };
  }

  const at = (i: number) => pts[i % n];
  const out: ChainSegment[] = [];
  let maxDev = 0;
  let arcs = 0;
  let lines = 0;

  let start = 0;
  let consumed = 0;

  while (consumed < n) {
    /* ---- The longest line from here ---- */
    let lineEnd = start + 1;
    let lineDev = 0;
    for (let e = start + 2; e - start <= n - consumed && e - start < n; e++) {
      let worst = 0;
      for (let k = start + 1; k < e; k++) worst = Math.max(worst, toLine(at(k), at(start), at(e)));
      if (worst > tol) break;
      lineEnd = e;
      lineDev = worst;
    }

    /* ---- The longest arc from here ---- */
    let arcEnd = start;
    let arcDev = 0;
    let arcFit: { c: ChainPoint; r: number } | null = null;
    for (let e = start + 3; e - start <= n - consumed && e - start < n; e++) {
      const mid = at(start + Math.floor((e - start) / 2));
      const cir = circleThrough(at(start), mid, at(e));
      if (!cir || cir.r < minArcR) break;
      let worst = 0;
      for (let k = start + 1; k < e; k++) worst = Math.max(worst, Math.abs(dist(at(k), cir.c) - cir.r));
      if (worst > tol) break;
      arcEnd = e;
      arcDev = worst;
      arcFit = cir;
    }

    /*
     * An arc only wins when it covers MORE than the line. A straight edge is
     * also a very large circle, and a tie handed to the arc would put a
     * meaningless R400 arc where a machinist expects G1 — which reads as a
     * mistake in the program even though the motion is the same.
     */
    if (arcFit && arcEnd > lineEnd) {
      const run: ChainPoint[] = [];
      for (let k = start; k <= arcEnd; k++) run.push(at(k));
      out.push({ kind: "ARC", to: at(arcEnd), center: arcFit.c, cw: turnsClockwise(run, arcFit.c) });
      maxDev = Math.max(maxDev, arcDev);
      arcs++;
      consumed += arcEnd - start;
      start = arcEnd;
    } else {
      out.push({ kind: "LINE", to: at(lineEnd) });
      maxDev = Math.max(maxDev, lineDev);
      lines++;
      consumed += lineEnd - start;
      start = lineEnd;
    }
  }

  /*
   * The walk stops when it has consumed every point, which lands the last
   * segment back on the start by construction. Saying so rather than assuming
   * it: a chain that does not close is one the contour engine refuses, and it
   * would refuse it a long way from here.
   */
  const last = out[out.length - 1];
  if (last && dist(last.to, pts[0]) > 1e-7) {
    out.push({ kind: "LINE", to: pts[0] });
    lines++;
  }

  let chainStart = pts[0];

  /*
   * THE SEAM.
   *
   * The walk starts wherever the chord list happens to start, which on a
   * scanned part is almost always the middle of an edge — so the first run and
   * the last run are two halves of the same straight edge, and a 4-sided plate
   * fits to five segments with a corner in the middle of one side. That corner
   * is not in the part. It is a break in the program where a machinist would
   * see a continuous wall, and the offset puts a pivot arc at it.
   *
   * So the two ends are examined and joined when they are one piece of
   * geometry: collinear lines, or arcs about the same centre going the same
   * way. Anything else is a real corner and is left alone.
   */
  if (out.length >= 3) {
    const first = out[0];
    const tail = out[out.length - 1];
    const tailFrom = out.length >= 2 ? out[out.length - 2].to : pts[0];

    const collinear =
      first.kind === "LINE" && tail.kind === "LINE" && toLine(pts[0], tailFrom, first.to) <= tol;
    const sameArc =
      first.kind === "ARC" &&
      tail.kind === "ARC" &&
      first.cw === tail.cw &&
      dist(first.center, tail.center) <= tol &&
      Math.abs(dist(first.to, first.center) - dist(tailFrom, tail.center)) <= tol;

    if (collinear || sameArc) {
      out.pop();
      chainStart = tailFrom;
      if (collinear) lines--;
      else arcs--;
      notes.push("The two ends met in the middle of one edge and were joined — a break there is a corner the part does not have.");
    }
  }

  /*
   * TANGENCY, WHICH THE FIT BREAKS BY A HAIR AND THE PART DOES NOT HAVE.
   *
   * A fillet meets its edges tangentially by construction. Line and arc are
   * fitted independently here, so their shared point lands a thousandth off
   * the true tangent point and the joint comes out very slightly concave —
   * and `offsetChain` then refuses the whole profile as a sharp inside corner
   * a cutter cannot make. It is right to refuse a real one. This is not one:
   * it is 0.06 degrees of fitting noise at a joint the part has smooth.
   *
   * The joint is moved to where the two are exactly tangent: the point on the
   * arc that the perpendicular from its centre to the line reaches.
   *
   * WHAT MAKES THAT SAFE is that the move runs ALONG the line. A greedy fit
   * always eats the first part of a tangent arc — near the tangent point the
   * arc is inside tolerance of the line, so the line keeps extending — and the
   * handover lands a couple of hundredths past where the fillet really starts.
   * Sliding the handover back does not move the line, which is the same line,
   * or the arc, which is the same arc. It changes only which of the two covers
   * the overlap. So the test is not how far the joint moves; it is whether the
   * line is genuinely tangent to that circle, and whether the tangent point
   * lies on the run the line already covers. A line that misses the circle, or
   * crosses it, is a real corner and is left alone.
   *
   * Fixing the geometry rather than loosening the check: `offsetChain` must
   * keep refusing real inside corners, because a drawn profile can have one.
   */
  let snapped = 0;
  let worstSnap = 0;
  const pointOf = (i: number) => (i === 0 ? chainStart : out[i - 1].to);
  for (let i = 0; i < out.length; i++) {
    const cur = out[i];
    const next = out[(i + 1) % out.length];
    // The joint between them is `cur.to`.
    const arc = cur.kind === "ARC" ? cur : next.kind === "ARC" ? next : null;
    const line = cur.kind === "LINE" ? cur : next.kind === "LINE" ? next : null;
    if (!arc || !line || cur.kind === next.kind) continue;

    /*
     * The tangent point is SOLVED, not iterated toward.
     *
     * Taking the perpendicular foot of the centre onto the line moves the
     * joint, which changes the line's direction, which moves the foot — a
     * fixed point that one pass does not reach, and the residual is still
     * enough for `offsetChain` to read the joint as concave and refuse the
     * profile.
     *
     * The line's FAR end is fixed. From an external point P, the tangent to a
     * circle (C, r) touches at T where the triangle P-C-T is right-angled at
     * T — so the angle at C is arccos(r / |PC|), and T is exact in one step.
     * The line P→T is then tangent by construction.
     */
    const far = line === cur ? pointOf(i) : line.to;
    const toFar = { x: far.x - arc.center.x, y: far.y - arc.center.y };
    const d = Math.hypot(toFar.x, toFar.y);
    const r = dist(arc.center, arc === cur ? pointOf(i) : arc.to);
    if (!(d > r + EPS)) continue;

    const alpha = Math.acos(Math.min(1, r / d));
    const base = Math.atan2(toFar.y, toFar.x);
    const candidates = [base + alpha, base - alpha].map((a) => ({
      x: arc.center.x + r * Math.cos(a),
      y: arc.center.y + r * Math.sin(a),
    }));
    const tangentPoint = dist(candidates[0], cur.to) <= dist(candidates[1], cur.to) ? candidates[0] : candidates[1];

    /*
     * The move runs ALONG the line, which is what makes it safe: it does not
     * move the line or the arc, only which of the two covers the overlap a
     * greedy fit leaves. So the test is whether the handover still lands on
     * the stretch the line covered, not how far it travelled. A tangent point
     * off the end of that run means these two do not meet tangentially at all,
     * and that is a real corner — left alone, for `offsetChain` to rule on.
     */
    const runLen = dist(far, cur.to);
    if (dist(far, tangentPoint) > runLen + tol) continue;
    if (dist(cur.to, tangentPoint) < 1e-12) continue;

    worstSnap = Math.max(worstSnap, dist(cur.to, tangentPoint));
    cur.to = tangentPoint;
    /*
     * The last segment's end IS the chain's start. Moving one without the
     * other opens the loop, and an open boundary is refused a long way from
     * here with a message about a gap nobody drew.
     */
    if (i === out.length - 1) chainStart = tangentPoint;
    snapped++;
  }

  notes.push(
    `${chain.segments.length} chords fitted to ${out.length} segments within ${tol.toFixed(4)}". Worst deviation ${maxDev.toFixed(5)}".`,
  );
  if (snapped > 0) {
    notes.push(
      `${snapped} line-to-arc ${snapped === 1 ? "joint was" : "joints were"} moved onto exact tangency, the largest by ${worstSnap.toFixed(5)}". A fillet meets its edges tangentially and the fit does not, so without this the profile reads as having inside corners the part does not have.`,
    );
  }
  notes.push(
    "Nothing was rounded to a nominal. A 0.4986 radius is reported as 0.4986 — a scan of a used part carries that part's wear, and rounding it would launder wear into design intent.",
  );

  return { chain: { start: chainStart, segments: out }, from: chain.segments.length, to: out.length, maxDeviation: maxDev, arcs, lines, notes };
}
