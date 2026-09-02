import { notFound, redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import Link from "next/link";
import { requireUser, requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { loadRevision } from "@/lib/data";
import { TopBar } from "@/components/nav";
import { Button, EmptyState, Notice, Panel, SectionHeading, StatusChip, Table, Td } from "@/components/ui";
import { derivePlan, NEVER_DERIVABLE, METHOD_NOT_ASSIGNED } from "@/lib/engines/inspection-plan";

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

  // What a plan derived from this revision right now would contain, and what it
  // would not. Shown before the button is pressed, so the shop is not handed a
  // sheet and left to work out what is missing from it.
  const derived = derivePlan(revision.features);

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

  async function createPlan() {
    "use server";
    const currentUser = await requireWrite();
    const rev = await loadRevision(currentUser.organizationId, id);
    if (!rev) notFound();

    // Derived server-side from the revision as it is now, not from anything the
    // form posted. A nominal or a tolerance arriving in a request body is a
    // number the browser chose.
    const plan = derivePlan(rev.features);
    if (plan.items.length === 0) return;

    // One plan per revision. A second would give the readiness gate two
    // answers and the inspector two sheets.
    const existing = await db.inspectionPlan.findFirst({ where: { partRevisionId: rev.revisionId }, select: { id: true } });
    if (existing) return;

    const created = await db.inspectionPlan.create({
      data: {
        partRevisionId: rev.revisionId,
        name: `First article — Rev ${rev.revision}`,
        samplingPlan: "FIRST_ARTICLE",
        items: {
          create: plan.items.map((i) => ({
            featureId: i.featureId,
            label: i.label,
            nominal: i.nominal,
            plusTol: i.plusTol,
            minusTol: i.minusTol,
            method: i.method,
            deviceType: i.deviceType,
            sequence: i.sequence,
          })),
        },
      },
    });

    await audit({
      organizationId: currentUser.organizationId,
      userId: currentUser.id,
      entityType: "InspectionPlan",
      entityId: created.id,
      action: "CREATE",
      actorType: "HUMAN",
      // The gaps are recorded with the creation. A plan that covered nine of
      // twelve characteristics is a different document from one that covered
      // all twelve, and the audit is where that survives.
      reason:
        `Inspection plan derived from ${plan.items.length} feature characteristic${plan.items.length === 1 ? "" : "s"}.` +
        (plan.uncovered.length > 0
          ? ` ${plan.uncovered.length} could not be derived: ${plan.uncovered.map((u) => u.label).join(", ")}.`
          : "") +
        " Relationships between features — position, spacing, form and orientation — are never derived and are not in it.",
    });

    revalidatePath(`/parts/${id}`, "layout");
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
            <Panel
              title="No inspection plan"
              meta={
                derived.items.length > 0 ? (
                  <form action={createPlan}>
                    <Button type="submit" variant="primary" size="sm">
                      Derive plan from {derived.items.length} characteristic{derived.items.length === 1 ? "" : "s"}
                    </Button>
                  </form>
                ) : undefined
              }
            >
              <p className="max-w-2xl text-[12.5px] leading-relaxed text-platinum">
                Readiness treats a missing inspection plan as a blocking gap for a critical component. Create one before
                the first article runs, not after it fails.
              </p>

              {derived.items.length === 0 ? (
                <Notice tone="review" title="Nothing on this revision can be derived into a plan">
                  A characteristic needs a nominal and a tolerance band. Nothing here has both — add tolerances to the
                  features that carry them, and the plan can be derived from the part rather than typed twice.
                </Notice>
              ) : (
                <>
                  <p className="mt-4 text-[12px] leading-relaxed text-muted">
                    Derived from the part, so the nominals cannot drift from the geometry. Each row takes its instrument
                    from the method assigned on the feature.
                  </p>
                  <ul className="mt-2 space-y-1">
                    {derived.items.map((i) => (
                      <li key={i.featureId} className="flex flex-wrap items-baseline gap-x-3 text-[12.5px] text-platinum">
                        <span className="font-mono text-[11.5px] text-muted tabular-nums">{i.sequence}</span>
                        <span>{i.label}</span>
                        <span className="font-mono text-[11.5px] text-muted tabular-nums">
                          {i.nominal.toFixed(4)} +{i.plusTol.toFixed(4)}/−{i.minusTol.toFixed(4)}
                        </span>
                        <span className={i.method === METHOD_NOT_ASSIGNED ? "text-review" : "text-muted"}>{i.method}</span>
                      </li>
                    ))}
                  </ul>
                </>
              )}

              {derived.uncovered.length > 0 && (
                <div className="mt-5">
                  <SectionHeading>What it will not cover on this part</SectionHeading>
                  <ul className="mt-2 space-y-1.5">
                    {derived.uncovered.map((u) => (
                      <li key={u.label} className="text-[12px] leading-relaxed text-muted">
                        <span className="text-platinum">{u.label}</span> — {u.reason}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="mt-5">
                <SectionHeading>What a derived plan never covers</SectionHeading>
                <p className="mt-1 max-w-2xl text-[12px] leading-relaxed text-muted">
                  These are relationships between features rather than features, and CANVAS holds features. A derived
                  plan is a starting point — add these rows by hand before the part ships.
                </p>
                <ul className="mt-2 space-y-1">
                  {NEVER_DERIVABLE.map((n) => (
                    <li key={n} className="flex gap-2 text-[12px] leading-relaxed text-muted">
                      <span className="text-precision">—</span>
                      <span>{n}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </Panel>
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
