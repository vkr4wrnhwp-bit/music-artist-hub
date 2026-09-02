import { Button, Field, Notice, Panel, inputClass } from "@/components/ui";

/**
 * Raising a quote.
 *
 * Unlike a job, a quote is not gated on readiness: quoting a part CANVAS is
 * not ready to run is ordinary shop work, and refusing it would stop a shop
 * pricing the job it is trying to win. What is gated is sending one — a quote
 * with no stored estimate on it prices nothing.
 */
export function RaiseQuoteForm({
  parts,
  action,
}: {
  parts: { id: string; name: string }[];
  action: (formData: FormData) => void;
}) {
  if (parts.length === 0) {
    return (
      <Notice tone="review" title="No parts to quote">
        A quote is raised against a part. Create one first.
      </Notice>
    );
  }
  return (
    <Panel title="Raise a quote">
      <form action={action} className="grid gap-3 sm:grid-cols-4">
        <Field label="Part">
          <select name="partId" className={inputClass}>
            {parts.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </Field>
        <Field label="Quote number">
          <input name="quoteNumber" required maxLength={60} className={inputClass} />
        </Field>
        <Field label="Customer">
          <input name="customer" maxLength={200} className={inputClass} />
        </Field>
        <Field label="Valid until">
          <input name="validUntil" type="date" className={inputClass} />
        </Field>
        <div className="sm:col-span-4">
          <Button type="submit" variant="primary">Raise quote</Button>
        </div>
      </form>
    </Panel>
  );
}
