import type { Mesh, Triangle } from "./mesh";

/**
 * WHAT A SCAN IS ALLOWED TO CLAIM.
 *
 * A triangle mesh is exact about whatever the scanner resolved. That is the
 * whole of it. The envelope is arithmetic over vertices and is trustworthy
 * to the scanner's uncertainty. Everything past that gets progressively less
 * defensible, and this module stops where the defensibility does:
 *
 *   DERIVED       envelope, mesh integrity, planar faces by normal grouping
 *   NOT ATTEMPTED bores, radii, threads, tolerances, datums, functional
 *                 roles — all of which need surface fitting and human
 *                 judgement that pretending to do here would be faking
 *
 * Nothing in this file infers a nominal. A scan says "there is a round hole
 * about this big"; it never says "this is a 40 mm bearing bore". That is the
 * reverse-engineering flow's job, from an instrument, with a human ruling on
 * it — which is why a scan import produces PROPOSALS into that flow rather
 * than a finished model.
 */

/** STL carries no units. The importer declares them; nothing guesses. */
export type MeshUnits = "IN" | "MM";

export interface Envelope {
  minX: number; maxX: number;
  minY: number; maxY: number;
  minZ: number; maxZ: number;
  /** Extents, inches. */
  x: number; y: number; z: number;
}

export interface PlanarFace {
  /** Unit normal the group shares. */
  normal: [number, number, number];
  triangles: number;
  /** Total area, in², so a speck of noise is not called a face. */
  area: number;
}

export interface MeshIntegrity {
  /**
   * A closed surface: every edge shared by exactly two triangles. An open
   * mesh has holes, and a hole means the envelope may be smaller than the
   * part — the scanner did not see all of it.
   */
  watertight: boolean;
  openEdges: number;
  degenerateTriangles: number;
}

export interface ScanInspection {
  units: MeshUnits;
  triangles: number;
  envelope: Envelope;
  integrity: MeshIntegrity;
  /** Large flat regions, biggest first. Candidate datum faces for a human. */
  planarFaces: PlanarFace[];
  /** Stated, in the output, every time. */
  notAttempted: string[];
  assumptions: string[];
  missingInputs: string[];
  developmentAnalysis: true;
}

const MM_PER_INCH = 25.4;

/** Coplanar grouping tolerance: about 1 degree. Stated, not tuned to taste. */
const NORMAL_TOLERANCE_DEG = 1;

/**
 * A planar region smaller than this is scanner noise or a chamfer facet, not
 * a face a machinist would datum from. Stated so the number is arguable.
 */
const MIN_FACE_AREA_IN2 = 0.05;

export function inspectMesh(mesh: Mesh, units: MeshUnits): ScanInspection {
  const scale = units === "MM" ? 1 / MM_PER_INCH : 1;
  const tris = mesh.triangles;

  /* ---- Envelope: arithmetic over every vertex ---- */
  let minX = Infinity, minY = Infinity, minZ = Infinity;
  let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
  for (const t of tris) {
    for (const v of [t.a, t.b, t.c]) {
      if (v[0] < minX) minX = v[0];
      if (v[0] > maxX) maxX = v[0];
      if (v[1] < minY) minY = v[1];
      if (v[1] > maxY) maxY = v[1];
      if (v[2] < minZ) minZ = v[2];
      if (v[2] > maxZ) maxZ = v[2];
    }
  }
  const s = (v: number) => Number((v * scale).toFixed(4));
  const envelope: Envelope = {
    minX: s(minX), maxX: s(maxX), minY: s(minY), maxY: s(maxY), minZ: s(minZ), maxZ: s(maxZ),
    x: s(maxX - minX), y: s(maxY - minY), z: s(maxZ - minZ),
  };

  /* ---- Integrity ---- */
  const integrity = checkIntegrity(tris);

  /* ---- Planar faces ---- */
  const planarFaces = groupPlanarFaces(tris, scale);

  const assumptions = [
    `Units declared as ${units === "IN" ? "inches" : "millimetres"} at import — an STL file carries no units and CANVAS did not infer these.`,
    `Coplanar facets grouped within ${NORMAL_TOLERANCE_DEG}° of a shared normal.`,
    `Planar regions under ${MIN_FACE_AREA_IN2} in² treated as noise rather than as faces.`,
  ];
  if (mesh.recomputedNormals > 0) {
    assumptions.push(
      `${mesh.recomputedNormals.toLocaleString()} facet normals were zero or non-unit in the file and were recomputed from the vertex winding.`,
    );
  }

  const missingInputs: string[] = [];
  if (!integrity.watertight) {
    missingInputs.push(
      `The mesh is not closed — ${integrity.openEdges.toLocaleString()} open edges. The scanner did not see the whole part, so the envelope is a lower bound on it, not the part.`,
    );
  }

  return {
    units,
    triangles: tris.length,
    envelope,
    integrity,
    planarFaces,
    notAttempted: [
      "Bores, holes and radii — finding them needs surface fitting this does not do.",
      "Threads — a scanned helix is not a thread designation.",
      "Tolerances and fits — a scan measures one worn example, not the drawing it came from.",
      "Datums — which face seats in service is a human's knowledge, not the mesh's.",
      "Functional roles — what the part does cannot be read off its shape.",
    ],
    assumptions,
    missingInputs,
    developmentAnalysis: true,
  };
}

/**
 * Every edge of a closed surface is shared by exactly two triangles. Edges
 * are keyed on rounded vertex positions because scanners emit the same
 * corner with float noise between facets; the rounding is at 1e-6 of the
 * file's own units, far below anything a scanner resolves.
 */
function checkIntegrity(tris: Triangle[]): MeshIntegrity {
  const edges = new Map<string, number>();
  let degenerate = 0;
  const key = (v: [number, number, number]) => v.map((n) => Math.round(n * 1e6)).join(",");
  for (const t of tris) {
    if (t.normal[0] === 0 && t.normal[1] === 0 && t.normal[2] === 0) degenerate++;
    const ks = [key(t.a), key(t.b), key(t.c)];
    for (let i = 0; i < 3; i++) {
      // Undirected: an edge is the same edge from either triangle.
      const pair = [ks[i], ks[(i + 1) % 3]].sort().join("|");
      edges.set(pair, (edges.get(pair) ?? 0) + 1);
    }
  }
  let open = 0;
  for (const count of edges.values()) if (count !== 2) open++;
  return { watertight: open === 0, openEdges: open, degenerateTriangles: degenerate };
}

function groupPlanarFaces(tris: Triangle[], scale: number): PlanarFace[] {
  const cos = Math.cos((NORMAL_TOLERANCE_DEG * Math.PI) / 180);
  const groups: { normal: [number, number, number]; triangles: number; area: number }[] = [];
  for (const t of tris) {
    if (t.normal[0] === 0 && t.normal[1] === 0 && t.normal[2] === 0) continue;
    const area = triangleArea(t) * scale * scale;
    const g = groups.find((x) => dot(x.normal, t.normal) >= cos);
    if (g) {
      g.triangles++;
      g.area += area;
    } else {
      groups.push({ normal: t.normal, triangles: 1, area });
    }
  }
  return groups
    .filter((g) => g.area >= MIN_FACE_AREA_IN2)
    .map((g) => ({ normal: g.normal, triangles: g.triangles, area: Number(g.area.toFixed(4)) }))
    .sort((a, b) => b.area - a.area);
}

function triangleArea(t: Triangle): number {
  const u = [t.b[0] - t.a[0], t.b[1] - t.a[1], t.b[2] - t.a[2]];
  const v = [t.c[0] - t.a[0], t.c[1] - t.a[1], t.c[2] - t.a[2]];
  const n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
  return Math.hypot(n[0], n[1], n[2]) / 2;
}

const dot = (a: [number, number, number], b: [number, number, number]) =>
  a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
