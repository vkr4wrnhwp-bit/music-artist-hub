/**
 * THE ONE PLACE PART-Z BECOMES SCENE-Z.
 *
 * The part coordinate convention is Z=0 at the top of the stock, cuts
 * negative, clearance positive. The scene draws the solid with its bottom on
 * local 0 and its top face on local `stock.z` (part-solid.ts translates the
 * box by `stock.z / 2` to put it there), and the enclosing group carries the
 * `-stock.z / 2` that centres the whole part on the origin.
 *
 * That offset was being applied twice. The toolpath, the tool marker and the
 * whole simulation rig each added their own `stock.z / 2`, so they drew half a
 * stock height BELOW the solid, the features, the datum indicator and the
 * floor. On the seeded 0.750" plate a move at Z0 — touching the top of the
 * stock — rendered 0.375" inside the material, and a rapid at Z+0.100, a
 * tenth of an inch of clearance ABOVE the part, still rendered 0.275" under
 * its top face.
 *
 * A machinist looking at the CUT view saw a toolpath buried in the solid. That
 * is not a cosmetic offset: clearance is the thing you look at a toolpath to
 * check.
 *
 * Two functions, used by everything that draws in the part's frame, so the
 * convention cannot be half-applied again.
 */

/** Local scene Z for a point at `partZ` in part coordinates. */
export function sceneZ(stockZ: number, partZ: number): number {
  return stockZ + partZ;
}

/** Local scene Z of the top face of the stock — where part Z is zero. */
export function stockTopZ(stockZ: number): number {
  return stockZ;
}

/** Local scene Z of the bottom of the stock. */
export const STOCK_BOTTOM_Z = 0;
