import type { Feature, Stock } from "./features";

/**
 * A BOLT CIRCLE IS ONE STATEMENT ON A DRAWING AND SIX FEATURES ON A PART.
 *
 * Every hole in a pattern had to be typed in by hand, one at a time, with its
 * coordinates worked out off the machine. Six holes on a 3.000" bolt circle is
 * twelve numbers to compute and twelve to mistype, on the most common thing
 * there is on a plate — and a hole entered at the wrong angle is a hole that
 * gets drilled in the wrong place and measures perfectly on its own diameter.
 *
 * WHY THIS EXPANDS RATHER THAN STAYS A PATTERN
 *
 * Everything downstream of the feature list is per feature: coverage asks
 * whether each one is cut, inspection assigns each one a method, measurement
 * records a reading against each one, and A7 made operations per feature for
 * exactly that reason. A virtual pattern would have to be unfolded at every one
 * of those points, and the first place it was not unfolded would be a hole
 * nobody checked.
 *
 * So a pattern is an INPUT: the drawing's statement is turned into the real
 * features it describes, and the statement travels with them as provenance so
 * the group stays visible, editable and inspectable as a group.
 */

export const PATTERN_KINDS = ["BOLT_CIRCLE", "GRID", "LINEAR"] as const;
export type PatternKind = (typeof PATTERN_KINDS)[number];

export interface BoltCirclePattern {
  kind: "BOLT_CIRCLE";
  /** Centre of the circle, in part coordinates. */
  centerX: number;
  centerY: number;
  /** Bolt circle diameter, as the drawing states it. */
  diameter: number;
  count: number;
  /** Where the first hole sits, degrees counter-clockwise from +X. */
  startAngle: number;
}

export interface GridPattern {
  kind: "GRID";
  /** The first instance. The grid runs +X and +Y from here. */
  originX: number;
  originY: number;
  columns: number;
  rows: number;
  pitchX: number;
  pitchY: number;
}

export interface LinearPattern {
  kind: "LINEAR";
  originX: number;
  originY: number;
  count: number;
  pitch: number;
  /** Direction, degrees counter-clockwise from +X. */
  angle: number;
}

export type PatternSpec = BoltCirclePattern | GridPattern | LinearPattern;

export interface PatternRefusal {
  reason: string;
  recommendations: string[];
}

export interface PatternPosition {
  x: number;
  y: number;
  /** 1-based, for labelling. */
  index: number;
}

const rad = (deg: number) => (deg * Math.PI) / 180;
/** Four decimals is the machine's resolution; float noise below it is not. */
const round = (v: number) => Number(v.toFixed(6));

export function expandPattern(spec: PatternSpec): PatternPosition[] | { error: PatternRefusal } {
  if (spec.kind === "BOLT_CIRCLE") {
    if (!Number.isInteger(spec.count) || spec.count < 2) {
      return {
        error: {
          reason: `A bolt circle of ${spec.count} is not a pattern.`,
          recommendations: ["Two or more holes", "One hole on its own is just a hole — record it as one"],
        },
      };
    }
    if (!(spec.diameter > 0)) {
      return {
        error: {
          reason: `A bolt circle needs a diameter, and ${spec.diameter} is not one.`,
          recommendations: ["Record the bolt circle diameter as the drawing states it — the circle the hole CENTRES sit on"],
        },
      };
    }
    const r = spec.diameter / 2;
    return Array.from({ length: spec.count }, (_, i) => {
      const a = rad(spec.startAngle) + (i * 2 * Math.PI) / spec.count;
      return { x: round(spec.centerX + r * Math.cos(a)), y: round(spec.centerY + r * Math.sin(a)), index: i + 1 };
    });
  }

  if (spec.kind === "GRID") {
    if (!Number.isInteger(spec.columns) || !Number.isInteger(spec.rows) || spec.columns < 1 || spec.rows < 1) {
      return {
        error: {
          reason: `A ${spec.columns} × ${spec.rows} grid is not a pattern.`,
          recommendations: ["At least one column and one row, and more than one instance between them"],
        },
      };
    }
    if (spec.columns * spec.rows < 2) {
      return {
        error: {
          reason: "A grid of one is not a pattern.",
          recommendations: ["Two or more instances"],
        },
      };
    }
    if ((spec.columns > 1 && !(spec.pitchX > 0)) || (spec.rows > 1 && !(spec.pitchY > 0))) {
      return {
        error: {
          reason: "A grid needs a pitch in every direction it repeats in, and a pitch of zero puts two features in the same place.",
          recommendations: ["Record the centre-to-centre spacing", "Use a linear pattern if it only repeats one way"],
        },
      };
    }
    const out: PatternPosition[] = [];
    // Row-major, which is the order a machinist reads a grid and the order the
    // holes come out of the drill cycle.
    for (let row = 0; row < spec.rows; row++) {
      for (let col = 0; col < spec.columns; col++) {
        out.push({
          x: round(spec.originX + col * spec.pitchX),
          y: round(spec.originY + row * spec.pitchY),
          index: out.length + 1,
        });
      }
    }
    return out;
  }

  if (!Number.isInteger(spec.count) || spec.count < 2) {
    return {
      error: {
        reason: `A line of ${spec.count} is not a pattern.`,
        recommendations: ["Two or more instances"],
      },
    };
  }
  if (!(spec.pitch > 0)) {
    return {
      error: {
        reason: "A linear pattern needs a pitch, and a pitch of zero puts every instance in the same place.",
        recommendations: ["Record the centre-to-centre spacing"],
      },
    };
  }
  const ux = Math.cos(rad(spec.angle));
  const uy = Math.sin(rad(spec.angle));
  return Array.from({ length: spec.count }, (_, i) => ({
    x: round(spec.originX + i * spec.pitch * ux),
    y: round(spec.originY + i * spec.pitch * uy),
    index: i + 1,
  }));
}

/**
 * Which of a pattern's positions land off the stock entirely.
 *
 * A bolt circle bigger than the plate is a transposed diameter or a pattern
 * measured from the wrong datum, and it is far easier to see here — before six
 * features exist — than as one hole in the middle of a rapid.
 *
 * This tests the CENTRE against the stock outline and nothing else. A hole
 * whose centre is on the plate and whose edge hangs off it is a different
 * question, and answering it needs the feature's own size rather than the
 * pattern's — so this does not pretend to.
 */
export function offStock(positions: PatternPosition[], stock: Stock): PatternPosition[] {
  const hx = stock.x / 2;
  const hy = stock.y / 2;
  return positions.filter((p) => Math.abs(p.x) > hx || Math.abs(p.y) > hy);
}

/** Feature kinds a pattern can place: the ones that carry a centre. */
export function patternable(feature: Feature): boolean {
  return "centerX" in feature && "centerY" in feature;
}
