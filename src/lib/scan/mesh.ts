/**
 * STL MESH PARSER — deterministic, dependency-free.
 *
 * A 3D scan arrives as a triangle soup. This reads it and nothing more: no
 * model call, no inference, no geometry interpretation. The recognizer on
 * top decides what, if anything, the triangles are allowed to claim.
 *
 * Two facts about STL that decide how the whole import behaves:
 *
 * 1. AN STL FILE CARRIES NO UNITS. None. A cube 25.4 units on a side is a
 *    1" cube or a 25.4 mm cube and the file cannot tell you which. Every
 *    scanner writes whatever its own setting was. So the units are a
 *    DECLARATION by the person importing, recorded as such — this parser
 *    returns bare numbers and refuses to guess, and `MeshUnits` is a
 *    required argument at the point of conversion rather than a default
 *    somewhere.
 *
 * 2. AN STL FILE CARRIES NO ACCURACY. The triangles are exact; what they
 *    are exact about is whatever the scanner resolved, which is a property
 *    of the scanner. That number comes from the metrology record, never
 *    from here.
 */

export interface Triangle {
  /** Vertices, in file units, in file order. */
  a: [number, number, number];
  b: [number, number, number];
  c: [number, number, number];
  /** Facet normal as WRITTEN. Many exporters write zeroes; see `normalOf`. */
  normal: [number, number, number];
}

export interface Mesh {
  triangles: Triangle[];
  format: "BINARY" | "ASCII";
  /** The solid name from an ASCII header, when one was given. */
  name: string | null;
  /**
   * Facets whose written normal was zero or non-unit, so the geometric
   * normal was used instead. Not an error — a fact about the exporter.
   */
  recomputedNormals: number;
  warnings: string[];
}

export interface MeshParseFailure {
  /** Why this is not a mesh CANVAS can read. Machinist voice, not a stack. */
  reason: string;
  recommendations: string[];
}

export type MeshParseResult = { ok: true; mesh: Mesh } | { ok: false; error: MeshParseFailure };

/** Binary STL: 80-byte header, uint32 count, then 50 bytes per triangle. */
const BINARY_HEADER = 80;
const BINARY_COUNT = 4;
const BINARY_TRIANGLE = 50;

/**
 * A scan of a real part is hundreds of thousands of triangles. This bound
 * exists so a mistaken upload fails as a sentence rather than as an
 * out-of-memory crash, and it is stated rather than silently truncating.
 */
export const MAX_TRIANGLES = 2_000_000;

export function parseStl(bytes: Uint8Array): MeshParseResult {
  if (bytes.length === 0) {
    return fail("The file is empty.", ["Check the export completed", "Re-export the scan as STL"]);
  }
  return looksBinary(bytes) ? parseBinary(bytes) : parseAscii(bytes);
}

/**
 * Format detection by ARITHMETIC, not by the leading "solid" keyword.
 *
 * Plenty of binary exporters write "solid" into their 80-byte header, so
 * sniffing the keyword misreads those files as ASCII. The triangle count
 * at offset 80 either accounts for the file's exact length or it does not.
 */
function looksBinary(bytes: Uint8Array): boolean {
  if (bytes.length < BINARY_HEADER + BINARY_COUNT) return false;
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const count = view.getUint32(BINARY_HEADER, true);
  if (count > MAX_TRIANGLES) return false;
  return bytes.length === BINARY_HEADER + BINARY_COUNT + count * BINARY_TRIANGLE;
}

function parseBinary(bytes: Uint8Array): MeshParseResult {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const count = view.getUint32(BINARY_HEADER, true);
  if (count === 0) {
    return fail("The file declares zero triangles.", ["Check the export included the geometry"]);
  }
  const triangles: Triangle[] = [];
  let recomputed = 0;
  let off = BINARY_HEADER + BINARY_COUNT;
  for (let i = 0; i < count; i++) {
    const f = (k: number) => view.getFloat32(off + k * 4, true);
    const written: [number, number, number] = [f(0), f(1), f(2)];
    const a: [number, number, number] = [f(3), f(4), f(5)];
    const b: [number, number, number] = [f(6), f(7), f(8)];
    const c: [number, number, number] = [f(9), f(10), f(11)];
    if (![...written, ...a, ...b, ...c].every(Number.isFinite)) {
      return fail(
        `Triangle ${i + 1} contains a value that is not a number. The file is damaged or was truncated in transfer.`,
        ["Re-export the scan", "Check the file transferred completely"],
      );
    }
    const { normal, wasRecomputed } = resolveNormal(written, a, b, c);
    if (wasRecomputed) recomputed++;
    triangles.push({ a, b, c, normal });
    off += BINARY_TRIANGLE;
  }
  return { ok: true, mesh: { triangles, format: "BINARY", name: null, recomputedNormals: recomputed, warnings: [] } };
}

function parseAscii(bytes: Uint8Array): MeshParseResult {
  const text = new TextDecoder().decode(bytes);
  if (!/^\s*solid\b/i.test(text)) {
    return fail(
      "This is not an STL file — it begins with neither a binary triangle count that matches its length nor the ASCII keyword 'solid'.",
      ["Export the scan as STL (binary or ASCII)", "Check the file is not a project file from the scanning software"],
    );
  }
  const name = /^\s*solid[ \t]+(\S.*?)\s*$/im.exec(text)?.[1] ?? null;
  const triangles: Triangle[] = [];
  const warnings: string[] = [];
  let recomputed = 0;

  // One facet at a time, each with exactly three vertices. A facet with a
  // different vertex count is not a triangle and is not guessed at.
  const facetRe = /facet\s+normal\s+([^\n]*)\n([\s\S]*?)endfacet/gi;
  for (const m of text.matchAll(facetRe)) {
    const written = numbers(m[1]);
    const verts = [...m[2].matchAll(/vertex\s+([^\n]*)/gi)].map((v) => numbers(v[1]));
    if (verts.length !== 3 || verts.some((v) => v.length !== 3) || written.length !== 3) {
      return fail(
        `Facet ${triangles.length + 1} does not have a normal and exactly three XYZ vertices. CANVAS will not guess at a damaged facet.`,
        ["Re-export the scan", "Repair the mesh in the scanning software"],
      );
    }
    const [a, b, c] = verts.map((v) => [v[0], v[1], v[2]] as [number, number, number]);
    const { normal, wasRecomputed } = resolveNormal(written as [number, number, number], a, b, c);
    if (wasRecomputed) recomputed++;
    triangles.push({ a, b, c, normal });
  }

  if (triangles.length === 0) {
    return fail("The file says 'solid' but contains no facets.", ["Check the export included the geometry"]);
  }
  if (triangles.length > MAX_TRIANGLES) {
    return fail(
      `${triangles.length.toLocaleString()} triangles exceeds the ${MAX_TRIANGLES.toLocaleString()} CANVAS will read.`,
      ["Decimate the mesh in the scanning software before exporting"],
    );
  }
  return { ok: true, mesh: { triangles, format: "ASCII", name, recomputedNormals: recomputed, warnings } };
}

const numbers = (s: string): number[] =>
  (s.trim().match(/[-+]?[\d.]+(?:[eE][-+]?\d+)?/g) ?? []).map(Number).filter(Number.isFinite);

/**
 * The written normal, or the geometric one when the file's is unusable.
 *
 * Exporters commonly write (0,0,0) and expect the reader to derive it. A
 * zero normal is not a direction, and face grouping is done on normals, so
 * accepting one would silently put every such facet in the same bucket.
 */
function resolveNormal(
  written: [number, number, number],
  a: [number, number, number],
  b: [number, number, number],
  c: [number, number, number],
): { normal: [number, number, number]; wasRecomputed: boolean } {
  const len = Math.hypot(...written);
  if (len > 0.9 && len < 1.1) return { normal: written, wasRecomputed: false };
  const u: [number, number, number] = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
  const v: [number, number, number] = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
  const n: [number, number, number] = [
    u[1] * v[2] - u[2] * v[1],
    u[2] * v[0] - u[0] * v[2],
    u[0] * v[1] - u[1] * v[0],
  ];
  const nl = Math.hypot(...n);
  // A degenerate (zero-area) triangle has no normal. Zero is returned and
  // the inspector counts it rather than treating it as a direction.
  if (nl === 0) return { normal: [0, 0, 0], wasRecomputed: true };
  return { normal: [n[0] / nl, n[1] / nl, n[2] / nl], wasRecomputed: true };
}

const fail = (reason: string, recommendations: string[]): MeshParseResult => ({
  ok: false,
  error: { reason, recommendations },
});
