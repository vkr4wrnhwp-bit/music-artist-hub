import { Button, Field, Panel, StatusChip, inputClass } from "@/components/ui";

/**
 * Freezing the live cost figure into something a quote can carry.
 *
 * The warnings are the point of the control, not a footnote on it. The cost
 * engine already knows which assumptions its arithmetic is not valid over,
 * and an estimate stored while one is open is stored WITH it — the shop can
 * quote with caveats, but the caveat travels with the price rather than being
 * dismissed at the moment of storing.
 */
export function StoreEstimate({
  quantity,
  unitPrice,
  warnings,
  missingInputs = [],
  stored,
  action,
}: {
  quantity: number;
  unitPrice: string;
  warnings: string[];
  /**
   * Inputs that were never established. Distinct from `warnings`, which are
   * assumptions outside the range the arithmetic is valid over — those can be
   * stored WITH the estimate and travel to the customer. These cannot, because
   * there is no price: the server action refuses, and the button says so
   * rather than letting a machinist press it and watch nothing happen.
   */
  missingInputs?: string[];
  stored: { id: string; quantity: number; unitPrice: string; createdAt: Date; quoteNumber: string | null }[];
  action: (formData: FormData) => void;
}) {
  return (
    <Panel
      title="Store this estimate"
      meta={stored.length > 0 ? <StatusChip tone="neutral">{stored.length} stored</StatusChip> : null}
    >
      <p className="max-w-2xl text-[12.5px] leading-relaxed text-muted">
        Freezes the assumption set, the line breakdown and the price as they are now. A quote that cannot be defended
        in a customer meeting is worthless, and defending it means showing the inputs as they stood — not recomputing
        them later and presenting today&rsquo;s answer as the promise that was made.
      </p>

      {warnings.length > 0 && (
        <div className="mt-3 border border-review/40 bg-review/5 p-3">
          <p className="tech-label text-review">
            Stored with {warnings.length} assumption {warnings.length === 1 ? "warning" : "warnings"}
          </p>
          <p className="mt-1 text-[12px] leading-relaxed text-platinum-dim">
            The estimate can still be stored. The warnings are stored with it and shown on the quote, so nobody sends
            this price without seeing what it stands on.
          </p>
        </div>
      )}

      {missingInputs.length > 0 && (
        <div className="mt-3 border border-review/40 bg-review/5 p-3">
          <p className="tech-label text-review">Nothing to store</p>
          <ul className="mt-1 space-y-1">
            {missingInputs.map((m) => (
              <li key={m} className="text-[12px] leading-relaxed text-platinum-dim">
                — {m}
              </li>
            ))}
          </ul>
        </div>
      )}

      <form action={action} className="mt-4 flex flex-wrap items-end gap-3">
        <Field label="Quantity">
          <input name="quantity" type="number" min={1} defaultValue={quantity} className={inputClass} />
        </Field>
        <Button type="submit" variant="primary" disabled={missingInputs.length > 0}>
          {missingInputs.length > 0 ? "No price to store" : `Store at ${unitPrice} per part`}
        </Button>
      </form>

      {stored.length > 0 && (
        <ul className="mt-4 space-y-1 border-t border-line pt-3">
          {stored.map((e) => (
            <li key={e.id} className="flex flex-wrap items-baseline justify-between gap-3 text-[12px]">
              <span className="text-platinum-dim">
                Qty {e.quantity} at {e.unitPrice} per part
              </span>
              <span className="tech-label">
                {new Date(e.createdAt).toISOString().slice(0, 10)} ·{" "}
                {e.quoteNumber ? `on quote ${e.quoteNumber}` : "not on a quote"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
