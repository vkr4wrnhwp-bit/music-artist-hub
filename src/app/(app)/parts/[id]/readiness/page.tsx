import { notFound, redirect } from "next/navigation";
import Link from "next/link";
import { requireUser, canApprove } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { buildPackage } from "@/lib/package";
import { PROCESS_LABEL } from "@/lib/engines/process-advisor";
import { TopBar } from "@/components/nav";
import { PartStatusChip } from "@/components/part-status";
import { Disagree } from "@/components/disagree";
import { recordDisagreement } from "@/lib/disagreement";
import { revalidatePath } from "next/cache";
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

  async function approve() {
    "use server";
    const currentUser = await requireUser();
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
    const currentUser = await requireUser();
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

          <Panel title="Gates" dense>
            <ul>
              {readiness.gates.map((g) => (
                <li key={g.id} className="border-b border-line/60 px-4 py-3 last:border-0">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex min-w-0 items-start gap-2.5">
                      <span className="mt-1.5">
                        <Dot tone={STATUS_TONE[g.status]} />
                      </span>
                      <div className="min-w-0">
                        <p className="flex items-center gap-2 font-mono text-[12px] text-platinum">
                          {g.label}
                          {g.blocking && <span className="tech-label text-precision">blocking</span>}
                        </p>
                        <p className="mt-0.5 text-[12px] leading-relaxed text-muted">{g.detail}</p>
                        {g.actions.length > 0 && (
                          <ul className="mt-1.5 space-y-0.5">
                            {g.actions.map((a) => (
                              <li key={a} className="text-[11.5px] text-platinum-dim">
                                — {a}
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    </div>
                    <StatusChip tone={STATUS_TONE[g.status]}>{g.status.replace(/_/g, " ")}</StatusChip>
                  </div>
                  {g.status !== "PASS" && g.status !== "NOT_ATTEMPTED" && (
                    <div className="mt-2.5 pl-6">
                      <Disagree
                        action={disagree}
                        subjectType="READINESS_GATE"
                        subjectId={g.id}
                        partRevisionId={pkg.revision.revisionId}
                        canvasPosition={`${g.label} — ${g.status.replace(/_/g, " ")}. ${g.detail}`}
                      />
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </Panel>

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
