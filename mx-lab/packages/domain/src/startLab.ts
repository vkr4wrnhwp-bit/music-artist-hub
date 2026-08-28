import type { StartAttempt } from './types';

/**
 * Start Lab analytics (section 14). Rankings are computed from the recorded
 * attempts; the recommendation logic deliberately prefers non-map causes when
 * the evidence supports them — a start problem is not automatically a map
 * problem.
 */

export type StartRankKey =
  | 'fastest' | 'most_consistent' | 'least_wheelspin' | 'best_rpm_control'
  | 'best_confidence' | 'best_second_phase';

const mean = (xs: number[]) => xs.reduce((s, x) => s + x, 0) / Math.max(1, xs.length);
const std = (xs: number[]) => {
  const m = mean(xs);
  return Math.sqrt(mean(xs.map((x) => (x - m) ** 2)));
};

export function rankStarts(attempts: StartAttempt[], key: StartRankKey): StartAttempt[] {
  const sorted = [...attempts];
  switch (key) {
    case 'fastest': return sorted.sort((a, b) => a.timeTo30MphS - b.timeTo30MphS);
    case 'least_wheelspin': return sorted.sort((a, b) => a.estWheelspinPct - b.estWheelspinPct);
    case 'best_rpm_control': return sorted.sort((a, b) => (a.initialRpm - a.minRpmAfterRelease) - (b.initialRpm - b.minRpmAfterRelease));
    case 'best_confidence': return sorted.sort((a, b) => b.riderRating - a.riderRating);
    case 'best_second_phase': return sorted.sort((a, b) => b.secondPhaseG - a.secondPhaseG);
    case 'most_consistent': {
      // consistency is a session property; order by distance from the session mean time
      const m = mean(sorted.map((a) => a.timeTo30MphS));
      return sorted.sort((a, b) => Math.abs(a.timeTo30MphS - m) - Math.abs(b.timeTo30MphS - m));
    }
  }
}

export interface StartInsight {
  attempts: number;
  bestTimeTo30: number;
  meanTimeTo30: number;
  stdTimeTo30: number;
  meanWheelspin: number;
  rpmDropPctVsMean: (a: StartAttempt) => number;
  recommendation: string[];
  mapChangeAdvised: boolean;
}

export function startInsight(attempts: StartAttempt[]): StartInsight {
  const times = attempts.map((a) => a.timeTo30MphS);
  const spins = attempts.map((a) => a.estWheelspinPct);
  const rpmDrops = attempts.map((a) => a.initialRpm - a.minRpmAfterRelease);
  const meanDrop = mean(rpmDrops);

  // Correlate wheelspin variance with rider-controlled variables: if spin
  // varies far more than RPM drop does, launch delivery is not the driver.
  const spinCv = std(spins) / Math.max(1, mean(spins));
  const dropCv = std(rpmDrops) / Math.max(1, meanDrop);
  const mapChangeAdvised = dropCv > spinCv * 1.5; // RPM handling is the unstable variable

  const recommendation = mapChangeAdvised
    ? [
        'RPM-drop variance dominates: launch-region delivery is the least consistent variable.',
        'Ask the tuner to review the launch region — within the validated envelope only.',
        'Hold clutch, gearing, and gate prep constant for the next comparison.',
      ]
    : [
        'Retain the current engine map.',
        'Wheelspin variance tracks release technique and surface more than RPM handling.',
        'Test a smaller clutch-release change before altering ignition or fuel.',
        'Re-check gate preparation consistency between attempts.',
      ];

  return {
    attempts: attempts.length,
    bestTimeTo30: Math.min(...times),
    meanTimeTo30: +mean(times).toFixed(2),
    stdTimeTo30: +std(times).toFixed(3),
    meanWheelspin: +mean(spins).toFixed(1),
    rpmDropPctVsMean: (a) => +(((a.initialRpm - a.minRpmAfterRelease) - meanDrop) / meanDrop * 100).toFixed(0),
    recommendation,
    mapChangeAdvised,
  };
}
