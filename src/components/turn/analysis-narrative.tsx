import { Dot } from "@/components/ui";
import type { TurnAnalysis } from "@/lib/manufacturing/turn/analysis";

/**
 * A TurnAnalysis, rendered whole.
 *
 * Every turning analysis carries four things a machinist needs together: the
 * verdict's reasoning, what the model could not be told, what it would
 * change, and what it assumed in order to answer at all. The three hold
 * panels each rendered a different subset of them — grip showed missing
 * inputs but not recommendations, stickout and part-off showed
 * recommendations but not missing inputs, and none of them showed
 * assumptions. So "Cutoff insert width not recorded" and "Stickout from the
 * jaw face not recorded" were written by the engine and never reached the
 * screen, and a DEVELOPMENT verdict was read without the assumptions that
 * qualify it.
 *
 * One component, so a field cannot be dropped from one panel and not
 * another. `detail` is rendered by the caller, next to the verdict chip.
 */
export function TurnAnalysisNarrative({ analysis }: { analysis: TurnAnalysis }) {
  const { missingInputs, recommendations, assumptions } = analysis;
  if (missingInputs.length === 0 && recommendations.length === 0 && assumptions.length === 0) return null;
  return (
    <>
      {missingInputs.length > 0 && (
        <ul className="mt-1.5 space-y-1">
          {missingInputs.map((m) => (
            <li key={m} className="flex gap-2 text-[11.5px] text-review">
              <Dot tone="review" /> {m}
            </li>
          ))}
        </ul>
      )}
      {recommendations.length > 0 && <p className="mt-1 text-[11.5px] text-muted">{recommendations.join(" · ")}</p>}
      {assumptions.length > 0 && (
        <p className="mt-1.5 border-t border-line/60 pt-1.5 text-[10.5px] leading-relaxed text-muted">
          <span className="tech-label mr-1.5">Assumed</span>
          {assumptions.join(" · ")}
        </p>
      )}
    </>
  );
}
