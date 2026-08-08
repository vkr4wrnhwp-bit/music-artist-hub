import { notFound } from "next/navigation";
import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { buildPackage } from "@/lib/package";
import { RISK_LABEL } from "@/lib/engines/workholding";
import { ShowCalculation, MissingInputs } from "@/components/show-calculation";
import { TopBar } from "@/components/nav";
import { PartStatusChip } from "@/components/part-status";
import { DataRow, DevLabel, EmptyState, LinkButton, Notice, Panel, SectionHeading, StatusChip, type Tone } from "@/components/ui";

/**
 * SETUP PLANNING
 *
 * The optimisation actions are shown but not wired to an optimiser — a button
 * that reorders operations without a model behind it is worse than no button,
 * so they are labelled as not implemented rather than animated.
 */
export default async function SetupsPage(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  const user = await requireUser();
  const pkg = await buildPackage(user.organizationId, id);
  if (!pkg) notFound();

  return (
    <>
      <TopBar>
        <Link href={`/parts/${id}`} className="tech-label hover:text-platinum">
          {pkg.revision.partName}
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">Setups</span>
              <PartStatusChip readiness={pkg.readiness} />
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-4xl space-y-6">
          <SectionHeading sub="Setup count is the single biggest lever on cost for a prismatic part. Every additional setup adds fixturing, a work offset, a re-datum and a chance to stack error.">
            Setup planning
          </SectionHeading>

          {pkg.setups.length === 0 ? (
            <EmptyState title="No setups" body="A part needs at least one setup before operations can be planned against a machine and workholding." />
          ) : (
            pkg.setups.map((s) => {
              const a = pkg.workholdingBySetup[s.id];
              const tone: Tone =
                a?.level === "SAFE" || a?.level === "LIKELY_SAFE" ? "pass" : a?.level === "REVIEW" ? "review" : a?.level === "HIGH_RISK" ? "risk" : "unknown";
              const ops = s.operations;
              const paths = pkg.toolpaths.filter((t) => ops.some((o) => o.id === t.operationId));
              const minutes = paths.reduce((sum, t) => sum + t.cycleTimeMinutes, 0);
              const toolChanges = new Set(ops.map((o) => o.tool?.toolNumber)).size;

              return (
                <Panel
                  key={s.id}
                  title={s.name}
                  meta={<StatusChip tone={tone}>{a ? RISK_LABEL[a.level] : "Not assessed"}</StatusChip>}
                >
                  <div className="grid gap-x-8 gap-y-1 sm:grid-cols-2">
                    <DataRow label="Orientation" value={s.orientation} />
                    <DataRow label="Work offset" value={s.workOffset} />
                    <DataRow label="Machine" value={s.machine ? `${s.machine.manufacturer} ${s.machine.model}` : "Not assigned"} />
                    <DataRow label="Workholding" value={s.workholding?.description ?? "Not defined"} />
                    <DataRow label="Grip depth" value={s.gripDepth != null ? `${s.gripDepth.toFixed(3)}″` : "—"} tone={tone === "risk" ? "risk" : undefined} />
                    <DataRow label="Stock projection" value={s.stockProjection != null ? `${s.stockProjection.toFixed(3)}″` : "—"} />
                    <DataRow label="Tool changes" value={String(toolChanges)} />
                    <DataRow label="Estimated cycle" value={`${minutes.toFixed(2)} min`} />
                  </div>

                  {/* Holding margin — the force balance, not the rule of thumb */}
                  {a && (
                    <div className="mt-4 space-y-2">
                      {a.holdingMargin ? (
                        <ShowCalculation
                          title="Holding margin"
                          headline={a.holdingMargin.margin?.toFixed(2) ?? null}
                          unit="× against a 2.00× target"
                          method={a.holdingMargin.method}
                          inputs={a.holdingMargin.inputs}
                          assumptions={a.holdingMargin.assumptions}
                          developmentAnalysis
                        >
                          <div className="grid gap-x-8 sm:grid-cols-2">
                            <DataRow label="Resisting — friction" value={`${a.holdingMargin.frictionComponent} lbf`} />
                            <DataRow label="Resisting — positive stop" value={`${a.holdingMargin.stopComponent} lbf`} />
                            <DataRow label="Applied at peak" value={`${a.holdingMargin.appliedLoad} lbf`} />
                            <DataRow
                              label="Governing failure mode"
                              value={a.holdingMargin.governingMode === "TIPPING" ? "Rolling out of the jaws" : "Sliding in the jaws"}
                            />
                            <DataRow label="Margin — sliding" value={a.holdingMargin.slidingMargin?.toFixed(2) ?? "—"} />
                            <DataRow label="Margin — tipping" value={a.holdingMargin.tippingMargin?.toFixed(2) ?? "not checked"} />
                            <DataRow
                              label="Clamping pressure"
                              value={a.holdingMargin.contactPressure != null ? `${a.holdingMargin.contactPressure} psi` : "—"}
                            />
                          </div>
                          {a.holdingMargin.primaryRisk && (
                            <div>
                              <p className="tech-label mb-1 text-risk">Primary risk</p>
                              <p className="text-[12px] leading-relaxed text-platinum">{a.holdingMargin.primaryRisk}</p>
                            </div>
                          )}
                          {a.holdingMargin.recommendations.length > 0 && (
                            <div>
                              <p className="tech-label mb-1.5">What would change it</p>
                              <ul className="space-y-1.5">
                                {a.holdingMargin.recommendations.map((r) => (
                                  <li key={r} className="flex gap-2 text-[12px] leading-relaxed text-muted">
                                    <span className="text-precision">—</span>
                                    <span>{r}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </ShowCalculation>
                      ) : (
                        <MissingInputs
                          title="Holding margin not calculable"
                          items={a.missingInputs}
                        />
                      )}

                      {a.forceEstimate.ok ? (
                        <ShowCalculation
                          title="Estimated cutting force"
                          headline={a.forceEstimate.tangential?.toFixed(0) ?? null}
                          unit={`lbf tangential · ${a.forceEstimate.peakTangential?.toFixed(0)} lbf peak`}
                          method={a.forceEstimate.method}
                          inputs={a.forceEstimate.inputs}
                          assumptions={a.forceEstimate.assumptions}
                          uncertaintyPercent={a.forceEstimate.uncertaintyPercent}
                          confidence={a.forceEstimate.confidence}
                          cautions={a.forceEstimate.cautions}
                        >
                          <div className="grid gap-x-8 sm:grid-cols-2">
                            <DataRow label="Tangential" value={`${a.forceEstimate.tangential} lbf`} />
                            <DataRow label="Radial" value={`${a.forceEstimate.radial} lbf`} />
                            <DataRow label="Axial" value={`${a.forceEstimate.axial} lbf`} />
                            <DataRow label="Resultant" value={`${a.forceEstimate.resultant} lbf`} />
                            <DataRow label="Spindle power at cut" value={`${a.forceEstimate.spindlePower} hp`} />
                            <DataRow label="Material removal" value={`${a.forceEstimate.materialRemovalRate} in³/min`} />
                          </div>
                        </ShowCalculation>
                      ) : (
                        <MissingInputs
                          title="Cutting force not calculable"
                          items={a.forceEstimate.missingInputs}
                        />
                      )}
                    </div>
                  )}

                  {s.datumNote && <p className="mt-3 text-[12px] leading-relaxed text-muted">{s.datumNote}</p>}
                  {s.notes && <p className="mt-1.5 text-[12px] leading-relaxed text-muted">{s.notes}</p>}

                  {/* Operation timeline */}
                  <div className="mt-4">
                    <p className="tech-label mb-2">Operation sequence</p>
                    <div className="flex flex-wrap items-center gap-1">
                      {ops.map((o, i) => (
                        <span key={o.id} className="flex items-center gap-1">
                          <span className="border border-line px-2 py-1 font-mono text-[10px] uppercase tracking-[0.1em] text-platinum-dim">
                            {o.type.replace(/_2D|_DRILL/g, "")}
                          </span>
                          {i < ops.length - 1 && <span className="text-muted">→</span>}
                        </span>
                      ))}
                    </div>
                  </div>

                  {s.jaws.length > 0 && (
                    <Notice tone="pass" title={`${s.jaws.length} soft jaws generated for this setup`}>
                      Step depth {s.jaws[0].stepDepth.toFixed(3)}″ with R{s.jaws[0].reliefRadius.toFixed(3)} corner relief.
                    </Notice>
                  )}

                  <div className="mt-4 flex flex-wrap gap-2">
                    {["Optimize setup", "Reduce tool changes", "Reduce cycle time", "Reduce risk", "Improve finish"].map((label) => (
                      <span key={label} className="flex items-center gap-1.5 border border-line px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-unknown">
                        {label}
                        <DevLabel>Not implemented</DevLabel>
                      </span>
                    ))}
                  </div>
                </Panel>
              );
            })
          )}

          <div className="flex gap-2">
            <LinkButton href={`/parts/${id}/soft-jaws`} size="sm" variant="primary">
              Generate soft jaws
            </LinkButton>
            <LinkButton href={`/parts/${id}/readiness`} size="sm">
              Readiness
            </LinkButton>
          </div>

          <Notice tone="review" title="Setup optimisation is not built">
            Reordering operations to cut tool changes, or re-orienting a part to eliminate a setup, requires a search
            over feature accessibility that this phase does not implement. The buttons above are labelled rather than
            animated, because a button that appears to optimise and does not is a lie you would act on.
          </Notice>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";
