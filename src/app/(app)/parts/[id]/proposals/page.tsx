import { notFound, redirect } from "next/navigation";
import Link from "next/link";
import { requireUser, requireWrite } from "@/lib/auth";
import { db } from "@/lib/db";
import { audit } from "@/lib/audit";
import { loadRevision } from "@/lib/data";
import type { FeatureSuggestion } from "@/lib/domain/features";
import { coerceFeatureParameters, validateFeatureParameters } from "@/lib/domain/feature-input";
import { TopBar } from "@/components/nav";
import { Button, EmptyState, Notice, Panel, SectionHeading, StatusChip } from "@/components/ui";

/**
 * AI PROPOSALS
 *
 * A model suggestion is never geometry. It sits here as a proposal with a
 * rationale attached, and becomes a feature only when a named human accepts
 * it — which is recorded in the audit trail as an ACCEPT_SUGGESTION by that
 * person, not as a system action.
 */

export default async function ProposalsPage(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  const user = await requireUser();
  const revision = await loadRevision(user.organizationId, id);
  if (!revision) notFound();

  const proposals = await db.aIRecommendation.findMany({
    where: { partRevisionId: revision.revisionId },
    orderBy: { createdAt: "desc" },
  });

  async function decide(formData: FormData) {
    "use server";
    const currentUser = await requireWrite();
    const rev = await loadRevision(currentUser.organizationId, id);
    if (!rev) notFound();

    const proposalId = String(formData.get("proposalId"));
    const accept = formData.get("decision") === "accept";

    const proposal = await db.aIRecommendation.findFirst({
      where: { id: proposalId, partRevisionId: rev.revisionId },
    });
    if (!proposal) notFound();

    if (accept && proposal.kind === "FEATURE") {
      const suggestions = JSON.parse(proposal.payloadJson) as FeatureSuggestion[];
      const existingCount = await db.feature.count({ where: { partRevisionId: rev.revisionId } });

      /*
       * Validated against the same field spec the hand-entry form uses.
       * featureSuggestionSchema types parameters as a free record, so a
       * proposal missing a diameter used to be written straight through and
       * every engine downstream met undefined where it expected a number.
       * A suggestion that does not describe a buildable feature is skipped,
       * and the proposal records which ones were.
       */
      let written = 0;
      const skipped: string[] = [];
      for (const [i, s] of suggestions.entries()) {
        const { rationale, ...params } = { ...s.parameters, rationale: s.rationale };
        const refusals = validateFeatureParameters(s.kind, params);
        if (refusals.length > 0) {
          skipped.push(`${s.label}: ${refusals.map((r) => r.reason).join(" ")}`);
          continue;
        }
        await db.feature.create({
          data: {
            partRevisionId: rev.revisionId,
            kind: s.kind,
            label: s.label,
            functionalRole: s.functionalRole ?? "NONE",
            critical: s.critical ?? false,
            parametersJson: JSON.stringify(coerceFeatureParameters(s.kind, params)),
            notes: typeof rationale === "string" ? rationale : undefined,
            orderIndex: existingCount + written,
          },
        });
        written++;
      }
      if (skipped.length > 0) {
        await audit({
          organizationId: currentUser.organizationId,
          userId: currentUser.id,
          actorType: "HUMAN",
          entityType: "PartRevision",
          entityId: rev.revisionId,
          action: "ACCEPT_SUGGESTION",
          reason: `${skipped.length} suggested feature(s) did not describe a buildable feature and were not written: ${skipped.join("; ").slice(0, 800)}`,
        });
      }
    }

    await db.aIRecommendation.update({
      where: { id: proposalId },
      data: { status: accept ? "ACCEPTED" : "REJECTED", decidedBy: currentUser.id, decidedAt: new Date() },
    });

    await audit({
      organizationId: currentUser.organizationId,
      userId: currentUser.id,
      entityType: "AIRecommendation",
      entityId: proposalId,
      action: accept ? "ACCEPT_SUGGESTION" : "REJECT_SUGGESTION",
      actorType: "HUMAN",
      newValue: proposal.summary,
      reason: accept ? "Proposal accepted into the part model" : "Proposal rejected",
    });

    redirect(`/parts/${id}/proposals`);
  }

  const open = proposals.filter((p) => p.status === "PROPOSED");
  const decided = proposals.filter((p) => p.status !== "PROPOSED");

  return (
    <>
      <TopBar>
        <Link href={`/parts/${id}`} className="tech-label hover:text-platinum">
          {revision.partName}
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">Proposals</span>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          <SectionHeading sub="Nothing a model proposes enters the part model on its own. Accepting is a human act with a name and a timestamp on it, recorded in the audit trail as such.">
            AI proposals
          </SectionHeading>

          {open.length === 0 && decided.length === 0 ? (
            <EmptyState title="No proposals" body="Feature suggestions are generated when a part is created from a description." />
          ) : null}

          {open.map((p) => {
            const suggestions: FeatureSuggestion[] = p.kind === "FEATURE" ? JSON.parse(p.payloadJson) : [];
            return (
              <Panel
                key={p.id}
                title={p.summary}
                meta={
                  <span className="flex gap-2">
                    <StatusChip tone="review">AI suggestion</StatusChip>
                    {p.confidence !== null && <StatusChip tone="neutral">{(p.confidence * 100).toFixed(0)}% intake completeness</StatusChip>}
                  </span>
                }
              >
                <div className="space-y-2">
                  {suggestions.map((s, i) => (
                    <div key={i} className="border border-line px-3.5 py-2.5">
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-mono text-[12px] text-platinum">{s.label}</span>
                        <span className="tech-label">{s.kind.replace(/_/g, " ").toLowerCase()}</span>
                      </div>
                      <p className="tech-label mt-1">
                        {Object.entries(s.parameters)
                          .map(([k, v]) => `${k} ${typeof v === "number" ? v.toFixed(4).replace(/0+$/, "") : v}`)
                          .join(" · ")}
                      </p>
                      {s.rationale && <p className="mt-1.5 text-[12px] leading-relaxed text-muted">{s.rationale}</p>}
                    </div>
                  ))}
                </div>

                <Notice tone="review" title="Confirm the numbers before accepting">
                  Positions and sizes that were not stated in your description have been inferred from convention.
                  Accepting creates real geometry that the CAM engine will cut.
                </Notice>

                <div className="mt-4 flex gap-2">
                  <form action={decide}>
                    <input type="hidden" name="proposalId" value={p.id} />
                    <input type="hidden" name="decision" value="accept" />
                    <Button type="submit" variant="primary">
                      Accept {suggestions.length} features
                    </Button>
                  </form>
                  <form action={decide}>
                    <input type="hidden" name="proposalId" value={p.id} />
                    <input type="hidden" name="decision" value="reject" />
                    <Button type="submit">Reject</Button>
                  </form>
                </div>
              </Panel>
            );
          })}

          {decided.length > 0 && (
            <Panel title="Decided">
              <ul className="space-y-2">
                {decided.map((p) => (
                  <li key={p.id} className="flex items-center justify-between gap-3 border-b border-line/60 py-2 last:border-0">
                    <span className="text-[12px] text-platinum-dim">{p.summary}</span>
                    <StatusChip tone={p.status === "ACCEPTED" ? "pass" : "neutral"}>{p.status}</StatusChip>
                  </li>
                ))}
              </ul>
            </Panel>
          )}
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";
