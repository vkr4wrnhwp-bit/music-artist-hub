/**
 * Air density from field conditions, and the trim nudge it suggests.
 *
 * Folded in from the Holeshot Tuner / Trackside worksheets. TRACE had no
 * atmospherics at all before this — sessions recorded what the bike did, but
 * nothing recorded that Tuesday was 40°F at sea level and Saturday was 95°F at
 * 6,000ft, which moves an engine more than most map edits do.
 *
 * The suggestion is a suggestion. Like everything else advisory in TRACE it is
 * offered, labelled and never applied on its own: `suggestedFuelTrimPct` is a
 * number to consider next to a plug reading, not a value to write to a table.
 */

export type ElevationUnit = 'ft' | 'm';
export type TemperatureUnit = 'F' | 'C';

export interface AirConditions {
  elevation: number;
  elevationUnit: ElevationUnit;
  temperature: number;
  temperatureUnit: TemperatureUnit;
  humidityPct: number;
  /** Altimeter setting in inches of mercury; 29.92 is the standard datum. */
  baroInHg: number;
}

export interface AirResult {
  densityAltitudeFt: number;
  /** Air density as a fraction of the sea-level standard: 1.0 is the datum. */
  densityRatio: number;
  suggestedFuelTrimPct: number;
  suggestedIgnitionOffsetDeg: number;
}

export const DEFAULT_AIR: AirConditions = {
  elevation: 500,
  elevationUnit: 'ft',
  temperature: 75,
  temperatureUnit: 'F',
  humidityPct: 40,
  baroInHg: 29.92,
};

export const toFeet = (v: number, unit: ElevationUnit): number => (unit === 'm' ? v * 3.28084 : v);
export const toFahrenheit = (v: number, unit: TemperatureUnit): number =>
  (unit === 'C' ? (v * 9) / 5 + 32 : v);

const clamp = (v: number, lo: number, hi: number): number => Math.min(hi, Math.max(lo, v));
const snap = (v: number, step: number): number => Math.round(v / step) * step;

export function computeAir(a: AirConditions): AirResult {
  const elevationFt = toFeet(a.elevation, a.elevationUnit);
  const tempF = toFahrenheit(a.temperature, a.temperatureUnit);
  const tempC = ((tempF - 32) * 5) / 9;

  // Pressure altitude: field elevation corrected by the altimeter setting.
  const pressureAltitude = elevationFt + (29.92 - a.baroInHg) * 1000;

  // ISA temperature at that altitude, then the classic density-altitude
  // approximation from the temperature deviation off standard.
  const isaC = 15 - 1.98 * (pressureAltitude / 1000);
  let densityAltitude = pressureAltitude + 118.8 * (tempC - isaC);

  // Water vapour displaces air. This is a rough correction — worth a few
  // hundred feet on a hot humid day and negligible when it is cold, which is
  // the behaviour that matters. It is not a psychrometric calculation.
  densityAltitude += Math.max(0, (a.humidityPct / 100) * (tempC - 10) * 30);
  densityAltitude = Math.round(densityAltitude);

  // Standard-atmosphere density ratio at that density altitude.
  const densityRatio = Math.pow(1 - 6.87535e-6 * densityAltitude, 4.2561);

  // The ECU's own baro and intake-air-temperature sensors already compensate
  // for most of the density change. What a rider actually dials on top is a
  // fraction of the raw density delta, which is what the 0.35 is: a damping
  // factor on a correction the engine has largely made already.
  const suggestedFuelTrimPct = clamp(snap((densityRatio - 1) * 100 * 0.35, 0.5), -6, 6);

  // Thin air burns slower; a little more advance is conventional up high.
  // Deliberately coarse and capped — this is a starting point, not a curve.
  const suggestedIgnitionOffsetDeg =
    densityAltitude > 3000 ? Math.min(3, Math.round(densityAltitude / 4000)) : 0;

  return {
    densityAltitudeFt: densityAltitude,
    densityRatio,
    suggestedFuelTrimPct,
    suggestedIgnitionOffsetDeg,
  };
}
