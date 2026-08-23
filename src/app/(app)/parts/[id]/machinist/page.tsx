import { notFound, redirect } from "next/navigation";
import Link from "next/link";
import { canApprove, requireUser, requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { buildPackage } from "@/lib/package";
import { getMaterials } from "@/lib/data";
import { reviewApproaches, comparePlans, type ScoredPlan } from "@/lib/machinist-review";
import { relevantKnowledge } from "@/lib/disagreement";
import { PLACEHOLDER_OPERATIONS, type OperationType } from "@/lib/engines/cam/types";
import { THOUGHT_PATTERNS, PHILOSOPHIES, type ThoughtPattern } from "@/lib/engines/machinist";
import { RISK_LABEL } from "@/lib/engines/workholding";
import { money } from "@/lib/engines/cost";
import { TopBar } from "@/components/nav";
import { PartStatusChip } from "@/components/part-status";
import { Button, DataRow, Dot, EmptyState, Notice, Panel, SectionHeading, StatusChip, type Tone } from "@/components/ui";
import { selectMaterial } from "@/lib/package-selectors";

/**
 * THE AI MACHINIST
 *
 * Several complete manufacturing approaches, each from a different set of
 * priorities, scored by the same deterministic engines. The human picks one and
 * it becomes the plan — which is the only point at which anything is written.
 */

const RISK_TONE: Record<string, Tone> = {
  SAFE: "pass",
  LIKELY_SAFE: "pass",
  REVIEW: "review",
  HIGH_RISK: "risk",
  UNKNOWN: "unknown",
};

export default async function MachinistPage(props: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ approach?: string; approved?: string }>;
}) {
  const { id } = await props.params;
  const { approach, approved } = await props.searchParams;
  const user = await requireUser();

  const pkg = await buildPackage(user.organizationId, id);
  if (!pkg) notFound();

  const materials = await getMaterials(user.organizationId);
  const material = selectMaterial(materials, pkg.revision.intent.material.value);

  const blocked =
    !pkg.revision.stock
      ? "Stock is not defined, so there is nothing to plan from."
      : !pkg.primaryMachine
        ? "No machine is available. The machinist will not plan against a machine you do not own."
        : pkg.tools.length === 0
          ? "The tool crib is empty. Every approach below depends on what you actually have."
          : pkg.revision.features.length === 0
            ? "This part has no features yet."
            : null;

  // Shop knowledge scoped to this machine, these tools, this material. A
  // filter, not a ranking — knowledge about other equipment is not shown.
  const knowledge = blocked
    ? []
    : await relevantKnowledge({
        organizationId: user.organizationId,
        machineId: pkg.primaryMachine?.id ?? null,
        toolIds: pkg.tools.map((t) => t.id),
        materialId: material?.id ?? null,
      });

  let scored: ScoredPlan[] = [];
  let comparison = { fastest: null, cheapest: null, safest: null, fewestSetups: null, fewestTools: null } as ReturnType<
    typeof comparePlans
  >;

  if (!blocked && pkg.revision.stock && pkg.primaryMachine) {
    const envelope = pkg.revision.intent.finishedEnvelope.value as { z: number } | null;
    scored = reviewApproaches({
      stock: pkg.revision.stock,
      features: pkg.revision.features,
      machine: pkg.primaryMachine,
      tools: pkg.tools,
      workholding: pkg.primaryWorkholding,
      finishedHeight: envelope?.z ?? pkg.revision.stock.z * 0.85,
      materialSfmMin: material?.sfmCarbideMin ?? null,
      materialSfmMax: material?.sfmCarbideMax ?? null,
      materialName: material?.name ?? "Unspecified",
      specificEnergy: material?.specificEnergy ?? null,
      costAssumptions: pkg.costAssumptions,
      quantity: pkg.revision.intent.quantity.value ?? 1,
    });
    comparison = comparePlans(scored);
  }

  const selected = scored.find((s) => s.plan.pattern === approach) ?? scored[0] ?? null;

  /* ---------------- Approve an approach ---------------- */

  async function approvePlan(formData: FormData) {
    "use server";
    const currentUser = await requireWrite();
    if (!canApprove(currentUser)) redirect(`/parts/${id}/machinist`);

    const pattern = String(formData.get("pattern")) as ThoughtPattern;
    if (!THOUGHT_PATTERNS.includes(pattern)) redirect(`/parts/${id}/machinist`);

    const fresh = await buildPackage(currentUser.organizationId, id);
    if (!fresh || !fresh.revision.stock || !fresh.primaryMachine) notFound();

    const freshMaterials = await getMaterials(currentUser.organizationId);
    const mat = selectMaterial(freshMaterials, fresh.revision.intent.material.value);
    const env = fresh.revision.intent.finishedEnvelope.value as { z: number } | null;

    const plans = reviewApproaches({
      stock: fresh.revision.stock,
      features: fresh.revision.features,
      machine: fresh.primaryMachine,
      tools: fresh.tools,
      workholding: fresh.primaryWorkholding,
      finishedHeight: env?.z ?? fresh.revision.stock.z * 0.85,
      materialSfmMin: mat?.sfmCarbideMin ?? null,
      materialSfmMax: mat?.sfmCarbideMax ?? null,
      materialName: mat?.name ?? "Unspecified",
      specificEnergy: mat?.specificEnergy ?? null,
      costAssumptions: fresh.costAssumptions,
      quantity: fresh.revision.intent.quantity.value ?? 1,
    });

    const chosen = plans.find((p) => p.plan.pattern === pattern);
    if (!chosen) redirect(`/parts/${id}/machinist`);

    // Replacing the plan discards the previous setups and their operations.
    // The audit trail keeps what was there before, and geometry is untouched.
    await db.setup.deleteMany({ where: { partRevisionId: fresh.revision.revisionId } });

    for (const s of chosen.plan.setups) {
      const setup = await db.setup.create({
        data: {
          partRevisionId: fresh.revision.revisionId,
          sequence: s.sequence,
          name: s.name,
          orientation: s.orientation,
          machineId: fresh.primaryMachine.id,
          workholdingId: fresh.primaryWorkholding?.id ?? null,
          workOffset: s.workOffset,
          datumNote: s.datumNote,
          gripDepth: s.gripDepth,
          gripLength: s.gripLength,
          stockProjection: s.stockProjection,
          notes: s.rationale,
        },
      });

      for (const o of s.operations) {
        await db.operation.create({
          data: {
            setupId: setup.id,
            featureId: o.featureId,
            toolId: o.toolId,
            sequence: o.sequence,
            type: o.type,
            label: o.label,
            topZ: o.topZ,
            finalZ: o.finalZ,
            clearanceZ: 0.1,
            retractZ: 1,
            overridesJson: JSON.stringify({ stepover: o.stepover, stockToLeave: o.stockToLeave }),
            // Membership in the engine's own list, so this cannot drift when
            // an operation type gains an engine.
            isPlaceholder: PLACEHOLDER_OPERATIONS.includes(o.type as OperationType),
          },
        });
      }
    }

    await db.aIRecommendation.create({
      data: {
        partRevisionId: fresh.revision.revisionId,
        kind: "PROCESS",
        summary: `Manufacturing approach: ${chosen.plan.philosophy.name}`,
        payloadJson: JSON.stringify({
          pattern,
          setups: chosen.plan.setups.length,
          operations: chosen.operationCount,
          cycleMinutes: chosen.cycleMinutes,
          risk: chosen.risk,
        }),
        providerId: "canvas-machinist",
        status: "ACCEPTED",
        decidedBy: currentUser.id,
        decidedAt: new Date(),
      },
    });

    await audit({
      organizationId: currentUser.organizationId,
      userId: currentUser.id,
      entityType: "PartRevision",
      entityId: fresh.revision.revisionId,
      action: "ACCEPT_SUGGESTION",
      actorType: "HUMAN",
      field: "manufacturingApproach",
      newValue: chosen.plan.philosophy.name,
      reason: `Approved the ${chosen.plan.philosophy.name} approach — ${chosen.plan.setups.length} setups, ${chosen.operationCount} operations, ${chosen.cycleMinutes.toFixed(2)} min estimated cycle`,
    });

    redirect(`/parts/${id}/machinist?approach=${pattern}&approved=1`);
  }

  return (
    <>
      <TopBar>
        <Link href={`/parts/${id}`} className="tech-label hover:text-platinum">
          {pkg.revision.partName}
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">Machinist</span>
              <PartStatusChip readiness={pkg.readiness} />
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-5xl space-y-6">
          <SectionHeading sub="Ask two machinists to plan the same part and you get two different plans — both defensible, optimising different things. These are five complete approaches, each scored by the same engines that generate the toolpaths. Pick the one that suits the job; it becomes the plan.">
            The machinist&apos;s approaches
          </SectionHeading>

          {approved === "1" && (
            <Notice tone="pass" title="Approach approved">
              The setups and operations have been written to this revision, and the decision is recorded against your
              name in the part history. Geometry was not touched — you can change approach at any time.
            </Notice>
          )}

          {blocked ? (
            <EmptyState
              title="Nothing to plan yet"
              body={blocked}
              action={{ label: "Back to the part", href: `/parts/${id}` }}
            />
          ) : (
            <>
              {knowledge.length > 0 && (
                <Panel title="What this shop knows about this setup" meta={<Link href="/knowledge" className="tech-label hover:text-platinum">Shop knowledge</Link>}>
                  <p className="mb-2 text-[12px] leading-relaxed text-muted">
                    Recorded on this shop&apos;s own equipment and scoped to the machine, tools and material in play
                    here. This is experience, not published data — weigh it like you would a note from the last person
                    who ran the job.
                  </p>
                  <ul className="space-y-2">
                    {knowledge.map((k) => (
                      <li key={k.id} className="border border-line px-3 py-2">
                        <p className="text-[12.5px] leading-relaxed text-platinum">{k.observation}</p>
                        <p className="tech-label mt-1">
                          {[
                            k.machine ? `${k.machine.manufacturer} ${k.machine.model}` : null,
                            k.tool ? `T${k.tool.toolNumber} ${k.tool.description}` : null,
                            k.material?.name ?? null,
                          ]
                            .filter(Boolean)
                            .join(" · ")}
                          {" · "}
                          {k.jobCount} {k.jobCount === 1 ? "job" : "jobs"} · confidence {k.confidence.toLowerCase()}
                        </p>
                      </li>
                    ))}
                  </ul>
                </Panel>
              )}

              {/* ---------------- Comparison: strategy cards ---------------- */}
              {(() => {
                const maxCycle = Math.max(...scored.map((x) => x.cycleMinutes), 0.001);
                const maxCost = Math.max(...scored.map((x) => x.unitCost), 0.001);
                return (
                  <section>
                    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                      {scored.map((sc) => {
                        const active = selected?.plan.pattern === sc.plan.pattern;
                        return (
                          <Link
                            key={sc.plan.pattern}
                            href={`/parts/${id}/machinist?approach=${sc.plan.pattern}`}
                            className={`group block border bg-surface transition-colors ${
                              active ? "border-precision/70" : "border-line hover:border-line-strong"
                            }`}
                          >
                            <div className="border-b border-line px-4 py-3">
                              <p className={`text-[10px] font-semibold uppercase tracking-[0.16em] ${active ? "text-precision" : "text-muted"}`}>
                                {sc.plan.philosophy.name}
                              </p>
                              <p className="mt-1.5 font-mono text-[26px] font-light text-white tabular-nums">
                                {sc.cycleMinutes > 0 ? `${sc.cycleMinutes.toFixed(1)} min` : "—"}
                              </p>
                              <p className="tech-label mt-0.5">
                                {sc.setupCount} setup{sc.setupCount === 1 ? "" : "s"} · {sc.distinctTools} tools · {sc.operationCount} ops
                              </p>
                            </div>
                            <div className="space-y-2 px-4 py-3">
                              {/* Relative bars — comparison, not judgement. */}
                              <div>
                                <div className="flex items-baseline justify-between">
                                  <span className="tech-label">Cycle</span>
                                  <span className="font-mono text-[10.5px] text-muted tabular-nums">{sc.cycleMinutes.toFixed(1)}m</span>
                                </div>
                                <div className="mt-0.5 h-1 bg-line">
                                  <div className="h-1 bg-precision/70" style={{ width: `${(sc.cycleMinutes / maxCycle) * 100}%` }} />
                                </div>
                              </div>
                              <div>
                                <div className="flex items-baseline justify-between">
                                  <span className="tech-label">Unit cost</span>
                                  <span className="font-mono text-[10.5px] text-muted tabular-nums">{money(sc.unitCost)}</span>
                                </div>
                                <div className="mt-0.5 h-1 bg-line">
                                  <div className="h-1 bg-platinum/50" style={{ width: `${(sc.unitCost / maxCost) * 100}%` }} />
                                </div>
                              </div>
                              <div className="flex items-center justify-between pt-1">
                                <span className="flex items-center gap-1.5">
                                  <Dot tone={RISK_TONE[sc.risk]} />
                                  <span className="text-[11px] text-muted">{RISK_LABEL[sc.risk]}</span>
                                </span>
                                <span className={`text-[10px] font-semibold uppercase tracking-[0.12em] ${active ? "text-precision" : "text-precision-dim group-hover:text-precision"}`}>
                                  {active ? "Selected" : "View approach"}
                                </span>
                              </div>
                              <p className="border-t border-line/60 pt-2 text-[11px] leading-relaxed text-muted">
                                {sc.plan.philosophy.tradeoff}
                              </p>
                            </div>
                          </Link>
                        );
                      })}
                    </div>
                    <p className="mt-2 text-[12px] leading-relaxed text-muted">
                      CANVAS does not declare an overall winner. Which card matters is a decision about this job —
                      quantity, material cost, whether it runs unattended — and that belongs to you, not to the software.
                    </p>
                    <details className="mt-2 border border-line bg-surface">
                      <summary className="cursor-pointer px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-muted hover:text-platinum">
                        View table
                      </summary>
                      <div className="overflow-x-auto border-t border-line">
                        <table className="w-full border-collapse text-left">
                          <thead>
                            <tr className="border-b border-line">
                              {["Approach", "Setups", "Tools", "Ops", "Cycle", "Risk", "Unit cost"].map((h) => (
                                <th key={h} className="tech-label whitespace-nowrap px-3 py-2 font-normal">{h}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody className="font-mono text-[12px]">
                            {scored.map((sc) => (
                              <tr key={sc.plan.pattern} className="hover:bg-raised">
                                <td className="border-b border-line/50 px-3 py-2 text-platinum">{sc.plan.philosophy.name}</td>
                                <td className="border-b border-line/50 px-3 py-2">{sc.setupCount}</td>
                                <td className="border-b border-line/50 px-3 py-2">{sc.distinctTools}</td>
                                <td className="border-b border-line/50 px-3 py-2">{sc.operationCount}</td>
                                <td className="border-b border-line/50 px-3 py-2">{sc.cycleMinutes > 0 ? `${sc.cycleMinutes.toFixed(1)} min` : "—"}</td>
                                <td className="border-b border-line/50 px-3 py-2 text-muted">{RISK_LABEL[sc.risk]}</td>
                                <td className="border-b border-line/50 px-3 py-2">{money(sc.unitCost)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        <div className="flex flex-wrap gap-x-6 gap-y-1 border-t border-line px-4 py-3">
                          {[
                            ["Fastest", comparison.fastest],
                            ["Cheapest", comparison.cheapest],
                            ["Safest", comparison.safest],
                            ["Fewest setups", comparison.fewestSetups],
                            ["Fewest tools", comparison.fewestTools],
                          ].map(([label, winner]) => (
                            <span key={label as string} className="text-[11.5px]">
                              <span className="tech-label">{label}</span>{" "}
                              <span className="text-platinum">{winner ?? "—"}</span>
                            </span>
                          ))}
                        </div>
                      </div>
                    </details>
                  </section>
                );
              })()}

              {/* ---------------- Selected approach ---------------- */}
              {selected && (
                <>
                  <Panel
                    title={selected.plan.philosophy.name}
                    meta={
                      <span className="flex flex-wrap gap-2">
                        <StatusChip tone={RISK_TONE[selected.risk]}>{RISK_LABEL[selected.risk]}</StatusChip>
                        <StatusChip tone="neutral">{selected.cycleMinutes.toFixed(1)} min</StatusChip>
                        <StatusChip tone="neutral">{money(selected.unitCost)}/part</StatusChip>
                      </span>
                    }
                  >
                    <p className="max-w-2xl text-[13.5px] leading-relaxed text-platinum">
                      {selected.plan.philosophy.stance}
                    </p>
                    <div className="mt-4 grid gap-x-8 gap-y-2 sm:grid-cols-2">
                      <div>
                        <p className="tech-label">What it trades away</p>
                        <p className="mt-1 text-[12.5px] leading-relaxed text-muted">
                          {selected.plan.philosophy.tradeoff}
                        </p>
                      </div>
                      <div>
                        <p className="tech-label">Suited to</p>
                        <p className="mt-1 text-[12.5px] leading-relaxed text-muted">
                          {selected.plan.philosophy.suitedTo}
                        </p>
                      </div>
                    </div>
                  </Panel>

                  {selected.plan.concerns.length > 0 && (
                    <Notice tone="review" title="What this machinist wants you to know">
                      <ul className="mt-1 space-y-1.5">
                        {selected.plan.concerns.map((c) => (
                          <li key={c}>— {c}</li>
                        ))}
                      </ul>
                    </Notice>
                  )}

                  {selected.errors.length > 0 && (
                    <Notice tone="risk" title="Operations that cannot be produced">
                      <ul className="mt-1 space-y-1">
                        {selected.errors.map((e) => (
                          <li key={e}>— {e}</li>
                        ))}
                      </ul>
                    </Notice>
                  )}

                  {/* ---------------- The plan itself ---------------- */}
                  {selected.plan.setups.map((s) => (
                    <Panel
                      key={s.sequence}
                      title={s.name}
                      meta={
                        s.requiresSoftJaws ? <StatusChip tone="precision">Soft jaws</StatusChip> : undefined
                      }
                    >
                      <p className="mb-3 max-w-2xl text-[12.5px] leading-relaxed text-muted">{s.rationale}</p>
                      <div className="grid gap-x-8 sm:grid-cols-2">
                        <DataRow label="Work offset" value={s.workOffset} />
                        <DataRow label="Orientation" value={s.orientation} />
                        <DataRow label="Grip depth" value={`${s.gripDepth.toFixed(3)}″`} />
                        <DataRow label="Projection" value={`${s.stockProjection.toFixed(3)}″`} />
                      </div>
                      <p className="tech-label mt-3 leading-relaxed">{s.datumNote}</p>

                      <ol className="mt-4 space-y-2.5">
                        {s.operations.map((o) => (
                          <li key={o.sequence} className="flex gap-3 border-b border-line/50 pb-2.5 last:border-0">
                            <span className="font-mono text-[11px] text-precision">
                              {String(o.sequence).padStart(2, "0")}
                            </span>
                            <span className="min-w-0">
                              <span className="block font-mono text-[12.5px] text-platinum">{o.label}</span>
                              <span className="tech-label block">
                                {o.type} · T{o.toolNumber ?? "—"} · {(o.stepover * 100).toFixed(0)}% stepover
                                {o.stockToLeave > 0 ? ` · ${o.stockToLeave.toFixed(3)}″ left on` : ""}
                              </span>
                              <span className="mt-1 block text-[12px] leading-relaxed text-muted">{o.rationale}</span>
                            </span>
                          </li>
                        ))}
                      </ol>
                    </Panel>
                  ))}

                  {/* ---------------- Approve ---------------- */}
                  <Panel title="Approve this approach">
                    <p className="mb-4 max-w-2xl text-[12.5px] leading-relaxed text-muted">
                      Approving writes these setups and operations to the revision, replacing any existing plan.
                      Geometry, features and measurements are untouched, the decision is recorded against your name,
                      and you can switch to a different approach at any time. It does not approve the part for
                      manufacture — the readiness gates still apply.
                    </p>
                    <form action={approvePlan} className="flex flex-wrap items-center gap-3">
                      <input type="hidden" name="pattern" value={selected.plan.pattern} />
                      <Button type="submit" variant="primary" data-guide-target="approve-approach" disabled={!canApprove(user) || selected.errors.length > 0}>
                        Approve {selected.plan.philosophy.name}
                      </Button>
                      <Link href={`/parts/${id}/readiness`} className="tech-label hover:text-platinum">
                        Check readiness first
                      </Link>
                    </form>
                    {!canApprove(user) && (
                      <p className="mt-2 text-[11.5px] text-muted">Your role does not permit approving a plan.</p>
                    )}
                    {selected.errors.length > 0 && (
                      <p className="mt-2 text-[11.5px] text-risk">
                        This approach has operations the engine cannot produce, so it cannot be approved as-is.
                      </p>
                    )}
                  </Panel>
                </>
              )}

              <Notice tone="precision" title="Why this is rules and not a language model">
                A plan you are going to sign your name to has to be inspectable. Every tool choice above states why it
                was made, and you can disagree with the reasoning. The scores come from the same deterministic engines
                that produce the toolpaths, so the comparison is arithmetic on the actual plans rather than an opinion
                about them.
              </Notice>
            </>
          )}
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";
