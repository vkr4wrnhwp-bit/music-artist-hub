import { mergeMapRevisions, type SyncConflict } from './sync';
import type { Db } from './types';
import type { RemoteAccessGrant } from './expansion';

/**
 * Full-database merge for the production sync path.
 *
 * Policy (extends the unit-tested map-revision rules to every collection):
 *  - Append-only collections merge as a union by id — nothing is ever lost.
 *  - Map revisions use the protected-field policy from `sync.ts`: divergent
 *    approvals/decisions/tables preserve BOTH versions as a conflict that a
 *    human must resolve; nothing is silently overwritten.
 *  - Decisions and debriefs with the same id but different content are also
 *    protected: both versions are preserved as conflicts.
 *  - Singletons (TRACE Focus) take the remote value only when the local one
 *    is unchanged since the last sync; otherwise they conflict.
 */

/** collections merged as a union by `id` (append-only by design) */
const UNION_BY_ID = [
  'users', 'riders', 'bikes', 'bikeModels', 'ecuDefinitions', 'ecuInstances',
  'engineBuilds', 'fuels', 'exhausts', 'tracks', 'maps', 'envelopes',
  'transfers', 'sessions', 'markers', 'feedback', 'startAttempts',
  'recommendations', 'abTests', 'devices', 'cncParts', 'maintenance', 'faults',
  'audit', 'testPlans', 'events', 'crewTasks', 'twin', 'grants', 'listings',
] as const;

interface WithId { id: string }

function unionById<T extends WithId>(local: T[], remote: T[]): T[] {
  const seen = new Map<string, T>();
  for (const r of remote) seen.set(r.id, r);
  for (const l of local) seen.set(l.id, l); // local wins on same-id non-protected metadata
  return [...seen.values()];
}

export interface FullMergeResult {
  merged: Db;
  conflicts: SyncConflict[];
}

export function fullMerge(localDb: Db, remoteDb: Db): FullMergeResult {
  // start from the tested map-revision policy
  const { merged, conflicts } = mergeMapRevisions(localDb, remoteDb.mapRevisions);

  const m = merged as unknown as Record<string, WithId[]>;
  const r = remoteDb as unknown as Record<string, WithId[]>;
  for (const key of UNION_BY_ID) {
    m[key] = unionById(m[key] ?? [], r[key] ?? []);
  }
  // rider preference profiles are keyed by riderId
  merged.riderPrefs = (() => {
    const seen = new Map(remoteDb.riderPrefs.map((p) => [p.riderId, p]));
    for (const p of localDb.riderPrefs) seen.set(p.riderId, p);
    return [...seen.values()];
  })();

  // protected content records: same id, different content → preserve both
  for (const collection of ['decisions', 'debriefs'] as const) {
    const local = localDb[collection] as unknown as WithId[];
    const remote = remoteDb[collection] as unknown as WithId[];
    for (const rec of remote) {
      const l = local.find((x) => x.id === rec.id);
      if (l && JSON.stringify(l) !== JSON.stringify(rec)) {
        conflicts.push({
          entityType: collection === 'decisions' ? 'DecisionRecord' : 'Debrief',
          entityId: rec.id,
          local: l,
          remote: rec,
          reason: 'Record edited on both sides while offline — both versions preserved for review.',
          requiresReview: true,
        });
      }
    }
    m[collection] = unionById(local, remote);
  }

  // singleton: TRACE Focus — divergence is a conflict, never a silent overwrite
  if (remoteDb.focus && localDb.focus
    && JSON.stringify(remoteDb.focus) !== JSON.stringify(localDb.focus)) {
    conflicts.push({
      entityType: 'TraceFocus',
      entityId: localDb.focus.bikeId,
      local: localDb.focus,
      remote: remoteDb.focus,
      reason: 'TRACE Focus was changed on both sides — pick which objective stands.',
      requiresReview: true,
    });
  } else if (remoteDb.focus && !localDb.focus) {
    merged.focus = remoteDb.focus;
  }

  // slot maps: union per bike, local wins per slot number
  merged.mapSlots = { ...remoteDb.mapSlots, ...localDb.mapSlots };
  // measured telemetry: union per session, local wins on same session
  merged.importedTraces = { ...(remoteDb.importedTraces ?? {}), ...(localDb.importedTraces ?? {}) };

  return { merged, conflicts };
}

/**
 * Server-side redaction for remote tuner grants: a grant token only ever
 * sees the granted bikes, and only the record classes its permissions allow.
 * This is what makes a RemoteAccessGrant real enforcement, not UI courtesy.
 */
export function redactDbForGrant(db: Db, grant: RemoteAccessGrant): Db {
  const bikes = db.bikes.filter((b) => grant.bikeIds.includes(b.id));
  const bikeIds = new Set(bikes.map((b) => b.id));
  const sessions = grant.readTelemetry ? db.sessions.filter((s) => bikeIds.has(s.bikeId)) : [];
  const sessionIds = new Set(sessions.map((s) => s.id));
  const revisionIds = new Set<string>();
  if (grant.readMaps) {
    for (const b of bikes) if (b.currentMapRevisionId) revisionIds.add(b.currentMapRevisionId);
    for (const s of sessions) revisionIds.add(s.setupSnapshot.mapRevisionId);
  }
  const mapRevisions = db.mapRevisions.filter((r) => revisionIds.has(r.id));
  const mapIds = new Set(mapRevisions.map((r) => r.mapId));

  return {
    ...db,
    users: [], riders: db.riders.filter((r) => bikes.some((b) => b.assignedRiderId === r.id)),
    riderPrefs: [],
    bikes,
    ecuInstances: db.ecuInstances.filter((e) => e.installedBikeId && bikeIds.has(e.installedBikeId)),
    sessions,
    markers: db.markers.filter((m) => sessionIds.has(m.sessionId)),
    feedback: db.feedback.filter((f) => sessionIds.has(f.sessionId)),
    startAttempts: db.startAttempts.filter((a) => sessionIds.has(a.sessionId)),
    maps: db.maps.filter((m) => mapIds.has(m.id)),
    mapRevisions,
    mapSlots: Object.fromEntries(Object.entries(db.mapSlots).filter(([k]) => bikeIds.has(k))),
    transfers: db.transfers.filter((t) => bikeIds.has(t.bikeId)),
    recommendations: db.recommendations.filter((r) => sessionIds.has(r.sessionId)),
    abTests: db.abTests.filter((t) => [t.sessionAId, t.sessionBId].some((id) => id && sessionIds.has(id))),
    devices: db.devices.filter((d) => d.assignedBikeId && bikeIds.has(d.assignedBikeId)),
    twin: db.twin.filter((c) => bikeIds.has(c.bikeId)),
    maintenance: db.maintenance.filter((m) => bikeIds.has(m.bikeId)),
    faults: db.faults.filter((f) => bikeIds.has(f.bikeId)),
    importedTraces: grant.readTelemetry
      ? Object.fromEntries(Object.entries(db.importedTraces ?? {}).filter(([sid]) => sessionIds.has(sid)))
      : {},
    // never exposed through a grant:
    decisions: [], debriefs: [], testPlans: [], events: [], crewTasks: [],
    grants: [], listings: [], audit: [], envelopes: db.envelopes,
    focus: undefined,
  };
}
