import Link from "next/link";
import type { ReadinessReport } from "@/lib/engines/readiness";
import type { NextAction } from "@/lib/engines/next-action";

/**
 * PART STATUS, EVERYWHERE
 *
 * Readiness stops being something you go to a page to look up. The status
 * travels with the part, on every screen, and it is always the worst
 * unresolved required gate — never an average, never a percentage, never a
 * count of how many gates passed.
 *
 * "Nine of eleven gates pass" is the kind of sentence that gets a part run.
 * The two that do not pass are the whole story.
 */

/**
 * The persistent status summary. Worst unresolved required gate, plus how many
 * things are in each state — never a score, never a percentage, and never
 * "9 of 11 passed", because the two that did not pass are the whole story.
 */
export function PartStatusSummary({ readiness }: { readiness: ReadinessReport }) {
  const blocking = readiness.gates.filter(
    (g) => g.blocking && (g.status === "FAIL" || g.status === "MISSING"),
  ).length;
  const review = readiness.gates.filter((g) => g.status === "REVIEW").length;

  const label =
    readiness.overall === "READY_TO_RUN"
      ? "Ready to run"
      : readiness.overall === "REVIEW_REQUIRED"
        ? "Review required"
        : "Not ready";

  const dot =
    readiness.overall === "READY_TO_RUN"
      ? "bg-pass"
      : readiness.overall === "REVIEW_REQUIRED"
        ? "bg-review"
        : "bg-risk";

  return (
    <span className="flex shrink-0 flex-col items-center leading-none">
      <span className="instrument-label mb-1 hidden sm:block">Part status</span>
      <span className="flex items-center gap-2 whitespace-nowrap">
        <span aria-hidden className={`h-2 w-2 shrink-0 rounded-full ${dot}`} />
        <span className="text-[12px] font-semibold uppercase tracking-[0.1em] text-platinum sm:text-[13px]">
          {label}
        </span>
      </span>
      {(blocking > 0 || review > 0) && (
        <span className="instrument-label mt-1 hidden whitespace-nowrap sm:block">
          {blocking > 0 && `${blocking} blocking`}
          {blocking > 0 && review > 0 && " · "}
          {review > 0 && `${review} review`}
        </span>
      )}
    </span>
  );
}

export function PartStatusChip({ readiness }: { readiness: ReadinessReport }) {
  const label =
    readiness.overall === "READY_TO_RUN"
      ? "Ready to run"
      : readiness.overall === "REVIEW_REQUIRED"
        ? "Review required"
        : "Not ready";

  const tone =
    readiness.overall === "READY_TO_RUN"
      ? "border-pass/50 text-pass"
      : readiness.overall === "REVIEW_REQUIRED"
        ? "border-review/50 text-review"
        : "border-risk/50 text-risk";

  return (
    <span
      className={`border ${tone} px-2 py-[3px] text-[10px] font-semibold uppercase tracking-[0.14em] whitespace-nowrap`}
    >
      {label}
    </span>
  );
}

/**
 * The single most useful unresolved thing, stated as an instruction.
 *
 * Deliberately one primary action rather than a list: a list of twelve things
 * to fix is the problem this exists to solve, not the solution to it. The
 * next two are shown underneath, smaller, so the sequence is visible without
 * competing with the first.
 */
export function NextActionPanel({ actions }: { actions: NextAction[] }) {
  if (actions.length === 0) return null;
  const [primary, ...rest] = actions;

  const border =
    primary.severity === "BLOCKING"
      ? "border-l-risk"
      : primary.severity === "REVIEW"
        ? "border-l-review"
        : "border-l-pass";

  return (
    <section className={`border border-line ${border} border-l-2 bg-surface`}>
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 px-4 py-2.5">
        <span className="instrument-label shrink-0">
          {primary.severity === "BLOCKING" ? "Next" : primary.severity === "REVIEW" ? "Next — review" : "Next"}
        </span>
        <span className="min-w-0 flex-1 text-[14px] leading-snug text-platinum">{primary.action}</span>
        {primary.href && (
          <Link
            href={primary.href}
            className="shrink-0 border border-precision/50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-precision-dim hover:bg-precision/10"
          >
            {primary.linkLabel}
          </Link>
        )}
      </div>

      {/* The evidence and the queue behind it, one disclosure away. The
          instruction is what matters on arrival; the reasoning matters only if
          it is questioned. */}
      <details className="group border-t border-line">
        <summary className="cursor-pointer list-none px-4 py-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted hover:text-platinum">
          <span className="group-open:hidden">Why{rest.length > 0 ? ` · ${rest.length} more` : ""}</span>
          <span className="hidden group-open:inline">Hide</span>
        </summary>
        <div className="space-y-2 px-4 pb-3">
          <p className="max-w-3xl text-[12.5px] leading-relaxed text-muted">{primary.reason}</p>
          {rest.length > 0 && (
            <ol className="space-y-1">
              {rest.map((a, i) => (
                <li key={`${a.gateId}-${i}`} className="flex gap-2.5 text-[12px] leading-relaxed">
                  <span className="font-mono text-[11px] text-muted">{String(i + 2).padStart(2, "0")}</span>
                  {a.href ? (
                    <Link href={a.href} className="text-platinum-dim hover:text-platinum">
                      {a.action}
                    </Link>
                  ) : (
                    <span className="text-platinum-dim">{a.action}</span>
                  )}
                </li>
              ))}
            </ol>
          )}
        </div>
      </details>
    </section>
  );
}
