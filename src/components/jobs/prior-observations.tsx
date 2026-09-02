import { Panel, StatusChip } from "@/components/ui";
import { OUTCOME_LABEL } from "@/lib/engines/network";
import type { PriorObservation } from "@/lib/job-knowledge";

/**
 * What previous jobs on this machine, in this material, in this workholding
 * actually did.
 *
 * Presented beside the recommendation, never folded into it. Principle 11:
 * this is shop knowledge scoped to what it was seen on, and it does not
 * become an engineering fact by being displayed next to one.
 */
export function PriorObservations({ observations, scope }: { observations: PriorObservation[]; scope: string }) {
  if (observations.length === 0) return null;
  return (
    <Panel
      title="What happened last time"
      meta={<StatusChip tone="review">{observations.length}</StatusChip>}
    >
      <p className="max-w-2xl text-[12.5px] leading-relaxed text-muted">
        Recorded outcomes from earlier jobs in the same scope — {scope}. This is your shop&rsquo;s observation, not a
        published fact, and it has not changed any number above it. Nothing here applies outside the machine,
        workholding and material it was seen on.
      </p>
      <ul className="mt-3 space-y-2">
        {observations.map((o, i) => (
          <li key={`${o.jobNumber}-${i}`} className="border-l-2 border-l-review/60 bg-raised px-3.5 py-2.5">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <span className="font-mono text-[12px] text-platinum">{OUTCOME_LABEL[o.code]}</span>
              <span className="tech-label">
                {o.samePart ? "this part" : o.partName} · job {o.jobNumber} ·{" "}
                {new Date(o.recordedAt).toISOString().slice(0, 10)}
                {o.toolNumber != null && ` · T${o.toolNumber}`}
              </span>
            </div>
            <p className="tech-label mt-1">Cause: {o.cause}</p>
            <p className="mt-1 text-[12px] leading-relaxed text-platinum-dim">Then: {o.correctiveAction}</p>
          </li>
        ))}
      </ul>
    </Panel>
  );
}
