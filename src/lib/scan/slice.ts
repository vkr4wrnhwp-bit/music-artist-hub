import type { Mesh, Triangle } from "./mesh";
import type { MeshUnits } from "./inspect";
import type { RawSegment } from "@/lib/geometry/loop";

/**
 * A CROSS-SECTION THROUGH A SCANNED PART.
 *
 * Reverse engineering stopped before geometry, and said so: a scan produced an
 * envelope, mesh integrity and planar faces, with bores, radii and threads
 * marked NOT ATTEMPTED. That is honest and it left the outside profile — the
 * one thing a 3-axis program most needs — coming from nowhere.
 *
 * A part a 3-axis mill makes is 2.5D. Its profile IS the cross-section of the
 * mesh at any Z between the top and the bottom face, and slicing a triangle
 * mesh with a plane is exact arithmetic: every triangle the plane crosses
 * contributes exactly one segment, between the two points where the plane cuts
 * its edges. No fitting, no inference, no vision model.
 *
 * WHAT COMES OUT IS NOT YET A PROFILE
 *
 * It is a polygon of hundreds of tiny chords — one per triangle — which is a
 * faceted approximation of the real edge and not the edge. Cutting it directly
 * would give a program of hundreds of blocks and a wall you can feel. Turning
 * chords back into the lines and arcs somebody drew is `geometry/fit.ts`, and
 * it is a separate step because it involves a tolerance somebody has to choose.
 *
 * WHERE TO SLICE
 *
 * Not at the very top or bottom: the plane would land in the face itself, where
 * triangles lie IN the plane rather than crossing it, and a coplanar triangle
 * has no single crossing segment. Mid-height is the default and it is stated,
 * because a part with a step in it has a different outline at different heights
 * and which one you want is a question about the part.
 */

const MM_PER_INCH = 25.4;

/**
 * A triangle lying in the plane contributes no crossing segment. Its edges are
 * picked up by its neighbours, which do cross — so it is skipped rather than
 * counted as a failure.
 */
function crossSegment(t: Triangle, z: number, scale: number): RawSegment | null {
  const vs = [t.a, t.b, t.c];
  const hits: { x: number; y: number }[] = [];

  for (let i = 0; i < 3; i++) {
    const p = vs[i];
    const q = vs[(i + 1) % 3];
    const dp = p[2] - z;
    const dq = q[2] - z;

    // Both above or both below: this edge does not cross.
    if ((dp > 0 && dq > 0) || (dp < 0 && dq < 0)) continue;
    if (dp === 0 && dq === 0) continue; // edge lies in the plane

    if (dp === 0) {
      hits.push({ x: p[0] * scale, y: p[1] * scale });
      continue;
    }
    if (dq === 0) continue; // picked up as `dp === 0` on the next edge

    const f = dp / (dp - dq);
    hits.push({ x: (p[0] + (q[0] - p[0]) * f) * scale, y: (p[1] + (q[1] - p[1]) * f) * scale });
  }

  if (hits.length < 2) return null;
  const a = hits[0];
  const b = hits[1];
  if (Math.hypot(b.x - a.x, b.y - a.y) < 1e-9) return null;
  return { kind: "LINE", a, b };
}

export interface SliceResult {
  /** Unordered chords, inches. Feed to assembleLoops. */
  segments: RawSegment[];
  /** The Z the slice was taken at, inches, in the mesh's own frame. */
  z: number;
  /** How many triangles the plane crossed. */
  crossed: number;
  /** Triangles lying in the plane, which contribute no crossing segment. */
  coplanar: number;
  assumptions: string[];
}

/**
 * Slice at a height, or at mid-height when none is given.
 *
 * `z` is in INCHES in the mesh's own coordinates, matching the envelope the
 * inspector reports — so an operator reading "Z from 0.000 to 0.750" can ask
 * for 0.375 and get what they expect.
 */
export function sliceMesh(mesh: Mesh, units: MeshUnits, atZ?: number): SliceResult {
  const scale = units === "MM" ? 1 / MM_PER_INCH : 1;

  let minZ = Infinity;
  let maxZ = -Infinity;
  for (const t of mesh.triangles) {
    for (const v of [t.a, t.b, t.c]) {
      if (v[2] < minZ) minZ = v[2];
      if (v[2] > maxZ) maxZ = v[2];
    }
  }

  const zIn = atZ ?? ((minZ + maxZ) / 2) * scale;
  const zRaw = zIn / scale;

  const segments: RawSegment[] = [];
  let coplanar = 0;
  for (const t of mesh.triangles) {
    const ds = [t.a[2] - zRaw, t.b[2] - zRaw, t.c[2] - zRaw];
    if (ds.every((d) => d === 0)) {
      coplanar++;
      continue;
    }
    const seg = crossSegment(t, zRaw, scale);
    if (seg) segments.push(seg);
  }

  const assumptions = [
    atZ === undefined
      ? `Sliced at mid-height, Z ${zIn.toFixed(4)}" of ${(minZ * scale).toFixed(4)} to ${(maxZ * scale).toFixed(4)}. A part with a step has a different outline at a different height, so this is a choice and not a fact about the part.`
      : `Sliced at Z ${zIn.toFixed(4)}" as asked.`,
    "The cross-section is a chord per triangle — a faceted approximation of the edge, not the edge. Lines and arcs are fitted to it separately, to a stated tolerance.",
  ];
  if (coplanar > 0) {
    assumptions.push(
      `${coplanar} triangles lie in the slice plane and contribute no crossing segment. Slice away from a face if the outline comes back broken.`,
    );
  }

  return { segments, z: zIn, crossed: segments.length, coplanar, assumptions };
}
