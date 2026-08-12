"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { DevLabel, Dot, StatusChip, type Tone } from "@/components/ui";
import type { NextActionInfo, RunwayData, RunwayOperation } from "./panel-data";

/**
 * THE OPERATION TIMELINE
 *
 * The process plan as table rows, in the order the machine will see it, with
 * a per-setup risk rail on the left — the refactor-spec layout. Rows beat the
 * old horizontal cards because nine operations read as nine, not as four plus
 * a hidden scroll.
 *
 * WHAT THIS TABLE IS NOT
 * It is not a live job. `Operation` has no status column. `OperationState`
 * exists in the schema with zero write sites and zero readers. Nothing in
 * `src/` ever writes a `Job`, there is no machine connection, and the seeded
 * job is COMPLETE. So COMPLETE / ACTIVE / NEXT / PENDING cannot be shown here
 * without inventing the one fact a machinist would act on hardest. The only
 * state column is SELECTED — which is real UI state — and "PLAN STARTS",
 * which is a property of the ordered sequence, not a claim about execution.
 *
 * Selecting a row drives `activeOperation` in the interaction model and
 * selects the feature the operation cuts, so the 3D view and the feature
 * panel follow the operation you are reading. Setup risk comes verbatim from
 * `workholding.ts` RiskLevel — never restyled ad hoc.
 */

const RISK_TONE: Record<string, Tone> = {
  SAFE: "pass",
  LIKELY_SAFE: "pass",
  REVIEW: "review",
  HIGH_RISK: "risk",
  UNKNOWN: "unknown",
};

export function OperationRunway({
  partId,
  data,
  nextActions,
  activeOperation,
  operationChosenByUser,
  selectedFeature,
  onSelectOperation,
}: {
  partId: string;
  data: RunwayData;
  /** The whole ordered queue, not just its head. */
  nextActions: NextActionInfo[];
  activeOperation: string | null;
  /** False while the highlighted card is the plan's own first operation. */
  operationChosenByUser: boolean;
  selectedFeature: string | null;
  onSelectOperation: (op: RunwayOperation | null) => void;
}) {
  const bySetup = data.setups.map((s) => ({
    setup: s,
    operations: data.operations.filter((o) => o.setupId === s.id),
  }));

  // Collapsed state survives reload per browser — pure layout preference,
  // nothing engineering-grade about it. Focus Workspace minimizes it too.
  const [collapsed, setCollapsed] = useState(false);
  useEffect(() => {
    try {
      const stored = window.localStorage.getItem("canvas.timelineCollapsed");
      // Laptop widths start minimized unless the user has chosen otherwise.
      setCollapsed(stored === null ? window.innerWidth < 1440 : stored === "1");
    } catch {
      /* fine */
    }
    const onFocus = (e: Event) => setCollapsed(Boolean((e as CustomEvent).detail));
    window.addEventListener("canvas:timeline-minimize", onFocus);
    return () => window.removeEventListener("canvas:timeline-minimize", onFocus);
  }, []);
  const toggle = () => {
    setCollapsed((c) => {
      try {
        window.localStorage.setItem("canvas.timelineCollapsed", c ? "0" : "1");
      } catch {
        /* fine */
      }
      return !c;
    });
  };

  return (
    <footer
      className="shrink-0 bg-footer"
      style={{ borderTop: "1px solid var(--canvas-border-strong)" }}
      aria-label="Operation plan"
    >
      {/* Header — states what the table is before anybody reads a row.
          It wraps rather than scrolls: a caveat you have to discover is not a
          caveat. */}
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 border-b border-line px-3 py-[5px]">
        <button
          type="button"
          onClick={toggle}
          aria-expanded={!collapsed}
          className="instrument-label shrink-0 text-platinum-dim transition-colors hover:text-platinum"
        >
          Operation plan {collapsed ? "▸" : "▾"}
        </button>
        <span className="font-mono text-[10px] tracking-[0.06em] text-muted tabular-nums">
          {data.operations.length} operations · {data.setups.length} setups ·{" "}
          {data.cycleMinutes > 0 ? `${data.cycleMinutes.toFixed(2)} min cut time` : "no cycle time"}
          {data.placeholderCount > 0 && ` · ${data.placeholderCount} without an engine`}
        </span>
        <span
          className="basis-full text-[11px] text-muted lg:basis-auto"
          title="Operation has no status column, OperationState has no write sites and there is no machine connection. Nothing here is running, complete or pending. The model shows the finished part, not the state after any operation."
        >
          Planned sequence — CANVAS does not track execution state.
        </span>
        {/* Minimized summary: the selected operation stays readable while
            the table is away. A selection, not an execution state. */}
        {collapsed && activeOperation && (() => {
          const op = data.operations.find((o) => o.id === activeOperation);
          if (!op) return null;
          const next = data.operations.find((o) => o.setupId === op.setupId && o.sequence === op.sequence + 1);
          return (
            <span className="font-mono text-[10.5px] tracking-[0.04em] text-platinum-dim tabular-nums">
              Selected: op {String(op.sequence).padStart(2, "0")} · {op.label}
              {op.toolNumber != null && ` · T${op.toolNumber}`}
              {op.cycleMinutes != null && ` · ${op.cycleMinutes.toFixed(2)} min`}
              {next && ` · then op ${String(next.sequence).padStart(2, "0")}`}
            </span>
          );
        })()}
      </div>

      <div className={`${collapsed ? "hidden" : "flex"} flex-col items-stretch lg:flex-row`}>
        <Timeline
          partId={partId}
          bySetup={bySetup}
          total={data.operations.length}
          activeOperation={activeOperation}
          operationChosenByUser={operationChosenByUser}
          selectedFeature={selectedFeature}
          onSelectOperation={onSelectOperation}
        />

        {/* Standing summaries — the four things you check before Cycle Start.
            Below `lg` only the next step survives; three truncated tiles on a
            phone are three things nobody can read. */}
        <div className="flex w-full shrink-0 flex-col gap-1.5 border-t border-line px-3 py-1.5 lg:w-[340px] lg:border-t-0 lg:border-l lg:border-line-strong xl:w-[452px]">
          {/* The tiles need room to say a whole word. At `lg` they truncate to
              "WOR…" and "4 planned · 0 re…", which is three unreadable things
              rather than three checks, so they wait for `xl`. */}
          <div className="hidden grid-cols-3 gap-1 xl:grid">
            <Tile
              label="Workholding"
              value={data.workholding.worstLabel ?? "not assessed"}
              tone={RISK_TONE[data.workholding.worstLevel ?? "UNKNOWN"] ?? "unknown"}
              detail={data.workholding.device ?? "no device assigned"}
              href={`/parts/${partId}/soft-jaws`}
              /* holding-margin.ts carries a non-optional developmentAnalysis
                 flag because the model has never been checked against a
                 pull-off test. Principle 12 requires that classification in
                 the UI, not only in a tooltip — this is a prominent verdict on
                 a new surface, so it carries the chip. */
              dev={data.workholding.developmentAnalysis}
              note={
                data.workholding.developmentAnalysis
                  ? "Development analysis — the holding model is not validated against physical testing."
                  : undefined
              }
            />
            <Tile
              label="Inspection"
              value={
                data.inspection.hasPlan
                  ? `${data.inspection.itemCount} planned · ${data.inspection.resultCount} results`
                  : "no plan"
              }
              tone={data.inspection.hasPlan ? "neutral" : "review"}
              detail={
                data.inspection.measurementCount > 0
                  ? `${data.inspection.measurementCount} readings · ${data.inspection.pendingResolutionCount} unresolved`
                  : "no readings recorded"
              }
              href={`/parts/${partId}/inspection`}
              note="Counts of records. Inspection results have no write path in CANVAS yet, so that figure stays at zero."
            />
            <Tile
              label="Material"
              value={data.material.name ?? "not defined"}
              tone="neutral"
              detail={
                data.material.stockSize
                  ? `${data.material.condition ?? "condition not stated"} · ${data.material.stockSize}`
                  : (data.material.condition ?? "condition not stated")
              }
              note="Material and temper as recorded on the part. CANVAS stores no heat number, lot number or mill certificate."
            />
          </div>

          <NextStep actions={nextActions} />
        </div>
      </div>
    </footer>
  );
}

/* ------------------------------------------------------------------ */
/* The timeline                                                        */
/* ------------------------------------------------------------------ */

/**
 * Table rows grouped by setup, with the setup's risk rail on the left. All
 * rows are visible at once (the body scrolls vertically past ~5 rows) — the
 * old horizontal scroller hid operations past the fold.
 */
function Timeline({
  partId,
  bySetup,
  total,
  activeOperation,
  operationChosenByUser,
  selectedFeature,
  onSelectOperation,
}: {
  partId: string;
  bySetup: { setup: RunwayData["setups"][number]; operations: RunwayOperation[] }[];
  total: number;
  activeOperation: string | null;
  operationChosenByUser: boolean;
  selectedFeature: string | null;
  onSelectOperation: (op: RunwayOperation | null) => void;
}) {
  if (total === 0) {
    return (
      <div className="flex min-w-0 flex-1 items-center px-3 py-3">
        <p className="text-[11.5px] text-muted">
          No operations are planned for this revision.{" "}
          <Link href={`/parts/${partId}/setups`} className="text-precision-dim hover:underline">
            Setup planning
          </Link>
        </p>
      </div>
    );
  }

  return (
    <div className="max-h-[228px] min-w-0 flex-1 overflow-y-auto overflow-x-auto">
      <table className="w-full min-w-[560px] border-collapse">
        <thead className="sticky top-0 z-10 bg-footer">
          <tr className="border-b border-line">
            {["Setup", "Op", "Type", "Description", "Tool", "Cycle", "Moves", ""].map((h, i) => (
              <th
                key={i}
                className={`instrument-label whitespace-nowrap px-2.5 py-1.5 text-left font-normal ${i === 3 ? "w-full" : ""}`}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {bySetup.map(({ setup, operations }) =>
            operations.map((op, i) => {
              const selected = activeOperation === op.id;
              const cutsSelection = selectedFeature != null && op.featureId === selectedFeature;
              return (
                <tr
                  key={op.id}
                  onClick={() => onSelectOperation(selected ? null : op)}
                  aria-selected={selected}
                  title={op.error ?? (op.warnings.length > 0 ? op.warnings.join(" · ") : undefined)}
                  className={`cursor-pointer border-b border-line/60 transition-colors ${
                    selected
                      ? "bg-card shadow-[inset_2px_0_0_var(--c-blue)]"
                      : cutsSelection
                        ? "bg-card-quiet shadow-[inset_2px_0_0_color-mix(in_srgb,var(--c-blue)_55%,transparent)]"
                        : "hover:bg-card-quiet"
                  }`}
                >
                  {/* The setup rail: one cell spanning the setup's rows, risk
                      verbatim from the workholding engine. */}
                  {i === 0 ? (
                    <td
                      rowSpan={operations.length}
                      className="w-[128px] min-w-[128px] border-r border-line-strong px-2.5 py-1.5 align-top"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <span className="instrument-label block">Setup {String(setup.sequence).padStart(2, "0")}</span>
                      <span className="mt-0.5 block text-[10.5px] leading-tight text-platinum-dim">{setup.name}</span>
                      {setup.riskLabel && (
                        <span className="mt-1 block">
                          <StatusChip tone={RISK_TONE[setup.riskLevel ?? "UNKNOWN"] ?? "unknown"}>
                            {setup.riskLabel}
                          </StatusChip>
                        </span>
                      )}
                    </td>
                  ) : null}
                  <td className={`whitespace-nowrap px-2.5 py-1.5 font-mono text-[12px] tabular-nums ${selected ? "text-precision-dim" : "text-platinum-dim"}`}>
                    {String(op.sequence).padStart(2, "0")}
                  </td>
                  <td className="whitespace-nowrap px-2.5 py-1.5">
                    {op.isPlaceholder ? (
                      <DevLabel>No engine</DevLabel>
                    ) : op.error ? (
                      <span className="flex items-center gap-1">
                        <Dot tone="risk" />
                        <span className="text-[8.5px] font-semibold uppercase tracking-[0.1em] text-risk">No path</span>
                      </span>
                    ) : (
                      <span className="text-[9px] font-semibold uppercase tracking-[0.1em] text-muted">
                        {op.type.replace(/_/g, " ").toLowerCase()}
                      </span>
                    )}
                  </td>
                  <td className="max-w-0 px-2.5 py-1.5">
                    <span className={`block truncate text-[12px] ${selected ? "text-platinum" : "text-platinum-dim"}`}>
                      {op.label}
                    </span>
                    <span className="block truncate text-[9.5px] text-muted">{op.featureLabel ?? "no feature"}</span>
                  </td>
                  <td className="whitespace-nowrap px-2.5 py-1.5 font-mono text-[11px] text-muted tabular-nums">
                    {op.toolNumber != null ? `T${op.toolNumber}` : "—"}
                  </td>
                  <td className="whitespace-nowrap px-2.5 py-1.5 font-mono text-[11px] text-muted tabular-nums">
                    {op.cycleMinutes != null ? `${op.cycleMinutes.toFixed(2)} min` : op.isPlaceholder ? "—" : "no path"}
                  </td>
                  <td className="whitespace-nowrap px-2.5 py-1.5 font-mono text-[11px] text-muted tabular-nums">
                    {op.moveCount ?? "—"}
                  </td>
                  <td className="whitespace-nowrap px-2.5 py-1.5 text-right">
                    {selected && (
                      <span className="text-[8.5px] font-semibold uppercase tracking-[0.12em] text-precision-dim">
                        {operationChosenByUser ? "Selected" : "Plan starts"}
                      </span>
                    )}
                  </td>
                </tr>
              );
            }),
          )}
        </tbody>
      </table>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Next required action                                                */
/* ------------------------------------------------------------------ */

/**
 * The single most useful unresolved thing, stated as an instruction.
 *
 * It used to be a one-line tile that truncated the action by 65px and the
 * reason by 444px, in the bottom-right corner, at 10.5px — below a gated NC
 * route rendered as the loudest control on the screen. The instruction now
 * outweighs the operation cards beside it, the reason is readable without a
 * pointer, and the rest of the ordered queue is one disclosure away rather
 * than discarded.
 */
function NextStep({ actions }: { actions: NextActionInfo[] }) {
  if (actions.length === 0) {
    return (
      <div className="border border-line border-l-2 border-l-pass bg-card px-3 py-2">
        <span className="instrument-label">Next required action</span>
        <p className="mt-1 text-[12.5px] text-muted">No outstanding action from the readiness gates.</p>
      </div>
    );
  }

  const [primary, ...rest] = actions;
  const rule =
    primary.severity === "BLOCKING"
      ? "border-l-risk"
      : primary.severity === "REVIEW"
        ? "border-l-review"
        : "border-l-pass";

  return (
    <div className={`min-w-0 border border-line border-l-2 ${rule} bg-card px-2.5 py-1.5`}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="instrument-label shrink-0">Next required action</span>
        <span
          className={`shrink-0 text-[9px] font-semibold uppercase tracking-[0.12em] ${
            primary.severity === "BLOCKING"
              ? "text-risk"
              : primary.severity === "REVIEW"
                ? "text-review"
                : "text-pass"
          }`}
        >
          {primary.severity.toLowerCase()}
        </span>
      </div>

      <p className="mt-1 text-[14px] font-semibold leading-snug text-platinum">{primary.action}</p>
      <p className="mt-1 text-[11.5px] leading-snug text-muted line-clamp-2">{primary.reason}</p>

      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
        {primary.href && (
          <Link
            href={primary.href}
            className="shrink-0 border border-precision/50 px-2 py-[2px] text-[9.5px] font-semibold uppercase tracking-[0.12em] text-precision-dim transition-colors hover:bg-precision/10"
          >
            {primary.linkLabel ?? "Open"}
          </Link>
        )}
        <details className="group min-w-0">
          <summary className="instrument-label cursor-pointer list-none hover:text-platinum">
            <span className="group-open:hidden">Why{rest.length > 0 ? ` · ${rest.length} more` : ""}</span>
            <span className="hidden group-open:inline">Hide</span>
          </summary>
          <div className="mt-1.5 space-y-1.5">
            <p className="text-[11.5px] leading-relaxed text-muted">{primary.reason}</p>
            {rest.length > 0 && (
              <ol className="space-y-0.5">
                {rest.map((a, i) => (
                  <li key={`${a.action}-${i}`} className="flex gap-2 text-[11.5px] leading-snug">
                    <span className="font-mono text-[10px] text-muted tabular-nums">
                      {String(i + 2).padStart(2, "0")}
                    </span>
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
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Tiles                                                               */
/* ------------------------------------------------------------------ */

function Tile({
  label,
  value,
  detail,
  tone,
  href,
  note,
  dev,
}: {
  label: string;
  value: string;
  detail: string;
  tone: Tone;
  href?: string;
  note?: string;
  /** Render the DEVELOPMENT classification on the tile, not only in a tooltip. */
  dev?: boolean;
}) {
  const body: ReactNode = (
    <>
      <div className="flex items-center gap-1.5">
        <Dot tone={tone} />
        <span className="instrument-label truncate">{label}</span>
        {dev && <DevLabel>Dev</DevLabel>}
      </div>
      <p className="mt-0.5 truncate text-[11px] font-medium text-platinum" title={value}>
        {value}
      </p>
      <p className="truncate text-[10.5px] text-muted" title={note ? `${detail} — ${note}` : detail}>
        {detail}
      </p>
    </>
  );

  const cls = "min-w-0 border border-line bg-card px-2 py-1 block leading-tight";
  return href ? (
    <Link href={href} className={`${cls} transition-colors hover:border-line-strong`}>
      {body}
    </Link>
  ) : (
    <div className={cls}>{body}</div>
  );
}
