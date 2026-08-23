import type { ReactNode } from "react";
import type { CalculationInput } from "@/lib/engines/cutting-force";

/**
 * SHOW YOUR WORK
 *
 * Any consequential number CANVAS calculates must be openable. Not a tooltip
 * saying "estimated" — the method, the inputs it ran on, the assumptions it
 * made, and the uncertainty band on the result.
 *
 * A machinist cannot disagree with a bare number. They can disagree with
 * "0.35 friction coefficient, dry serrated jaws" — and that disagreement is
 * worth more to CANVAS than the original figure was.
 *
 * Rendered with <details> so it works without client JavaScript.
 */

export function ShowCalculation({
  title,
  headline,
  unit,
  method,
  inputs,
  assumptions,
  uncertaintyPercent,
  confidence,
  missingInputs = [],
  cautions = [],
  developmentAnalysis = false,
  children,
}: {
  title: string;
  headline: string | null;
  unit?: string;
  method: string;
  inputs: CalculationInput[];
  assumptions: string[];
  uncertaintyPercent?: number | null;
  confidence?: string;
  /**
   * Inputs the engine was never given. These name the evidence that would
   * move the answer, so they belong in the SUMMARY, not behind the fold: a
   * headline reading "—" with the reason hidden one click away is the same
   * as not saying it.
   */
  missingInputs?: string[];
  cautions?: string[];
  /** Marks a model that has not been validated against physical testing. */
  developmentAnalysis?: boolean;
  children?: ReactNode;
}) {
  return (
    <details className="group border border-line bg-void">
      <summary className="flex cursor-pointer list-none flex-wrap items-baseline justify-between gap-2 px-3 py-2 hover:bg-raised">
        <span className="flex items-baseline gap-2.5">
          <span className="tech-label">{title}</span>
          <span className="font-mono text-[13px] text-platinum">
            {headline ?? "—"}
            {headline && unit ? <span className="text-muted"> {unit}</span> : null}
          </span>
          {uncertaintyPercent != null && (
            <span className="font-mono text-[11px] text-muted">±{uncertaintyPercent}%</span>
          )}
        </span>
        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-precision">
          <span className="group-open:hidden">Show calculation</span>
          <span className="hidden group-open:inline">Hide calculation</span>
        </span>
      </summary>

      {missingInputs.length > 0 && (
        <ul className="space-y-1 border-t border-line/60 px-3 py-2">
          {missingInputs.map((m) => (
            <li key={m} className="flex gap-2 text-[11.5px] leading-relaxed text-review">
              <span>—</span>
              <span>{m}</span>
            </li>
          ))}
        </ul>
      )}

      <div className="space-y-4 border-t border-line px-3 py-3">
        <div>
          <p className="tech-label mb-1">Method</p>
          <p className="font-mono text-[12px] text-platinum-dim">{method}</p>
          {confidence && (
            <p className="tech-label mt-1">
              Source calculated · confidence {confidence.toLowerCase()}
            </p>
          )}
        </div>

        {inputs.length > 0 && (
          <div>
            <p className="tech-label mb-1.5">Inputs</p>
            <dl className="grid gap-x-8 gap-y-0.5 sm:grid-cols-2">
              {inputs.map((i) => (
                <div key={i.label} className="flex items-baseline justify-between gap-3 border-b border-line/50 py-1">
                  <dt className="text-[12px] text-muted">{i.label}</dt>
                  <dd className="font-mono text-[12px] text-platinum">{i.value}</dd>
                </div>
              ))}
            </dl>
          </div>
        )}

        {children}

        {assumptions.length > 0 && (
          <div>
            <p className="tech-label mb-1.5">Assumptions</p>
            <ul className="space-y-1">
              {assumptions.map((a) => (
                <li key={a} className="flex gap-2 text-[12px] leading-relaxed text-muted">
                  <span className="text-precision">—</span>
                  <span>{a}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {cautions.length > 0 && (
          <div>
            <p className="tech-label mb-1.5 text-review">Where this model is weak here</p>
            <ul className="space-y-1">
              {cautions.map((c) => (
                <li key={c} className="text-[12px] leading-relaxed text-review">
                  {c}
                </li>
              ))}
            </ul>
          </div>
        )}

        {developmentAnalysis && (
          <p className="border border-review/40 px-2.5 py-2 text-[11.5px] leading-relaxed text-review">
            <span className="font-mono uppercase tracking-[0.14em]">Development analysis</span> — this model has not
            been validated against physical testing. It is a basis for comparing setups and for catching the ones that
            are obviously wrong. It is not a certification that the part will stay in the fixture.
          </p>
        )}
      </div>
    </details>
  );
}

/** Renders the inputs a model wanted and did not get. */
export function MissingInputs({ items, title = "Not calculable" }: { items: string[]; title?: string }) {
  if (items.length === 0) return null;
  return (
    <div className="border border-line border-l-2 border-l-unknown bg-raised px-3 py-2.5">
      <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-platinum">{title}</p>
      <ul className="mt-1.5 space-y-1">
        {items.map((m) => (
          <li key={m} className="text-[12px] leading-relaxed text-muted">
            {m}
          </li>
        ))}
      </ul>
    </div>
  );
}
