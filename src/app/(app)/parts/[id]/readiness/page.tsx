import { notFound, redirect } from "next/navigation";
import Link from "next/link";
import { canApprove, requireUser, requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { buildPackage } from "@/lib/package";
import { EVALUATED_PROCESSES, PROCESS_LABEL, UNEVALUATED_PROCESSES } from "@/lib/engines/process-advisor";
import { TopBar } from "@/components/nav";
import { PartStatusChip } from "@/components/part-status";
import { Disagree } from "@/components/disagree";
import { recordDisagreement } from "@/lib/disagreement";
import { revalidatePath } from "next/cache";
import { showMeHrefFor } from "@/lib/guide/show-me";
import { Button, Dot, Notice, Panel, SectionHeading, StatusChip, type Tone } from "@/components/ui";

const STATUS_TONE: Record<string, Tone> = {
  PASS: "pass",
  REVIEW: "review",
  MISSING: "risk",
  FAIL: "risk",
  NOT_ATTEMPTED: "unknown",
};

export default async function ReadinessPage(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  const user = await requireUser();
  const pkg = await buildPackage(user.organizationId, id);
  if (!pkg) notFound();

  const { readiness, process } = pkg;

  /**
   * Jobs this shop has actually run, offered when a machinist says they have
   * run a comparable setup.
   *
   * The select for this existed and never rendered: `Disagree`'s `jobs` prop
   * defaults to `[]` and its only call site passed none, so a machinist could
   * answer "yes, I have run a comparable setup" and had no way to say which
   * one — and `comparableJobId` was never written. A disagreement backed by a
   * job nobody can name is an opinion; backed by a job number it is shop
   * evidence, which is the whole point of recording it.
   *
   * COMPLETE only: a job still on the machine has not demonstrated anything
   * yet.
   */
  const comparableJobs = await db.job.findMany({
    where: { organizationId: user.organizationId, status: "COMPLETE" },
    orderBy: { completedAt: "desc" },
    take: 50,
    include: { part: { select: { partNumber: true } } },
  });

  async function approve() {
    "use server";
    const currentUser = await requireWrite();
    if (!canApprove(currentUser)) redirect(`/parts/${id}/readiness`);

    const fresh = await buildPackage(currentUser.organizationId, id);
    if (!fresh) notFound();

    await db.approval.create({
      data: {
        partRevisionId: fresh.revision.revisionId,
        userId: currentUser.id,
        scope: "MANUFACTURING_PACKAGE",
        statement:
          "I have reviewed the geometry, setups, workholding, tooling and program for this revision and accept responsibility for running it.",
      },
    });

    await audit({
      organizationId: currentUser.organizationId,
      userId: currentUser.id,
      entityType: "PartRevision",
      entityId: fresh.revision.revisionId,
      action: "APPROVE",
      actorType: "HUMAN",
      reason: "Manufacturing package approved",
    });

    redirect(`/parts/${id}/readiness`);
  }

  /**
   * Recording a disagreement is a write, and it is deliberately the only thing
   * this action does. It does not touch the gate, it does not set a flag that
   * any gate reads, and there is no code path from here to a gate clearing.
   */
  async function disagree(formData: FormData) {
    "use server";
    const currentUser = await requireWrite();
    const fresh = await buildPackage(currentUser.organizationId, id);
    if (!fresh) notFound();

    const reasoning = String(formData.get("reasoning") ?? "").trim();
    if (!reasoning) redirect(`/parts/${id}/readiness`);

    await recordDisagreement({
      organizationId: currentUser.organizationId,
      userId: currentUser.id,
      subjectType: "READINESS_GATE",
      subjectId: String(formData.get("subjectId") ?? "") || null,
      partRevisionId: fresh.revision.revisionId,
      canvasPosition: String(formData.get("canvasPosition") ?? ""),
      reasoning,
      hasRunComparable: formData.get("hasRunComparable") === "yes",
      // Resolved against this organisation's own jobs, never trusted as an id.
      comparableJobId:
        (
          await db.job.findFirst({
            where: { id: String(formData.get("comparableJobId") ?? ""), organizationId: currentUser.organizationId },
            select: { id: true },
          })
        )?.id ?? null,
      proposedValue: String(formData.get("proposedValue") ?? "") || null,
    });

    revalidatePath(`/parts/${id}/readiness`);
    redirect(`/parts/${id}/readiness?recorded=1`);
  }

  const overallTone: Tone =
    readiness.overall === "READY_TO_RUN" ? "pass" : readiness.overall === "REVIEW_REQUIRED" ? "review" : "risk";

  return (
    <>
      <TopBar>
        <Link href={`/parts/${id}`} className="tech-label hover:text-platinum">
          {pkg.revision.partName}
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">Readiness</span>
              <PartStatusChip readiness={pkg.readiness} />
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-4xl space-y-6">
          <div className="flex items-start justify-between gap-6">
            <SectionHeading sub="Not a percentage. Each gate passes, needs review, is missing, or was never attempted — and the overall status is the worst of them, never an average. Averaging would let a part with no inspection plan read as 90% ready.">
              Manufacturing readiness
            </SectionHeading>
            <StatusChip tone={overallTone}>{readiness.overall.replace(/_/g, " ")}</StatusChip>
          </div>

          {readiness.criticalApplication && (
            <Notice tone="risk" title="Critical application">
              This component is load bearing or safety critical. CANVAS may assist with manufacturing planning but does
              not certify component safety. This package may require professional engineering validation, material
              certification, process controls, inspection and regulatory compliance.
            </Notice>
          )}

          {/* BLOCKER-FIRST: the worst gate is the page's one dominant object.
              The engine is untouched — this is presentation order only. */}
          {(() => {
            const blockers = readiness.gates.filter((g) => g.blocking && g.status !== "PASS" && g.status !== "REVIEW");
            const reviews = readiness.gates.filter((g) => g.status === "REVIEW");
            const passed = readiness.gates.filter((g) => g.status === "PASS");
            const others = readiness.gates.filter((g) => !blockers.includes(g) && !reviews.includes(g) && !passed.includes(g));
            const GATE_HREF: Record<string, string> = {
              inspection: `/parts/${id}/inspection`,
              metrology: `/parts/${id}/inspection`,
              workholding: `/parts/${id}/setups`,
              tooling: `/parts/${id}/tooling`,
              stock: `/parts/${id}`,
              simulation: `/parts/${id}`,
              approval: `/parts/${id}/readiness`,
            };
            const hrefFor = (gid: string, label: string) => {
              const key = Object.keys(GATE_HREF).find((k) => gid.toLowerCase().includes(k) || label.toLowerCase().includes(k));
              return key ? GATE_HREF[key] : `/parts/${id}`;
            };
            // SHOW ME — the shared gate→scene map (lib/guide/show-me.ts),
            // also used by the Guide card, so the two never disagree.
            const showMeFor = (gid: string, label: string): string | null => showMeHrefFor(id, gid, label);
            const GateBody = ({ g }: { g: (typeof readiness.gates)[number] }) => (
              <li className="border-b border-line/60 px-4 py-3 last:border-0">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex min-w-0 items-start gap-2.5">
                    <span className="mt-1.5"><Dot tone={STATUS_TONE[g.status]} /></span>
                    <div className="min-w-0">
                      <p className="flex items-center gap-2 font-mono text-[12px] text-platinum">
                        {g.label}
                        {g.blocking && <span className="tech-label text-precision">blocking</span>}
                      </p>
                      <p className="mt-0.5 text-[12px] leading-relaxed text-muted">{g.detail}</p>
                      {g.actions.length > 0 && (
                        <ul className="mt-1.5 space-y-0.5">
                          {g.actions.map((a) => (
                            <li key={a} className="text-[11.5px] text-platinum-dim">— {a}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                  <span className="flex shrink-0 items-center gap-2">
                    {g.status !== "PASS" && showMeFor(g.id, g.label) && (
                      <Link href={showMeFor(g.id, g.label)!} className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted hover:text-platinum">
                        Show me
                      </Link>
                    )}
                    <StatusChip tone={STATUS_TONE[g.status]}>{g.status.replace(/_/g, " ")}</StatusChip>
                  </span>
                </div>
                {g.status !== "PASS" && g.status !== "NOT_ATTEMPTED" && (
                  <div className="mt-2.5 pl-6">
                    <Disagree
                      action={disagree}
                      subjectType="READINESS_GATE"
                      subjectId={g.id}
                      partRevisionId={pkg.revision.revisionId}
                      canvasPosition={`${g.label} — ${g.status.replace(/_/g, " ")}. ${g.detail}`}
                      jobs={comparableJobs.map((j) => ({
                        id: j.id,
                        label: `${j.jobNumber} — ${j.part.partNumber} rev ${j.revision}, qty ${j.quantity}`,
                      }))}
                    />
                  </div>
                )}
              </li>
            );
            return (
              <>
                {blockers.length > 0 ? (
                  <section className="border-2 border-risk/50 bg-surface">
                    <header className="flex items-center justify-between gap-4 border-b border-risk/40 px-5 py-3">
                      <div>
                        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-risk">
                          Not ready — {blockers.length} blocking
                        </p>
                        <h2 className="mt-1 text-[19px] font-light tracking-[0.02em] text-white">{blockers[0].label}</h2>
                      </div>
                      <span className="flex shrink-0 items-center gap-2">
                        {showMeFor(blockers[0].id, blockers[0].label) && (
                          <Link
                            href={showMeFor(blockers[0].id, blockers[0].label)!}
                            className="border border-line-strong px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-platinum-dim hover:border-precision/60 hover:text-precision"
                          >
                            Show me
                          </Link>
                        )}
                        <Link
                          href={hrefFor(blockers[0].id, blockers[0].label)}
                          className="border border-precision/60 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-precision hover:bg-precision/10"
                        >
                          Resolve
                        </Link>
                      </span>
                    </header>
                    <div className="px-5 py-3">
                      <p className="text-[13px] leading-relaxed text-platinum-dim">{blockers[0].detail}</p>
                      {blockers[0].actions.length > 0 && (
                        <ul className="mt-2 space-y-0.5">
                          {blockers[0].actions.map((a) => (
                            <li key={a} className="text-[12px] text-platinum-dim">— {a}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                    {blockers.length > 1 && (
                      <ul className="border-t border-line/60">
                        {blockers.slice(1).map((g) => (
                          <li key={g.id} className="flex items-center gap-3 border-b border-line/40 px-5 py-2 last:border-0">
                            <Dot tone={STATUS_TONE[g.status]} />
                            <span className="min-w-0 flex-1 font-mono text-[12px] text-platinum">{g.label}</span>
                            {showMeFor(g.id, g.label) && (
                              <Link href={showMeFor(g.id, g.label)!} className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted hover:text-platinum">
                                Show me
                              </Link>
                            )}
                            <Link href={hrefFor(g.id, g.label)} className="text-[10px] font-semibold uppercase tracking-[0.12em] text-precision-dim hover:text-precision">
                              Resolve
                            </Link>
                          </li>
                        ))}
                      </ul>
                    )}
                  </section>
                ) : (
                  <Notice tone={reviews.length > 0 ? "review" : "pass"} title={reviews.length > 0 ? "No blocking gates — review items remain" : "Every required gate passes"}>
                    {reviews.length > 0
                      ? "Nothing blocks cycle start outright; the review items below deserve eyes before you trust the package."
                      : "Worst-gate aggregation has nothing to hold against this package."}
                  </Notice>
                )}

                {reviews.length > 0 && (
                  <Panel title={`Review — ${reviews.length}`} dense>
                    <ul>{reviews.map((g) => <GateBody key={g.id} g={g} />)}</ul>
                  </Panel>
                )}

                {others.length > 0 && (
                  <Panel title={`Unresolved — ${others.length}`} dense>
                    <ul>{others.map((g) => <GateBody key={g.id} g={g} />)}</ul>
                  </Panel>
                )}

                <details className="border border-line bg-surface">
                  <summary className="cursor-pointer px-4 py-2.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-muted hover:text-platinum">
                    {passed.length} gate{passed.length === 1 ? "" : "s"} passed — view all
                  </summary>
                  <ul className="border-t border-line">{passed.map((g) => <GateBody key={g.id} g={g} />)}</ul>
                </details>
              </>
            );
          })()}

          {!pkg.approved && (
            <Panel title="Operator approval">
              <p className="mb-4 max-w-2xl text-[12.5px] leading-relaxed text-muted">
                Approval is a human act with a name attached to it. Approving records who reviewed this package and when
                — it does not certify that the part is safe, and it does not override any failing gate above.
              </p>
              <form action={approve}>
                <Button type="submit" variant="primary" disabled={!canApprove(user)}>
                  Approve manufacturing package
                </Button>
              </form>
              {!canApprove(user) && (
                <p className="mt-2 text-[11.5px] text-muted">Your role does not permit approving a package.</p>
              )}
            </Panel>
          )}

          {/* ---------------- Process advisor ---------------- */}
          <Panel title="Manufacturing method advisor">
            <p className="mb-4 max-w-2xl text-[13px] leading-relaxed text-platinum">{process.headline}</p>

            {process.blockedBy.length > 0 && (
              <Notice tone="review" title="Blocked inputs">
                <ul className="mt-1 space-y-0.5">
                  {process.blockedBy.map((b) => (
                    <li key={b}>— {b}</li>
                  ))}
                </ul>
                <Link href={`/parts/${id}/responsibility`} className="mt-2 inline-block text-precision hover:underline">
                  Answer the responsibility interview
                </Link>
              </Notice>
            )}

            {/* What this comparison does NOT cover. Reading a list of four
                processes as "the options" is how somebody rules out turning
                for a part that should be turned. The engine has a rule for
                seven of the twenty-one processes CANVAS can name; the rest
                are vocabulary, and saying so is cheaper than being believed. */}
            <p className="mt-4 border border-line px-4 py-2.5 text-[11.5px] leading-relaxed text-muted">
              CANVAS reasons about {EVALUATED_PROCESSES.length} processes here. It does not yet compare this part
              against {UNEVALUATED_PROCESSES.map((p) => PROCESS_LABEL[p].toLowerCase()).join(", ")} — those are not
              ruled out, they are not assessed. Judge them yourself.
            </p>

            <div className="mt-4 space-y-3">
              {process.recommendations.map((r) => {
                const tone: Tone =
                  r.verdict === "RECOMMENDED"
                    ? "pass"
                    : r.verdict === "VIABLE"
                      ? "precision"
                      : r.verdict === "INVESTIGATE"
                        ? "review"
                        : r.verdict === "INSUFFICIENT_DATA"
                          ? "unknown"
                          : "neutral";
                return (
                  <div key={r.process} className="border border-line px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-mono text-[12px] text-platinum">{PROCESS_LABEL[r.process]}</span>
                      <span className="flex items-center gap-2">
                        <span className="tech-label">{r.volumeBand}</span>
                        <StatusChip tone={tone}>{r.verdict.replace(/_/g, " ")}</StatusChip>
                      </span>
                    </div>
                    <ul className="mt-2 space-y-1">
                      {r.rationale.map((x) => (
                        <li key={x} className="text-[12px] leading-relaxed text-muted">
                          {x}
                        </li>
                      ))}
                    </ul>
                    {r.blockers.length > 0 && (
                      <ul className="mt-2 space-y-0.5">
                        {r.blockers.map((b) => (
                          <li key={b} className="text-[11.5px] text-review">
                            — {b}
                          </li>
                        ))}
                      </ul>
                    )}
                    {(r.toolingCostOrder || r.leadTimeNote) && (
                      <p className="tech-label mt-2">
                        {[r.toolingCostOrder, r.leadTimeNote].filter(Boolean).join(" · ")}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>

            {process.volumeCrossovers.length > 0 && (
              <div className="mt-4 border-t border-line pt-4">
                <p className="tech-label mb-2">Volume crossovers to watch</p>
                {process.volumeCrossovers.map((c) => (
                  <p key={c.volume} className="text-[12px] text-muted">
                    <span className="font-mono text-platinum-dim">{c.volume.toLocaleString()}/yr</span> — {c.note}
                  </p>
                ))}
              </div>
            )}
          </Panel>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";
