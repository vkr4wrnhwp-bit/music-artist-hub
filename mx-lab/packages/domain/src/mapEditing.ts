/**
 * Grid editing operations for map tables.
 *
 * These came from the Holeshot Tuner / Trackside worksheets, which were
 * separate products until they were folded in here. Those tools carried a
 * fixed 10x9 RPM/TPS grid; TRACE's tables are sized by the ECU definition's
 * own axis breakpoints, so every operation below works on whatever shape it
 * is handed and clamps to that table's declared envelope.
 *
 * All functions are pure and return a new grid. None of them knows about
 * revision state or permissions: whether an edit is allowed at all is decided
 * by the caller, because that is a workflow question, not an arithmetic one.
 */

/** A cell coordinate as `[row, column]` — row indexes the Y axis. */
export type CellRef = readonly [row: number, col: number];

/** The part of a `MapTableDef` that constrains a cell value. */
export interface CellEnvelope {
  allowedMin: number;
  allowedMax: number;
  precision: number;
}

export interface SelectionBounds {
  r0: number;
  r1: number;
  c0: number;
  c1: number;
}

/** Clamps to the table's declared range and rounds to its display precision. */
export function clampToEnvelope(value: number, env: CellEnvelope): number {
  if (!Number.isFinite(value)) return 0;
  const clamped = Math.min(env.allowedMax, Math.max(env.allowedMin, value));
  return +clamped.toFixed(env.precision);
}

function cloneGrid(grid: readonly (readonly number[])[]): number[][] {
  return grid.map((row) => row.slice());
}

/** The bounding rectangle of a selection, or null when nothing is selected. */
export function selectionBounds(cells: readonly CellRef[]): SelectionBounds | null {
  if (cells.length === 0) return null;
  let r0 = cells[0][0], r1 = cells[0][0], c0 = cells[0][1], c1 = cells[0][1];
  for (const [r, c] of cells) {
    if (r < r0) r0 = r;
    if (r > r1) r1 = r;
    if (c < c0) c0 = c;
    if (c > c1) c1 = c;
  }
  return { r0, r1, c0, c1 };
}

/**
 * Applies `fn` to each selected cell. This is the single place cell writes are
 * clamped and rounded, so no caller can widen a table's envelope by accident.
 */
export function applyToCells(
  grid: readonly (readonly number[])[],
  cells: readonly CellRef[],
  fn: (value: number, row: number, col: number) => number,
  env: CellEnvelope,
): number[][] {
  const out = cloneGrid(grid);
  for (const [r, c] of cells) {
    if (out[r]?.[c] === undefined) continue;
    out[r][c] = clampToEnvelope(fn(grid[r][c], r, c), env);
  }
  return out;
}

/**
 * Replaces each selected cell with the mean of its 3x3 neighbourhood.
 *
 * Neighbours are read from the grid as it was before the call, so a smooth
 * over a region gives the same answer regardless of which cell is visited
 * first. Neighbours outside the selection still contribute — smoothing a
 * region against its surroundings is the point — but only selected cells are
 * written. Edge cells average over the neighbours that exist.
 */
export function smoothCells(
  grid: readonly (readonly number[])[],
  cells: readonly CellRef[],
  env: CellEnvelope,
): number[][] {
  const rows = grid.length;
  const cols = grid[0]?.length ?? 0;
  return applyToCells(grid, cells, (_v, r, c) => {
    let sum = 0;
    let n = 0;
    for (let dr = -1; dr <= 1; dr++) {
      for (let dc = -1; dc <= 1; dc++) {
        const rr = r + dr;
        const cc = c + dc;
        if (rr >= 0 && rr < rows && cc >= 0 && cc < cols) {
          sum += grid[rr][cc];
          n++;
        }
      }
    }
    return n === 0 ? 0 : sum / n;
  }, env);
}

/**
 * Bilinearly interpolates the selection from its four corner cells, so a tuner
 * can dial the corners of a region and let the middle follow.
 *
 * The corners are read before anything is written, so a corner that is itself
 * selected still contributes its original value. Returns null when the
 * selection is not at least 2x2 — there is nothing to interpolate across a
 * single row or column of one cell, and silently doing nothing would look like
 * a bug to the person who pressed the button.
 */
export function interpolateCells(
  grid: readonly (readonly number[])[],
  cells: readonly CellRef[],
  env: CellEnvelope,
): number[][] | null {
  const b = selectionBounds(cells);
  if (!b) return null;
  if (b.r0 === b.r1 && b.c0 === b.c1) return null;

  const topLeft = grid[b.r0][b.c0];
  const topRight = grid[b.r0][b.c1];
  const bottomLeft = grid[b.r1][b.c0];
  const bottomRight = grid[b.r1][b.c1];

  return applyToCells(grid, cells, (_v, r, c) => {
    const u = b.r1 === b.r0 ? 0 : (r - b.r0) / (b.r1 - b.r0);
    const w = b.c1 === b.c0 ? 0 : (c - b.c0) / (b.c1 - b.c0);
    return (
      topLeft * (1 - u) * (1 - w) +
      topRight * (1 - u) * w +
      bottomLeft * u * (1 - w) +
      bottomRight * u * w
    );
  }, env);
}

/**
 * Where a breakpoint sits within its axis, as 0..1 across the axis range.
 * A single-breakpoint axis degenerates to 0.
 */
function axisPositions(breakpoints: readonly number[]): number[] {
  if (breakpoints.length <= 1) return breakpoints.map(() => 0);
  const lo = breakpoints[0];
  const hi = breakpoints[breakpoints.length - 1];
  const span = hi - lo;
  if (span === 0) return breakpoints.map(() => 0);
  return breakpoints.map((bp) => (bp - lo) / span);
}

/**
 * Resamples a coarse control grid onto a table's real axes.
 *
 * The folded-in worksheets described each condition as a small hand-authored
 * grid stretched across their own fixed 10x9 axes. TRACE's axes come from the
 * ECU definition and differ per bike — the seeded definition is 8x7 — so the
 * shape has to be resampled rather than pasted.
 *
 * Resampling is by breakpoint **value**, not by index, and that distinction is
 * load-bearing. A throttle axis is routinely spaced unevenly (the seeded one
 * runs 0,10,20,40,60,80,100 — fine down low where response tuning happens,
 * coarse up top). "Richer just off the bottom" is a claim about throttle
 * position, so mapping by index would slide that enrichment up to a third
 * throttle purely because the ECU spends more bins down there.
 */
export function resampleControlGrid(
  control: readonly (readonly number[])[],
  yBreakpoints: readonly number[],
  xBreakpoints: readonly number[],
  env: CellEnvelope,
): number[][] {
  const cr = control.length;
  const cc = control[0]?.length ?? 0;
  const rows = yBreakpoints.length;
  const cols = xBreakpoints.length;
  if (cr === 0 || cc === 0) {
    return Array.from({ length: rows }, () => Array<number>(cols).fill(0));
  }

  const yPos = axisPositions(yBreakpoints);
  const xPos = axisPositions(xBreakpoints);

  const out: number[][] = [];
  for (let r = 0; r < rows; r++) {
    // Position within the control grid, in control-cell units.
    const u = yPos[r] * (cr - 1);
    const i = Math.min(Math.max(Math.floor(u), 0), Math.max(cr - 2, 0));
    const fu = cr === 1 ? 0 : u - i;
    const i1 = Math.min(i + 1, cr - 1);
    const row: number[] = [];
    for (let c = 0; c < cols; c++) {
      const w = xPos[c] * (cc - 1);
      const j = Math.min(Math.max(Math.floor(w), 0), Math.max(cc - 2, 0));
      const fw = cc === 1 ? 0 : w - j;
      const j1 = Math.min(j + 1, cc - 1);
      const v =
        control[i][j] * (1 - fu) * (1 - fw) +
        control[i][j1] * (1 - fu) * fw +
        control[i1][j] * fu * (1 - fw) +
        control[i1][j1] * fu * fw;
      row.push(clampToEnvelope(v, env));
    }
    out.push(row);
  }
  return out;
}
