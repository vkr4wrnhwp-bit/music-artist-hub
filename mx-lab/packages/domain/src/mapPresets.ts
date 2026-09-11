/**
 * Condition presets — starting shapes for a draft, folded in from the Holeshot
 * Tuner / Trackside worksheets.
 *
 * Each preset is a coarse 4x4 control grid per table, rows running low to high
 * on the Y axis (RPM) and columns low to high on the X axis (throttle). They
 * are resampled onto whatever axes the bike's ECU definition actually declares
 * — see `resampleControlGrid`.
 *
 * These are offsets on top of the ECU's stock map, so they only apply to a
 * table whose `correctionType` is `'offset'`. Applying them to an absolute
 * table would write "2" meaning "+2%" into a cell that means "2 milliseconds",
 * so `presetTable` refuses rather than guessing.
 *
 * They are suggestions and nothing more. Every value here was authored by hand
 * as a plausible demonstration shape, not measured on a dyno or a track, which
 * is why `PRESET_DISCLAIMER` travels with them into the UI.
 */

import { resampleControlGrid, type CellEnvelope } from './mapEditing';
import type { MapTableDef, MapAxisDef } from './types';

export const PRESET_DISCLAIMER =
  'Simulated starting points, not measured tunes. Confirm with a plug reading, '
  + 'an AFR gauge or lap feel before trusting any of it.';

export interface MapPreset {
  id: string;
  name: string;
  blurb: string;
  /** Control grid per table-definition id. A table with no entry is left alone. */
  control: Record<string, number[][]>;
}

const flat = (v: number): number[][] => [
  [v, v, v, v],
  [v, v, v, v],
  [v, v, v, v],
  [v, v, v, v],
];

const zero = (): number[][] => flat(0);

export const MAP_PRESETS: MapPreset[] = [
  {
    id: 'zero',
    name: 'Zero card',
    blurb: 'Everything back to the base map. Start here after a reflash or on a new bike.',
    control: { fuel: zero(), ignition: zero() },
  },
  {
    id: 'hardpack',
    name: 'Hardpack / blue groove',
    blurb: 'Softens the hit off the bottom so the rear tyre hooks up instead of spinning across the hard stuff.',
    control: {
      fuel: [
        [2, 1.5, 0.5, 0],
        [1.5, 1, 0.5, 0],
        [0.5, 0.5, 0, 0],
        [0, 0, 0, 0],
      ],
      ignition: [
        [-2, -1.5, -0.5, 0],
        [-1.5, -1, 0, 0],
        [-0.5, 0, 0, 0],
        [0, 0, 0, 0],
      ],
    },
  },
  {
    id: 'sand',
    name: 'Sand / deep loam',
    blurb: 'More mid-to-top pull under heavy load; extra fuel keeps the motor cooler on long deep straights.',
    control: {
      fuel: [
        [0, 0.5, 1, 1],
        [0.5, 1.5, 2, 2],
        [0.5, 1.5, 2.5, 2.5],
        [0, 1, 1.5, 1.5],
      ],
      ignition: [
        [1, 1, 0.5, 0],
        [1, 1, 0.5, 0],
        [0.5, 0.5, 0, 0],
        [0, 0, 0, 0],
      ],
    },
  },
  {
    id: 'mud',
    name: 'Mud / tractor',
    blurb: 'Rich and lazy down low so it chugs through slop without flaming out or lighting up the rear wheel.',
    control: {
      fuel: [
        [2, 2, 1, 0.5],
        [1.5, 1.5, 0.5, 0],
        [0.5, 0.5, 0, 0],
        [0, 0, 0, 0],
      ],
      ignition: [
        [-1, -0.5, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
      ],
    },
  },
  {
    id: 'altitude',
    name: 'High altitude',
    blurb: "Thin air runs rich. The ECU's baro sensor does most of the correcting — this is the residual riders still dial.",
    control: { fuel: flat(-3), ignition: flat(1) },
  },
  {
    id: 'cold',
    name: 'Cold snap / dense air',
    blurb: 'Cold dense air leans the motor out and runs it hot. Feed it a little extra everywhere.',
    control: { fuel: flat(2), ignition: zero() },
  },
];

/**
 * Resolves a preset into a table-shaped grid for one table definition.
 *
 * Returns null when the preset says nothing about this table, or when the
 * table is not an offset table — see the note at the top of this file.
 */
export function presetTable(
  preset: MapPreset,
  tableDef: MapTableDef,
  xAxis: MapAxisDef,
  yAxis: MapAxisDef,
): number[][] | null {
  const control = preset.control[tableDef.id];
  if (!control) return null;
  if (tableDef.correctionType !== 'offset') return null;
  const envelope: CellEnvelope = {
    allowedMin: tableDef.allowedMin,
    allowedMax: tableDef.allowedMax,
    precision: tableDef.precision,
  };
  return resampleControlGrid(control, yAxis.breakpoints, xAxis.breakpoints, envelope);
}
