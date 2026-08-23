import { test } from "node:test";
import assert from "node:assert/strict";
import { parseStl, MAX_TRIANGLES } from "@/lib/scan/mesh";
import { inspectMesh } from "@/lib/scan/inspect";
import { METROLOGY_DEVICES, SCANNING_INSTRUMENTS, isScanningInstrument } from "@/lib/domain/shop";
import { readFileSync } from "node:fs";

/**
 * Scan import. The load-bearing claims: an STL declares no units and CANVAS
 * never guesses them; a damaged file is refused by name rather than read
 * partially; an open mesh says the envelope is a lower bound; and the things
 * a mesh cannot establish are listed in the output every time rather than
 * left to be assumed absent.
 */

/* ---------------- Fixtures: real bytes, not hand-waved ---------------- */

/** A closed unit cube as 12 triangles, correctly wound. */
function cubeTriangles(size: number): [number, number, number][][] {
  const s = size;
  const v: Record<string, [number, number, number]> = {
    a: [0, 0, 0], b: [s, 0, 0], c: [s, s, 0], d: [0, s, 0],
    e: [0, 0, s], f: [s, 0, s], g: [s, s, s], h: [0, s, s],
  };
  const quad = (p: string, q: string, r: string, t: string) => [
    [v[p], v[q], v[r]],
    [v[p], v[r], v[t]],
  ];
  return [
    ...quad("a", "d", "c", "b"), // bottom
    ...quad("e", "f", "g", "h"), // top
    ...quad("a", "b", "f", "e"),
    ...quad("b", "c", "g", "f"),
    ...quad("c", "d", "h", "g"),
    ...quad("d", "a", "e", "h"),
  ] as [number, number, number][][];
}

function binaryStl(tris: [number, number, number][][], header = "CANVAS test"): Uint8Array {
  const buf = new ArrayBuffer(84 + tris.length * 50);
  const view = new DataView(buf);
  new Uint8Array(buf, 0, 80).set(new TextEncoder().encode(header.padEnd(80).slice(0, 80)));
  view.setUint32(80, tris.length, true);
  let off = 84;
  for (const t of tris) {
    // Normal written as zero on purpose: this is what many exporters do.
    for (let k = 0; k < 3; k++) view.setFloat32(off + k * 4, 0, true);
    let k = 3;
    for (const vert of t) for (const n of vert) view.setFloat32(off + k++ * 4, n, true);
    view.setUint16(off + 48, 0, true);
    off += 50;
  }
  return new Uint8Array(buf);
}

function asciiStl(tris: [number, number, number][][], name = "part"): Uint8Array {
  const body = tris
    .map(
      (t) =>
        `facet normal 0 0 0\n outer loop\n${t.map((v) => `  vertex ${v.join(" ")}`).join("\n")}\n endloop\nendfacet`,
    )
    .join("\n");
  return new TextEncoder().encode(`solid ${name}\n${body}\nendsolid ${name}\n`);
}

/* ---------------- Parsing ---------------- */

test("binary and ASCII STL of the same cube parse to the same geometry", () => {
  const tris = cubeTriangles(2);
  const bin = parseStl(binaryStl(tris));
  const asc = parseStl(asciiStl(tris));
  assert.equal(bin.ok, true, !bin.ok ? bin.error.reason : "");
  assert.equal(asc.ok, true, !asc.ok ? asc.error.reason : "");
  if (!bin.ok || !asc.ok) return;
  assert.equal(bin.mesh.format, "BINARY");
  assert.equal(asc.mesh.format, "ASCII");
  assert.equal(bin.mesh.triangles.length, 12);
  assert.equal(asc.mesh.triangles.length, 12);
  assert.equal(asc.mesh.name, "part");
  assert.deepEqual(bin.mesh.triangles[0].a, asc.mesh.triangles[0].a);
});

test("a binary file whose header says 'solid' is still read as binary", () => {
  // The classic STL trap: sniffing the leading keyword misreads every binary
  // file from an exporter that writes "solid" into its 80-byte header. The
  // triangle count either accounts for the file length or it does not.
  const r = parseStl(binaryStl(cubeTriangles(1), "solid produced by a scanner"));
  assert.equal(r.ok, true, !r.ok ? r.error.reason : "");
  assert.equal(r.ok && r.mesh.format, "BINARY");
});

test("zero normals are recomputed from the winding and counted, not trusted", () => {
  // A zero normal is not a direction. Face grouping is done on normals, so
  // accepting one would put every such facet into a single bucket.
  const r = parseStl(binaryStl(cubeTriangles(1)));
  assert.equal(r.ok, true);
  if (!r.ok) return;
  assert.equal(r.mesh.recomputedNormals, 12);
  for (const t of r.mesh.triangles) {
    assert.ok(Math.abs(Math.hypot(...t.normal) - 1) < 1e-6, "recomputed normals must be unit");
  }
});

test("a damaged or truncated file is refused by name, not read partially", () => {
  const empty = parseStl(new Uint8Array(0));
  assert.equal(empty.ok, false);
  assert.ok(!empty.ok && /empty/i.test(empty.error.reason));

  // A truncated binary file no longer satisfies the length arithmetic, so it
  // falls through to ASCII and is refused there rather than read as garbage.
  const truncated = binaryStl(cubeTriangles(1)).slice(0, 200);
  const t = parseStl(truncated);
  assert.equal(t.ok, false);
  assert.ok(!t.ok && t.error.recommendations.length > 0);

  // An ASCII facet with two vertices is not a triangle.
  const bad = new TextEncoder().encode(
    "solid x\nfacet normal 0 0 0\n outer loop\n  vertex 0 0 0\n  vertex 1 0 0\n endloop\nendfacet\nendsolid x\n",
  );
  const b = parseStl(bad);
  assert.equal(b.ok, false);
  assert.ok(!b.ok && /three XYZ vertices/i.test(b.error.reason), !b.ok ? b.error.reason : "");

  // Something that is not an STL at all.
  const notStl = parseStl(new TextEncoder().encode("ISO-10303-21;\nHEADER;\n"));
  assert.equal(notStl.ok, false);
  assert.ok(!notStl.ok && /not an STL/i.test(notStl.error.reason));
});

/* ---------------- Units: the one thing a scan cannot tell you ---------------- */

test("the same file is a different part in inches and in millimetres", () => {
  // 25.4 units on a side. That is a 25.4" block or a 1" block, and the file
  // does not know. Nothing in the parser or the inspector picks for you.
  const r = parseStl(binaryStl(cubeTriangles(25.4)));
  assert.equal(r.ok, true);
  if (!r.ok) return;
  const asInches = inspectMesh(r.mesh, "IN");
  const asMm = inspectMesh(r.mesh, "MM");
  assert.equal(asInches.envelope.x, 25.4);
  assert.equal(asMm.envelope.x, 1);
  // And each says which was declared, in its own assumptions.
  assert.ok(asMm.assumptions.some((a) => /millimetres.*declared|declared as millimetres/i.test(a)));
  assert.ok(asInches.assumptions.some((a) => /carries no units/i.test(a)));
});

/* ---------------- What the mesh is allowed to claim ---------------- */

test("a closed cube reads as watertight with six faces", () => {
  const r = parseStl(binaryStl(cubeTriangles(2)));
  assert.equal(r.ok, true);
  if (!r.ok) return;
  const i = inspectMesh(r.mesh, "IN");
  assert.equal(i.integrity.watertight, true);
  assert.equal(i.integrity.openEdges, 0);
  assert.equal(i.integrity.degenerateTriangles, 0);
  assert.deepEqual([i.envelope.x, i.envelope.y, i.envelope.z], [2, 2, 2]);
  assert.equal(i.planarFaces.length, 6);
  // Every face of a 2" cube is 4 in², and they are ordered biggest first.
  for (const f of i.planarFaces) assert.equal(f.area, 4);
  assert.equal(i.missingInputs.length, 0);
});

test("an open mesh says the envelope is a lower bound on the part", () => {
  // Drop the top two triangles: the scanner did not see that face.
  const r = parseStl(binaryStl(cubeTriangles(2).filter((_, n) => n > 1)));
  assert.equal(r.ok, true);
  if (!r.ok) return;
  const i = inspectMesh(r.mesh, "IN");
  assert.equal(i.integrity.watertight, false);
  assert.ok(i.integrity.openEdges > 0);
  assert.ok(
    i.missingInputs.some((m) => /lower bound/i.test(m)),
    `got ${JSON.stringify(i.missingInputs)}`,
  );
});

test("what a scan cannot establish is listed every time, not left to be assumed absent", () => {
  const r = parseStl(binaryStl(cubeTriangles(1)));
  assert.equal(r.ok, true);
  if (!r.ok) return;
  const i = inspectMesh(r.mesh, "IN");
  // A clean, closed, unambiguous scan still says what it did not attempt.
  assert.equal(i.integrity.watertight, true);
  for (const topic of [/bores?|holes?/i, /thread/i, /tolerance/i, /datum/i, /functional role/i]) {
    assert.ok(i.notAttempted.some((n) => topic.test(n)), `nothing said about ${topic}`);
  }
  // And it is a development analysis, non-optionally.
  assert.equal(i.developmentAnalysis, true);
});

test("noise-sized facets are not reported as faces", () => {
  const tris = cubeTriangles(0.05); // 0.0025 in² per face — under the floor
  const r = parseStl(binaryStl(tris));
  assert.equal(r.ok, true);
  if (!r.ok) return;
  assert.equal(inspectMesh(r.mesh, "IN").planarFaces.length, 0);
});

test("the triangle ceiling is stated rather than silently truncating", () => {
  assert.ok(MAX_TRIANGLES > 100_000, "a real scan is hundreds of thousands of triangles");
});

/* ---------------- The instrument, and the one list of them ---------------- */

test("only instruments that produce a mesh can be named as the source of a scan", () => {
  // Every entry must be real vocabulary — a rename that emptied this list
  // would make the import say "no scanning instrument on file" to a shop
  // that owns one, which is a dead end rather than a safe default.
  for (const t of SCANNING_INSTRUMENTS) {
    assert.ok(METROLOGY_DEVICES.includes(t), `${t} is not in the metrology vocabulary`);
    assert.ok(isScanningInstrument(t));
  }
  // A micrometer measures one dimension at a time; it does not produce a
  // mesh, and a scan attributed to one would be a fiction about provenance.
  for (const t of ["MICROMETER", "BORE_GAUGE", "SURFACE_PLATE", "TAPE_RULE"]) {
    assert.equal(isScanningInstrument(t), false, `${t} must not be offered as a scanner`);
  }
  assert.equal(isScanningInstrument("NOT_A_DEVICE"), false);
});

test("the scan importer and the scanner picker read the same list", () => {
  // Two copies of this list drifting apart means the picker offers an
  // instrument the route then refuses, or the reverse.
  const route = readFileSync("src/app/api/parts/scan/route.ts", "utf8");
  const page = readFileSync("src/app/(app)/reverse-engineer/page.tsx", "utf8");
  for (const [file, src] of [["route", route], ["page", page]] as const) {
    assert.match(src, /isScanningInstrument/, `the scan ${file} does not use the shared list`);
    assert.doesNotMatch(src, /"STRUCTURED_LIGHT_SCANNER"/, `the scan ${file} keeps its own copy of the scanner list`);
  }
});
