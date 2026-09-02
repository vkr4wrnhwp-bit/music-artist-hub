import { notFound } from "next/navigation";
import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { TopBar } from "@/components/nav";
import { DataRow, LinkButton, Notice, Panel, SectionHeading, StatusChip, type Tone } from "@/components/ui";
import { OUTCOME_LABEL, type JobOutcomeCode } from "@/lib/engines/network";
import { compareCycle, JOB_STATUS_LABEL, NEXT_STATUS, type JobStatus } from "@/lib/engines/jobs";
import { JobTransport, OutcomeForm, ActualsForm } from "@/components/jobs/job-forms";
import { advanceJob, recordActuals, recordOutcome } from "../actions";

/**
 * ONE JOB
 *
 * What was estimated, what happened, and what it taught. The comparison is
 * the point of the page, and it is refused rather than faked when either
 * side is missing: a cycle time compared against a substituted estimate is a
 * number that looks like feedback and is not.
 */

const STATUS_TONE: Record<JobStatus, Tone> = {
  PLANNED: "unknown",
  SETUP: "review",
  RUNNING: "precision",
  COMPLETE: "pass",
  CANCELLED: "unknown",
};

export default async function JobPage(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  const user = await requireUser();
  const job = await db.job.findFirst({
    where: { id, organizationId: user.organizationId },
    include: { part: true, outcomes: { orderBy: { recordedAt: "desc" } } },
  });
  if (!job) notFound();

  const revision = await db.partRevision.findFirst({
    where: { partId: job.partId, revision: job.revision },
    include: { setups: { include: { operations: { orderBy: { sequence: "asc" } } }, orderBy: { sequence: "asc" } } },
  });
  const snapshot = revision?.releaseSnapshotJson
    ? (JSON.parse(revision.releaseSnapshotJson) as {
        overall: string;
        reservations: { id: string; label: string; status: string }[];
        cycleMinutes: number | null;
      })
    : null;

  const cycle = compareCycle(snapshot?.cycleMinutes ?? null, job.actualCycleMinutes);
  const status = job.status as JobStatus;
  const operations = (revision?.setups ?? []).flatMap((s) =>
    s.operations.map((o) => ({ id: o.id, label: `${s.name} — ${o.label}` })),
  );

  return (
    <>
      <TopBar>
        <Link href="/jobs" className="tech-label hover:text-platinum">Jobs</Link>
        <span className="text-muted">/</span>
        <span className="tech-label">{job.jobNumber}</span>
        <StatusChip tone={STATUS_TONE[status]}>{JOB_STATUS_LABEL[status]}</StatusChip>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-4xl space-y-6">
          <SectionHeading
            sub={`${job.part.name}, revision ${job.revision}, quantity ${job.quantity}. What was estimated against what the job did — and what it taught, scoped to the machine, tooling and material it was seen on.`}
          >
            {job.jobNumber}
          </SectionHeading>

          {/* ---------------- Where it is ---------------- */}
          <Panel title="Status" meta={<StatusChip tone={STATUS_TONE[status]}>{JOB_STATUS_LABEL[status]}</StatusChip>}>
            <div className="grid gap-x-8 sm:grid-cols-2">
              <DataRow label="Part" value={`${job.part.name} rev ${job.revision}`} />
              <DataRow label="Quantity" value={String(job.quantity)} />
              <DataRow label="Due" value={job.dueDate ? new Date(job.dueDate).toISOString().slice(0, 10) : "Not set"} />
              <DataRow label="Started" value={job.startedAt ? new Date(job.startedAt).toISOString().slice(0, 16).replace("T", " ") : "Not started"} />
              <DataRow label="Completed" value={job.completedAt ? new Date(job.completedAt).toISOString().slice(0, 16).replace("T", " ") : "—"} />
              <DataRow label="Scrap" value={String(job.scrapCount)} />
            </div>
            {NEXT_STATUS[status].length > 0 ? (
              <JobTransport next={NEXT_STATUS[status]} action={advanceJob.bind(null, job.id)} />
            ) : (
              <p className="tech-label mt-3">
                {status === "COMPLETE"
                  ? "Complete. A finished job is the record of what happened and is not reopened — another run is another job."
                  : "Cancelled."}
              </p>
            )}
          </Panel>

          {/* ---------------- Released against ---------------- */}
          {snapshot ? (
            <Panel title="Released against" meta={<StatusChip tone={snapshot.overall === "READY_TO_RUN" ? "pass" : "review"}>{snapshot.overall.replace(/_/g, " ")}</StatusChip>}>
              <p className="max-w-2xl text-[12.5px] leading-relaxed text-muted">
                The readiness picture at the moment this revision was released, not as it is now. Readiness moves as the
                shop&rsquo;s tools, instruments and machines change; this is what was known when somebody said run it.
              </p>
              {snapshot.reservations.length > 0 && (
                <ul className="mt-2 space-y-0.5">
                  {snapshot.reservations.map((r) => (
                    <li key={r.id} className="text-[12px] text-review">
                      — {r.label}: {r.status.replace(/_/g, " ").toLowerCase()}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          ) : (
            <Notice tone="review" title="No release snapshot">
              This job predates the release record, so what was known when it was raised is not on file.
            </Notice>
          )}

          {/* ---------------- Estimated against actual ---------------- */}
          <Panel title="Estimated against actual">
            {cycle ? (
              <>
                <p>
                  <span className="font-mono text-[26px] text-white tabular-nums">{cycle.ratio.toFixed(2)}×</span>
                  <span className="ml-2 text-[12px] text-muted">
                    estimated {cycle.estimatedMinutes.toFixed(1)} min, actual {cycle.actualMinutes.toFixed(1)} min
                    {" · "}
                    {cycle.deltaMinutes >= 0 ? "+" : ""}
                    {cycle.deltaMinutes.toFixed(1)} min per part
                  </span>
                </p>
                <p className="mt-2 max-w-2xl text-[12px] leading-relaxed text-muted">
                  The estimate is CANVAS&rsquo;s cycle time from the toolpaths at release. It excludes setup, tool
                  changes off the program, inspection and anything the operator did between parts.
                </p>
              </>
            ) : (
              <p className="text-[12.5px] leading-relaxed text-review">
                No comparison:{" "}
                {snapshot?.cycleMinutes == null
                  ? "no estimated cycle time was stored with the release"
                  : "the actual cycle time has not been recorded"}
                . Nothing is substituted for it — an actual seeded from the estimate would make this comparison agree
                with itself.
              </p>
            )}
            <ActualsForm job={{ actualCycleMinutes: job.actualCycleMinutes, actualSetupHours: job.actualSetupHours, scrapCount: job.scrapCount, notes: job.notes }} action={recordActuals.bind(null, job.id)} />
          </Panel>

          {/* ---------------- What happened ---------------- */}
          <Panel title={`Outcomes — ${job.outcomes.length}`} dense>
            {job.outcomes.length === 0 ? (
              <p className="p-4 text-[12px] text-muted">
                Nothing recorded yet. What held, what chattered, what scrapped and why is the most valuable data this
                job produces and the one most often lost.
              </p>
            ) : (
              <ul>
                {job.outcomes.map((o) => (
                  <li key={o.id} className="border-b border-line/60 px-4 py-3 last:border-0">
                    <div className="flex flex-wrap items-baseline justify-between gap-3">
                      <span className="font-mono text-[12.5px] text-platinum">
                        {OUTCOME_LABEL[o.code as JobOutcomeCode]}
                      </span>
                      <span className="tech-label">
                        {o.partsAffected} affected · {o.recordedBy ?? "unattributed"} ·{" "}
                        {new Date(o.recordedAt).toISOString().slice(0, 10)}
                      </span>
                    </div>
                    <p className="tech-label mt-1">Cause: {o.cause}</p>
                    {o.code !== "SUCCESS" && (
                      <p className="mt-1.5 text-[12px] leading-relaxed text-platinum-dim">
                        Corrective action: {o.correctiveAction}
                      </p>
                    )}
                    {o.notes && <p className="mt-1 text-[11.5px] leading-relaxed text-muted">{o.notes}</p>}
                    <p className="tech-label mt-1.5">
                      Scope — {o.materialName ?? "material not recorded"} ·{" "}
                      {o.machineId ? "machine recorded" : "machine not recorded"} ·{" "}
                      {o.toolNumber != null ? `T${o.toolNumber}` : "no tool"}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <OutcomeForm operations={operations} action={recordOutcome.bind(null, job.id)} />

          <Notice tone="review" title="What an outcome is allowed to teach">
            An observation is scoped to the machine, workholding and material it was seen on, and is never promoted
            into a published engineering fact. Where any part of that scope was not recorded it matches nothing — a
            missing machine is a missing fact, not a wildcard.
          </Notice>

          <LinkButton href={`/parts/${job.partId}`} size="sm">
            Open the part
          </LinkButton>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";
