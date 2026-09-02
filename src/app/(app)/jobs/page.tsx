import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { OUTCOME_LABEL, type JobOutcomeCode } from "@/lib/engines/network";
import { JOB_STATUS_LABEL, type JobStatus } from "@/lib/engines/jobs";
import { TopBar } from "@/components/nav";
import { EmptyState, Notice, Panel, SectionHeading, StatusChip, Table, Td, type Tone } from "@/components/ui";
import { RaiseJobForm } from "@/components/jobs/raise-job";
import { createJob } from "./actions";

export default async function JobsPage() {
  const user = await requireUser();
  const jobs = await db.job.findMany({
    where: { organizationId: user.organizationId },
    include: { part: true, outcomes: true },
    orderBy: { startedAt: "desc" },
  });

  const outcomes = jobs.flatMap((j) => j.outcomes);
  const failures = outcomes.filter((o) => o.code !== "SUCCESS");

  // A job is raised against a RELEASED revision. That was always what the
  // page said; until release existed there was nothing to raise one against.
  const released = await db.partRevision.findMany({
    where: { status: "RELEASED", part: { organizationId: user.organizationId } },
    orderBy: { releasedAt: "desc" },
    select: { id: true, revision: true, releasedAt: true, part: { select: { id: true, name: true } } },
  });

  return (
    <>
      <TopBar>
        <span className="tech-label">Jobs</span>
      </TopBar>
      <main className="flex-1 space-y-6 overflow-y-auto p-4 sm:p-6">
        <SectionHeading sub="A job outcome is the most valuable data a shop generates and the one most often lost. What held, what chattered, what scrapped and why — recorded structurally so it can teach the workholding and process models rather than living in someone's memory.">
          Jobs
        </SectionHeading>

        <RaiseJobForm
          released={released.map((r) => ({ partId: r.part.id, partName: r.part.name, revision: r.revision }))}
          action={createJob}
        />

        {jobs.length === 0 ? (
          released.length === 0 ? (
            <EmptyState
              title="Nothing run yet"
              body="A job records what a run actually did — cycle time, setup hours, scrap, and what held or chattered or scrapped and why. The notice above says what has to happen before one can be raised."
              action={{ label: "Parts", href: "/parts" }}
            />
          ) : (
            <Notice tone="review" title="No jobs raised yet">
              There {released.length === 1 ? "is one released revision" : `are ${released.length} released revisions`} to
              raise one against. What held, what chattered, what scrapped and why is the most valuable data a shop
              generates and the one most often lost.
            </Notice>
          )
        ) : (
          <>
            <Panel title="Jobs" dense>
              <Table head={["Job", "Part", "Rev", "Qty", "Status", "Cycle actual", "Setup actual", "Scrap", "Outcome"]}>
                {jobs.map((j) => {
                  const worst = j.outcomes.find((o) => o.code !== "SUCCESS") ?? j.outcomes[0];
                  const tone: Tone = !worst ? "unknown" : worst.code === "SUCCESS" ? "pass" : "risk";
                  return (
                    <tr key={j.id} className="hover:bg-raised">
                      <Td className="text-precision">
                        <Link href={`/jobs/${j.id}`} className="underline decoration-dotted hover:text-precision-dim">
                          {j.jobNumber}
                        </Link>
                      </Td>
                      <Td>{j.part.name}</Td>
                      <Td muted>{j.revision}</Td>
                      <Td>{j.quantity}</Td>
                      <Td muted>{JOB_STATUS_LABEL[j.status as JobStatus] ?? j.status}</Td>
                      <Td>{j.actualCycleMinutes ? `${j.actualCycleMinutes} min` : "—"}</Td>
                      <Td>{j.actualSetupHours ? `${j.actualSetupHours} hr` : "—"}</Td>
                      <Td className={j.scrapCount > 0 ? "text-risk" : ""}>{j.scrapCount}</Td>
                      <Td>
                        <StatusChip tone={tone}>
                          {worst ? OUTCOME_LABEL[worst.code as JobOutcomeCode] : "Not recorded"}
                        </StatusChip>
                      </Td>
                    </tr>
                  );
                })}
              </Table>
            </Panel>

            {failures.length > 0 && (
              <Panel title={`Recorded failures — ${failures.length}`}>
                <div className="space-y-3">
                  {failures.map((f) => (
                    <div key={f.id} className="border-l-2 border-l-risk/60 bg-raised px-4 py-3">
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-mono text-[12px] text-platinum">
                          {OUTCOME_LABEL[f.code as JobOutcomeCode]}
                        </span>
                        <span className="tech-label">{f.partsAffected} parts affected</span>
                      </div>
                      <p className="tech-label mt-1">Cause: {f.cause}</p>
                      <p className="mt-1.5 text-[12px] leading-relaxed text-platinum-dim">
                        Corrective action: {f.correctiveAction}
                      </p>
                      {f.notes && <p className="mt-1 text-[11.5px] leading-relaxed text-muted">{f.notes}</p>}
                    </div>
                  ))}
                </div>
              </Panel>
            )}
          </>
        )}
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";
