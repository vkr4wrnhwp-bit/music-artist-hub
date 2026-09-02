import { Button, Field, Notice, Panel, inputClass } from "@/components/ui";

/**
 * Raising a job.
 *
 * The part list is the RELEASED revisions only — which is what the section
 * always said and could not do, because nothing set a revision to RELEASED.
 * A part with no released revision is not offered here; the way to offer it
 * is through its readiness gates, not through this form.
 */
export function RaiseJobForm({
  released,
  action,
}: {
  released: { partId: string; partName: string; revision: string }[];
  action: (formData: FormData) => void;
}) {
  /*
   * Nothing released is a state worth explaining rather than a reason to
   * render nothing. A page that simply has no form on it reads as a page
   * where raising a job is unbuilt, which is the thing this whole section
   * was being fixed for.
   */
  if (released.length === 0) {
    return (
      <Notice tone="review" title="No released revision to raise a job against">
        A job is raised against a released part revision. Release happens on a part&rsquo;s readiness page and is
        refused while any blocking gate is unresolved — there is no override, because a blocking gate is satisfied by
        evidence rather than by acknowledging it.
      </Notice>
    );
  }
  return (
    <Panel title="Raise a job">
      <form action={action} className="grid gap-3 sm:grid-cols-4">
        <Field label="Released revision">
          <select name="partId" className={inputClass}>
            {released.map((r) => (
              <option key={r.partId} value={r.partId}>
                {r.partName} — rev {r.revision}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Job number">
          <input name="jobNumber" required maxLength={60} className={inputClass} />
        </Field>
        <Field label="Quantity">
          <input name="quantity" type="number" min={1} defaultValue={1} required className={inputClass} />
        </Field>
        <Field label="Due date">
          <input name="dueDate" type="date" className={inputClass} />
        </Field>
        <div className="sm:col-span-4">
          <Button type="submit" variant="primary">Raise job</Button>
        </div>
      </form>
    </Panel>
  );
}
