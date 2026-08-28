import { computeReadiness } from './readiness';
import { componentLife, twinFor } from './twin';
import type { AuditEvent, Bike, Db, User } from './types';
import type { ChecklistItem, RemoteAccessGrant } from './expansion';

/**
 * Race operations: dynamic checklists, timeline, morning brief, debrief
 * drafting, remote-access grants. Checklists derive from real bike state —
 * the READY TO RACE verdict is the readiness engine plus race-day items.
 */

export function buildChecklist(db: Db, bike: Bike): { items: ChecklistItem[]; ready: boolean; blockers: string[] } {
  const readiness = computeReadiness(db, bike);
  const items: ChecklistItem[] = [];
  const gate = (id: string) => readiness.gates.find((g) => g.id === id);
  const fromGate = (id: string, label: string) => {
    const g = gate(id);
    items.push({ id, label, status: g?.pass ? 'pass' : 'blocked', detail: g?.detail ?? 'No data' });
  };
  fromGate('mapAssigned', 'Map verification');
  fromGate('transfer', 'ECU transfer confirmed');
  fromGate('maintenance', 'Maintenance current');
  fromGate('hardware', 'MX Node mounted');
  fromGate('sensors', 'Sensor status');
  fromGate('storage', 'Logger storage');

  // component-driven items
  for (const comp of twinFor(db, bike.id)) {
    const life = componentLife(comp);
    if (life.status === 'Service due') {
      items.push({ id: `life-${comp.id}`, label: `${comp.label} service`, status: 'blocked', detail: life.detail });
    } else if (life.status === 'Approaching service') {
      items.push({ id: `life-${comp.id}`, label: `${comp.label} inspection`, status: 'manual', detail: life.detail, checked: false });
    }
  }
  // standing manual race-day items
  for (const [id, label] of [
    ['fuel-load', 'Fuel load'], ['air-filter', 'Air filter'], ['chain', 'Chain tension & lube'],
    ['tire-pressure', 'Tire pressures set'], ['torque', 'Torque verification'], ['controls', 'Controls check'],
  ] as const) {
    items.push({ id, label, status: 'manual', detail: 'Physical check — confirm by hand.', checked: false });
  }
  const blockers = items.filter((i) => i.status === 'blocked').map((i) => `${i.label}: ${i.detail}`);
  return { items, ready: blockers.length === 0, blockers };
}

/** Race-day timeline — real system events (audit) for a given day, oldest first. */
export function dayTimeline(db: Db, dateISO: string, bikeId?: string): AuditEvent[] {
  const day = dateISO.slice(0, 10);
  return db.audit
    .filter((e) => e.at.slice(0, 10) === day)
    .filter((e) => !bikeId
      || e.entityId === bikeId
      || db.sessions.some((s) => s.id === e.entityId && s.bikeId === bikeId)
      || db.mapRevisions.some((r) => r.id === e.entityId && db.bikes.find((b) => b.id === bikeId)?.currentMapRevisionId === r.id))
    .sort((a, b) => a.at.localeCompare(b.at));
}

export interface MorningBriefData {
  ready: number;
  total: number;
  maintenanceItems: string[];
  focus?: string;
  openInsights: number;
  watch: string[];
  scheduled: string[];
}

export function morningBrief(db: Db): MorningBriefData {
  const bikes = db.bikes.filter((b) => !b.retired);
  const ready = bikes.filter((b) => computeReadiness(db, b).readyForInstrumentedTest).length;
  const maintenanceItems = bikes
    .filter((b) => b.maintenanceStatus !== 'Current')
    .map((b) => `${b.label}: maintenance ${b.maintenanceStatus.toLowerCase()}`);
  const watch: string[] = [];
  for (const b of bikes) {
    for (const comp of twinFor(db, b.id)) {
      const life = componentLife(comp);
      if (life.status !== 'OK' && life.status !== 'Insufficient history') watch.push(`${b.label} ${comp.label}: ${life.status.toLowerCase()}`);
    }
    for (const f of db.faults.filter((x) => x.bikeId === b.id && !x.resolved)) watch.push(`${b.label}: open fault ${f.code}`);
  }
  if (db.focus) watch.push(`Focus objective: ${db.focus.text}`);
  const scheduled = db.testPlans.filter((p) => p.status === 'planned' || p.status === 'running')
    .map((p) => `${db.bikes.find((b) => b.id === p.bikeId)?.label}: ${p.objective} (${p.variants.map((v) => v.label).join(' vs ')})`);
  return {
    ready, total: bikes.length, maintenanceItems,
    focus: db.focus?.text,
    openInsights: db.recommendations.filter((r) => r.status === 'AWAITING_TUNER_REVIEW').length,
    watch: watch.slice(0, 5),
    scheduled,
  };
}

export interface DebriefDraft { learned: string[]; tomorrow: string[] }

/** Draft an end-of-day debrief from real records; humans edit and approve. */
export function draftDebrief(db: Db, dateISO: string): DebriefDraft {
  const day = dateISO.slice(0, 10);
  const learned: string[] = [];
  const tomorrow: string[] = [];
  for (const ab of db.abTests.filter((t) => t.outcome)) {
    learned.push(`${ab.name}: ${ab.conclusion ?? `outcome ${ab.outcome}`}`);
  }
  for (const d of db.decisions.filter((x) => x.at.slice(0, 10) === day)) {
    learned.push(`Decision: ${d.decision}`);
    if (d.followUp) tomorrow.push(d.followUp);
  }
  for (const p of db.testPlans.filter((x) => x.status === 'complete' && x.conclusion)) {
    learned.push(`Test “${p.objective}”: ${p.conclusion}`);
  }
  for (const b of db.bikes.filter((x) => !x.retired)) {
    for (const f of db.faults.filter((x) => x.bikeId === b.id && !x.resolved)) {
      tomorrow.push(`Inspect ${b.label}: ${f.note}`);
    }
    if (b.maintenanceStatus !== 'Current') tomorrow.push(`Service ${b.label} (maintenance ${b.maintenanceStatus.toLowerCase()}).`);
  }
  for (const p of db.testPlans.filter((x) => x.status === 'planned')) {
    tomorrow.push(`Run planned test: ${p.objective}.`);
  }
  return { learned: learned.length ? learned : ['No concluded tests or decisions recorded today.'], tomorrow };
}

// ------------------------------------------------------------- remote access

export function grantIsActive(g: RemoteAccessGrant, now = new Date()): boolean {
  return !g.revokedAt && new Date(g.expiresAt) > now;
}

export function grantAllows(g: RemoteAccessGrant, action: 'telemetry' | 'maps' | 'export' | 'mapEdit' | 'comment', bikeId: string, now = new Date()): boolean {
  if (!grantIsActive(g, now)) return false;
  if (!g.bikeIds.includes(bikeId)) return false;
  switch (action) {
    case 'telemetry': return g.readTelemetry;
    case 'maps': return g.readMaps;
    case 'export': return g.exportAllowed;
    case 'mapEdit': return g.mapEditAllowed;
    case 'comment': return g.commentAccess;
  }
}
