import type { Db, MapRevision } from './types';

/**
 * Offline synchronization policy (section 28). Phase 1 is local-first; this
 * module defines — and tests enforce — the merge rules a future backend must
 * follow:
 *   - conflicts preserve BOTH versions and require human review
 *   - map approvals and tuner decisions are never silently overwritten
 */
export interface SyncConflict {
  entityType: string;
  entityId: string;
  local: unknown;
  remote: unknown;
  reason: string;
  requiresReview: true;
}

export interface MergeOutcome {
  merged: Db;
  conflicts: SyncConflict[];
}

/** fields whose divergence is never auto-resolved */
const PROTECTED_REVISION_FIELDS: Array<keyof MapRevision> = [
  'state', 'approvedByUserId', 'approvedAt',
];

export function mergeMapRevisions(localDb: Db, remoteRevisions: MapRevision[]): MergeOutcome {
  const merged: Db = JSON.parse(JSON.stringify(localDb));
  const conflicts: SyncConflict[] = [];

  for (const remote of remoteRevisions) {
    const idx = merged.mapRevisions.findIndex((r) => r.id === remote.id);
    if (idx === -1) {
      merged.mapRevisions.push(remote); // new remote revision — additive, safe
      continue;
    }
    const local = merged.mapRevisions[idx];
    const protectedDiverged = PROTECTED_REVISION_FIELDS.some(
      (f) => JSON.stringify(local[f]) !== JSON.stringify(remote[f]),
    );
    const tablesDiverged = JSON.stringify(local.tables) !== JSON.stringify(remote.tables);
    if (protectedDiverged || tablesDiverged) {
      // preserve both: local stays in place, remote parked for review
      conflicts.push({
        entityType: 'MapRevision',
        entityId: remote.id,
        local,
        remote,
        reason: protectedDiverged
          ? 'Approval/decision fields diverged — human review required; nothing was overwritten.'
          : 'Map tables diverged while offline — both versions preserved for review.',
        requiresReview: true,
      });
    }
    // identical or non-protected metadata only → local wins, no data loss
  }
  return { merged, conflicts };
}
