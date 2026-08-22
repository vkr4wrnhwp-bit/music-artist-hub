import { Button, DevLabel, Notice } from "@/components/ui";
import { ShowCalculation } from "@/components/show-calculation";
import type { SequenceProposal, SequencedOperation } from "@/lib/engines/sequencing";
import { applySequenceProposal } from "@/app/(app)/parts/[id]/setups/sequence-actions";

/**
 * The sequence proposal, as a machinist reads it.
 *
 * Three states, and the one that matters most is the third: when there is
 * nothing to gain, this says so in a sentence that names the reason. A panel
 * that quietly renders nothing when it has no advice teaches the operator to
 * ignore it; a panel that invents advice is worse.
 *
 * Applying is a separate, explicit action. The order is never rewritten as a
 * side effect of looking at it — principle 11's WHY / CHANGE / I DISAGREE
 * shape, where the recommendation is visible and the human decides.
 */
export function SequenceProposalPanel({
  proposal,
  operations,
  setupId,
  partId,
}: {
  proposal: SequenceProposal;
  operations: SequencedOperation[];
  setupId: string;
  partId: string;
}) {
  const byId = new Map(operations.map((o) => [o.id, o]));
  const label = (id: string) => {
    const o = byId.get(id);
    if (!o) return id;
    return `T${o.toolNumber ?? "—"} ${o.type.replace(/_2D|_DRILL/g, "")}`;
  };

  const hasChange = proposal.saved > 0 || proposal.violations.length > 0;

  return (
    <div className="mt-4 space-y-2">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <p className="tech-label">Tool changes</p>
        <p className="font-mono text-[20px] leading-none text-white tabular-nums">
          {proposal.currentToolChanges}
          {proposal.saved > 0 && (
            <>
              <span className="mx-1.5 text-[13px] text-muted">→</span>
              <span className="text-pass">{proposal.proposedToolChanges}</span>
            </>
          )}
        </p>
        {proposal.saved > 0 && (
          <span className="text-[11.5px] text-muted">
            {proposal.saved} fewer by regrouping — the cutting is identical
          </span>
        )}
      </div>

      {/* A plan that breaks its own precedence is the more serious finding,
          so it is stated before any talk of saved seconds. */}
      {proposal.violations.length > 0 && (
        <Notice
          tone="risk"
          title={`This order breaks ${proposal.violations.length} precedence rule${proposal.violations.length === 1 ? "" : "s"}`}
        >
          <ul className="space-y-1">
            {proposal.violations.slice(0, 5).map((v) => (
              <li key={`${v.beforeId}-${v.afterId}`} className="text-[12px] leading-relaxed">
                <span className="font-mono text-[11px] text-platinum">
                  {byId.get(v.beforeId)?.label ?? v.beforeId} before {byId.get(v.afterId)?.label ?? v.afterId}
                </span>
                <span className="ml-1.5 text-muted">— {v.rule}</span>
              </li>
            ))}
          </ul>
        </Notice>
      )}

      {hasChange ? (
        <>
          <div className="border border-line bg-void px-3 py-2.5">
            <p className="tech-label mb-1.5">Proposed order</p>
            <div className="flex flex-wrap items-center gap-1">
              {proposal.proposedOrder.map((id, i) => (
                <span key={id} className="flex items-center gap-1">
                  <span className="border border-line px-2 py-1 font-mono text-[10px] uppercase tracking-[0.1em] text-platinum-dim">
                    {label(id)}
                  </span>
                  {i < proposal.proposedOrder.length - 1 && <span className="text-muted">→</span>}
                </span>
              ))}
            </div>
          </div>

          <form action={applySequenceProposal}>
            <input type="hidden" name="setupId" value={setupId} />
            <input type="hidden" name="partId" value={partId} />
            <Button type="submit" size="sm" variant="primary">
              Apply this order
            </Button>
          </form>
        </>
      ) : (
        <p className="border border-line border-l-2 border-l-line-strong bg-raised px-3 py-2.5 text-[12.5px] leading-relaxed text-muted">
          {proposal.reason}
        </p>
      )}

      <ShowCalculation
        title="How the order was checked"
        headline={String(proposal.edges.length)}
        unit="precedence rules over this setup"
        method={proposal.method}
        inputs={[]}
        assumptions={proposal.limitations}
      >
        <div>
          <p className="tech-label mb-1.5">What fixes the order</p>
          <ul className="space-y-1">
            {[...new Set(proposal.edges.map((e) => e.rule))].map((rule) => (
              <li key={rule} className="flex gap-2 text-[12px] leading-relaxed text-muted">
                <span className="text-precision">—</span>
                <span>{rule}</span>
              </li>
            ))}
          </ul>
        </div>
        <p className="text-[12px] leading-relaxed text-review">
          Applying this changes the order operations are posted in. It does not regenerate a toolpath and does not
          change what is cut — but the program is not the same program, so verify it before it runs.
        </p>
      </ShowCalculation>
    </div>
  );
}

/**
 * The other four optimisation actions, still unbuilt.
 *
 * "Optimize setup" now carries the specific reason rather than a bare label:
 * eliminating a setup means re-orienting the part, and the feature model has
 * no per-feature access direction to search over — everything is defined
 * against one top face with Z=0 at it. That is a schema and parser change,
 * not a button, and saying which wall you hit is more use than "not
 * implemented".
 */
export function UnbuiltOptimisations() {
  const items: { label: string; why: string }[] = [
    {
      label: "Optimize setup",
      why: "Eliminating a setup means re-orienting the part, and features carry no access direction — everything is defined from one top face. Needs a model change, not a button.",
    },
    { label: "Reduce cycle time", why: "Needs a feed and speed search per operation against proven cutting data. Not built." },
    { label: "Reduce risk", why: "Needs a search over workholding alternatives. Not built." },
    { label: "Improve finish", why: "Needs a finish-pass strategy model. Not built." },
  ];
  return (
    <div className="mt-4 space-y-1.5">
      {items.map((i) => (
        <div key={i.label} className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
          <span className="flex items-center gap-1.5 border border-line px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-unknown">
            {i.label}
            <DevLabel>Not implemented</DevLabel>
          </span>
          <span className="text-[11.5px] leading-relaxed text-muted">{i.why}</span>
        </div>
      ))}
    </div>
  );
}
