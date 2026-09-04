import type { Move, Toolpath } from "./types";
import type { Stock } from "@/lib/domain/features";

/**
 * WHERE PROGRAM ZERO IS, AND WHICH WAY THE PART IS TURNED.
 *
 * `Setup` carried `orientation` — the string "TOP" or "BOTTOM" — and a work
 * offset, and nothing else. Feature coordinates were program coordinates by
 * assumption: no origin, no rotation, no statement of how the part sits.
 *
 * For the first setup on a centred part that assumption is true, which is why
 * it survived. For the second it is not. Turn a part over and every X on it
 * moves to the other side of the machine — a hole at X+2.2500 in the model is
 * at X−2.2500 once the part is flipped — and nothing in the system knew. The
 * program was dimensionally perfect and mirrored, which is the failure mode
 * that scraps a part while measuring correct on every individual feature.
 *
 * Worse, "BOTTOM" does not say which way it was turned. Rolled about X and
 * pitched about Y both put the bottom face up and they mirror different
 * coordinates, so the string on its own cannot be acted on at all.
 *
 * WHAT THIS FRAME IS AND IS NOT
 *
 * It maps PART coordinates to PROGRAM coordinates in X and Y: a turnover, a
 * quarter-turn index, and an origin. Rotation is restricted to quarter turns
 * because that is what a vise does — an arbitrary angle needs a fixture that
 * locates the part at it, and CANVAS does not model one. Every derived box
 * stays axis-aligned, which is what the simulator's height field and the
 * collision checks are built on.
 *
 * **Z is not transformed, and that is deliberate.** Operations are already
 * authored in the setup's own Z: the planner emits Setup 2's depths measured
 * from the face that is up in Setup 2. There is nothing to transform from. What
 * is still not expressible is a FEATURE whose depth is measured from the
 * opposite face — a counterbore on the underside — and this frame does not
 * pretend otherwise.
 *
 * The default is the convention the whole system already ran on: zero at the
 * centre of the stock, no rotation, part the way up it was modelled. A setup
 * that records nothing means exactly that, so nothing planned before this
 * existed changes.
 */

export type FlipAxis = "X" | "Y";

export interface SetupFrame {
  /**
   * Which axis the part was turned over about, or null for a setup that is the
   * way up it was modelled. Rolling about X mirrors Y; pitching about Y mirrors
   * X. Both put the bottom face up, and they are not the same setup.
   */
  flipAxis: FlipAxis | null;
  /** Index about Z, in quarter turns counter-clockwise: 0, 1, 2 or 3. */
  quarterTurns: 0 | 1 | 2 | 3;
  /**
   * The point, in the turned and indexed frame, that program zero sits at.
   * (0, 0) is the centre of the stock, which is the system's default.
   */
  originX: number;
  originY: number;
}

export interface FrameRefusal {
  reason: string;
  recommendations: string[];
}

/** The convention every setup meant before a setup could say otherwise. */
export const DEFAULT_FRAME: SetupFrame = { flipAxis: null, quarterTurns: 0, originX: 0, originY: 0 };

export interface SetupFrameInput {
  orientation: string;
  flipAxis?: string | null;
  quarterTurns?: number | null;
  originX?: number | null;
  originY?: number | null;
}

/**
 * The frame a setup describes, or what it is missing.
 *
 * A setup that says the part is upside down and does not say which way it was
 * turned is refused rather than guessed at: the two answers mirror different
 * coordinates and produce two different parts.
 */
export function setupFrame(setup: SetupFrameInput): SetupFrame | { error: FrameRefusal } {
  const upsideDown = setup.orientation === "BOTTOM";
  const axis = setup.flipAxis === "X" || setup.flipAxis === "Y" ? setup.flipAxis : null;

  if (upsideDown && axis === null) {
    return {
      error: {
        reason: `This setup has the part bottom up and does not record which axis it was turned about. Rolling it about X mirrors every Y and pitching it about Y mirrors every X — two different parts, and no way to tell them apart from "BOTTOM".`,
        recommendations: [
          "Record the flip axis on the setup: X if you rolled it front to back, Y if you turned it left to right",
          "Say which face is against the fixed jaw, and the axis follows from it",
        ],
      },
    };
  }
  if (!upsideDown && axis !== null) {
    return {
      error: {
        reason: `This setup records a flip about ${axis} but says the part is ${setup.orientation.toLowerCase()} up. One of the two is wrong, and either reading mirrors the program.`,
        recommendations: ["Set the orientation to BOTTOM, or clear the flip axis"],
      },
    };
  }

  const q = setup.quarterTurns ?? 0;
  if (!Number.isInteger(q) || q < 0 || q > 3) {
    return {
      error: {
        reason: `This setup records ${q} quarter turns, which is not an index a vise produces. A 3-axis setup is indexed in quarter turns; an angle between them needs a fixture that locates the part at it, and there is none modelled here.`,
        recommendations: ["Record 0, 1, 2 or 3 quarter turns counter-clockwise", "Fixture the part at the angle and model the fixture"],
      },
    };
  }

  return {
    flipAxis: axis,
    quarterTurns: q as 0 | 1 | 2 | 3,
    originX: setup.originX ?? 0,
    originY: setup.originY ?? 0,
  };
}

export const isIdentity = (f: SetupFrame): boolean =>
  f.flipAxis === null && f.quarterTurns === 0 && f.originX === 0 && f.originY === 0;

/**
 * The 2×2 linear part, applied to a vector.
 *
 * Turning the part over about Y sends x to −x; about X, y to −y. Both are
 * proper 180° rotations in 3D — the determinant of the full 3×3 is +1 — but in
 * the XY plane the machine sees, each has determinant −1, which is why the
 * direction of every arc reverses. Quarter turns are ordinary rotations and
 * leave it alone.
 */
function linear(f: SetupFrame, x: number, y: number): { x: number; y: number } {
  let px = f.flipAxis === "Y" ? -x : x;
  let py = f.flipAxis === "X" ? -y : y;
  for (let i = 0; i < f.quarterTurns; i++) {
    const t = px;
    px = -py;
    py = t;
  }
  // `+ 0` collapses negative zero, which is what mirroring 0 produces. It is
  // invisible in arithmetic and reads as "X-0.0000" wherever a coordinate is
  // formatted without guarding for it.
  return { x: px + 0, y: py + 0 };
}

/** True when the frame reverses the direction a circle is travelled in. */
export const reversesArcs = (f: SetupFrame): boolean => f.flipAxis !== null;

/** A point in part coordinates, in program coordinates. */
export function toProgram(f: SetupFrame, x: number, y: number): { x: number; y: number } {
  const p = linear(f, x, y);
  return { x: p.x - f.originX, y: p.y - f.originY };
}

/**
 * A move, in program coordinates.
 *
 * `i` and `j` are offsets from the move's start to the arc centre, so they are
 * a VECTOR and take the linear part without the origin. `cw` flips with the
 * plane's handedness, or a G2 on the top face comes out as a G2 on the bottom
 * and cuts the wrong side of the line.
 */
export function toProgramMove(f: SetupFrame, m: Move): Move {
  const p = toProgram(f, m.x, m.y);
  const out: Move = { ...m, x: p.x, y: p.y };
  if (m.i !== undefined && m.j !== undefined) {
    const v = linear(f, m.i, m.j);
    out.i = v.x;
    out.j = v.y;
    if (reversesArcs(f)) out.cw = !m.cw;
  }
  return out;
}

/**
 * The sentence a machinist reads before picking up an edge.
 *
 * The system had one sentence for every setup, because there was one
 * convention. Now it is a property of the setup, and a setup that is turned
 * over or indexed says so in the same breath as where zero is — those are the
 * two facts that decide whether the program cuts the part or the vise.
 */
export function frameSentence(f: SetupFrame, stock: Stock | null): { xy: string; z: string; sentence: string; prose: string } {
  const at =
    f.originX === 0 && f.originY === 0
      ? "the centre of the stock"
      : `X${f.originX.toFixed(4)} Y${f.originY.toFixed(4)} from the centre of the stock`;

  const turned =
    f.flipAxis === null
      ? ""
      : ` The part is turned over about ${f.flipAxis}, so every ${f.flipAxis === "Y" ? "X" : "Y"} on the model is on the other side of the machine.`;
  const indexed = f.quarterTurns === 0 ? "" : ` It is indexed ${f.quarterTurns * 90}° counter-clockwise from the model.`;

  const size = stock ? ` (${stock.x.toFixed(3)} × ${stock.y.toFixed(3)} × ${stock.z.toFixed(3)})` : "";

  return {
    xy: f.originX === 0 && f.originY === 0 ? "Centre of the stock" : `X${f.originX.toFixed(4)} Y${f.originY.toFixed(4)} from the stock centre`,
    z: "Top of the stock as it sits in this setup",
    sentence:
      `PROGRAM ZERO: X0 Y0 AT ${at.toUpperCase()}, Z0 AT THE TOP OF THE STOCK AS IT SITS IN THIS SETUP.` +
      turned.toUpperCase() +
      indexed.toUpperCase(),
    prose:
      `Program zero is ${at} in X and Y${size}, with Z0 at the top of the stock as it sits in this setup. Every coordinate in the program is measured from there.` +
      turned +
      indexed,
  };
}

/**
 * A whole toolpath, in program coordinates.
 *
 * The canned-cycle descriptor is transformed with the moves and not derived
 * from them: it is the thing the control actually executes, and a cycle left in
 * part coordinates beside a move list in program coordinates would drill the
 * pattern in one place and simulate it in another.
 */
export function toProgramToolpath(f: SetupFrame, tp: Toolpath): Toolpath {
  if (isIdentity(f)) return tp;
  const cy = tp.cannedCycle;
  return {
    ...tp,
    moves: tp.moves.map((m) => toProgramMove(f, m)),
    ...(cy ? { cannedCycle: { ...cy, ...toProgram(f, cy.x, cy.y) } } : {}),
  };
}
