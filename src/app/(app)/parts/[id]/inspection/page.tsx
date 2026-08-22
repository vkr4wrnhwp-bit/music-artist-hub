import { notFound, redirect } from "next/navigation";
import Link from "next/link";
import { requireUser, requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { loadRevision } from "@/lib/data";
import { TopBar } from "@/components/nav";
import { Button, EmptyState, Notice, Panel, SectionHeading, StatusChip, Table, Td } from "@/components/ui";

export default async function InspectionPage(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  const user = await requireUser();
  const revision = await loadRevision(user.organizationId, id);
  if (!revision) notFound();

  const plans = await db.inspectionPlan.findMany({
    where: { partRevisionId: revision.revisionId },
    include: { items: { orderBy: { sequence: "asc" }, include: { feature: true } }, results: true },
  });

  const unmethoded = revision.features.filter((f) => f.critical && !f.inspectionMethod);

  const sessions = await db.measurementSession.findMany({
    where: { partRevisionId: revision.revisionId, mode: "INSPECTION" },
    include: { _count: { select: { measurements: true } } },
    orderBy: { startedAt: "desc" },
  });

  async function startSession() {
    "use server";
    const currentUser = await requireWrite();
    const rev = await loadRevision(currentUser.organizationId, id);
    if (!rev) notFound();
    const session = await db.measurementSession.create({
      data: {
        partRevisionId: rev.revisionId,
        name: `First article — Rev ${rev.revision}`,
        mode: "INSPECTION",
        status: "IN_PROGRESS",
        operator: currentUser.name || currentUser.email,
      },
    });
    await audit({
      organizationId: currentUser.organizationId,
      userId: currentUser.id,
      entityType: "MeasurementSession",
      entityId: session.id,
      action: "CREATE",
      actorType: "HUMAN",
      reason: "First-article inspection session started",
    });
    redirect(`/parts/${id}/inspection/session/${session.id}`);
  }

  return (
    <>
      <TopBar>
        <Link href={`/parts/${id}`} className="tech-label hover:text-platinum">
          {revision.partName}
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">Inspection</span>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-4xl space-y-6">
          <SectionHeading sub="A critical dimension with no measurement method is a dimension nobody checks. The plan names the instrument for each characteristic so the person at the surface plate is not guessing at 6am.">
            Inspection
          </SectionHeading>

          {unmethoded.length > 0 && (
            <Notice tone="review" title={`${unmethoded.length} critical features have no inspection method`}>
              <ul className="mt-1 space-y-0.5">
                {unmethoded.map((f) => (
                  <li key={f.id}>— {f.label}</li>
                ))}
              </ul>
            </Notice>
          )}

          <Panel
            title="First-article measurement sessions"
            meta={
              <form action={startSession}>
                <Button type="submit" variant="primary" size="sm">
                  Start session
                </Button>
              </form>
            }
            dense
          >
            {sessions.length === 0 ? (
              <p className="px-4 py-3 text-[12px] leading-relaxed text-muted">
                No first-article measurements exist for this revision, and the FAIR says so. Reverse-engineering
                readings of a reference article are not first-article results and are deliberately excluded. Start a
                session to record readings against the finished part — each one needs an instrument from the
                metrology inventory.
              </p>
            ) : (
              <ul>
                {sessions.map((s) => (
                  <li key={s.id} className="border-b border-line/60 last:border-0">
                    <Link
                      href={`/parts/${id}/inspection/session/${s.id}`}
                      className="flex flex-wrap items-baseline justify-between gap-3 px-4 py-2.5 hover:bg-raised"
                    >
                      <span className="text-[13px] text-platinum">{s.name}</span>
                      <span className="flex items-center gap-3">
                        <span className="font-mono text-[11.5px] text-muted tabular-nums">
                          {s._count.measurements} reading{s._count.measurements === 1 ? "" : "s"} ·{" "}
                          {s.startedAt.toISOString().slice(0, 10)} · {s.operator ?? "operator not recorded"}
                        </span>
                        <StatusChip tone={s.status === "IN_PROGRESS" ? "precision" : "neutral"}>
                          {s.status === "IN_PROGRESS" ? "In progress" : "Completed"}
                        </StatusChip>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          {/* Coach-mark anchor: readiness SHOW ME lands here — the plan is
              the physical evidence behind the inspection gates. */}
          <div data-guide-target="inspection-plan" className="space-y-6">
          {plans.length === 0 ? (
            <EmptyState
              title="No inspection plan"
              body="Readiness treats a missing inspection plan as a blocking gap for a critical component. Create one before the first article runs, not after it fails."
            />
          ) : (
            plans.map((plan) => (
              <Panel
                key={plan.id}
                title={plan.name}
                meta={<StatusChip tone="neutral">{plan.samplingPlan.replace(/_/g, " ")}</StatusChip>}
                dense
              >
                <Table head={["#", "Characteristic", "Nominal", "Tolerance", "Method", "Instrument", "Results"]}>
                  {plan.items.map((i) => (
                    <tr key={i.id} className="hover:bg-raised">
                      <Td muted>{i.sequence}</Td>
                      <Td className="text-platinum">{i.label}</Td>
                      <Td>{i.nominal.toFixed(4)}</Td>
                      <Td className="text-precision">
                        {i.plusTol === i.minusTol ? `±${i.plusTol.toFixed(4)}` : `+${i.plusTol.toFixed(4)}/-${i.minusTol.toFixed(4)}`}
                      </Td>
                      <Td muted>{i.method}</Td>
                      <Td muted>{i.deviceType?.replace(/_/g, " ").toLowerCase() ?? "—"}</Td>
                      <Td muted>{plan.results.filter((r) => r.itemId === i.id).length}</Td>
                    </tr>
                  ))}
                </Table>
              </Panel>
            ))
          )}
          </div>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";
