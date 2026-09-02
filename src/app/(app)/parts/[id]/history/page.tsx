import { notFound } from "next/navigation";
import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { loadRevision } from "@/lib/data";
import { buildDnaTimeline, dnaCoverage, DNA_KIND_LABEL, type DnaInput } from "@/lib/engines/dna";
import { TopBar } from "@/components/nav";
import { Notice, Panel, SectionHeading, StatusChip, type Tone } from "@/components/ui";

/**
 * MANUFACTURING DNA
 *
 * Derived, never authored. Every row points at a record somebody's action
 * created — an audit entry, an approval, a job outcome, an inspection result,
 * a disagreement — and says which. A timeline that could be typed into would
 * go stale the moment somebody forgot, and could claim an event that never
 * happened.
 */

const SOURCE_LABEL: Record<string, string> = {
  PART_REVISION: "revision record",
  AUDIT_LOG: "audit log",
  APPROVAL: "approval",
  SIMULATION: "simulation record",
  JOB: "job",
  JOB_OUTCOME: "job outcome",
  INSPECTION_RESULT: "inspection result",
  DISAGREEMENT: "disagreement",
  FINDING_RESOLUTION: "review finding",
};

const KIND_TONE: Record<string, Tone> = {
  OUTCOME_OBSERVED: "risk",
  DISAGREEMENT_RAISED: "review",
  RELEASED: "pass",
  APPROVED: "pass",
  INSPECTION_RECORDED: "precision",
};

export default async function HistoryPage(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  const user = await requireUser();
  const revision = await loadRevision(user.organizationId, id);
  if (!revision) notFound();

  const rev = await db.partRevision.findUnique({
    where: { id: revision.revisionId },
    select: { id: true, revision: true, createdAt: true, releasedAt: true, releasedBy: true },
  });
  if (!rev) notFound();

  const [features, setups, approvals, simulations, jobs, disagreements, findings, plans] = await Promise.all([
    db.feature.findMany({ where: { partRevisionId: rev.id }, select: { id: true } }),
    db.setup.findMany({ where: { partRevisionId: rev.id }, select: { id: true, name: true } }),
    db.approval.findMany({ where: { partRevisionId: rev.id }, include: { user: { select: { name: true, email: true } } } }),
    db.simulation.findMany({ where: { setup: { partRevisionId: rev.id } }, include: { setup: { select: { name: true } } } }),
    db.job.findMany({ where: { organizationId: user.organizationId, partId: revision.partId, revision: rev.revision }, include: { outcomes: true } }),
    db.disagreement.findMany({ where: { partRevisionId: rev.id }, include: { user: { select: { name: true, email: true } } } }),
    db.reviewFinding.findMany({ where: { partRevisionId: rev.id }, include: { resolutions: true } }),
    db.inspectionPlan.findMany({ where: { partRevisionId: rev.id }, include: { items: { include: { results: true } } } }),
  ]);

  // Audit entries for the revision and everything under it. The ids are
  // gathered from the rows themselves rather than matched by a string, so a
  // renamed entity type cannot silently empty the timeline.
  const auditIds = [rev.id, ...features.map((f) => f.id), ...setups.map((s) => s.id)];
  const audit = await db.auditLog.findMany({
    where: { organizationId: user.organizationId, entityId: { in: auditIds } },
    include: { user: { select: { name: true, email: true } } },
    orderBy: { createdAt: "desc" },
    take: 300,
  });

  const input: DnaInput = {
    revision: rev,
    audit: audit.map((a) => ({
      id: a.id, entityType: a.entityType, entityId: a.entityId, action: a.action,
      field: a.field, oldValue: a.oldValue, newValue: a.newValue, actorType: a.actorType,
      reason: a.reason, createdAt: a.createdAt,
      userName: a.user?.name ?? a.user?.email ?? null,
    })),
    approvals: approvals.map((a) => ({
      id: a.id, scope: a.scope, statement: a.statement, approvedAt: a.approvedAt, revokedAt: a.revokedAt,
      userName: a.user?.name ?? a.user?.email ?? null,
    })),
    simulations: simulations.map((s) => ({ id: s.id, runAt: s.runAt, collisionChecked: s.collisionChecked, setupName: s.setup.name })),
    jobs: jobs.map((j) => ({
      id: j.id, jobNumber: j.jobNumber, quantity: j.quantity, status: j.status,
      createdAt: j.createdAt,
      completedAt: j.completedAt, actualCycleMinutes: j.actualCycleMinutes, scrapCount: j.scrapCount,
    })),
    outcomes: jobs.flatMap((j) =>
      j.outcomes.map((o) => ({
        id: o.id, jobNumber: j.jobNumber, code: o.code, cause: o.cause,
        correctiveAction: o.correctiveAction, partsAffected: o.partsAffected,
        recordedAt: o.recordedAt, recordedBy: o.recordedBy,
      })),
    ),
    inspections: plans.flatMap((p) =>
      p.items.flatMap((it) =>
        it.results.map((r) => ({
          id: r.id, label: it.label, measured: r.measured, pass: r.pass,
          measuredAt: r.measuredAt, inspector: r.inspector,
        })),
      ),
    ),
    disagreements: disagreements.map((d) => ({
      id: d.id, subjectType: d.subjectType, canvasPosition: d.canvasPosition, reasoning: d.reasoning,
      status: d.status, createdAt: d.createdAt,
      userName: d.user?.name ?? d.user?.email ?? null,
    })),
    findingResolutions: findings.flatMap((f) =>
      f.resolutions.map((r) => ({
        id: r.id, findingTitle: f.title, status: r.status, note: r.note,
        actorType: r.actorType, actorName: r.actorName, recordedAt: r.recordedAt,
      })),
    ),
  };

  const timeline = buildDnaTimeline(input);
  const coverage = dnaCoverage(input);
  const absent = coverage.filter((c) => !c.present);

  return (
    <>
      <TopBar>
        <Link href={`/parts/${id}`} className="tech-label hover:text-platinum">{revision.partName}</Link>
        <span className="text-muted">/</span>
        <span className="tech-label">History</span>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-4xl space-y-6">
          <SectionHeading sub="What has actually happened to this revision, newest first. Every entry is read from a record somebody's action created and says which one — nothing here is typed in, summarised or inferred, so it cannot claim an event that did not happen.">
            Manufacturing DNA
          </SectionHeading>

          <Panel title={`${timeline.length} event${timeline.length === 1 ? "" : "s"}`} dense>
            <ol>
              {timeline.map((e) => (
                <li key={`${e.source}-${e.sourceId}-${e.at.getTime()}`} className="border-b border-line/60 px-4 py-3 last:border-0">
                  <div className="flex flex-wrap items-baseline justify-between gap-3">
                    <span className="flex flex-wrap items-center gap-2">
                      <StatusChip tone={KIND_TONE[e.kind] ?? "unknown"}>{DNA_KIND_LABEL[e.kind]}</StatusChip>
                      <span className="font-mono text-[12.5px] text-platinum">{e.title}</span>
                    </span>
                    <span className="tech-label">{new Date(e.at).toISOString().slice(0, 16).replace("T", " ")}</span>
                  </div>
                  <p className="mt-1 max-w-2xl text-[12px] leading-relaxed text-platinum-dim">{e.detail}</p>
                  <p className="tech-label mt-1">
                    From the {SOURCE_LABEL[e.source] ?? e.source.toLowerCase()} ·{" "}
                    {e.actor.name ?? "actor not recorded"}
                    {" · "}
                    {e.actor.type ?? "actor type not recorded"}
                  </p>
                </li>
              ))}
            </ol>
          </Panel>

          {absent.length > 0 && (
            <Notice tone="review" title="What this history could not draw on">
              <p className="text-[12px] leading-relaxed">
                Nothing has been recorded yet in: {absent.map((a) => SOURCE_LABEL[a.source] ?? a.source).join(", ")}.
                A short history means little has happened to this revision, not that little was checked.
              </p>
            </Notice>
          )}
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";
