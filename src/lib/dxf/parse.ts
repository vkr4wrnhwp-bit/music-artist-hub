import type { RawSegment } from "@/lib/geometry/loop";

/**
 * DXF → LINES AND ARCS.
 *
 * A DXF is pairs of lines: a group code, then its value. Everything is nested
 * by SECTION/ENDSEC and ENTITY type, and the codes mean different things per
 * entity — 10/20 is a start point on a LINE, a centre on an ARC and a CIRCLE,
 * and a vertex on an LWPOLYLINE where it repeats. That is the whole format for
 * the 2D entities a profile is made of, which is why DXF is the practical way
 * to get real geometry out of any CAD a job shop owns.
 *
 * WHAT THIS READS, AND WHAT IT SAYS IT DOES NOT
 *
 * LINE, ARC, CIRCLE, LWPOLYLINE and POLYLINE, in model space. Those five carry
 * essentially every 2D profile a job shop cuts.
 *
 * SPLINE and ELLIPSE are NOT approximated. A spline flattened to chords is a
 * profile that no longer matches the drawing, cut to a tolerance nobody chose
 * and nobody was told about — and it would arrive looking like real geometry.
 * They are counted and named instead, so the answer is "CANVAS does not read
 * splines yet" rather than a part that is quietly the wrong shape.
 *
 * UNITS ARE READ, NEVER ASSUMED
 *
 * $INSUNITS says what the numbers mean. A file that does not say is not
 * assumed to be inches — a millimetre drawing read as inches is a part
 * 25.4 times too big, and it would pass every check in this system because
 * every number in it is self-consistent. The importer asks.
 */

export interface DxfEntitySummary {
  type: string;
  count: number;
}

export interface DxfRead {
  segments: RawSegment[];
  /** From $INSUNITS. Null when the file does not say — then nothing is assumed. */
  units: "IN" | "MM" | null;
  /** Entity types present that this reader does not turn into geometry. */
  ignored: DxfEntitySummary[];
  warnings: string[];
}

interface Pair {
  code: number;
  value: string;
}

/**
 * Group-code pairs. A DXF is line-oriented: an integer code, then its value on
 * the next line, both possibly padded with whitespace. Binary DXF is a
 * different format and is refused by the caller rather than misread here.
 */
function readPairs(text: string): Pair[] {
  const lines = text.split(/\r\n|\r|\n/);
  const pairs: Pair[] = [];
  for (let i = 0; i + 1 < lines.length; i += 2) {
    const code = Number(lines[i].trim());
    if (!Number.isFinite(code)) continue;
    pairs.push({ code, value: lines[i + 1].trim() });
  }
  return pairs;
}

/** $INSUNITS: 1 is inches, 4 millimetres. The others are not shop units. */
const INSUNITS: Record<string, "IN" | "MM"> = { "1": "IN", "4": "MM" };

/**
 * An LWPOLYLINE vertex carries a BULGE — the tangent of a quarter of the arc's
 * included angle, signed clockwise-negative. It is how a DXF stores a rounded
 * corner inside a polyline, and dropping it turns every fillet on the part into
 * a sharp corner the cutter cannot make.
 */
function bulgeToArc(a: { x: number; y: number }, b: { x: number; y: number }, bulge: number): RawSegment {
  const theta = 4 * Math.atan(bulge);
  const cw = bulge < 0;
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const chord = Math.hypot(dx, dy);
  const r = Math.abs(chord / (2 * Math.sin(theta / 2)));
  // Centre is off the chord's midpoint along its perpendicular; which side is
  // decided by the bulge's sign and whether the arc is major or minor.
  const h = Math.sqrt(Math.max(0, r * r - (chord / 2) ** 2));
  const sign = Math.abs(theta) > Math.PI ? -1 : 1;
  const ux = -dy / chord;
  const uy = dx / chord;
  const s = (cw ? -1 : 1) * sign;
  return {
    kind: "ARC",
    a,
    b,
    center: { x: (a.x + b.x) / 2 + ux * h * s, y: (a.y + b.y) / 2 + uy * h * s },
    cw,
  };
}

function arcFromCenter(cx: number, cy: number, r: number, startDeg: number, endDeg: number): RawSegment {
  const s = (startDeg * Math.PI) / 180;
  const e = (endDeg * Math.PI) / 180;
  return {
    kind: "ARC",
    a: { x: cx + r * Math.cos(s), y: cy + r * Math.sin(s) },
    b: { x: cx + r * Math.cos(e), y: cy + r * Math.sin(e) },
    center: { x: cx, y: cy },
    // A DXF ARC always runs counter-clockwise from start angle to end angle.
    cw: false,
  };
}

/** Every entity type this reader turns into geometry. */
const READS = new Set(["LINE", "ARC", "CIRCLE", "LWPOLYLINE", "POLYLINE", "VERTEX", "SEQEND"]);
/** Types worth naming when present, because their absence changes the part. */
const GEOMETRIC = new Set(["SPLINE", "ELLIPSE", "SOLID", "3DFACE", "MESH", "REGION", "BODY", "HELIX"]);

export function readDxf(text: string): DxfRead {
  const warnings: string[] = [];
  const segments: RawSegment[] = [];
  const ignoredCounts = new Map<string, number>();

  if (!/^\s*0\s*[\r\n]+\s*SECTION/m.test(text) && !/ENTITIES/.test(text)) {
    return {
      segments: [],
      units: null,
      ignored: [],
      warnings: [
        "This does not read as a DXF. A binary or DWG file has to be saved as an ASCII DXF before CANVAS can read it.",
      ],
    };
  }

  const pairs = readPairs(text);

  // $INSUNITS lives in HEADER as a 9/$INSUNITS pair followed by a 70 value.
  let units: "IN" | "MM" | null = null;
  for (let i = 0; i < pairs.length - 1; i++) {
    if (pairs[i].code === 9 && pairs[i].value === "$INSUNITS") {
      const v = pairs.find((p, j) => j > i && p.code === 70);
      if (v) units = INSUNITS[v.value] ?? null;
      break;
    }
  }

  // Only model space. Paper-space entities are the drawing's border and title
  // block, which are not the part.
  let inEntities = false;
  let current: { type: string; codes: Map<number, string[]> } | null = null;
  const entities: { type: string; codes: Map<number, string[]> }[] = [];

  const flush = () => {
    if (current) entities.push(current);
    current = null;
  };

  for (const p of pairs) {
    if (p.code === 2 && (p.value === "ENTITIES" || p.value === "BLOCKS")) {
      inEntities = p.value === "ENTITIES";
      continue;
    }
    if (p.code === 0 && p.value === "ENDSEC") {
      flush();
      inEntities = false;
      continue;
    }
    if (!inEntities) continue;
    if (p.code === 0) {
      flush();
      current = { type: p.value, codes: new Map() };
      continue;
    }
    if (!current) continue;
    const list = current.codes.get(p.code) ?? [];
    list.push(p.value);
    current.codes.set(p.code, list);
  }
  flush();

  const nums = (e: { codes: Map<number, string[]> }, code: number) =>
    (e.codes.get(code) ?? []).map(Number).filter((n) => Number.isFinite(n));
  const num = (e: { codes: Map<number, string[]> }, code: number, fallback = 0) => nums(e, code)[0] ?? fallback;

  // A POLYLINE's points arrive as separate VERTEX entities until SEQEND.
  let polylineOpen: { closed: boolean; pts: { x: number; y: number; bulge: number }[] } | null = null;

  const emitPolyline = (pts: { x: number; y: number; bulge: number }[], closed: boolean) => {
    for (let i = 0; i + 1 < pts.length; i++) {
      const a = { x: pts[i].x, y: pts[i].y };
      const b = { x: pts[i + 1].x, y: pts[i + 1].y };
      segments.push(pts[i].bulge ? bulgeToArc(a, b, pts[i].bulge) : { kind: "LINE", a, b });
    }
    if (closed && pts.length > 1) {
      const last = pts[pts.length - 1];
      const first = pts[0];
      const a = { x: last.x, y: last.y };
      const b = { x: first.x, y: first.y };
      segments.push(last.bulge ? bulgeToArc(a, b, last.bulge) : { kind: "LINE", a, b });
    }
  };

  for (const e of entities) {
    // 67 = 1 means paper space: the border and the title block, not the part.
    if (num(e, 67, 0) === 1) continue;

    switch (e.type) {
      case "LINE":
        segments.push({
          kind: "LINE",
          a: { x: num(e, 10), y: num(e, 20) },
          b: { x: num(e, 11), y: num(e, 21) },
        });
        break;

      case "ARC":
        segments.push(arcFromCenter(num(e, 10), num(e, 20), num(e, 40), num(e, 50), num(e, 51)));
        break;

      case "CIRCLE": {
        // Two half-arcs, because a chain segment cannot sweep a full turn: its
        // start and end point would be the same and the direction ambiguous.
        const cx = num(e, 10);
        const cy = num(e, 20);
        const r = num(e, 40);
        segments.push(arcFromCenter(cx, cy, r, 0, 180), arcFromCenter(cx, cy, r, 180, 360));
        break;
      }

      case "LWPOLYLINE": {
        const xs = nums(e, 10);
        const ys = nums(e, 20);
        /*
         * Bulges are sparse: a 42 appears only for a vertex that carries one,
         * so they cannot be zipped by index against the vertex list. Without
         * the per-vertex association every fillet in the polyline would land
         * on the wrong corner — which is worse than dropping them, because it
         * is wrong rather than absent. When the counts do not line up, the
         * bulges are refused by name.
         */
        const bulges = nums(e, 42);
        const pts = xs.map((x, i) => ({ x, y: ys[i] ?? 0, bulge: 0 }));
        if (bulges.length > 0 && bulges.length !== pts.length) {
          warnings.push(
            `An LWPOLYLINE carries ${bulges.length} bulge values for ${pts.length} vertices, so which corner each rounds cannot be established. Its arcs were not imported — explode the polyline in CAD and export again.`,
          );
        } else if (bulges.length === pts.length) {
          pts.forEach((p, i) => (p.bulge = bulges[i]));
        }
        emitPolyline(pts, (num(e, 70, 0) & 1) === 1);
        break;
      }

      case "POLYLINE":
        polylineOpen = { closed: (num(e, 70, 0) & 1) === 1, pts: [] };
        break;

      case "VERTEX":
        if (polylineOpen) polylineOpen.pts.push({ x: num(e, 10), y: num(e, 20), bulge: num(e, 42, 0) });
        break;

      case "SEQEND":
        if (polylineOpen) {
          emitPolyline(polylineOpen.pts, polylineOpen.closed);
          polylineOpen = null;
        }
        break;

      default:
        if (!READS.has(e.type)) ignoredCounts.set(e.type, (ignoredCounts.get(e.type) ?? 0) + 1);
    }
  }

  const ignored = [...ignoredCounts.entries()].map(([type, count]) => ({ type, count }));

  /*
   * A curve this reader does not understand is a fact about the reader, said
   * out loud. Flattening a spline to chords would produce a profile that no
   * longer matches the drawing, to a tolerance nobody chose — and it would
   * arrive looking like real geometry.
   */
  for (const { type, count } of ignored) {
    if (GEOMETRIC.has(type)) {
      warnings.push(
        `${count} ${type} ${count === 1 ? "entity is" : "entities are"} in this drawing and CANVAS does not read ${type} geometry. ` +
          (type === "SPLINE" || type === "ELLIPSE"
            ? "Approximating it with chords would cut a shape that is not the drawing, so it is left out rather than guessed."
            : "It is left out rather than guessed."),
      );
    }
  }

  return { segments, units, ignored, warnings };
}
