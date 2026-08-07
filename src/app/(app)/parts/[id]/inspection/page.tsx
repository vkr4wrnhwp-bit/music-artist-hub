import { notFound } from "next/navigation";
import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { db } from "@/lib/db";
import { loadRevision } from "@/lib/data";
import { TopBar } from "@/components/nav";
import { EmptyState, Notice, Panel, SectionHeading, StatusChip, Table, Td } from "@/components/ui";

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

  return (
    <>
      <TopBar>
        <Link href={`/parts/${id}`} className="tech-label hover:text-platinum">
          {revision.partName}
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">Inspection</span>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-6">
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
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";
