import type { Chain } from "./chain";
import type { ChamferFeature, Feature } from "@/lib/domain/features";
import type { Tool } from "@/lib/domain/shop";
import { rectangleChain } from "./chain";

/**
 * WHERE A CHAMFER MILL HAS TO BE TO CUT THE CHAMFER ON THE DRAWING.
 *
 * `chamferToolpath` ignored `feature.width` and `feature.angle` entirely. It
 * walked a rectangle around the STOCK outline — not the part — at a hard-coded
 * `R0.1` corner, at whatever Z the planner happened to put in the operation,
 * with a tool whose point angle nothing in the system recorded. A 0.030 × 45°
 * chamfer and a 0.005 × 60° chamfer produced the identical path. And where the
 * feature applied to HOLES it emitted a rapid, a plunge and a retract at X0 Y0
 * and nothing else — three moves at the origin, `isPlaceholder: false`, no
 * warning, and the pre-flight counted it as an operation that produced motion.
 *
 * That is the shape locked principle 5 is about. A button that appears to cut
 * a chamfer and does not is a lie the operator acts on, and this one was worse
 * than a stub, because a stub says so.
 *
 * THE GEOMETRY
 *
 * A chamfer mill is a cone. Its flank sits at the half of its included angle
 * from the axis, and that flank is the chamfer surface — so **the tool decides
 * the angle, and the depth and offset decide only the width**. A 90° chamfer
 * mill has a 45° flank and cuts 45° chamfers. It cannot cut a 30° chamfer at
 * any depth or any offset: the required tool is one with a 120° included angle,
 * and this refuses and says so rather than cutting a 45° chamfer of the right
 * width and calling it done.
 *
 * Working in the plane normal to the edge, with the top face at Z0 and the
 * boundary at radius R, a chamfer of horizontal width W at angle A from the
 * face runs from (R − W, 0) down to (R, −W·tan A). Setting the cone's flank on
 * that line, with the tip clearing the bottom of the chamfer by `c` so the dead
 * centre of the tool is not the cutting point:
 *
 *     Z of the tip     = −(W·tan A + c)
 *     radial offset    = tipRadius + c / tan A
 *
 * — measured from the finished boundary, OUTWARD for an outside edge and
 * INWARD for a pocket or a hole, and by symmetry it is the same number both
 * ways. Below the chamfer the tool clears the wall by c / tan A, which is what
 * `c` buys besides keeping the dead centre out of the cut.
 *
 * At 45° with a small tip flat the offset is a few thou, which is the familiar
 * result — the cutter centre rides just off the part line — but it is derived
 * here rather than assumed, and it is right at every other angle too.
 */

/** Below the bottom of the chamfer, so the tool's dead centre is out of the cut. */
export const TIP_CLEARANCE = 0.01;

/** How far the tool's own angle may differ from the drawing's, in degrees. */
const ANGLE_TOLERANCE = 0.5;

export interface ChamferGeometry {
  /** Tool Z at the bottom of the pass. Negative, below the top face. */
  z: number;
  /**
   * Cutter-centre offset from the finished boundary. Always positive: added to
   * an outside profile, subtracted from a pocket or a hole.
   */
  offset: number;
  /** Cone radius at a height above the tip — how the hole cases are solved. */
  radiusAt: (heightAboveTip: number) => number;
  /** Flat on the end of the tool. */
  tipRadius: number;
  /** tan of the chamfer angle, so callers do not re-derive it. */
  tanAngle: number;
  /** Included angle the tool has to have, for the message when it does not. */
  requiredIncludedAngle: number;
  /** Vertical leg of the chamfer — what it takes off the wall. */
  drop: number;
}

export interface ChamferRefusal {
  reason: string;
  recommendations: string[];
}

/** What a chamfer needs to know about the cone that cuts it. */
export interface ChamferTool {
  /** INCLUDED angle at the point, degrees. */
  pointAngle?: number;
  /** Flat ground on the end, inches. */
  tipDiameter?: number;
  description: string;
  diameter: number;
}

export function chamferGeometry(
  feature: ChamferFeature,
  tool: ChamferTool,
): ChamferGeometry | { error: ChamferRefusal } {
  const w = feature.width;
  if (!(w > 0)) {
    return {
      error: {
        reason: `${feature.label} records no chamfer width, so there is no size to cut to.`,
        recommendations: ["Record the chamfer width from the drawing", "A break-edge is still a width — 0.005 × 45° is a number"],
      },
    };
  }

  const a = feature.angle;
  if (!(a > 0 && a < 90)) {
    return {
      error: {
        reason: `${feature.label} records a ${a}° chamfer angle, which is not an angle a chamfer can have.`,
        recommendations: ["Record the angle from the drawing, measured off the face — 45° is the usual"],
      },
    };
  }

  // The tool's own geometry. Nothing is assumed: a chamfer mill with no point
  // angle recorded is a cone of unknown angle, and guessing 90° would cut a
  // 45° chamfer with a tool that might be ground at 60°.
  const missing: string[] = [];
  if (tool.pointAngle == null) missing.push("point angle");
  if (tool.tipDiameter == null) missing.push("tip diameter");
  if (missing.length > 0) {
    return {
      error: {
        reason: `${tool.description} has no ${missing.join(" or ")} recorded, and a chamfer is cut by the tool's cone. Without it there is no way to know what angle this tool cuts or where its edge is.`,
        recommendations: [
          `Record the ${missing.join(" and ")} on the tool — it is on the catalogue page and stamped on most shanks`,
          "The included angle is the full angle at the point: 90 for a 90° chamfer mill",
        ],
      },
    };
  }

  // The flank angle IS the chamfer angle. A chamfer at A° off the face needs a
  // flank A° off the face, which is (90 − A)° off the axis, which is an
  // included angle of 2(90 − A).
  const required = 2 * (90 - a);
  const flank = tool.pointAngle! / 2;
  if (Math.abs(90 - flank - a) > ANGLE_TOLERANCE) {
    return {
      error: {
        reason: `${tool.description} is ground at ${tool.pointAngle}° included, so its flank cuts a ${(90 - flank).toFixed(1)}° chamfer. ${feature.label} is ${a}°. The angle of a chamfer is the angle of the cone that cuts it — no depth or offset changes it.`,
        recommendations: [
          `Use a ${required.toFixed(0)}° included chamfer mill`,
          `Change the drawing to ${(90 - flank).toFixed(1)}° if the angle is not functional`,
        ],
      },
    };
  }

  const tanA = Math.tan((a * Math.PI) / 180);
  const tipRadius = tool.tipDiameter! / 2;
  const drop = w * tanA;
  return {
    z: -(drop + TIP_CLEARANCE),
    offset: tipRadius + TIP_CLEARANCE / tanA,
    // The cone widens going up from the tip at the flank angle, which is the
    // complement of the chamfer angle: 1 / tan A per unit of height.
    radiusAt: (h: number) => tipRadius + h / tanA,
    tipRadius,
    tanAngle: tanA,
    requiredIncludedAngle: required,
    drop,
  };
}

/**
 * THE EDGE THE CHAMFER RUNS ALONG.
 *
 * A chamfer is not a shape of its own — it breaks the edge of something else,
 * and which something is `applyTo` plus `targetFeatureId`. The old code rang
 * the STOCK outline, which is the one boundary that is definitely not the part:
 * on the seeded bearing support that is 6 × 4 while the finished profile is
 * 5.5 × 3.5, so the chamfer pass cut air a quarter of an inch outside the part
 * for its entire length.
 */
export type ChamferEdge =
  | { kind: "BOUNDARY"; chain: Chain; label: string }
  | {
      kind: "POCKET";
      pocket: { centerX: number; centerY: number; width: number; length: number; cornerRadius: number; label: string };
    }
  | { kind: "HOLES"; holes: { x: number; y: number; diameter: number; label: string }[] };

export function chamferEdge(feature: ChamferFeature, features: Feature[]): ChamferEdge | { error: ChamferRefusal } {
  const target = feature.targetFeatureId ? features.find((f) => f.id === feature.targetFeatureId) ?? null : null;

  if (feature.applyTo === "HOLES") {
    const pool = target ? [target] : features;
    const holes = pool
      .filter((f) => f.kind === "DRILLED_HOLE" || f.kind === "TAPPED_HOLE" || f.kind === "BORE")
      .map((f) => ({
        x: "centerX" in f ? f.centerX : 0,
        y: "centerY" in f ? f.centerY : 0,
        diameter: "diameter" in f && typeof f.diameter === "number" ? f.diameter : 0,
        label: f.label,
      }))
      .filter((h) => h.diameter > 0);
    if (holes.length === 0) {
      return {
        error: {
          reason: `${feature.label} chamfers holes, and there are no holes with a recorded diameter for it to break.`,
          recommendations: ["Point the chamfer at a hole feature", "Record the diameter on the holes it applies to"],
        },
      };
    }
    return { kind: "HOLES", holes };
  }

  if (feature.applyTo === "POCKET") {
    const pocket = target ?? features.find((f) => f.kind === "RECT_POCKET") ?? null;
    if (!pocket || pocket.kind !== "RECT_POCKET") {
      return {
        error: {
          reason: `${feature.label} chamfers a pocket edge, and no pocket on this part is named as the one it breaks.`,
          recommendations: ["Point the chamfer at the pocket it applies to"],
        },
      };
    }
    return {
      kind: "POCKET",
      pocket: {
        centerX: pocket.centerX,
        centerY: pocket.centerY,
        width: pocket.width,
        length: pocket.length,
        cornerRadius: pocket.cornerRadius,
        label: pocket.label,
      },
    };
  }

  // OUTSIDE_TOP / OUTSIDE_BOTTOM — the finished profile, not the stock.
  const contour = (target ?? features.find((f) => f.kind === "OUTSIDE_CONTOUR")) ?? null;
  if (!contour || contour.kind !== "OUTSIDE_CONTOUR") {
    return {
      error: {
        reason: `${feature.label} breaks the outside edge, and this part records no outside profile — so the only boundary available is the stock, which is not the part.`,
        recommendations: [
          "Add the outside profile as a feature",
          "Point the chamfer at the boundary it breaks",
        ],
      },
    };
  }
  return {
    kind: "BOUNDARY",
    chain:
      contour.chain && contour.chainStart
        ? { start: contour.chainStart, segments: contour.chain }
        : rectangleChain(contour.width, contour.length, contour.cornerRadius),
    label: contour.label,
  };
}
