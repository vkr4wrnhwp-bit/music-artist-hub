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
      className={`border ${tone} px-2 py-[3px] font-mono text-[10px] uppercase tracking-[0.14em] whitespace-nowrap`}
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
      <div className="px-4 py-3">
        <p className="tech-label">
          {primary.severity === "BLOCKING"
            ? "Next required action"
            : primary.severity === "REVIEW"
              ? "Next action — review"
              : "Next action"}
        </p>
        <p className="mt-1.5 text-[15px] leading-snug font-light text-white">{primary.action}</p>
        <p className="mt-1.5 max-w-2xl text-[12.5px] leading-relaxed text-muted">{primary.reason}</p>
        {primary.href && (
          <Link
            href={primary.href}
            className="mt-2.5 inline-block border border-precision/50 px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.14em] text-precision hover:bg-precision/10"
          >
            {primary.linkLabel}
          </Link>
        )}
      </div>

      {rest.length > 0 && (
        <div className="border-t border-line px-4 py-2.5">
          <p className="tech-label mb-1.5">Then</p>
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
        </div>
      )}
    </section>
  );
}
