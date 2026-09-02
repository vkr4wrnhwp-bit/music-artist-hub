import { Button, Field, Notice, Panel, inputClass } from "@/components/ui";
import { QUOTE_STATUS_LABEL, type QuoteStatus } from "@/lib/engines/quoting";

export function QuoteTransport({
  next,
  canSend,
  action,
}: {
  next: QuoteStatus[];
  canSend: boolean;
  action: (formData: FormData) => void;
}) {
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-line pt-3">
      <span className="tech-label">Next</span>
      {next.map((s) => (
        <form key={s} action={action}>
          <input type="hidden" name="to" value={s} />
          <Button type="submit" size="sm" variant={s === "SENT" ? "primary" : "default"} disabled={s === "SENT" && !canSend}>
            {QUOTE_STATUS_LABEL[s]}
          </Button>
        </form>
      ))}
      {next.includes("SENT") && !canSend && (
        <span className="text-[11px] text-review">A quote with no estimate on it prices nothing.</span>
      )}
    </div>
  );
}

export function AttachEstimate({
  estimates,
  action,
}: {
  estimates: { id: string; label: string }[];
  action: (formData: FormData) => void;
}) {
  if (estimates.length === 0) {
    return (
      <Notice tone="review" title="No unattached estimate for this part">
        Estimates are frozen from a part&rsquo;s Cost page, where the assumption set is computed. Only estimates for
        this quote&rsquo;s own part can be attached — a price for a different part is how a wrong number reaches a
        customer.
      </Notice>
    );
  }
  return (
    <Panel title="Attach a stored estimate">
      <form action={action} className="flex flex-wrap items-end gap-3">
        <Field label="Estimate">
          <select name="estimateId" className={inputClass}>
            {estimates.map((e) => (
              <option key={e.id} value={e.id}>{e.label}</option>
            ))}
          </select>
        </Field>
        <Button type="submit" variant="primary">Attach</Button>
      </form>
    </Panel>
  );
}
