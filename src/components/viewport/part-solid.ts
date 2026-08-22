import * as THREE from "three";
import type { Feature, Stock } from "@/lib/domain/features";

/**
 * PART SOLID — real subtracted geometry for prismatic parts
 *
 * Until now the viewport drew a stock block with translucent volumes floating
 * where material had been removed. A bore was never a hole. Anybody who
 * machines things notices that in about three seconds, and it undermines
 * everything else CANVAS says about the part.
 *
 * This builds the actual solid. It does not use a CSG library — it exploits
 * the fact that a 3-axis part IS a stack of 2D cross-sections. Slice the part
 * at every Z where a feature starts or ends, work out the cross-section in
 * each slab (outer profile, minus every feature whose depth range spans that
 * slab), extrude it, and stack them. For 2.5D prismatic geometry this is not
 * an approximation of the shape — it is the shape.
 *
 * WHAT THIS HANDLES
 *   through and blind holes, bores, circular and rectangular pockets, slots,
 *   the outside contour, and facing off the top.
 *
 * WHAT IT DOES NOT
 *   chamfers, fillets, and anything with a non-vertical wall. Those need a
 *   real kernel, and a fake chamfer is worse than a missing one — it would
 *   show an edge break that the toolpath does not produce. They are skipped
 *   and the caller is told, rather than approximated.
 *
 * Everything is authored Z-up in part coordinates, matching the CAM engine.
 */

export interface PartSolid {
  geometry: THREE.BufferGeometry;
  /** Features that could not be represented, so the UI can say so. */
  unrepresented: { id: string; label: string; reason: string }[];
  /** Number of slabs the part was decomposed into. */
  layerCount: number;
}

interface Footprint {
  /** Adds this feature's cross-section as a hole in the given shape. */
  addTo: (shape: THREE.Shape) => void;
  /** Z range the feature removes material over, in part coordinates. */
  zTop: number;
  zBottom: number;
}

const EPS = 1e-4;

function circleHole(cx: number, cy: number, r: number): (shape: THREE.Shape) => void {
  return (shape) => {
    const path = new THREE.Path();
    path.absarc(cx, cy, r, 0, Math.PI * 2, true);
    shape.holes.push(path);
  };
}

function rectHole(cx: number, cy: number, w: number, h: number, radius = 0): (shape: THREE.Shape) => void {
  return (shape) => {
    const path = new THREE.Path();
    const x = cx - w / 2;
    const y = cy - h / 2;
    const r = Math.min(radius, w / 2, h / 2);
    if (r <= 0) {
      path.moveTo(x, y);
      path.lineTo(x + w, y);
      path.lineTo(x + w, y + h);
      path.lineTo(x, y + h);
    } else {
      // Corner radii matter here: a pocket cut with an end mill physically
      // cannot have a sharp internal corner, and drawing one would misrepresent
      // what the machine produces.
      path.moveTo(x + r, y);
      path.lineTo(x + w - r, y);
      path.absarc(x + w - r, y + r, r, -Math.PI / 2, 0, false);
      path.lineTo(x + w, y + h - r);
      path.absarc(x + w - r, y + h - r, r, 0, Math.PI / 2, false);
      path.lineTo(x + r, y + h);
      path.absarc(x + r, y + h - r, r, Math.PI / 2, Math.PI, false);
      path.lineTo(x, y + r);
      path.absarc(x + r, y + r, r, Math.PI, 1.5 * Math.PI, false);
    }
    path.closePath();
    shape.holes.push(path);
  };
}

/** Outer profile, honouring the finished contour when one is defined. */
function outerShape(stock: Stock, features: Feature[]): THREE.Shape {
  const contour = features.find((f) => f.kind === "OUTSIDE_CONTOUR");
  const w = contour && "width" in contour ? contour.width : stock.x;
  const h = contour && "length" in contour ? contour.length : stock.y;
  const r = contour && "cornerRadius" in contour ? contour.cornerRadius : 0;

  const shape = new THREE.Shape();
  const x = -w / 2;
  const y = -h / 2;
  const rad = Math.min(r, w / 2, h / 2);
  if (rad <= 0) {
    shape.moveTo(x, y);
    shape.lineTo(x + w, y);
    shape.lineTo(x + w, y + h);
    shape.lineTo(x, y + h);
  } else {
    shape.moveTo(x + rad, y);
    shape.lineTo(x + w - rad, y);
    shape.absarc(x + w - rad, y + rad, rad, -Math.PI / 2, 0, false);
    shape.lineTo(x + w, y + h - rad);
    shape.absarc(x + w - rad, y + h - rad, rad, 0, Math.PI / 2, false);
    shape.lineTo(x + rad, y + h);
    shape.absarc(x + rad, y + h - rad, rad, Math.PI / 2, Math.PI, false);
    shape.lineTo(x, y + rad);
    shape.absarc(x + rad, y + rad, rad, Math.PI, 1.5 * Math.PI, false);
  }
  shape.closePath();
  return shape;
}

export function buildPartSolid(stock: Stock, features: Feature[]): PartSolid {
  const unrepresented: { id: string; label: string; reason: string }[] = [];

  // Facing removes material off the top before anything else is referenced.
  const faceDepth = features
    .filter((f) => f.kind === "FACE")
    .reduce((sum, f) => sum + ("depth" in f ? f.depth : 0), 0);

  const partTop = stock.z - faceDepth;
  const partBottom = 0;

  /* ---- Reduce every feature to a footprint and a Z range ---- */

  const footprints: Footprint[] = [];

  for (const f of features) {
    switch (f.kind) {
      case "FACE":
      case "OUTSIDE_CONTOUR":
        // Already accounted for in the outer profile and the top surface.
        break;

      case "BORE":
      case "CIRC_POCKET": {
        const top = partTop + (f.top ?? 0);
        const bottom = f.through ? partBottom - 1 : top - f.depth;
        footprints.push({ addTo: circleHole(f.centerX, f.centerY, f.diameter / 2), zTop: top, zBottom: bottom });
        break;
      }

      case "DRILLED_HOLE":
      case "TAPPED_HOLE": {
        const top = partTop + (f.top ?? 0);
        const bottom = f.through ? partBottom - 1 : top - f.depth;
        footprints.push({ addTo: circleHole(f.centerX, f.centerY, f.diameter / 2), zTop: top, zBottom: bottom });
        break;
      }

      case "COUNTERBORE": {
        const top = partTop + (f.top ?? 0);
        const bottom = f.through ? partBottom - 1 : top - f.depth;
        footprints.push({ addTo: circleHole(f.centerX, f.centerY, f.diameter / 2), zTop: top, zBottom: bottom });
        if (f.headDiameter && f.headDepth) {
          footprints.push({
            addTo: circleHole(f.centerX, f.centerY, f.headDiameter / 2),
            zTop: top,
            zBottom: top - f.headDepth,
          });
        }
        break;
      }

      case "RECT_POCKET": {
        const top = partTop + (f.top ?? 0);
        footprints.push({
          addTo: rectHole(f.centerX, f.centerY, f.width, f.length, f.cornerRadius),
          zTop: top,
          zBottom: top - f.depth,
        });
        break;
      }

      case "SLOT": {
        const top = partTop + (f.top ?? 0);
        const dx = f.endX - f.startX;
        const dy = f.endY - f.startY;
        const len = Math.hypot(dx, dy);
        // A slot is an obround. Approximating it as a rectangle of the same
        // extent is close enough for the ends to read correctly at this scale,
        // and the corner radius is the cutter radius, which is exact.
        const cx = (f.startX + f.endX) / 2;
        const cy = (f.startY + f.endY) / 2;
        if (Math.abs(dy) < EPS) {
          footprints.push({
            addTo: rectHole(cx, cy, len + f.width, f.width, f.width / 2),
            zTop: top,
            zBottom: top - f.depth,
          });
        } else if (Math.abs(dx) < EPS) {
          footprints.push({
            addTo: rectHole(cx, cy, f.width, len + f.width, f.width / 2),
            zTop: top,
            zBottom: top - f.depth,
          });
        } else {
          unrepresented.push({
            id: f.id,
            label: f.label,
            reason: "Angled slots are not represented in the solid — the cross-section builder works on axis-aligned footprints.",
          });
        }
        break;
      }

      case "COUNTERSINK":
      case "CHAMFER":
      case "FILLET":
        unrepresented.push({
          id: f.id,
          label: f.label,
          reason:
            "Non-vertical walls need a geometry kernel. Drawing an approximate edge break would show a finish this builder cannot derive from the stored parameters — the operation, where one is planned, still appears in the plan.",
        });
        break;

      default:
        break;
    }
  }

  /* ---- Slice at every Z boundary ---- */

  const boundaries = new Set<number>([partBottom, partTop]);
  for (const fp of footprints) {
    if (fp.zTop < partTop - EPS && fp.zTop > partBottom + EPS) boundaries.add(fp.zTop);
    if (fp.zBottom < partTop - EPS && fp.zBottom > partBottom + EPS) boundaries.add(fp.zBottom);
  }

  const levels = [...boundaries].sort((a, b) => a - b);

  // Collapse consecutive slabs that cut the same set of features. Without this
  // a part with several features at the same depth is split into slabs that
  // are geometrically identical, which is wasted triangles and extra internal
  // faces for no gain.
  const slabs: { zLow: number; zHigh: number; active: Footprint[] }[] = [];
  for (let i = 0; i < levels.length - 1; i++) {
    const zLow = levels[i];
    const zHigh = levels[i + 1];
    if (zHigh - zLow <= EPS) continue;
    const mid = (zLow + zHigh) / 2;
    const active = footprints.filter((fp) => fp.zTop > mid && fp.zBottom < mid);
    const prev = slabs[slabs.length - 1];
    const sameAsPrev =
      prev && prev.active.length === active.length && prev.active.every((fp) => active.includes(fp));
    if (sameAsPrev) prev.zHigh = zHigh;
    else slabs.push({ zLow, zHigh, active });
  }

  // Slabs are extruded slightly into the one below. Butted exactly, the cap of
  // one slab and the cap of the next are coplanar, and the renderer has no way
  // to choose between them — which shows up as a shimmering line across the
  // face of the part. Overlapping buries those faces inside solid material
  // where they cannot be seen. The overlap is an order of magnitude below any
  // dimension CANVAS reports, so nothing measurable changes.
  const OVERLAP = 0.002;

  const geometries: THREE.BufferGeometry[] = [];
  for (let i = 0; i < slabs.length; i++) {
    const { zLow, zHigh, active } = slabs[i];
    const overlap = i === 0 ? 0 : OVERLAP;
    const shape = outerShape(stock, features);
    for (const fp of active) fp.addTo(shape);

    const geom = new THREE.ExtrudeGeometry(shape, {
      depth: zHigh - zLow + overlap,
      bevelEnabled: false,
      curveSegments: 48,
    });
    geom.translate(0, 0, zLow - overlap);
    geometries.push(geom);
  }

  if (geometries.length === 0) {
    // No usable geometry — fall back to the plain stock block rather than
    // rendering nothing.
    const box = new THREE.BoxGeometry(stock.x, stock.y, stock.z);
    box.translate(0, 0, stock.z / 2);
    return { geometry: box, unrepresented, layerCount: 0 };
  }

  const merged = mergeGeometries(geometries);
  merged.computeVertexNormals();
  computeMachiningTangents(merged);

  return { geometry: merged, unrepresented, layerCount: geometries.length };
}

/**
 * A tangent frame aligned to one machining direction.
 *
 * WHY THIS IS NOT `computeTangents()`. Three's helper derives tangents from
 * the UV parameterisation, and this geometry has no UVs to derive them from:
 * `mergeGeometries` below concatenates position and normal only, and the
 * ExtrudeGeometry UVs are dropped on the way in. Without a tangent attribute
 * the material's `anisotropy` runs on a degenerate frame, which is not a
 * subtle error — measured on the seeded plate it clipped the top face to
 * rgb(255,255,255) and crushed the side walls to rgb(0,0,0).
 *
 * WHAT IT CLAIMS. Anisotropy is what makes a milled face look milled: the
 * highlight smears along the cutter marks. The honest version of that here is
 * ONE consistent direction, because CANVAS does not know the real feed
 * direction per face — the solid is merged slabs with no per-operation
 * channel, so a tangent field pretending to follow each operation's actual
 * cut would be invented. Each vertex gets the fixed world direction projected
 * onto its own surface plane, so every face carries a valid frame and the
 * smear runs the same way across the part.
 *
 * Faces whose normal is parallel to the reference direction get the fallback
 * axis instead, which is the standard degenerate-case handling — without it
 * those faces would receive a zero-length tangent and render as the same
 * blown-out garbage this function exists to prevent.
 */
function computeMachiningTangents(geometry: THREE.BufferGeometry): void {
  const pos = geometry.getAttribute("position");
  const nor = geometry.getAttribute("normal");
  if (!pos || !nor) return;

  const REFERENCE = new THREE.Vector3(1, 0, 0);
  const FALLBACK = new THREE.Vector3(0, 1, 0);
  const n = new THREE.Vector3();
  const t = new THREE.Vector3();
  // vec4: xyz tangent, w handedness. Uniform +1 — there is no UV winding to
  // disagree with, so bitangents are consistently n × t.
  const tangents = new Float32Array(pos.count * 4);

  for (let i = 0; i < pos.count; i++) {
    n.set(nor.getX(i), nor.getY(i), nor.getZ(i)).normalize();
    // Gram-Schmidt: the reference direction with its normal component removed.
    t.copy(REFERENCE).addScaledVector(n, -REFERENCE.dot(n));
    if (t.lengthSq() < 1e-8) {
      t.copy(FALLBACK).addScaledVector(n, -FALLBACK.dot(n));
    }
    t.normalize();
    tangents[i * 4] = t.x;
    tangents[i * 4 + 1] = t.y;
    tangents[i * 4 + 2] = t.z;
    tangents[i * 4 + 3] = 1;
  }

  geometry.setAttribute("tangent", new THREE.BufferAttribute(tangents, 4));
}

/**
 * Concatenates the slab geometries into one buffer.
 *
 * Written out rather than pulled from three's BufferGeometryUtils so the
 * viewport does not depend on an addon path that has moved between three
 * versions more than once.
 */
function mergeGeometries(geoms: THREE.BufferGeometry[]): THREE.BufferGeometry {
  const positions: number[] = [];
  const normals: number[] = [];

  for (const g of geoms) {
    const nonIndexed = g.index ? g.toNonIndexed() : g;
    const pos = nonIndexed.getAttribute("position");
    const nor = nonIndexed.getAttribute("normal");
    for (let i = 0; i < pos.count; i++) {
      positions.push(pos.getX(i), pos.getY(i), pos.getZ(i));
      if (nor) normals.push(nor.getX(i), nor.getY(i), nor.getZ(i));
    }
    if (nonIndexed !== g) nonIndexed.dispose();
    g.dispose();
  }

  const out = new THREE.BufferGeometry();
  out.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  if (normals.length === positions.length) {
    out.setAttribute("normal", new THREE.Float32BufferAttribute(normals, 3));
  }
  return out;
}
