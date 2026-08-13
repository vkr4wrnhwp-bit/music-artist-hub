import { assertCan } from './permissions';
import { appendAudit } from './audit';
import { checkCompatibility } from './compatibility';
import type { Db, MapRevision, MapRevisionState, User } from './types';

/**
 * Map lifecycle (section 8.5). Every transition is role-gated and audited.
 * There is no code path that flashes an ECU — TRANSFER_CONFIRMED only records
 * that an authorized person performed the change in the external Vortex
 * workflow and confirmed it here.
 */
const TRANSITIONS: Record<MapRevisionState, MapRevisionState[]> = {
  DRAFT: ['TUNER_REVIEW'],
  TUNER_REVIEW: ['APPROVED_FOR_TEST', 'REJECTED', 'DRAFT'],
  APPROVED_FOR_TEST: ['EXPORTED', 'RETIRED'],
  EXPORTED: ['TRANSFER_CONFIRMED', 'RETIRED'],
  TRANSFER_CONFIRMED: ['TESTED'],
  TESTED: ['ACCEPTED', 'REJECTED', 'REVISED'],
  ACCEPTED: ['TEAM_BASELINE', 'RETIRED'],
  REJECTED: ['REVISED', 'RETIRED'],
  REVISED: ['DRAFT'],
  TEAM_BASELINE: ['RETIRED'],
  RETIRED: [],
};

const ACTION_FOR: Partial<Record<MapRevisionState, Parameters<typeof assertCan>[1]>> = {
  TUNER_REVIEW: 'map.submitForReview',
  APPROVED_FOR_TEST: 'map.approveForTest',
  REJECTED: 'map.reject',
  ACCEPTED: 'ai.decide',
  TEAM_BASELINE: 'map.promoteBaseline',
  RETIRED: 'map.retire',
  EXPORTED: 'map.export',
  TRANSFER_CONFIRMED: 'transfer.confirm',
};

export function canTransition(from: MapRevisionState, to: MapRevisionState): boolean {
  return TRANSITIONS[from]?.includes(to) ?? false;
}

export function transitionRevision(
  db: Db,
  actor: User,
  revision: MapRevision,
  to: MapRevisionState,
  note?: string,
): MapRevision {
  if (!canTransition(revision.state, to)) {
    throw new Error(`Invalid map workflow transition: ${revision.state} → ${to}`);
  }
  const action = ACTION_FOR[to];
  if (action) assertCan(actor.role, action);

  if (to === 'APPROVED_FOR_TEST') {
    // approval is a human act: it must carry the approver's identity
    revision.approvedByUserId = actor.id;
    revision.approvedAt = new Date().toISOString();
    // an approval against an incompatible bike is meaningless — verify against
    // any bike currently pointed at this revision
    const bike = db.bikes.find((b) => b.currentMapRevisionId === revision.id);
    if (bike) {
      const compat = checkCompatibility(revision.compatibility, db, bike);
      if (compat.blocking) {
        throw new Error(`Cannot approve: ${compat.verdict} — ${compat.details[0]}`);
      }
    }
  }

  const from = revision.state;
  revision.state = to;
  appendAudit(db, actor.id, `map.${to.toLowerCase()}`, 'MapRevision', revision.id,
    `${revision.rev}: ${from.replaceAll('_', ' ')} → ${to.replaceAll('_', ' ')}${note ? ` — ${note}` : ''}`);
  return revision;
}

/** Cell-level diff between two revisions of the same map definition. */
export interface CellDiff {
  tableId: string;
  x: number;
  y: number;
  a: number;
  b: number;
  delta: number;
}

export function diffRevisions(a: MapRevision, b: MapRevision): CellDiff[] {
  const out: CellDiff[] = [];
  for (const tableId of Object.keys(b.tables)) {
    const ta = a.tables[tableId];
    const tb = b.tables[tableId];
    if (!ta || !tb) continue;
    tb.forEach((row, y) => row.forEach((vb, x) => {
      const va = ta[y]?.[x] ?? 0;
      if (va !== vb) out.push({ tableId, x, y, a: va, b: vb, delta: +(vb - va).toFixed(3) });
    }));
  }
  return out;
}

export function diffTrims(a: MapRevision, b: MapRevision): Array<{ trim: string; a: number; b: number }> {
  const keys = new Set([...Object.keys(a.globalTrims), ...Object.keys(b.globalTrims)]);
  return [...keys]
    .filter((k) => a.globalTrims[k] !== b.globalTrims[k])
    .map((k) => ({ trim: k, a: a.globalTrims[k] ?? 0, b: b.globalTrims[k] ?? 0 }));
}

/**
 * Envelope check: a proposed revision whose largest single-cell change exceeds
 * the tuner-defined validated envelope is flagged. AI can propose inside the
 * envelope only; it can never define or widen one.
 */
export function exceedsEnvelope(
  db: Db,
  base: MapRevision,
  proposed: MapRevision,
): { exceeded: boolean; details: string[] } {
  const env = db.envelopes.find(
    (e) => e.ecuDefinitionId === proposed.compatibility.ecuDefinitionId
      && e.version === proposed.compatibility.envelopeVersion,
  );
  if (!env) return { exceeded: true, details: ['No validated tuning envelope exists for this ECU definition — tuner must define one before approval.'] };
  const details: string[] = [];
  for (const d of diffRevisions(base, proposed)) {
    const max = env.maxStepDelta[d.tableId];
    if (max !== undefined && Math.abs(d.delta) > max) {
      details.push(`${d.tableId}[${d.y}][${d.x}] change ${d.delta > 0 ? '+' : ''}${d.delta} exceeds validated step of ±${max}.`);
    }
  }
  return { exceeded: details.length > 0, details };
}
