import type { StockDims } from "./stock-removal";

/**
 * THE VISE, AS GEOMETRY THE SIMULATOR CAN HIT
 *
 * The CUT view simulated stock removal and holder-vs-stock contact and
 * modelled no fixture at all, while the Simulation row it wrote set
 * `collisionChecked: true` — a flag whose own schema comment says it exists
 * so no consumer can mistake a visualisation for a verification.
 *
 * This builds the jaws as two boxes in part coordinates so the cutter can be
 * checked against them. It is a PARAMETRIC APPROXIMATION of a vise, not the
 * fixture's geometry: it is built from four recorded numbers and the
 * assumptions below, all of which are returned with the model so the UI can
 * state them rather than imply a solve.
 *
 * It returns null rather than a guess whenever a datum is missing. The one
 * that matters most is the jaw axis: put the jaws on the wrong two faces and
 * the check clears exactly the setup that would crash.
 */

export type JawAxis = "X" | "Y";

export interface FixtureModel {
  axis: JawAxis;
  /** Top of the jaws, in part coordinates — Z=0 is the top of the stock. */
  topZ: number;
  /**
   * Half-extent of the stock along the closing axis. The jaw faces sit
   * against the stock faces, so the jaw bodies occupy everything beyond this.
   */
  stockHalf: number;
  /** Half-width of the jaw across the other axis, centred on the part. */
  halfWidth: number;
  /** How far each jaw body extends outward from the stock face. */
  outward: number;
  assumptions: string[];
}

export interface FixtureInput {
  jawAxis: string | null;
  jawWidth: number | null;
  jawHeight: number | null;
  /** Stock standing proud of the jaws, inches. */
  stockProjection: number | null;
  gripDepth: number | null;
  stock: StockDims | null;
}

/** Why no fixture could be built — named, so the UI can ask for the number. */
export type FixtureGap = { missing: string; consequence: string };

export function buildFixture(input: FixtureInput): { fixture: FixtureModel } | { fixture: null; gap: FixtureGap } {
  if (input.jawAxis !== "X" && input.jawAxis !== "Y") {
    return {
      fixture: null,
      gap: {
        missing: "the axis the jaws close on",
        consequence:
          "Without it the vise could be modelled across either pair of faces. Guessing puts it on the wrong two, and a fixture in the wrong place clears the setup that would crash.",
      },
    };
  }
  if (!input.stock) {
    return { fixture: null, gap: { missing: "the stock size", consequence: "The jaw faces are located from the stock faces." } };
  }
  if (input.jawWidth == null || input.jawWidth <= 0) {
    return {
      fixture: null,
      gap: { missing: "the jaw width", consequence: "The jaw footprint across the part is what decides whether a move passes over the jaw or beside it." },
    };
  }

  // Same derivation the pre-flight review uses: the part sits on parallels,
  // so what stands proud of the jaws plus what is gripped is the stock
  // height. stockProjection is preferred because it is measured directly.
  const topZ =
    input.stockProjection != null
      ? -input.stockProjection
      : input.gripDepth != null
        ? input.gripDepth - input.stock.z
        : null;
  if (topZ == null) {
    return {
      fixture: null,
      gap: {
        missing: "how much stock stands proud of the jaws",
        consequence: "Without it there is no jaw top, and jaw top is the height every clearance answer is measured against.",
      },
    };
  }

  const stockHalf = (input.jawAxis === "X" ? input.stock.x : input.stock.y) / 2;

  return {
    fixture: {
      axis: input.jawAxis,
      topZ,
      stockHalf,
      halfWidth: input.jawWidth / 2,
      // The jaw body beyond the stock face. A jaw is deeper than any cutter
      // will travel past the part before it has already hit the face, so this
      // is generous on purpose: the question this answers is "is the tool
      // out over the jaw", not "how far into the jaw".
      outward: Math.max(1, input.jawHeight ?? 1),
      assumptions: [
        "The vise is modelled as two boxes, not as the fixture's geometry. Screws, handles, jaw plates and the vise body below the jaws are not in it.",
        "The jaws are taken as centred on the part across their width.",
        "The jaw faces are taken as flush with the stock faces, so nothing inside the stock outline can contact a jaw.",
        "Soft jaws machined with a pocket are not modelled — a part nested into soft jaws sits lower than this assumes.",
      ],
    },
  };
}

/**
 * Is a cutter of this radius, with its tip at this height, inside a jaw?
 *
 * Part coordinates throughout: Z=0 at the top of the stock, negative down.
 * Nothing above the jaw top can contact, and nothing within the stock
 * outline can, because the jaw faces are flush with the stock faces.
 */
export function cutterHitsJaw(f: FixtureModel, x: number, y: number, tipZ: number, radius: number): boolean {
  if (tipZ >= f.topZ) return false;
  const along = f.axis === "X" ? x : y;
  const across = f.axis === "X" ? y : x;
  // The cutter is a cylinder: its outermost point along the closing axis is
  // what reaches the jaw first.
  const reach = Math.abs(along) + radius;
  if (reach <= f.stockHalf) return false;
  if (Math.abs(along) - radius > f.stockHalf + f.outward) return false;
  return Math.abs(across) - radius < f.halfWidth;
}
