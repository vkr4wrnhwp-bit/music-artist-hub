import { describe, expect, it } from 'vitest';
import {
  applyToCells, clampToEnvelope, computeAir, DEFAULT_AIR, interpolateCells,
  MAP_PRESETS, presetTable, resampleControlGrid, selectionBounds, smoothCells,
  createSeededDb, type CellEnvelope, type CellRef,
} from '../src';

const ENV: CellEnvelope = { allowedMin: -15, allowedMax: 15, precision: 1 };

const grid = (rows: number, cols: number, fill = 0): number[][] =>
  Array.from({ length: rows }, () => Array<number>(cols).fill(fill));

const allCells = (rows: number, cols: number): CellRef[] => {
  const out: CellRef[] = [];
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) out.push([r, c]);
  return out;
};

describe('the envelope is the only way a cell value is written', () => {
  it('clamps to the table range and rounds to its precision', () => {
    expect(clampToEnvelope(99, ENV)).toBe(15);
    expect(clampToEnvelope(-99, ENV)).toBe(-15);
    expect(clampToEnvelope(1.26, ENV)).toBe(1.3);
    expect(clampToEnvelope(Number.NaN, ENV)).toBe(0);
  });

  it('refuses to let an edit widen the envelope', () => {
    const g = grid(3, 3);
    const out = applyToCells(g, allCells(3, 3), () => 500, ENV);
    expect(out.flat().every((v) => v === 15)).toBe(true);
  });

  it('leaves unselected cells untouched and does not mutate the input', () => {
    const g = grid(2, 2);
    const out = applyToCells(g, [[0, 0]], () => 5, ENV);
    expect(out).toEqual([[5, 0], [0, 0]]);
    expect(g).toEqual([[0, 0], [0, 0]]);
  });

  it('ignores coordinates outside the grid rather than growing it', () => {
    const g = grid(2, 2);
    const out = applyToCells(g, [[9, 9]], () => 5, ENV);
    expect(out).toEqual([[0, 0], [0, 0]]);
  });
});

describe('smooth', () => {
  it('averages the 3x3 neighbourhood', () => {
    // A single spike of 9 in the centre of a 3x3 becomes 9/9 = 1.
    const g = [[0, 0, 0], [0, 9, 0], [0, 0, 0]];
    const out = smoothCells(g, [[1, 1]], ENV);
    expect(out[1][1]).toBe(1);
  });

  it('reads neighbours from the original, so the result does not depend on visit order', () => {
    const g = [[0, 0, 0], [0, 9, 0], [0, 0, 0]];
    const forwards = smoothCells(g, allCells(3, 3), ENV);
    const backwards = smoothCells(g, [...allCells(3, 3)].reverse(), ENV);
    expect(forwards).toEqual(backwards);
  });

  it('pulls in unselected neighbours but never writes to them', () => {
    const g = [[0, 0, 0], [0, 9, 0], [0, 0, 0]];
    const out = smoothCells(g, [[0, 0]], ENV);
    // corner sees a 2x2 window containing the 9 → 9/4
    expect(out[0][0]).toBe(2.3);
    expect(out[1][1]).toBe(9); // untouched
  });
});

describe('interpolate', () => {
  it('fills a rectangle from its four corners', () => {
    const g = grid(3, 3);
    g[0][0] = 0; g[0][2] = 10; g[2][0] = 0; g[2][2] = 10;
    const out = interpolateCells(g, allCells(3, 3), ENV)!;
    expect(out[0]).toEqual([0, 5, 10]);
    expect(out[1]).toEqual([0, 5, 10]);
    expect(out[2]).toEqual([0, 5, 10]);
  });

  it('captures the corners before writing, so a selected corner keeps its value', () => {
    const g = [[0, 0, 4], [0, 0, 0], [0, 0, 0]];
    const out = interpolateCells(g, allCells(3, 3), ENV)!;
    expect(out[0][2]).toBe(4);
  });

  it('refuses a selection with nothing to interpolate across', () => {
    const g = grid(3, 3);
    expect(interpolateCells(g, [[1, 1]], ENV)).toBeNull();
    expect(interpolateCells(g, [], ENV)).toBeNull();
  });

  it('interpolates along a single row', () => {
    const g = grid(1, 3);
    g[0][0] = 0; g[0][2] = 8;
    const out = interpolateCells(g, [[0, 0], [0, 1], [0, 2]], ENV)!;
    expect(out[0]).toEqual([0, 4, 8]);
  });
});

describe('selectionBounds', () => {
  it('returns the bounding rectangle of a ragged selection', () => {
    expect(selectionBounds([[2, 5], [0, 1], [4, 3]])).toEqual({ r0: 0, r1: 4, c0: 1, c1: 5 });
  });
  it('is null for an empty selection', () => {
    expect(selectionBounds([])).toBeNull();
  });
});

describe('resampling a control grid onto real ECU axes', () => {
  it('reproduces the control grid when the axes line up with it', () => {
    const control = [[1, 2], [3, 4]];
    const out = resampleControlGrid(control, [0, 100], [0, 100], ENV);
    expect(out).toEqual([[1, 2], [3, 4]]);
  });

  it('maps by breakpoint value, not by index', () => {
    // A control grid that is 0 at the low end and 10 at the high end, resampled
    // onto an axis whose middle breakpoint sits at 25% of the range. Index
    // mapping would put 5 there; value mapping puts 2.5.
    const control = [[0, 0], [0, 0]];
    const ramp = [[0, 10], [0, 10]];
    expect(resampleControlGrid(control, [0, 1], [0, 1], ENV)).toEqual([[0, 0], [0, 0]]);
    const out = resampleControlGrid(ramp, [0, 100], [0, 25, 100], ENV);
    expect(out[0]).toEqual([0, 2.5, 10]);
  });

  it('clamps the resampled shape into the table envelope', () => {
    const tight: CellEnvelope = { allowedMin: -2, allowedMax: 2, precision: 1 };
    const out = resampleControlGrid([[10, 10], [10, 10]], [0, 1], [0, 1], tight);
    expect(out.flat().every((v) => v === 2)).toBe(true);
  });

  it('produces a grid shaped by the axes it is given', () => {
    const out = resampleControlGrid([[1, 2], [3, 4]], [0, 1, 2, 3, 4, 5, 6, 7], [0, 1, 2, 3, 4, 5, 6], ENV);
    expect(out.length).toBe(8);
    expect(out.every((r) => r.length === 7)).toBe(true);
  });
});

describe('condition presets', () => {
  const db = createSeededDb();
  const map = db.maps[0];
  const fuel = map.tableDefs.find((t) => t.id === 'fuel')!;
  const xAxis = map.axes.find((a) => a.id === fuel.xAxisId)!;
  const yAxis = map.axes.find((a) => a.id === fuel.yAxisId)!;

  it('fits every preset to the seeded ECU definition, in range', () => {
    for (const preset of MAP_PRESETS) {
      const table = presetTable(preset, fuel, xAxis, yAxis);
      expect(table, preset.id).not.toBeNull();
      expect(table!.length).toBe(yAxis.breakpoints.length);
      expect(table!.every((r) => r.length === xAxis.breakpoints.length), preset.id).toBe(true);
      const flatVals = table!.flat();
      expect(flatVals.every((v) => v >= fuel.allowedMin && v <= fuel.allowedMax), preset.id).toBe(true);
    }
  });

  it('zeroes the card for the zero preset', () => {
    const zero = MAP_PRESETS.find((p) => p.id === 'zero')!;
    const table = presetTable(zero, fuel, xAxis, yAxis)!;
    expect(table.flat().every((v) => v === 0)).toBe(true);
  });

  it('keeps hardpack enrichment down low, where the blurb says it is', () => {
    const hardpack = MAP_PRESETS.find((p) => p.id === 'hardpack')!;
    const table = presetTable(hardpack, fuel, xAxis, yAxis)!;
    const lowRpmClosedThrottle = table[0][0];
    const highRpmFullThrottle = table[table.length - 1][table[0].length - 1];
    expect(lowRpmClosedThrottle).toBeGreaterThan(0);
    expect(highRpmFullThrottle).toBe(0);
  });

  it('refuses to write offsets into an absolute table', () => {
    const absolute = { ...fuel, correctionType: 'absolute' as const };
    expect(presetTable(MAP_PRESETS[1], absolute, xAxis, yAxis)).toBeNull();
  });

  it('leaves a table the preset says nothing about alone', () => {
    const unknown = { ...fuel, id: 'injector-latency' };
    expect(presetTable(MAP_PRESETS[1], unknown, xAxis, yAxis)).toBeNull();
  });
});

describe('air density', () => {
  it('reports the standard datum at sea level on a standard day', () => {
    const r = computeAir({
      elevation: 0, elevationUnit: 'ft', temperature: 59, temperatureUnit: 'F',
      humidityPct: 0, baroInHg: 29.92,
    });
    expect(Math.abs(r.densityAltitudeFt)).toBeLessThan(50);
    expect(r.densityRatio).toBeCloseTo(1, 2);
    expect(r.suggestedIgnitionOffsetDeg).toBe(0);
  });

  it('thins the air as it gets hotter and higher', () => {
    const cool = computeAir({ ...DEFAULT_AIR, elevation: 0, temperature: 40 });
    const hot = computeAir({ ...DEFAULT_AIR, elevation: 6000, temperature: 95 });
    expect(hot.densityAltitudeFt).toBeGreaterThan(cool.densityAltitudeFt);
    expect(hot.densityRatio).toBeLessThan(cool.densityRatio);
    // Thin air runs rich, so the suggestion is to pull fuel out.
    expect(hot.suggestedFuelTrimPct).toBeLessThan(0);
    expect(cool.suggestedFuelTrimPct).toBeGreaterThanOrEqual(0);
    expect(hot.suggestedIgnitionOffsetDeg).toBeGreaterThan(0);
  });

  it('converts metric input to the same answer', () => {
    const imperial = computeAir({
      elevation: 3280.84, elevationUnit: 'ft', temperature: 68, temperatureUnit: 'F',
      humidityPct: 40, baroInHg: 29.92,
    });
    const metric = computeAir({
      elevation: 1000, elevationUnit: 'm', temperature: 20, temperatureUnit: 'C',
      humidityPct: 40, baroInHg: 29.92,
    });
    expect(metric.densityAltitudeFt).toBeCloseTo(imperial.densityAltitudeFt, 0);
  });

  it('keeps the suggestion inside the range a rider would actually dial', () => {
    const extreme = computeAir({
      elevation: 14000, elevationUnit: 'ft', temperature: 120, temperatureUnit: 'F',
      humidityPct: 100, baroInHg: 25,
    });
    expect(extreme.suggestedFuelTrimPct).toBeGreaterThanOrEqual(-6);
    expect(extreme.suggestedFuelTrimPct).toBeLessThanOrEqual(6);
    expect(extreme.suggestedIgnitionOffsetDeg).toBeLessThanOrEqual(3);
  });

  it('ignores humidity when it is cold, where water vapour barely matters', () => {
    const dry = computeAir({ ...DEFAULT_AIR, temperature: 20, humidityPct: 0 });
    const wet = computeAir({ ...DEFAULT_AIR, temperature: 20, humidityPct: 100 });
    expect(dry.densityAltitudeFt).toBe(wet.densityAltitudeFt);
  });
});
