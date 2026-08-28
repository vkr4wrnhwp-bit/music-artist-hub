import type { AuditEvent, Db } from './types';

let counter = 0;

/**
 * Append-only audit log. There is deliberately no update or delete API —
 * history is team IP and evidence. Callers never construct events directly.
 */
export function appendAudit(
  db: Db,
  actorUserId: string,
  action: string,
  entityType: string,
  entityId: string,
  summary: string,
  meta?: Record<string, unknown>,
): AuditEvent {
  const ev: AuditEvent = {
    id: `audit-${Date.now()}-${counter++}`,
    orgId: db.org.id,
    at: new Date().toISOString(),
    actorUserId,
    action,
    entityType,
    entityId,
    summary,
    meta,
  };
  db.audit.push(ev);
  return ev;
}

export function auditFor(db: Db, entityId: string): AuditEvent[] {
  return db.audit.filter((e) => e.entityId === entityId).sort((a, b) => b.at.localeCompare(a.at));
}
