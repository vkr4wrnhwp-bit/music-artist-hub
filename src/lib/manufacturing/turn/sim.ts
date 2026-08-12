import type { RotationalProfile } from "./geometry";
import type { TurnMove, TurnOperation } from "./operations";
import { effectiveRpm } from "./operations";

/**
 * TURNING STOCK SIMULATION — DEVELOPMENT ANALYSIS.
 *
 * A turned part is axisymmetric, so the entire stock state is one curve:
 * radius as a function of Z. This module replays the deterministic turn
 * toolpaths against that curve — a kinematic material-removal replay, and
 * exactly that:
 *
 * - it shows WHERE material is removed and WHEN, timed with the same
 *   per-rev arithmetic the cycle estimates use (rapids at a stated IPM);
 * - it is NOT a collision checker, not a gouge detector, and knows
 *   nothing about tool geometry beyond the programmed point — the
 *   development label is not decoration;
 * - internal (bore) moves are SKIPPED with a note, never faked on the
 *   outside surface.
 *
 * Everything is deterministic and pure; `stateAt` replays from zero on
 * each call because a few hundred moves against a few hundred cells is
 * cheaper than being clever about incremental state.
 */

export const SIM_RAPID_IPM = 800; // same stated assumption as the NC analyzer

export interface TimedTurnMove {
  opIndex: number;
  operationNumber: number;
  kind: TurnMove["kind"];
  /** Internal (centerline/ID) — advances the clock, never carves the OD envelope. */
  internal: boolean;
  /** Diameter at the move end. */
  x: number;
  z: number;
  x0: number;
  z0: number;
  /** Minutes at which the move starts/ends on the sim clock. */
  t0: number;
  t1: number;
}

export interface TurnSim {
  moves: TimedTurnMove[];
  totalMinutes: number;
  /** Cells along Z. */
  nz: number;
  cell: number;
  stockRadius: number;
  stockLength: number;
  /** Clock time at which each operation ends — the stock-state steps. */
  opEnds: { opIndex: number; operationNumber: number; label: string; tEnd: number }[];
  notes: string[];
  developmentAnalysis: true;
}

export interface TurnOpForSim {
  op: TurnOperation;
  moves: TurnMove[];
}

export function buildTurnSim(profile: RotationalProfile, ops: TurnOpForSim[], cells = 400): TurnSim {
  const stockLength = profile.stockLength;
  const stockRadius = profile.stockDiameter / 2;
  const cell = stockLength / cells;
  const notes: string[] = [`Rapids timed at ${SIM_RAPID_IPM} in/min — a stated assumption, not machine data.`];

  const timed: TimedTurnMove[] = [];
  const opEnds: TurnSim["opEnds"] = [];
  let t = 0;
  let skippedInternal = 0;

  const INTERNAL_TYPES = new Set(["ID_DRILL", "CENTER_DRILL", "ID_BORE_ROUGH", "ID_BORE_FINISH", "GROOVE_ID", "THREAD_ID"]);
  ops.forEach(({ op, moves }, opIndex) => {
    const internal = INTERNAL_TYPES.has(op.type);
    let px = profile.stockDiameter + 0.2;
    let pz = stockLength + 0.5;
    let first = true;
    for (const m of moves) {
      if (first) {
        // Seed the previous point at the move's own start so the lead-in
        // rapid does not sweep from an arbitrary corner.
        px = m.x;
        pz = m.z;
        first = false;
      }
      const dr = Math.abs(m.x - px) / 2;
      const dz = Math.abs(m.z - pz);
      const dist = Math.hypot(dr, dz);
      let minutes = 0;
      if (m.kind === "RAPID") {
        minutes = dist / SIM_RAPID_IPM;
      } else {
        const meanDia = Math.max(0.05, (Math.abs(m.x) + Math.abs(px)) / 2);
        const rpm = effectiveRpm(op.params, meanDia);
        const feed = m.feedPerRev ?? op.params.feedPerRev;
        minutes = rpm > 0 && feed > 0 ? dist / (feed * rpm) : 0;
      }
      timed.push({ opIndex, operationNumber: op.operationNumber, kind: m.kind, internal, x: m.x, z: m.z, x0: px, z0: pz, t0: t, t1: t + minutes });
      t += minutes;
      px = m.x;
      pz = m.z;
    }
    if (internal) skippedInternal++;
    opEnds.push({ opIndex, operationNumber: op.operationNumber, label: op.label, tEnd: t });
  });

  if (skippedInternal > 0) {
    notes.push(`${skippedInternal} centerline/ID operation(s) advance the clock but do not carve the OD envelope — internal stock state is not modelled, and the view says so rather than faking it.`);
  }

  return { moves: timed, totalMinutes: t, nz: cells, cell, stockRadius, stockLength, opEnds, notes, developmentAnalysis: true };
}

/**
 * Radii per cell at sim time t, replayed from raw stock. OD cuts clamp the
 * envelope down; a partially elapsed move carves only the swept portion.
 * Radius never grows — material does not come back.
 */
export function stateAt(sim: TurnSim, t: number): Float64Array {
  const r = new Float64Array(sim.nz).fill(sim.stockRadius);
  for (const m of sim.moves) {
    if (m.t0 >= t) break;
    if (m.kind === "RAPID" || m.internal) continue;
    const frac = m.t1 <= t ? 1 : (t - m.t0) / Math.max(1e-9, m.t1 - m.t0);
    // Swept span of this cut, interpolating the endpoint.
    const zEnd = m.z0 + (m.z - m.z0) * frac;
    const xEnd = m.x0 + (m.x - m.x0) * frac;
    const z0 = Math.min(m.z0, zEnd);
    const z1 = Math.max(m.z0, zEnd);
    const radius = Math.max(0, Math.min(Math.abs(m.x0), Math.abs(xEnd)) / 2);
    const i0 = Math.max(0, Math.floor(z0 / sim.cell));
    const i1 = Math.min(sim.nz - 1, Math.ceil(z1 / sim.cell));
    for (let i = i0; i <= i1; i++) if (r[i] > radius) r[i] = radius;
  }
  return r;
}

/** Tool position (diameter, z) and motion kind at time t. */
export function toolAt(sim: TurnSim, t: number): { x: number; z: number; kind: TimedTurnMove["kind"]; operationNumber: number } | null {
  if (sim.moves.length === 0) return null;
  const clamped = Math.min(Math.max(t, 0), sim.totalMinutes);
  for (const m of sim.moves) {
    if (clamped <= m.t1 || m === sim.moves[sim.moves.length - 1]) {
      const frac = m.t1 <= m.t0 ? 1 : Math.min(1, Math.max(0, (clamped - m.t0) / (m.t1 - m.t0)));
      return {
        x: m.x0 + (m.x - m.x0) * frac,
        z: m.z0 + (m.z - m.z0) * frac,
        kind: m.kind,
        operationNumber: m.operationNumber,
      };
    }
  }
  return null;
}
