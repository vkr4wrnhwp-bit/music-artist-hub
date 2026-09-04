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

/**
 * Providers that are a parser and arithmetic rather than a model. Their
 * proposals still go through human acceptance — that is what makes geometry
 * safe — but calling them AI would be a false provenance, and CANVAS types
 * the actor rather than inferring it.
 */
const DETERMINISTIC_PROVIDERS = new Set(["step-recognizer", "dxf-import", "canvas-sketch", "scan-slice"]);

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
        /*
         * THE BOUNDARY TRAVELS WITH THE FEATURE.
         *
         * `Feature.chain` is read by the contour and chamfer engines and was
         * written by nothing, so every profile was `rectangleChain()` — a
         * rounded rectangle from three numbers, whatever shape the part
         * actually was. A suggestion that carries a real closed loop writes it
         * here, alongside the scalars, and the data mapper spreads it back on
         * to the domain feature. Both halves or neither: a chain with no start
         * point has no first segment to leave from.
         */
        const boundary = s.chain && s.chainStart ? { chain: s.chain, chainStart: s.chainStart } : {};
        await db.feature.create({
          data: {
            partRevisionId: rev.revisionId,
            kind: s.kind,
            label: s.label,
            functionalRole: s.functionalRole ?? "NONE",
            critical: s.critical ?? false,
            parametersJson: JSON.stringify({ ...coerceFeatureParameters(s.kind, params), ...boundary }),
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

      /*
       * ACCEPTING SOMETHING THAT WROTE NOTHING IS NOT AN ACCEPTANCE.
       *
       * The skip was audited and the proposal was marked ACCEPTED, so the
       * screen said "accepted" and the part gained nothing — the operator's
       * next clue would have been a missing feature at the machine. A proposal
       * where every suggestion was refused stays PROPOSED, and the refusal is
       * shown where the proposal is.
       */
      if (written === 0) {
        await db.aIRecommendation.update({
          where: { id: proposalId },
          data: { summary: `${proposal.summary}\n\nNOT ACCEPTED — ${skipped.join("; ")}`.slice(0, 2000) },
        });
        redirect(`/parts/${id}/proposals`);
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
                    {/*
                      WHAT PROPOSED THIS, AND WHETHER IT HAS A SCORE.

                      A parser is not a model. The STEP recognizer, the DXF
                      reader and the drawing surface are arithmetic — labelling
                      their output "AI suggestion" is a false provenance, and it
                      undercuts the line above about nothing a model proposes
                      entering the part model on its own.

                      And the confidence: a deterministic reader stores 1
                      because the column is not nullable there, which rendered
                      as "100% intake completeness" — a number that looks like a
                      live measure and is nothing of the kind. A score belongs
                      only to something that actually scored.
                    */}
                    {DETERMINISTIC_PROVIDERS.has(p.providerId ?? "") ? (
                      <StatusChip tone="neutral">Read from geometry</StatusChip>
                    ) : (
                      <>
                        <StatusChip tone="review">AI suggestion</StatusChip>
                        {p.confidence !== null && (
                          <StatusChip tone="neutral">{(p.confidence * 100).toFixed(0)}% intake completeness</StatusChip>
                        )}
                      </>
                    )}
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
