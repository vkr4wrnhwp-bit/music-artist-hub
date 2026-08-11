import type { FeatureSuggestion } from "@/lib/domain/features";
import { parseStep, asRef, asNum, asList, type StepEntity, type StepFile } from "./parse";

/**
 * STEP FEATURE RECOGNIZER — deterministic 2.5D spike
 *
 * Reads the entity graph and proposes CANVAS features for the geometry it can
 * genuinely identify: axis-aligned cylindrical holes and the stock envelope.
 * Everything it cannot identify is counted and named in the report — a
 * surface the recognizer does not understand is a fact about the recognizer,
 * stated as one, never silently dropped.
 *
 * What this deliberately is NOT:
 * - Not a B-rep kernel. Pocket and slot floors are recognized only when an
 *   interior horizontal planar face matches a circular, slot or rectangular
 *   boundary exactly; bosses, fillets, freeform surfaces and any floor
 *   profile that does not match are reported as unrecognized, never
 *   approximated. A floor is assumed milled from the top face — an island
 *   top looks identical in 2.5D, which is one reason every proposal passes
 *   through human acceptance.
 * - Not a thread detector. STEP geometry carries no thread; a hole is
 *   proposed as a plain hole even if the design intent is a tapped hole.
 * - Not an authority. Output goes through the proposals flow — a human
 *   accepts every feature before it becomes geometry. Zero-click ingest,
 *   never zero-click geometry.
 */

export interface StepRecognition {
  partName: string | null;
  /** Detected drawing units, converted: all output values are inches. */
  units: "IN" | "MM";
  /** Bounding envelope of all geometry, inches, after recentering. */
  envelope: { x: number; y: number; z: number };
  suggestions: FeatureSuggestion[];
  surfaces: { recognized: number; total: number };
  unrecognized: { type: string; count: number }[];
  warnings: string[];
}

export function recognizeStep(text: string): StepRecognition {
  const file = parseStep(text);
  const warnings = [...file.warnings];
  const e = file.entities;

  // FILE_NAME often carries the exporting machine's full path — keep the leaf.
  const rawName = /FILE_NAME\s*\(\s*'([^']*)'/.exec(file.header)?.[1] ?? "";
  const partName = rawName.split(/[\\/]/).pop()?.replace(/\.(stp|step)$/i, "") || null;

  // Units: an AP203/214 file states length units as SI (millimetre) or a
  // conversion-based unit named INCH. Sniff both single and complex records.
  let scale = 1 / 25.4; // default millimetre → inch
  let units: "IN" | "MM" = "MM";
  for (const ent of e.values()) {
    const raw = ent.raw ?? (ent.type === "CONVERSION_BASED_UNIT" ? JSON.stringify(ent.args) : "");
    if (ent.type === "CONVERSION_BASED_UNIT" || ent.type === "COMPLEX") {
      if (/INCH/i.test(raw ?? "")) { scale = 1; units = "IN"; break; }
    }
  }
  if (units === "MM" && ![...e.values()].some((x) => x.type === "COMPLEX" || x.type === "SI_UNIT" || x.type === "CONVERSION_BASED_UNIT")) {
    warnings.push("No unit record found — assuming millimetres, verify dimensions after import.");
  }

  // Assemblies place each component's geometry in its own local frame; a
  // recognizer that pooled them would put every hole in the wrong place.
  const assemblyLinks = [...e.values()].filter((x) => x.type === "NEXT_ASSEMBLY_USAGE_OCCURRENCE").length;
  if (assemblyLinks > 0) {
    warnings.push(
      `This file is an assembly (${assemblyLinks} component placements). The recognizer works on single parts — positions below are in component-local coordinates and the envelope spans the whole assembly. Export the individual part and re-import.`,
    );
  }

  /* ---- bounding box over every cartesian point ---- */
  const pts: [number, number, number][] = [];
  for (const ent of e.values()) {
    if (ent.type !== "CARTESIAN_POINT") continue;
    const coords = asList(ent.args[1]).map(asNum);
    if (coords.length === 3 && coords.every((c) => c !== null)) {
      pts.push([coords[0]! * scale, coords[1]! * scale, coords[2]! * scale]);
    }
  }
  if (pts.length === 0) {
    return {
      partName, units, envelope: { x: 0, y: 0, z: 0 }, suggestions: [],
      surfaces: { recognized: 0, total: 0 }, unrecognized: [],
      warnings: [...warnings, "No 3D points in the file — nothing to recognize."],
    };
  }
  const min = [Infinity, Infinity, Infinity];
  const max = [-Infinity, -Infinity, -Infinity];
  for (const p of pts) for (let k = 0; k < 3; k++) { min[k] = Math.min(min[k], p[k]); max[k] = Math.max(max[k], p[k]); }
  const envelope = { x: r4(max[0] - min[0]), y: r4(max[1] - min[1]), z: r4(max[2] - min[2]) };
  const cx0 = (min[0] + max[0]) / 2;
  const cy0 = (min[1] + max[1]) / 2;
  const topZ = max[2];

  /* ---- walk ADVANCED_FACEs ---- */
  const faces = [...e.values()].filter((x) => x.type === "ADVANCED_FACE");
  const unrecognizedCount = new Map<string, number>();
  interface Cyl { cx: number; cy: number; radius: number; zMin: number; zMax: number; offAxis: boolean }
  const cyls: Cyl[] = [];
  interface Floor { z: number; pts: [number, number, number][]; circles: { cx: number; cy: number; r: number }[] }
  const floors: Floor[] = [];
  let planeCount = 0;

  for (const face of faces) {
    const surf = face.args[2]?.kind === "REF" ? e.get((face.args[2] as { id: number }).id) : null;
    if (!surf) continue;
    if (surf.type === "PLANE") {
      planeCount++;
      // A horizontal plane strictly between the top and bottom of the part is
      // a pocket-floor candidate. Horizontality is read off the bound
      // vertices themselves — a wall face spans multiple Z and drops out.
      const boundPts = collectPoints(e, face.args[1], scale);
      if (boundPts.length >= 1) {
        const zs = boundPts.map((p) => p[2]);
        const z = zs[0];
        if (zs.every((v) => Math.abs(v - z) < 1e-3) && z < topZ - 0.005 && z > min[2] + 0.005) {
          floors.push({ z, pts: boundPts, circles: collectCircles(e, face.args[1], scale, z) });
        }
      }
      continue;
    }
    if (surf.type !== "CYLINDRICAL_SURFACE") {
      // Complex records carry their real surface type inside the raw text —
      // "BOUNDED_SURFACE(B_SPLINE_SURFACE…)" reports as what it is, not as
      // an opaque COMPLEX.
      const name =
        surf.type === "COMPLEX"
          ? (surf.raw?.match(/([A-Z_0-9]*SURFACE[A-Z_0-9]*)\s*\(/)?.[1] ?? "COMPLEX_SURFACE")
          : surf.type;
      unrecognizedCount.set(name, (unrecognizedCount.get(name) ?? 0) + 1);
      continue;
    }
    const placement = refEntity(e, surf.args[1]);
    const radius = asNum(surf.args[2]);
    if (!placement || radius === null) continue;
    const loc = refEntity(e, placement.args[1]);
    const axis = refEntity(e, placement.args[2]);
    const locC = loc ? asList(loc.args[1]).map(asNum) : [];
    const axisC = axis ? asList(axis.args[1]).map(asNum) : [0, 0, 1];
    const dz = Math.abs(axisC[2] ?? 1);
    const offAxis = dz < 0.999;

    // Depth from the face's own bound vertices, not guessed.
    const boundPts = collectPoints(e, face.args[1], scale);
    const zs = boundPts.map((p) => p[2]);
    cyls.push({
      cx: (locC[0] ?? 0) * scale,
      cy: (locC[1] ?? 0) * scale,
      radius: radius * scale,
      zMin: zs.length ? Math.min(...zs) : min[2],
      zMax: zs.length ? Math.max(...zs) : max[2],
      offAxis,
    });
  }

  // Cylindrical bores are usually exported as two half-faces: merge coaxial
  // cylinders of equal radius.
  const merged: Cyl[] = [];
  for (const c of cyls) {
    const hit = merged.find(
      (m) => Math.abs(m.cx - c.cx) < 1e-4 && Math.abs(m.cy - c.cy) < 1e-4 && Math.abs(m.radius - c.radius) < 1e-4 && m.offAxis === c.offAxis,
    );
    if (hit) { hit.zMin = Math.min(hit.zMin, c.zMin); hit.zMax = Math.max(hit.zMax, c.zMax); }
    else merged.push({ ...c });
  }

  const suggestions: FeatureSuggestion[] = [];
  let holeIndex = 0;
  let offAxisCount = 0;
  for (const c of merged) {
    if (c.offAxis) { offAxisCount++; continue; }
    // A cylinder wider than the part is context, not a hole.
    if (c.radius * 2 >= Math.min(envelope.x, envelope.y)) continue;
    holeIndex++;
    const depth = r4(c.zMax - c.zMin);
    const through = depth >= envelope.z - 0.005;
    const dia = r4(c.radius * 2);
    const kind = dia > 0.75 ? "BORE" : "DRILLED_HOLE";
    suggestions.push({
      kind,
      label: `⌀${dia.toFixed(4)} hole ${holeIndex}`,
      functionalRole: "NONE",
      critical: false,
      parameters: {
        centerX: r4(c.cx - cx0),
        centerY: r4(c.cy - cy0),
        diameter: dia,
        depth,
        through,
        top: r4(topZ - c.zMax),
      },
      rationale:
        `Cylindrical face set in the STEP geometry: ⌀${dia.toFixed(4)}" × ${depth.toFixed(4)}"` +
        `${through ? " through" : ""}. Kind ${kind} assigned by size heuristic (>0.75" proposes BORE) — ` +
        `reclassify on acceptance if this is tapped, reamed or a press-fit seat. STEP geometry carries no thread data.`,
    });
  }
  if (offAxisCount > 0) {
    warnings.push(`${offAxisCount} cylindrical face group(s) are not aligned to Z and were not proposed — the 2.5D recognizer only handles top-down holes.`);
  }

  /* ---- pocket / slot floors ---- */
  // Classification is exact-match or nothing. The floor boundary must fully
  // account for itself as one of three profiles; a boundary that does not is
  // reported by Z, never force-fitted into the nearest rectangle.
  const TOL = 2e-3;
  let pocketIndex = 0;
  for (const f of floors) {
    const depth = r4(topZ - f.z);
    const top = 0; // milled from the top face — stated in the rationale
    // An arc's center point is construction geometry the point sweep also
    // reaches — it is not part of the boundary and must not skew the extents.
    const boundary = f.pts.filter(
      (p) => !f.circles.some((c) => Math.abs(c.cx - p[0]) < 1e-3 && Math.abs(c.cy - p[1]) < 1e-3),
    );
    if (boundary.length === 0) continue;
    const xs = boundary.map((p) => p[0]);
    const ys = boundary.map((p) => p[1]);
    const w = Math.max(...xs) - Math.min(...xs);
    const l = Math.max(...ys) - Math.min(...ys);
    const fcx = (Math.max(...xs) + Math.min(...xs)) / 2;
    const fcy = (Math.max(...ys) + Math.min(...ys)) / 2;
    const radii = [...new Set(f.circles.map((c) => r4(c.r)))];

    // One circle set, extents match its diameter: circular pocket.
    if (radii.length === 1 && f.circles.length >= 1) {
      const rc = f.circles[0].r; // unrounded — r4 only at output
      const centers = dedupeXY(f.circles);
      if (centers.length === 1 && (w < TOL || Math.abs(w - 2 * rc) < TOL) && (l < TOL || Math.abs(l - 2 * rc) < TOL)) {
        pocketIndex++;
        suggestions.push({
          kind: "CIRC_POCKET",
          label: `⌀${r4(2 * rc).toFixed(4)} pocket ${pocketIndex}`,
          functionalRole: "NONE",
          critical: false,
          parameters: {
            centerX: r4(centers[0].cx - cx0), centerY: r4(centers[0].cy - cy0),
            diameter: r4(2 * rc), depth, through: false, top,
          },
          rationale:
            `Interior horizontal planar face at Z ${r4(f.z)} bounded by a single ⌀${r4(2 * rc).toFixed(4)}" circle. ` +
            `Depth ${depth.toFixed(4)}" measured from the top face, assuming the pocket is milled from the top — ` +
            `verify orientation on acceptance.`,
        });
        continue;
      }
      // Two circle centers of equal radius spanning the extents: slot.
      if (centers.length === 2 && Math.abs(Math.min(w, l) - 2 * rc) < TOL) {
        pocketIndex++;
        suggestions.push({
          kind: "SLOT",
          label: `${r4(2 * rc).toFixed(4)}" slot ${pocketIndex}`,
          functionalRole: "NONE",
          critical: false,
          parameters: {
            startX: r4(centers[0].cx - cx0), startY: r4(centers[0].cy - cy0),
            endX: r4(centers[1].cx - cx0), endY: r4(centers[1].cy - cy0),
            width: r4(2 * rc), depth, top,
          },
          rationale:
            `Interior horizontal planar face at Z ${r4(f.z)} bounded by two ⌀${r4(2 * rc).toFixed(4)}" end arcs — ` +
            `a full-radius slot. Depth ${depth.toFixed(4)}" from the top face; verify orientation on acceptance.`,
        });
        continue;
      }
    }

    // Rectangular floor: every bound vertex sits on the axis-aligned
    // perimeter; corner arcs, when present, share one radius.
    const rc = radii.length === 1 ? f.circles[0].r : radii.length === 0 ? 0 : null;
    const onPerimeter = (p: [number, number, number]) =>
      Math.abs(Math.abs(p[0] - fcx) - w / 2) < TOL || Math.abs(Math.abs(p[1] - fcy) - l / 2) < TOL;
    if (rc !== null && w > TOL && l > TOL && rc <= Math.min(w, l) / 2 + TOL && boundary.every(onPerimeter)) {
      pocketIndex++;
      suggestions.push({
        kind: "RECT_POCKET",
        label: `${r4(w).toFixed(3)} × ${r4(l).toFixed(3)} pocket ${pocketIndex}`,
        functionalRole: "NONE",
        critical: false,
        parameters: {
          centerX: r4(fcx - cx0), centerY: r4(fcy - cy0),
          width: r4(w), length: r4(l), cornerRadius: r4(rc), depth, top,
        },
        rationale:
          `Interior horizontal planar face at Z ${r4(f.z)} with a rectangular boundary ` +
          `${r4(w).toFixed(4)} × ${r4(l).toFixed(4)}"` +
          (rc > 0 ? ` and R${r4(rc).toFixed(4)}" corner arcs.` : ` with sharp corners as modelled.`) +
          ` Depth ${depth.toFixed(4)}" from the top face, assuming the pocket is milled from the top — ` +
          `verify orientation on acceptance.`,
      });
      continue;
    }

    warnings.push(
      `An interior horizontal face at Z ${r4(f.z)} (${f.pts.length} boundary vertices, ${f.circles.length} arcs) did not match a circular, slot or rectangular floor profile and was not proposed. The recognizer does not approximate boundaries it cannot account for.`,
    );
  }

  const recognized = planeCount + (cyls.length - [...unrecognizedCount.values()].reduce((a, b) => a + b, 0) >= 0 ? cyls.filter((c) => !c.offAxis).length : 0);
  const unrecognized = [...unrecognizedCount.entries()].map(([type, count]) => ({ type, count }));
  if (faces.length === 0) warnings.push("No ADVANCED_FACE entities — file may be a mesh export rather than a B-rep model.");

  return {
    partName,
    units,
    envelope,
    suggestions,
    surfaces: { recognized, total: faces.length },
    unrecognized,
    warnings,
  };
}

/* ---------------- helpers ---------------- */

function refEntity(e: StepFile["entities"], arg: StepEntity["args"][number] | undefined): StepEntity | null {
  const id = asRef(arg);
  return id === null ? null : (e.get(id) ?? null);
}

/** Every CARTESIAN_POINT reachable from an argument subtree, scaled. */
function collectPoints(
  e: StepFile["entities"],
  root: StepEntity["args"][number] | undefined,
  scale: number,
  visited: Set<number> = new Set(),
  out: [number, number, number][] = [],
  depth = 0,
): [number, number, number][] {
  if (!root || depth > 12) return out;
  if (root.kind === "LIST") {
    for (const item of root.items) collectPoints(e, item, scale, visited, out, depth + 1);
    return out;
  }
  if (root.kind !== "REF" || visited.has(root.id)) return out;
  visited.add(root.id);
  const ent = e.get(root.id);
  if (!ent) return out;
  if (ent.type === "CARTESIAN_POINT") {
    const c = asList(ent.args[1]).map(asNum);
    if (c.length === 3 && c.every((v) => v !== null)) out.push([c[0]! * scale, c[1]! * scale, c[2]! * scale]);
    return out;
  }
  for (const a of ent.args) collectPoints(e, a, scale, visited, out, depth + 1);
  return out;
}

/**
 * Every CIRCLE reachable from a face's bound subtree whose center sits on the
 * floor plane. Circles on other planes (a chamfered mouth, a wall feature)
 * belong to other faces' stories, not this floor's.
 */
function collectCircles(
  e: StepFile["entities"],
  root: StepEntity["args"][number] | undefined,
  scale: number,
  floorZ: number,
  visited: Set<number> = new Set(),
  out: { cx: number; cy: number; r: number }[] = [],
  depth = 0,
): { cx: number; cy: number; r: number }[] {
  if (!root || depth > 12) return out;
  if (root.kind === "LIST") {
    for (const item of root.items) collectCircles(e, item, scale, floorZ, visited, out, depth + 1);
    return out;
  }
  if (root.kind !== "REF" || visited.has(root.id)) return out;
  visited.add(root.id);
  const ent = e.get(root.id);
  if (!ent) return out;
  if (ent.type === "CIRCLE") {
    const placement = ent.args[1]?.kind === "REF" ? e.get((ent.args[1] as { id: number }).id) : null;
    const loc = placement && placement.args[1]?.kind === "REF" ? e.get((placement.args[1] as { id: number }).id) : null;
    const c = loc ? asList(loc.args[1]).map(asNum) : [];
    const r = asNum(ent.args[2]);
    if (c.length === 3 && c.every((v) => v !== null) && r !== null && Math.abs(c[2]! * scale - floorZ) < 1e-3) {
      out.push({ cx: c[0]! * scale, cy: c[1]! * scale, r: r * scale });
    }
    return out;
  }
  for (const a of ent.args) collectCircles(e, a, scale, floorZ, visited, out, depth + 1);
  return out;
}

/** Distinct circle centers in XY; STEP arcs often split one circle into halves. */
function dedupeXY(circles: { cx: number; cy: number; r: number }[]): { cx: number; cy: number }[] {
  const out: { cx: number; cy: number }[] = [];
  for (const c of circles) {
    if (!out.some((o) => Math.abs(o.cx - c.cx) < 1e-3 && Math.abs(o.cy - c.cy) < 1e-3)) out.push({ cx: c.cx, cy: c.cy });
  }
  return out;
}

const r4 = (v: number) => Number(v.toFixed(4));
