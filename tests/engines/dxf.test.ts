import test from "node:test";
import assert from "node:assert/strict";
import { readDxf } from "@/lib/dxf/parse";
import { assembleLoops, splitProfile } from "@/lib/geometry/loop";
import { offsetChain, chainLength } from "@/lib/engines/cam/chain";

/**
 * DXF → LINES AND ARCS
 *
 * The practical way to get a real profile out of any CAD a job shop owns. A
 * DXF is group-code pairs: an integer, then its value on the next line.
 */

/**
 * Group-code pairs as a DXF writes them: an integer code, then its value on
 * the next line. Flat, like the file, so the tests exercise the real parse.
 */
type Pairs = (string | number | Pairs)[];

const dxf = (body: Pairs, header: Pairs = []): string =>
  (
    [
      ...(header.length ? ["0", "SECTION", "2", "HEADER", ...header, "0", "ENDSEC"] : []),
      "0", "SECTION", "2", "ENTITIES",
      ...body,
      "0", "ENDSEC", "0", "EOF",
    ] as Pairs
  )
    .flat(4)
    .join("\n");

const LINE = (x1: number, y1: number, x2: number, y2: number): Pairs =>
  ["0", "LINE", "8", "0", "10", x1, "20", y1, "11", x2, "21", y2];

/* ---------------- The five entities a profile is made of ---------------- */

test("a LINE is a line", () => {
  const { segments, warnings } = readDxf(dxf([...LINE(0, 0, 4, 0)]));
  assert.deepEqual(warnings, []);
  assert.equal(segments.length, 1);
  assert.deepEqual(segments[0], { kind: "LINE", a: { x: 0, y: 0 }, b: { x: 4, y: 0 } });
});

test("an ARC runs counter-clockwise from its start angle, which is what a DXF means", () => {
  // A DXF ARC is always CCW from code 50 to code 51. Reading it either way
  // round would bulge half the arcs on the part the wrong side.
  const { segments } = readDxf(dxf([["0", "ARC"], ["10", 1], ["20", 2], ["40", 0.5], ["50", 0], ["51", 90]]));
  assert.equal(segments.length, 1);
  const a = segments[0];
  assert.equal(a.kind, "ARC");
  if (a.kind !== "ARC") throw new Error("unreachable");
  assert.equal(a.cw, false);
  assert.ok(Math.abs(a.a.x - 1.5) < 1e-9 && Math.abs(a.a.y - 2) < 1e-9, `start ${JSON.stringify(a.a)}`);
  assert.ok(Math.abs(a.b.x - 1) < 1e-9 && Math.abs(a.b.y - 2.5) < 1e-9, `end ${JSON.stringify(a.b)}`);
  assert.deepEqual(a.center, { x: 1, y: 2 });
});

test("a CIRCLE becomes two half arcs, because a chain segment cannot sweep a full turn", () => {
  // Start and end would be the same point and the direction ambiguous.
  const { segments } = readDxf(dxf([["0", "CIRCLE"], ["10", 0], ["20", 0], ["40", 0.25]]));
  assert.equal(segments.length, 2);
  const { loops } = assembleLoops(segments);
  assert.equal(loops.length, 1);
  assert.ok(Math.abs(loops[0].area - Math.PI * 0.0625) < 1e-9, `area ${loops[0].area}`);
  assert.equal(loops[0].fromClosedEntity, false);
});

test("an LWPOLYLINE closes itself when the closed flag is set", () => {
  const { segments } = readDxf(
    dxf(
      [
        ["0", "LWPOLYLINE"], ["90", 4], ["70", 1],
        ["10", -2], ["20", -1], ["10", 2], ["20", -1], ["10", 2], ["20", 1], ["10", -2], ["20", 1],
      ]),
  );
  assert.equal(segments.length, 4, "the closing edge was not emitted");
  const { loops, refusals } = assembleLoops(segments);
  assert.deepEqual(refusals, []);
  assert.ok(Math.abs(loops[0].area - 8) < 1e-9);
});

test("an open LWPOLYLINE is left open rather than closed for the drawing", () => {
  // Whether a polyline closes is a fact the file states. Closing it because it
  // nearly does would invent a boundary.
  const { segments } = readDxf(
    dxf([["0", "LWPOLYLINE"], ["90", 3], ["70", 0], ["10", 0], ["20", 0], ["10", 1], ["20", 0], ["10", 1], ["20", 1]]),
  );
  assert.equal(segments.length, 2);
});

test("a POLYLINE collects its VERTEX entities until SEQEND", () => {
  const { segments } = readDxf(
    dxf(
      [
        ["0", "POLYLINE"], ["70", 1],
        ["0", "VERTEX"], ["10", 0], ["20", 0],
        ["0", "VERTEX"], ["10", 2], ["20", 0],
        ["0", "VERTEX"], ["10", 2], ["20", 2],
        ["0", "VERTEX"], ["10", 0], ["20", 2],
        ["0", "SEQEND"],
      ]),
  );
  assert.equal(segments.length, 4);
  assert.ok(Math.abs(assembleLoops(segments).loops[0].area - 4) < 1e-9);
});

/* ---------------- The bulge, which is every fillet on the part ---------------- */

test("a bulge becomes the arc it describes", () => {
  /*
   * A bulge is the tangent of a quarter of the arc's included angle, signed
   * clockwise-negative. It is how a DXF stores a rounded corner inside a
   * polyline, and dropping it turns every fillet on the part into a sharp
   * corner the cutter cannot make.
   *
   * tan(pi/8) over a quarter circle from (1,0) to (0,1) is centred on the
   * origin at r = 1.
   */
  const b = Math.tan(Math.PI / 8);
  const { segments } = readDxf(
    dxf([["0", "LWPOLYLINE"], ["90", 2], ["70", 0], ["10", 1], ["20", 0], ["42", b], ["10", 0], ["20", 1], ["42", 0]]),
  );
  assert.equal(segments.length, 1);
  const a = segments[0];
  assert.equal(a.kind, "ARC");
  if (a.kind !== "ARC") throw new Error("unreachable");
  assert.ok(Math.abs(a.center.x) < 1e-9 && Math.abs(a.center.y) < 1e-9, `centre ${JSON.stringify(a.center)}`);
  assert.equal(a.cw, false, "a positive bulge is counter-clockwise");
  assert.ok(Math.abs(Math.hypot(a.a.x - a.center.x, a.a.y - a.center.y) - 1) < 1e-9);
});

test("a negative bulge goes the other way round", () => {
  const b = -Math.tan(Math.PI / 8);
  const { segments } = readDxf(
    dxf([["0", "LWPOLYLINE"], ["90", 2], ["70", 0], ["10", 1], ["20", 0], ["42", b], ["10", 0], ["20", 1], ["42", 0]]),
  );
  const a = segments[0];
  if (a.kind !== "ARC") throw new Error("expected an arc");
  assert.equal(a.cw, true);
  assert.ok(Math.abs(a.center.x - 1) < 1e-9 && Math.abs(a.center.y - 1) < 1e-9, `centre ${JSON.stringify(a.center)}`);
});

test("a major arc bulge puts the centre on the far side", () => {
  // bulge > 1 is an arc sweeping more than half a turn. The centre crosses to
  // the other side of the chord, and getting that wrong bows the arc inward.
  const b = Math.tan((3 * Math.PI) / 8); // 270 degrees
  const { segments } = readDxf(
    dxf([["0", "LWPOLYLINE"], ["90", 2], ["70", 0], ["10", 1], ["20", 0], ["42", b], ["10", 0], ["20", 1], ["42", 0]]),
  );
  const a = segments[0];
  if (a.kind !== "ARC") throw new Error("expected an arc");
  assert.ok(Math.abs(a.center.x - 1) < 1e-9 && Math.abs(a.center.y - 1) < 1e-9, `centre ${JSON.stringify(a.center)}`);
});

test("bulges that cannot be matched to their vertices are refused, not guessed", () => {
  /*
   * A 42 appears only for a vertex that carries one, so bulges cannot be
   * zipped by index against the vertex list. Landing each fillet on the wrong
   * corner is worse than dropping them, because it is wrong rather than absent.
   */
  const { segments, warnings } = readDxf(
    dxf(
      [
        ["0", "LWPOLYLINE"], ["90", 4], ["70", 1],
        ["10", -2], ["20", -1], ["10", 2], ["20", -1], ["42", 0.4], ["10", 2], ["20", 1], ["10", -2], ["20", 1],
      ]),
  );
  assert.equal(segments.filter((s) => s.kind === "ARC").length, 0, "a bulge was placed on a guessed corner");
  assert.match(warnings.join(" "), /1 bulge values for 4 vertices/);
  assert.match(warnings.join(" "), /explode the polyline/);
});

/* ---------------- Units are read, never assumed ---------------- */

test("$INSUNITS is read", () => {
  assert.equal(readDxf(dxf([...LINE(0, 0, 1, 0)], [["9", "$INSUNITS"], ["70", 1]])).units, "IN");
  assert.equal(readDxf(dxf([...LINE(0, 0, 1, 0)], [["9", "$INSUNITS"], ["70", 4]])).units, "MM");
});

test("a file that does not say what its numbers mean is not assumed to be inches", () => {
  /*
   * A millimetre drawing read as inches is a part 25.4 times too big, and it
   * would pass every check in this system because every number in it is
   * self-consistent.
   */
  assert.equal(readDxf(dxf([...LINE(0, 0, 1, 0)])).units, null);
  // Unitless is not inches either.
  assert.equal(readDxf(dxf([...LINE(0, 0, 1, 0)], [["9", "$INSUNITS"], ["70", 0]])).units, null);
});

/* ---------------- What it will not pretend to read ---------------- */

test("a spline is named rather than flattened into chords", () => {
  /*
   * Approximating it would produce a profile that no longer matches the
   * drawing, to a tolerance nobody chose and nobody was told about — and it
   * would arrive looking like real geometry.
   */
  const { segments, warnings, ignored } = readDxf(
    dxf([...LINE(0, 0, 1, 0), ["0", "SPLINE", "10", 0, "20", 0]]),
  );
  assert.equal(segments.length, 1);
  assert.deepEqual(ignored.filter((i) => i.type === "SPLINE"), [{ type: "SPLINE", count: 1 }]);
  assert.match(warnings.join(" "), /does not read SPLINE geometry/);
  assert.match(warnings.join(" "), /cut a shape that is not the drawing/);
});

test("text and dimensions are ignored without complaint", () => {
  // They are not geometry and their absence changes nothing about the part.
  const { warnings, ignored } = readDxf(
    dxf([...LINE(0, 0, 1, 0), "0", "TEXT", "1", "PART A", "0", "DIMENSION"]),
  );
  assert.deepEqual(warnings, []);
  assert.equal(ignored.length, 2);
});

test("a binary or DWG file says so rather than reading as empty", () => {
  const r = readDxf("  not a dxf at all");
  assert.deepEqual(r.segments, []);
  assert.match(r.warnings.join(" "), /saved as an ASCII DXF/);
});

test("the title block is not the part", () => {
  // Paper-space entities are the drawing's border and title block.
  const { segments } = readDxf(
    dxf([...LINE(0, 0, 4, 0), "0", "LINE", "67", 1, "10", 0, "20", 0, "11", 100, "21", 0]),
  );
  assert.equal(segments.length, 1, "a paper-space line was imported as geometry");
  assert.deepEqual(segments[0].b, { x: 4, y: 0 });
});

/* ---------------- End to end: a real plate ---------------- */

test("a plate with a filleted corner and two holes imports as a profile plus its interiors", () => {
  const b = Math.tan(Math.PI / 8);
  const file = dxf(
    [
      // Outline: 4 x 2 with the top-right corner rounded R0.5.
      ...[
        ["0", "LWPOLYLINE"], ["90", 5], ["70", 1],
        ["10", -2], ["20", -1], ["42", 0],
        ["10", 2], ["20", -1], ["42", 0],
        ["10", 2], ["20", 0.5], ["42", b],
        ["10", 1.5], ["20", 1], ["42", 0],
        ["10", -2], ["20", 1], ["42", 0],
      ].flat(),
      "0", "CIRCLE", "10", -1, "20", 0, "40", 0.125,
      "0", "CIRCLE", "10", 1, "20", 0, "40", 0.125,
    ],
    [["9", "$INSUNITS"], ["70", 1]],
  );

  const read = readDxf(file);
  assert.deepEqual(read.warnings, []);
  assert.equal(read.units, "IN");

  const { loops, refusals } = assembleLoops(read.segments);
  assert.deepEqual(refusals, [], "the plate did not assemble into closed loops");
  assert.equal(loops.length, 3, "the outline and both holes did not come through");

  const { profile, interior } = splitProfile(loops);
  assert.ok(profile);
  assert.equal(interior.length, 2);
  // 4 x 2 less the corner the fillet takes off: r² − πr²/4 at r = 0.5.
  const expected = 8 - (0.25 - (Math.PI * 0.25) / 4);
  assert.ok(Math.abs(profile!.area - expected) < 1e-9, `area ${profile!.area} against ${expected}`);

  // And the contour engine will actually cut it.
  const off = offsetChain(profile!.chain, 0.25);
  assert.ok(!("error" in off), `the contour engine refuses this profile: ${JSON.stringify(off)}`);
  if ("error" in off) throw new Error("unreachable");
  assert.ok(chainLength(off) > chainLength(profile!.chain), "the cutter would run inside the part");
});
