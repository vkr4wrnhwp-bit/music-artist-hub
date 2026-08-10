"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { DevLabel, Dot, StatusChip, type Tone } from "@/components/ui";
import type { NextActionInfo, RunwayData, RunwayOperation } from "./panel-data";

/**
 * THE OPERATION RUNWAY
 *
 * The process plan, read left to right, in the order the machine will see it.
 *
 * WHAT THIS STRIP IS NOT
 * It is not a live job. `Operation` has no status column. `OperationState`
 * exists in the schema with zero write sites and zero readers. Nothing in
 * `src/` ever writes a `Job`, there is no machine connection, and the seeded
 * job is COMPLETE. So COMPLETE / ACTIVE / NEXT / PENDING cannot be shown here
 * without inventing the one fact a machinist would act on hardest.
 *
 * The honest version, and the one implemented: the strip is labelled a PLAN,
 * and one card stands out — on arrival it is the operation the plan STARTS at,
 * marked "Plan starts here", which is a property of the ordered sequence and
 * not a claim about execution; after that it is whatever the user selected.
 * That selection is real state — it drives `activeOperation` in the interaction
 * model and selects the feature the operation cuts, so the 3D view and the
 * feature panel follow the operation you are reading.
 *
 * What each card does show is real: sequence, type, tool, feature, whether the
 * deterministic CAM engine produced a toolpath for it, and how long that
 * toolpath takes. An operation the engine cannot plan says so.
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

  return (
    <footer
      className="shrink-0 bg-footer"
      style={{ borderTop: "1px solid var(--canvas-border-strong)" }}
      aria-label="Operation plan"
    >
      {/* Header — states what the strip is before anybody reads a card.
          It wraps rather than scrolls: the caveat used to sit inside a
          horizontal scroller with no scrollbar, so at phone width the operator
          saw cycle times and never saw the sentence saying none of it is
          live. A caveat you have to discover is not a caveat. */}
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 border-b border-line px-3 py-[5px]">
        <span className="instrument-label shrink-0 text-platinum-dim">Operation plan</span>
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
      </div>

      <div className="flex flex-col items-stretch lg:flex-row">
        <Sequence
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
/* The sequence                                                        */
/* ------------------------------------------------------------------ */

/**
 * A plan that runs off the edge has to look like a plan that runs off the
 * edge. The scroller carries no scrollbar by design (it is chrome, not
 * content), which previously meant nine operations read as four — the strip
 * appeared to end after op 04. The fade and the arrow are the affordance, and
 * the arrow really scrolls.
 */
function Sequence({
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
  const ref = useRef<HTMLDivElement>(null);
  const [more, setMore] = useState({ left: false, right: false });

  const measure = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    const max = el.scrollWidth - el.clientWidth;
    setMore({ left: el.scrollLeft > 2, right: max - el.scrollLeft > 2 });
  }, []);

  useEffect(() => {
    measure();
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [measure, total]);

  const nudge = (direction: 1 | -1) => {
    const el = ref.current;
    if (!el) return;
    el.scrollBy({ left: direction * Math.max(220, el.clientWidth * 0.7), behavior: "smooth" });
  };

  return (
    <div className="relative min-w-0 flex-1">
      <div
        ref={ref}
        onScroll={measure}
        className="no-scrollbar flex min-w-0 items-stretch gap-1 overflow-x-auto px-3 py-2"
      >
        {total === 0 ? (
          <div className="flex items-center border border-dashed border-line-strong px-4 py-3">
            <p className="text-[11.5px] text-muted">
              No operations are planned for this revision.{" "}
              <Link href={`/parts/${partId}/setups`} className="text-precision-dim hover:underline">
                Setup planning
              </Link>
            </p>
          </div>
        ) : (
          bySetup.map(({ setup, operations }) => (
            <div key={setup.id} className="flex shrink-0 items-stretch gap-1 pr-1.5">
              {/* 120px, and the setup name wraps rather than truncating at
                  "SETUP 1 — T…". A machinist cannot act on half a word. */}
              <div className="flex w-[120px] shrink-0 flex-col justify-center border-l-2 border-l-line-strong pl-2">
                <span className="instrument-label">Setup {String(setup.sequence).padStart(2, "0")}</span>
                <span className="mt-0.5 text-[11px] leading-tight text-platinum-dim" title={setup.name}>
                  {setup.name}
                </span>
                {setup.riskLabel && (
                  <span className="mt-1">
                    <StatusChip tone={RISK_TONE[setup.riskLevel ?? "UNKNOWN"] ?? "unknown"}>
                      {setup.riskLabel}
                    </StatusChip>
                  </span>
                )}
              </div>

              {operations.map((op, i) => (
                <div key={op.id} className="flex shrink-0 items-stretch">
                  {i > 0 && <span aria-hidden className="h-px w-2 self-center bg-line-strong" />}
                  <OperationCard
                    op={op}
                    selected={activeOperation === op.id}
                    chosenByUser={operationChosenByUser}
                    cutsSelection={selectedFeature != null && op.featureId === selectedFeature}
                    onSelect={() => onSelectOperation(activeOperation === op.id ? null : op)}
                  />
                </div>
              ))}
            </div>
          ))
        )}
      </div>

      {more.left && <EdgeFade side="left" onClick={() => nudge(-1)} />}
      {more.right && <EdgeFade side="right" onClick={() => nudge(1)} />}
    </div>
  );
}

function EdgeFade({ side, onClick }: { side: "left" | "right"; onClick: () => void }) {
  const isRight = side === "right";
  return (
    /* The gradient is inert so it cannot swallow a click on the card beneath
       it; only the 22px chevron is a target, and it really scrolls. */
    <div
      aria-hidden
      className={`pointer-events-none absolute inset-y-0 ${isRight ? "right-0" : "left-0"} flex w-10 items-center ${
        isRight ? "justify-end pr-0.5" : "justify-start pl-0.5"
      }`}
      style={{
        background: `linear-gradient(to ${isRight ? "right" : "left"}, transparent, var(--canvas-footer-bg) 70%)`,
      }}
    >
      <button
        type="button"
        onClick={onClick}
        aria-hidden={false}
        aria-label={isRight ? "Later operations" : "Earlier operations"}
        className="pointer-events-auto flex h-[22px] w-[22px] items-center justify-center border border-line-strong bg-card text-muted transition-colors hover:text-platinum"
      >
        <svg width="10" height="10" viewBox="0 0 12 12" aria-hidden="true">
          <path
            d={isRight ? "M4 1.5 L8.5 6 L4 10.5" : "M8 1.5 L3.5 6 L8 10.5"}
            fill="none"
            stroke="currentColor"
            strokeWidth="1.4"
          />
        </svg>
      </button>
    </div>
  );
}

function OperationCard({
  op,
  selected,
  chosenByUser,
  cutsSelection,
  onSelect,
}: {
  op: RunwayOperation;
  selected: boolean;
  chosenByUser: boolean;
  cutsSelection: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      title={op.error ?? (op.warnings.length > 0 ? op.warnings.join(" · ") : undefined)}
      className={`relative flex h-[94px] w-[130px] shrink-0 flex-col justify-between px-2 pb-1 pt-1.5 text-left transition-colors ${
        selected
          ? "bg-card shadow-[inset_0_0_0_1px_var(--c-blue),0_4px_14px_rgba(16,20,24,0.13)]"
          : /* A quiet card rather than white: the footer is meant to read as
               the region darker than the centre canvas, and near-white cards
               over it inverted that by sampled area. It also widens the gap
               between an unselected card and the selected one. */
            "border border-line bg-card-quiet hover:border-line-strong hover:bg-card"
      }`}
    >
      {selected && <span aria-hidden className="absolute inset-x-0 top-0 h-[2px] bg-precision" />}
      {!selected && cutsSelection && <span aria-hidden className="absolute inset-y-0 left-0 w-[2px] bg-precision/60" />}

      <div className="min-w-0">
        <div className="flex items-center justify-between gap-1">
          <span
            className={`font-mono text-[13px] leading-none tabular-nums ${selected ? "text-precision-dim" : "text-platinum-dim"}`}
          >
            {String(op.sequence).padStart(2, "0")}
          </span>
          {/* Selection is said by the blue rule, the blue sequence number and
              the marker on the bottom row — never by replacing the operation's
              own state, which is the part a machinist needs. */}
          {op.isPlaceholder ? (
            <DevLabel>No engine</DevLabel>
          ) : op.error ? (
            <span className="flex items-center gap-1">
              <Dot tone="risk" />
              <span className="text-[8.5px] font-semibold uppercase tracking-[0.1em] text-risk">No path</span>
            </span>
          ) : (
            <span className="truncate text-[8.5px] font-semibold uppercase tracking-[0.1em] text-muted">
              {op.type.replace(/_/g, " ").toLowerCase()}
            </span>
          )}
        </div>
        <p className={`mt-1 truncate text-[12px] leading-tight ${selected ? "text-platinum" : "text-platinum-dim"}`}>
          {op.label}
        </p>
        {/* Tool number is a machine value and keeps the mono chip. The feature
            label is a name and wraps — "1/4-20 MOUNTI…" is not readable, and a
            tool/feature line truncated mid-token is worse than a shorter card. */}
        <p className="mt-1 flex items-start gap-1">
          <span className="shrink-0 border border-line px-1 font-mono text-[9px] leading-[13px] text-muted tabular-nums">
            {op.toolNumber != null ? `T${op.toolNumber}` : "—"}
          </span>
          <span className="min-w-0 flex-1 break-words text-[9.5px] leading-[12px] text-muted line-clamp-2">
            {op.featureLabel ?? "no feature"}
          </span>
        </p>
      </div>

      <div className="flex items-baseline justify-between gap-1">
        <p className="truncate font-mono text-[9.5px] tabular-nums text-muted">
          {op.cycleMinutes != null
            ? `${op.cycleMinutes.toFixed(2)} min · ${op.moveCount ?? 0} moves`
            : op.isPlaceholder
              ? "interface only"
              : "no toolpath"}
        </p>
        {selected && (
          <span className="shrink-0 text-[8px] font-semibold uppercase tracking-[0.12em] text-precision-dim">
            {chosenByUser ? "Selected" : "Plan starts"}
          </span>
        )}
      </div>
    </button>
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
