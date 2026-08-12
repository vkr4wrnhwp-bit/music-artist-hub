import type { Feature } from "@/lib/domain/features";
import type { ProtectedRegion } from "./load";

/**
 * FINISH-PASS PROTECTION — regions built deterministically from the part's
 * own features. No AI, no comment parsing: a feature earns protection from
 * recorded engineering facts —
 *
 *   - marked critical, or
 *   - total tolerance band ≤ 0.001", or
 *   - surface finish ≤ 32 Ra, or
 *   - a functional role that IS a finish surface (bearing, seal, thread), or
 *   - a tapped hole (the thread is the feature).
 *
 * The region is the feature's footprint plus a tool allowance, over the
 * feature's own Z span. Cutting inside it never receives an automatic
 * proposal in either direction; overriding protection is a separate,
 * audited human act (not built in V1 — protection is absolute for now,
 * and the docs say so).
 *
 * Z convention matches the analyzer's stated assumption: program Z0 =
 * stock top, depths negative downward.
 */

const PROTECTED_ROLES = new Set([
  "BEARING_SEAT",
  "BEARING_BORE",
  "SEAL_SURFACE",
  "SEALING_SURFACE",
  "THREAD",
  "DOWEL_HOLE",
  "LOCATING_BORE",
]);
const TOOL_ALLOWANCE = 0.15; // in — the cutter cutting the wall stands off by its radius
const TIGHT_TOL = 0.001;
const FINE_FINISH_RA = 32;

function needsProtection(f: Feature): string | null {
  if (f.critical) return "Marked critical";
  const tol = f.tolerance ? Math.abs(f.tolerance.plus) + Math.abs(f.tolerance.minus) : null;
  if (tol !== null && tol <= TIGHT_TOL) return `Tolerance band ${tol.toFixed(4)}"`;
  if (f.surfaceFinish !== undefined && f.surfaceFinish <= FINE_FINISH_RA) return `${f.surfaceFinish} Ra surface`;
  if (PROTECTED_ROLES.has(f.functionalRole)) return `Functional role ${f.functionalRole.replace(/_/g, " ").toLowerCase()}`;
  if (f.kind === "TAPPED_HOLE") return "Threaded feature";
  return null;
}

export function buildProtectedRegions(features: Feature[]): ProtectedRegion[] {
  const regions: ProtectedRegion[] = [];
  for (const f of features) {
    const reason = needsProtection(f);
    if (!reason) continue;
    let centerX: number | null = null;
    let centerY: number | null = null;
    let radius = 0;
    let top = 0;
    let depth = 0;

    if (f.kind === "CIRC_POCKET" || f.kind === "BORE") {
      centerX = f.centerX; centerY = f.centerY;
      radius = f.diameter / 2 + TOOL_ALLOWANCE;
      top = f.top; depth = f.depth;
    } else if (f.kind === "DRILLED_HOLE" || f.kind === "TAPPED_HOLE" || f.kind === "COUNTERBORE" || f.kind === "COUNTERSINK") {
      centerX = f.centerX; centerY = f.centerY;
      radius = f.diameter / 2 + TOOL_ALLOWANCE;
      top = f.top; depth = f.depth;
    } else if (f.kind === "RECT_POCKET") {
      centerX = f.centerX; centerY = f.centerY;
      radius = Math.hypot(f.width, f.length) / 2 + TOOL_ALLOWANCE;
      top = f.top; depth = f.depth;
    } else if (f.kind === "SLOT") {
      centerX = (f.startX + f.endX) / 2; centerY = (f.startY + f.endY) / 2;
      radius = Math.hypot(f.endX - f.startX, f.endY - f.startY) / 2 + f.width / 2 + TOOL_ALLOWANCE;
      top = f.top; depth = f.depth;
    } else {
      // FACE / CONTOUR / others: no bounded XY footprint to protect honestly.
      continue;
    }

    regions.push({
      label: f.label,
      reason,
      centerX,
      centerY,
      radius: Number(radius.toFixed(4)),
      zTop: -top,
      zBottom: -(top + depth),
    });
  }
  return regions;
}
