import "server-only";
import { db } from "./db";

/**
 * Append-only audit trail.
 *
 * Manufacturing requires history. If a feed rate, a tolerance or a material
 * changes between the part that passed inspection and the part that failed,
 * somebody has to be able to find out what changed, when, and whether a human
 * or a model did it. `actorType` is always passed explicitly — it is never
 * inferred, because the whole value of the field is that it is trustworthy.
 */

export type ActorType = "HUMAN" | "AI" | "SYSTEM";

export interface AuditEntry {
  organizationId: string;
  userId?: string | null;
  entityType: string;
  entityId: string;
  action: "CREATE" | "UPDATE" | "DELETE" | "APPROVE" | "GENERATE" | "EXPORT" | "ACCEPT_SUGGESTION" | "REJECT_SUGGESTION";
  actorType: ActorType;
  field?: string;
  oldValue?: string | null;
  newValue?: string | null;
  reason?: string;
}

export async function audit(entry: AuditEntry): Promise<void> {
  await db.auditLog.create({
    data: {
      organizationId: entry.organizationId,
      userId: entry.userId ?? null,
      entityType: entry.entityType,
      entityId: entry.entityId,
      action: entry.action,
      actorType: entry.actorType,
      field: entry.field,
      oldValue: entry.oldValue ?? null,
      newValue: entry.newValue ?? null,
      reason: entry.reason,
    },
  });
}

/** Records a field-level change set in one call, one row per changed field. */
export async function auditChanges(
  base: Omit<AuditEntry, "field" | "oldValue" | "newValue" | "action">,
  before: Record<string, unknown>,
  after: Record<string, unknown>,
): Promise<void> {
  const keys = new Set([...Object.keys(before), ...Object.keys(after)]);
  const rows = [...keys]
    .filter((k) => JSON.stringify(before[k]) !== JSON.stringify(after[k]))
    .map((k) => ({
      organizationId: base.organizationId,
      userId: base.userId ?? null,
      entityType: base.entityType,
      entityId: base.entityId,
      action: "UPDATE" as const,
      actorType: base.actorType,
      field: k,
      oldValue: serialize(before[k]),
      newValue: serialize(after[k]),
      reason: base.reason,
    }));
  if (rows.length) await db.auditLog.createMany({ data: rows });
}

const serialize = (v: unknown): string | null =>
  v === undefined || v === null ? null : typeof v === "string" ? v : JSON.stringify(v);
