import { notFound } from "next/navigation";
import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { buildPackage } from "@/lib/package";
import { RISK_LABEL } from "@/lib/engines/workholding";
import { ShowCalculation, MissingInputs } from "@/components/show-calculation";
import { TopBar } from "@/components/nav";
import { PartStatusChip } from "@/components/part-status";
import { HoldScene } from "@/components/hold-scene";
import { SequenceProposalPanel, UnbuiltOptimisations } from "@/components/sequence-proposal";
import { proposeSequence, type SequencedOperation } from "@/lib/engines/sequencing";
import { DataRow, DevLabel, EmptyState, LinkButton, Notice, Panel, SectionHeading, StatusChip, type Tone } from "@/components/ui";

/**
 * SETUP PLANNING
 *
 * The optimisation actions are shown but not wired to an optimiser — a button
 * that reorders operations without a model behind it is worse than no button,
 * so they are labelled as not implemented rather than animated.
 */
/** The engine's view of a setup's operations. Tool number, not tool id — the
 *  sequencer reasons about what is in the spindle, and two records of the
 *  same physical cutter would otherwise read as a change. */
function sequencedOps(s: {
  operations: { id: string; sequence: number; type: string; label: string; featureId?: string | null; feature?: { label: string } | null; tool?: { toolNumber: number } | null }[];
}): SequencedOperation[] {
  return s.operations.map((o) => ({
    id: o.id,
    sequence: o.sequence,
    type: o.type,
    label: o.label,
    featureId: o.featureId ?? null,
    featureLabel: o.feature?.label ?? null,
    toolNumber: o.tool?.toolNumber ?? null,
  }));
}

export default async function SetupsPage(props: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ problem?: string }>;
}) {
  const { id } = await props.params;
  const { problem } = await props.searchParams;
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

          {problem && (
            <Notice tone="review" title="Nothing applied">
              {problem}
            </Notice>
          )}

          <div data-guide-target="hold-scene" className="space-y-6">
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
              // This was labelled "Tool changes" and was in fact the count of
              // distinct tools — a two-operation setup with two cutters reads
              // as 2 changes when it has 1. The number was right; the label
              // was wrong. Tool changes are the sequencer's business and are
              // shown, correctly, in the panel below.
              const toolsUsed = new Set(ops.map((o) => o.tool?.toolNumber).filter((n) => n != null)).size;

              return (
                <Panel
                  key={s.id}
                  title={s.name}
                  meta={<StatusChip tone={tone}>{a ? RISK_LABEL[a.level] : "Not assessed"}</StatusChip>}
                >
                  {/* The hold is the object: the drawing carries grip,
                      projection and the peak force where it acts. */}
                  <div className="grid gap-4 lg:grid-cols-[300px_1fr]">
                    <div className="h-[190px]">
                      <HoldScene
                        stockX={pkg.revision.stock ? pkg.revision.stock.x : null}
                        gripDepth={s.gripDepth}
                        stockProjection={s.stockProjection}
                        peakForceLbf={a?.forceEstimate.ok ? a.forceEstimate.peakTangential : null}
                        governingMode={a?.holdingMargin?.governingMode ?? null}
                      />
                    </div>
                    <div>
                      {a?.holdingMargin?.margin != null ? (
                        <p className="mb-2">
                          <span className="font-mono text-[26px] text-white tabular-nums">{a.holdingMargin.margin.toFixed(2)}×</span>
                          <span className="ml-2 text-[11.5px] text-muted">holding margin against a 2.00× target · {a.holdingMargin.governingMode === "TIPPING" ? "governed by rolling out of the jaws" : "governed by sliding in the jaws"} · DEVELOPMENT ANALYSIS</span>
                        </p>
                      ) : (
                        <p className="mb-2 text-[12.5px] text-review">
                          Holding margin not calculable — {a?.missingInputs.join("; ") ?? "workholding not assessed"}
                        </p>
                      )}
                      <div className="grid gap-x-8 gap-y-1 sm:grid-cols-2">
                        <DataRow label="Orientation" value={s.orientation} />
                        <DataRow label="Work offset" value={s.workOffset} />
                        <DataRow label="Machine" value={s.machine ? `${s.machine.manufacturer} ${s.machine.model}` : "Not assigned"} />
                        <DataRow label="Workholding" value={s.workholding?.description ?? "Not defined"} />
                        <DataRow label="Tools used" value={String(toolsUsed)} />
                        <DataRow label="Estimated cycle" value={`${minutes.toFixed(2)} min`} />
                      </div>
                    </div>
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

                  {/* Reduce tool changes, for real. The other four stay
                      labelled, but each now says which wall it hits. */}
                  <SequenceProposalPanel
                    proposal={proposeSequence(sequencedOps(s))}
                    operations={sequencedOps(s)}
                    setupId={s.id}
                    partId={id}
                  />
                  <UnbuiltOptimisations />
                </Panel>
              );
            })
          )}
          </div>

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
