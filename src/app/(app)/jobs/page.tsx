import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { OUTCOME_LABEL, type JobOutcomeCode } from "@/lib/engines/network";
import { TopBar } from "@/components/nav";
import { EmptyState, Panel, SectionHeading, StatusChip, Table, Td, type Tone } from "@/components/ui";

export default async function JobsPage() {
  const user = await requireUser();
  const jobs = await db.job.findMany({
    where: { organizationId: user.organizationId },
    include: { part: true, outcomes: true },
    orderBy: { startedAt: "desc" },
  });

  const outcomes = jobs.flatMap((j) => j.outcomes);
  const failures = outcomes.filter((o) => o.code !== "SUCCESS");

  return (
    <>
      <TopBar>
        <span className="tech-label">Jobs</span>
      </TopBar>
      <main className="flex-1 space-y-6 overflow-y-auto p-6">
        <SectionHeading sub="A job outcome is the most valuable data a shop generates and the one most often lost. What held, what chattered, what scrapped and why — recorded structurally so it can teach the workholding and process models rather than living in someone's memory.">
          Jobs
        </SectionHeading>

        {jobs.length === 0 ? (
          <EmptyState
            title="No jobs"
            body="Jobs are created from a released part revision. Until one runs, CANVAS has no actual results to compare its estimates against."
            action={{ label: "Part library", href: "/parts" }}
          />
        ) : (
          <>
            <Panel title="Jobs" dense>
              <Table head={["Job", "Part", "Rev", "Qty", "Status", "Cycle actual", "Setup actual", "Scrap", "Outcome"]}>
                {jobs.map((j) => {
                  const worst = j.outcomes.find((o) => o.code !== "SUCCESS") ?? j.outcomes[0];
                  const tone: Tone = !worst ? "unknown" : worst.code === "SUCCESS" ? "pass" : "risk";
                  return (
                    <tr key={j.id} className="hover:bg-raised">
                      <Td className="text-precision">{j.jobNumber}</Td>
                      <Td>{j.part.name}</Td>
                      <Td muted>{j.revision}</Td>
                      <Td>{j.quantity}</Td>
                      <Td muted>{j.status}</Td>
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
