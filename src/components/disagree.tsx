import { inputClass } from "@/components/ui";
import type { DisagreementSubject } from "@/lib/disagreement";

/**
 * WHY / CHANGE / I DISAGREE
 *
 * Attached to a recommendation, not to the app. The point is that an
 * experienced machinist can push back at the moment they disagree, in one
 * click, without leaving what they were doing.
 *
 * The form is deliberately blunt about what recording it does and does not do.
 * Software that implies a safety gate can be argued away is worse than
 * software with no disagree button at all.
 */
export function Disagree({
  action,
  partId,
  surface,
  subjectType,
  subjectId,
  setupId,
  canvasPosition,
  jobs,
}: {
  action: (formData: FormData) => void | Promise<void>;
  /** The part this is about. The action derives the revision from it. */
  partId: string;
  /** Where the machinist was, so they are put back there afterwards. */
  surface: "readiness" | "setups" | "tooling" | "cost" | "part";
  subjectType: DisagreementSubject;
  subjectId?: string;
  setupId?: string;
  /** What CANVAS said — stored verbatim so the record survives a recompute. */
  canvasPosition: string;
  /**
   * Completed jobs to choose from. NOT optional and with no default: it
   * defaulted to `[]` once, its only call site passed none, and the form asked
   * "have you run a comparable setup?" with no way to answer. A required prop
   * makes that a compile error rather than dead UI.
   */
  jobs: { id: string; label: string }[];
}) {
  // Several of these render on one page now. Ids have to differ or a label
  // points at the wrong field.
  const slug = `${subjectType}-${subjectId ?? "x"}`;
  return (
    <details className="group">
      <summary className="inline-flex cursor-pointer list-none items-center gap-1 border border-line px-2 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-muted hover:border-line-strong hover:text-platinum">
        <span className="group-open:hidden">I disagree</span>
        <span className="hidden group-open:inline">Cancel</span>
      </summary>

      <form action={action} className="mt-3 space-y-3 border border-line bg-void px-3 py-3">
        <input type="hidden" name="subjectType" value={subjectType} />
        {subjectId && <input type="hidden" name="subjectId" value={subjectId} />}
        {/* The part, not the revision. A form that can name a revision can
            name another shop's; the action looks it up from the part under
            this organisation instead. */}
        <input type="hidden" name="partId" value={partId} />
        <input type="hidden" name="surface" value={surface} />
        {setupId && <input type="hidden" name="setupId" value={setupId} />}
        <input type="hidden" name="canvasPosition" value={canvasPosition} />

        <div>
          <p className="tech-label mb-1">CANVAS position</p>
          <p className="text-[12px] leading-relaxed text-muted">{canvasPosition}</p>
        </div>

        <div>
          <label htmlFor={`reasoning-${slug}`} className="tech-label mb-1 block">
            Why do you disagree?
          </label>
          <textarea
            id={`reasoning-${slug}`}
            name="reasoning"
            required
            rows={3}
            className={inputClass}
            placeholder="What does CANVAS not know? Machine behaviour, fixture behaviour, how this material actually cuts here."
          />
        </div>

        <div>
          <p className="tech-label mb-1.5">Have you successfully run a comparable setup?</p>
          <div className="flex gap-4">
            <label className="flex items-center gap-1.5 text-[12px] text-platinum-dim">
              <input type="radio" name="hasRunComparable" value="yes" className="accent-[color:var(--c-blue)]" />
              Yes
            </label>
            <label className="flex items-center gap-1.5 text-[12px] text-platinum-dim">
              <input type="radio" name="hasRunComparable" value="no" defaultChecked className="accent-[color:var(--c-blue)]" />
              No
            </label>
          </div>
        </div>

        {jobs.length > 0 && (
          <div>
            <label htmlFor={`comparableJobId-${slug}`} className="tech-label mb-1 block">
              Comparable job
            </label>
            <select id={`comparableJobId-${slug}`} name="comparableJobId" className={inputClass} defaultValue="">
              <option value="">Not specified</option>
              {jobs.map((j) => (
                <option key={j.id} value={j.id}>
                  {j.label}
                </option>
              ))}
            </select>
          </div>
        )}

        <div>
          <label htmlFor={`proposedValue-${slug}`} className="tech-label mb-1 block">
            What should it say instead? (optional)
          </label>
          <input id={`proposedValue-${slug}`} name="proposedValue" className={inputClass} placeholder="e.g. 0.080 grip is fine here" />
        </div>

        <p className="border border-line border-l-2 border-l-review bg-raised px-2.5 py-2 text-[11.5px] leading-relaxed text-muted">
          Recording this does not clear the gate. A gate reflects the state of the evidence, and disagreeing with it is a
          claim about the evidence rather than a change to it. What you write here is kept as shop knowledge, scoped to
          this shop and this equipment, and it carries more weight when a comparable job backs it up.
        </p>

        <button
          type="submit"
          className="border border-precision/50 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-precision hover:bg-precision/10"
        >
          Record disagreement
        </button>
      </form>
    </details>
  );
}
