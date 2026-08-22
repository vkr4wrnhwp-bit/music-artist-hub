import "server-only";
import type { ManufacturingPackage } from "@/lib/package";
import type { JawBlank } from "@/lib/domain/shop";
import type { SoftJawRequest } from "@/lib/engines/workholding";
import { selectWorkholdingDevice } from "./package-selectors";

/**
 * ONE assembler for the soft-jaw request.
 *
 * The soft-jaws page, its save action and the DXF export all need the same
 * request built from the same package. Three inline copies is how the
 * drawing a machinist downloads stops matching the jaws the page shows —
 * the measurementGeometry lesson, applied to fixtures.
 */

export interface SoftJawParams {
  setupId?: string | null;
  grip?: number | null;
  allowance?: number | null;
  clearance?: number | null;
  includeStop?: boolean | null;
  dir?: string | null;
}

export function assembleSoftJawRequest(
  pkg: ManufacturingPackage,
  blank: JawBlank | null,
  params: SoftJawParams,
): { request: SoftJawRequest; setupId: string; setupName: string } | null {
  const setup =
    pkg.setups.find((s) => s.id === params.setupId) ??
    pkg.setups.find((s) => s.sequence > 1) ??
    pkg.setups[0];
  const device = selectWorkholdingDevice(pkg.workholdingDevices, setup);
  if (!setup || !device || !blank || !pkg.revision.stock) return null;

  const stock = pkg.revision.stock;
  const contour = pkg.revision.features.find((f) => f.kind === "OUTSIDE_CONTOUR");
  const partWidth = contour && "width" in contour ? (contour.width as number) : stock.x;
  const partLength = contour && "length" in contour ? (contour.length as number) : stock.y;
  const cornerRadius = contour && "cornerRadius" in contour ? (contour.cornerRadius as number) : 0.25;

  return {
    setupId: setup.id,
    setupName: setup.name,
    request: {
      device,
      blank,
      partWidth,
      partLength,
      partHeight: stock.z,
      desiredGrip: params.grip ?? 0.15,
      jawAllowance: params.allowance ?? 0.01,
      clearance: params.clearance ?? 0.03,
      includeStop: params.includeStop ?? true,
      clampingDirection: params.dir === "Y" ? "Y" : "X",
      cornerRadius,
    },
  };
}
