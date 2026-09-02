import { db } from "@/lib/db";
import type { ReviewFinding } from "@/lib/engines/review";
import type { ActorType } from "@/lib/audit";
import { evidenceDigest, type FindingRecord, type ResolutionStatus } from "@/lib/review-findings";

/**
 * The database half of review-finding persistence. The vocabulary, the digest
 * rule and the shape of a record live in `review-findings.ts`, which stays
 * free of `db` so the rules can be tested without a database and so a client
 * component can name the types.
 */

/**
 * Reconciles the freshly computed findings against what is on record, and
 * returns the history for each.
 *
 * A finding the engine no longer raises is marked cleared rather than
 * deleted — the evidence changed, and that is worth being able to see. It is
 * un-cleared if it comes back.
 */
export async function syncFindings(
  organizationId: string,
  partRevisionId: string,
  findings: ReviewFinding[],
): Promise<Record<string, FindingRecord>> {
  const rows = await db.reviewFinding.findMany({
    where: { partRevisionId },
    include: { resolutions: { orderBy: { recordedAt: "desc" } } },
  });
  const byKey = new Map(rows.map((r) => [r.findingKey, r]));
  const now = new Date();

  for (const f of findings) {
    const digest = evidenceDigest(f.severity, f.evidence);
    const snapshot = {
      severity: f.severity,
      title: f.title,
      detail: f.detail,
      method: f.method,
      evidenceJson: JSON.stringify(f.evidence),
      evidenceDigest: digest,
      lastSeenAt: now,
      clearedAt: null,
    };
    const existing = byKey.get(f.key);
    if (existing) {
      await db.reviewFinding.update({ where: { id: existing.id }, data: snapshot });
      Object.assign(existing, snapshot);
    } else {
      const created = await db.reviewFinding.create({
        data: { organizationId, partRevisionId, findingKey: f.key, firstSeenAt: now, ...snapshot },
      });
      byKey.set(f.key, { ...created, resolutions: [] });
    }
  }

  // Raised before, not raised now. The engine stopped saying it, which is the
  // only way a finding legitimately goes away.
  const live = new Set(findings.map((f) => f.key));
  const stillOpen = rows.filter((r) => !live.has(r.findingKey) && r.clearedAt === null);
  if (stillOpen.length > 0) {
    await db.reviewFinding.updateMany({ where: { id: { in: stillOpen.map((r) => r.id) } }, data: { clearedAt: now } });
  }

  const out: Record<string, FindingRecord> = {};
  for (const f of findings) {
    const row = byKey.get(f.key)!;
    const latest = row.resolutions[0];
    out[f.key] = {
      findingKey: f.key,
      firstSeenAt: row.firstSeenAt,
      lastSeenAt: now,
      clearedAt: null,
      resolution: latest
        ? {
            status: latest.status as ResolutionStatus,
            note: latest.note,
            actorType: latest.actorType as ActorType,
            actorName: latest.actorName,
            recordedAt: latest.recordedAt,
            current: latest.evidenceDigest === row.evidenceDigest,
          }
        : null,
      history: row.resolutions.map((r) => ({
        status: r.status as ResolutionStatus,
        note: r.note,
        actorName: r.actorName,
        actorType: r.actorType as ActorType,
        recordedAt: r.recordedAt,
      })),
    };
  }
  return out;
}

/** Findings previously raised against this revision that the engine no longer raises. */
export async function clearedFindings(partRevisionId: string) {
  return db.reviewFinding.findMany({
    where: { partRevisionId, clearedAt: { not: null } },
    orderBy: { clearedAt: "desc" },
    select: { findingKey: true, title: true, severity: true, firstSeenAt: true, clearedAt: true },
  });
}
