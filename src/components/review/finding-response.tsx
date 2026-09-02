import { RESOLUTION_LABEL, RESOLUTION_STATUSES, type FindingRecord } from "@/lib/review-findings";
import { Button, StatusChip } from "@/components/ui";

/**
 * The human response to a finding, and its history.
 *
 * Three things this deliberately does not do:
 *
 * - It does not offer a control that closes the finding. There is no "resolve
 *   and hide". A finding goes away when the engine stops raising it, which
 *   means the evidence changed — principle 2.
 * - It does not present a stale response as if it still stood. When the
 *   evidence moved since somebody answered, the previous answer is shown as
 *   history and the finding reads as open again, in those words.
 * - It does not accept a disagreement with no reasoning. A dismissal is not
 *   shop knowledge.
 */

const STATUS_TONE = { ACKNOWLEDGED: "unknown", ACTIONED: "pass", DISPUTED: "review" } as const;

const when = (d: Date) => new Date(d).toISOString().slice(0, 10);

export function FindingResponse({
  record,
  findingKey,
  action,
}: {
  record: FindingRecord | undefined;
  findingKey: string;
  action: (formData: FormData) => void;
}) {
  const current = record?.resolution?.current ? record.resolution : null;
  const stale = record?.resolution && !record.resolution.current ? record.resolution : null;

  return (
    <div className="mt-4 border-t border-line pt-3">
      {record && (
        <p className="tech-label mb-2">
          First raised {when(record.firstSeenAt)}
          {record.history.length > 0 && ` · ${record.history.length} response${record.history.length === 1 ? "" : "s"} on record`}
        </p>
      )}

      {current && (
        <div className="mb-3 flex flex-wrap items-baseline gap-2">
          <StatusChip tone={STATUS_TONE[current.status]}>{RESOLUTION_LABEL[current.status]}</StatusChip>
          <span className="text-[12px] text-platinum-dim">{current.note}</span>
          <span className="tech-label">
            {current.actorName} · {current.actorType} · {when(current.recordedAt)}
          </span>
        </div>
      )}

      {stale && (
        <p className="mb-3 text-[12px] leading-relaxed text-review">
          {stale.actorName} recorded &ldquo;{RESOLUTION_LABEL[stale.status]}&rdquo; on {when(stale.recordedAt)}, against
          different numbers than the ones above. The evidence has changed since, so that answer does not carry over —
          this finding is open.
        </p>
      )}

      <form action={action} className="flex flex-wrap items-center gap-2">
        <input type="hidden" name="findingKey" value={findingKey} />
        <select
          name="status"
          defaultValue="ACKNOWLEDGED"
          aria-label="Response"
          className="border border-line-strong bg-surface px-1.5 py-1.5 text-[11px] text-platinum-dim"
        >
          {RESOLUTION_STATUSES.map((s) => (
            <option key={s} value={s}>
              {RESOLUTION_LABEL[s]}
            </option>
          ))}
        </select>
        <input
          name="note"
          maxLength={2000}
          placeholder="What you found, or why you disagree"
          aria-label="Note"
          className="min-w-[18rem] flex-1 border border-line-strong bg-surface px-2 py-1.5 text-[12px] text-platinum placeholder:text-muted"
        />
        <Button type="submit" size="sm">
          Record
        </Button>
      </form>
      <p className="tech-label mt-2">
        Recording a response does not clear this finding or any readiness gate. It goes away when the check stops
        raising it.
      </p>
    </div>
  );
}
