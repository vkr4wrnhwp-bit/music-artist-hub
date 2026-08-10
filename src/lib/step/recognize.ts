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
 * What this deliberately is NOT, in Phase 1:
 * - Not a B-rep kernel. Pockets, slots, bosses, fillets and freeform surfaces
 *   are reported as unrecognized, not approximated.
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
  let planeCount = 0;

  for (const face of faces) {
    const surf = face.args[2]?.kind === "REF" ? e.get((face.args[2] as { id: number }).id) : null;
    if (!surf) continue;
    if (surf.type === "PLANE") { planeCount++; continue; }
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

const r4 = (v: number) => Number(v.toFixed(4));
