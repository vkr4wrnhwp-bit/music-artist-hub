import { computeReadiness } from './readiness';
import type { Bike, Db } from './types';
import type { BikeReliability, ComponentLifeEstimate, DigitalTwinComponent, ReliabilityFactor } from './expansion';

/**
 * Digital twin + component life + reliability.
 * Life estimates are DEVELOPMENT: the interval math is real, but the
 * intervals themselves come from seeded team history, not validated wear data.
 */

export function twinFor(db: Db, bikeId: string): DigitalTwinComponent[] {
  return db.twin.filter((c) => c.bikeId === bikeId);
}

export function componentLife(comp: DigitalTwinComponent): ComponentLifeEstimate {
  if (!comp.typicalServiceH) {
    return {
      componentId: comp.id, status: 'Insufficient history',
      detail: 'No team service interval on file yet — tracking hours only.',
      kind: 'AI estimate', state: 'DEVELOPMENT',
    };
  }
  const ratio = comp.hours / comp.typicalServiceH;
  if (ratio >= 1) {
    return {
      componentId: comp.id, status: 'Service due',
      detail: `${comp.hours.toFixed(1)} h against a ${comp.typicalServiceH.toFixed(1)} h team interval.`,
      kind: 'Scheduled service', state: 'DEVELOPMENT',
    };
  }
  if (ratio >= 0.8) {
    return {
      componentId: comp.id, status: 'Approaching service',
      detail: `${comp.hours.toFixed(1)} h — similar components for this team begin degrading around ${comp.typicalServiceH.toFixed(1)} h.`,
      kind: 'Predicted service', state: 'DEVELOPMENT',
    };
  }
  return {
    componentId: comp.id, status: 'OK',
    detail: `${comp.hours.toFixed(1)} of ~${comp.typicalServiceH.toFixed(1)} h interval used.`,
    kind: 'Predicted service', state: 'DEVELOPMENT',
  };
}

/**
 * Reliability summary. Never reduces safety to one number: a failed critical
 * readiness gate overrides the score entirely.
 */
export function bikeReliability(db: Db, bike: Bike): BikeReliability {
  const readiness = computeReadiness(db, bike);
  const factors: ReliabilityFactor[] = [];
  const push = (label: string, score: number, detail: string, critical: boolean, pass: boolean) =>
    factors.push({ label, score: Math.max(0, Math.min(100, Math.round(score))), detail, critical, pass });

  const failedCritical = readiness.gates.find((g) => g.critical && !g.pass);

  push('Maintenance', bike.maintenanceStatus === 'Current' ? 100 : bike.maintenanceStatus === 'Due Soon' ? 70 : 20,
    `Status: ${bike.maintenanceStatus}`, true, bike.maintenanceStatus !== 'Required');
  push('Engine hours', Math.max(20, 100 - bike.hoursSinceRebuild * 8),
    `${bike.hoursSinceRebuild.toFixed(1)} h since rebuild`, false, true);

  const comps = twinFor(db, bike.id);
  const due = comps.map(componentLife).filter((l) => l.status === 'Service due');
  const approaching = comps.map(componentLife).filter((l) => l.status === 'Approaching service');
  push('Component life', 100 - due.length * 30 - approaching.length * 10,
    due.length || approaching.length
      ? `${due.length} due, ${approaching.length} approaching service`
      : 'All tracked components inside intervals', false, due.length === 0);

  const device = db.devices.find((d) => d.id === bike.hardwareDeviceId);
  const badCh = device ? Object.values(device.channelHealth).filter((q) => q === 'Missing' || q === 'Intermittent' || q === 'Out of range').length : 1;
  push('Electronics & sensors', badCh === 0 ? 100 : 60 - badCh * 15,
    badCh ? `${badCh} channel fault${badCh > 1 ? 's' : ''}` : 'All channels healthy (SIMULATED)', false, badCh === 0);

  const mapGate = readiness.gates.find((g) => g.id === 'transfer');
  push('ECU / map confirmation', mapGate?.pass ? 100 : 30, mapGate?.detail ?? 'No map', true, !!mapGate?.pass);

  const faults = db.faults.filter((f) => f.bikeId === bike.id && !f.resolved);
  push('Fault history', 100 - faults.length * 25, faults.length ? `${faults.length} open fault${faults.length > 1 ? 's' : ''}` : 'No open faults', false, faults.length === 0);

  if (failedCritical) {
    return { scorePct: null, overriddenBy: `${failedCritical.label}: ${failedCritical.detail}`, factors };
  }
  const score = Math.round(factors.reduce((s, f) => s + f.score, 0) / factors.length);
  return { scorePct: score, factors };
}
