/**
 * A DRILL DOES NOT MAKE A HOLE AS DEEP AS IT GOES.
 *
 * `depthOf` returns `stock.z` for a feature marked `through`, and the drill
 * operation went to exactly that Z. A twist drill is ground to a point: the
 * full diameter is reached a point-length behind the tip, so a ⌀0.201″ jobber
 * drill at 118° reaches full diameter 0.060″ up from where its tip stopped.
 *
 * Drilled to exactly the stock thickness, every through hole on the part comes
 * off the machine with a cone of material still in the bottom of it. It looks
 * finished on the setup sheet, it looks finished in the plan, and it fails
 * inspection on the first part — or worse, it does not, because the operator
 * pushed the drill through by hand and nobody recorded that the program was
 * short.
 *
 * WHY THE POINT ANGLE IS REQUIRED RATHER THAN ASSUMED
 *
 * 118° is the jobber grind and 135° is the split point, and they differ by a
 * quarter of the point length on the same diameter. There is no safe direction
 * to guess in: too shallow leaves the cone, too deep drills the parallels. So a
 * THROUGH hole with no point angle on its drill is refused and the message
 * names the field. A hole with a recorded depth is untouched — that depth is
 * the drawing's and it is measured to the shoulder, not to the point.
 */

/**
 * How far past the full diameter to run, so the burr breaks clean and a stock
 * thickness that came off the saw a few thou heavy still goes through.
 *
 * A stated process allowance, not a derived one — which is why the operation's
 * own rationale prints it rather than burying it in the Z.
 */
export const BREAKOUT_CLEARANCE = 0.02;

export interface DrillPoint {
  /** Tip to full diameter. Zero for a flat-bottom tool. */
  pointLength: number;
  /** How far past the bottom of the material the tip has to go. */
  breakthrough: number;
}

export interface DrillPointRefusal {
  reason: string;
  recommendations: string[];
}

/**
 * The point on a drill of this diameter, ground at this included angle.
 *
 * Half the included angle is the flank's angle off the axis, so the point
 * stands (D/2) / tan(half) above the tip.
 */
export function drillPoint(
  tool: { diameter: number; pointAngle?: number; description: string },
): DrillPoint | { error: DrillPointRefusal } {
  if (tool.pointAngle == null) {
    return {
      error: {
        reason: `${tool.description} has no point angle recorded, and a through hole has to be drilled past the material by the length of the drill's own point. 118° and 135° differ by a quarter of that length on the same drill, and there is no safe direction to guess in.`,
        recommendations: [
          "Record the point angle on the drill — 118° is the jobber grind, 135° the split point",
          "Give the hole a recorded depth instead, if it is not actually through",
        ],
      },
    };
  }
  // 180° is allowed: that is a flat-bottom tool, and it has no point at all.
  if (!(tool.pointAngle > 0 && tool.pointAngle <= 180)) {
    return {
      error: {
        reason: `${tool.description} records a ${tool.pointAngle}° point, which is not an angle a drill point can have.`,
        recommendations: ["Record the INCLUDED angle at the point — the full angle, not half of it"],
      },
    };
  }
  const half = (tool.pointAngle / 2) * (Math.PI / 180);
  const pointLength = tool.pointAngle === 180 ? 0 : tool.diameter / 2 / Math.tan(half);
  return { pointLength, breakthrough: pointLength + BREAKOUT_CLEARANCE };
}
