import Link from "next/link";
import type { ReactNode } from "react";
import type { Source, Confidence, Provenanced } from "@/lib/provenance";
import { SOURCE_LABEL, provenanceDetail } from "@/lib/provenance";

/**
 * The CANVAS component vocabulary.
 *
 * Compact controls, minimal borders, generous negative space, technical
 * labels. No oversized rounded cards, no gradients, no illustration, no emoji.
 * Blue appears only for active state, datum, measurement and confirmation.
 */

export function Panel({
  title,
  meta,
  actions,
  children,
  className = "",
  dense = false,
}: {
  title?: string;
  meta?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  dense?: boolean;
}) {
  return (
    <section className={`border border-line bg-surface ${className}`}>
      {(title || actions) && (
        <header className="d-panel-header flex items-center justify-between gap-4 border-b border-line px-4 py-2.5">
          <div className="flex items-baseline gap-3">
            {title && <h2 className="tech-label text-platinum-dim">{title}</h2>}
            {meta}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={dense ? "" : "d-panel-body p-4"}>{children}</div>
    </section>
  );
}

export function SectionHeading({ children, sub }: { children: ReactNode; sub?: string }) {
  return (
    <div className="mb-5">
      <h1 className="text-[22px] font-light tracking-[0.06em] text-white">{children}</h1>
      {sub && <p className="mt-1.5 max-w-2xl text-[13px] leading-relaxed text-muted">{sub}</p>}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Status                                                              */
/* ------------------------------------------------------------------ */

export type Tone = "pass" | "review" | "risk" | "unknown" | "precision" | "neutral";

const TONE_CLASS: Record<Tone, string> = {
  pass: "border-pass/40 text-pass",
  review: "border-review/40 text-review",
  risk: "border-risk/50 text-risk",
  unknown: "border-unknown/40 text-unknown",
  precision: "border-precision/50 text-precision",
  neutral: "border-line-strong text-platinum-dim",
};

/**
 * A state, said in words. Not monospace: "Likely safe" and "High risk" are
 * prose, and monospace here was part of what made half the workspace read as
 * machine output when only the dimensions are.
 */
export function StatusChip({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={`instrument-label inline-flex items-center gap-1.5 border px-1.5 py-[2px] ${TONE_CLASS[tone]}`}
    >
      {children}
    </span>
  );
}

export function Dot({ tone = "neutral" }: { tone?: Tone }) {
  const bg: Record<Tone, string> = {
    pass: "bg-pass",
    review: "bg-review",
    risk: "bg-risk",
    unknown: "bg-unknown",
    precision: "bg-precision",
    neutral: "bg-line-strong",
  };
  return <span className={`inline-block h-1.5 w-1.5 shrink-0 ${bg[tone]}`} />;
}

/* ------------------------------------------------------------------ */
/* Provenance — the visual expression of the safety model              */
/* ------------------------------------------------------------------ */

const SOURCE_TONE: Record<Source, Tone> = {
  USER: "pass",
  MEASURED: "pass",
  MANUFACTURER: "pass",
  CALCULATED: "precision",
  SIMULATION: "precision",
  AI_INFERENCE: "review",
  STANDARD: "precision",
  DEFAULT: "unknown",
};

/**
 * The badge, and what is behind it.
 *
 * It was a `<span>` whose `title=` repeated what the badge already said in
 * text. Two fields the engines fill were rendered nowhere: `note` — the
 * reason, "Recognised from the description", "6203 outer diameter per ISO
 * 15" — and `score`, the model's own confidence. provenance.ts documented
 * note as "shown in the provenance popover" and there was no popover.
 *
 * A tooltip was the wrong container anyway. LimitsDisclosure two hundred
 * lines below states the rule this violated: a limit that changes what an
 * operator would do is never only in a tooltip. Whether the material a whole
 * plan rests on can satisfy a required gate is exactly such a limit.
 *
 * READ-ONLY, and it must stay that way. A "confirm this value" control here
 * would let a click inside a disclosure promote an AI inference to
 * engineering grade, which is the precise thing principle 2 forbids.
 */
export function ProvenanceBadge({ field, compact = false }: { field: Provenanced<unknown>; compact?: boolean }) {
  const { source, confidence, confirmedByUser: confirmed } = field;
  const label = compact ? SOURCE_LABEL[source].split(" ")[0] : SOURCE_LABEL[source];
  const rows = provenanceDetail(field);
  return (
    <details className="group/prov inline-block min-w-0 align-baseline">
      <summary
        className={`inline-flex cursor-pointer list-none items-center gap-1 border px-1 py-[1px] font-mono text-[9px] uppercase tracking-[0.12em] ${TONE_CLASS[SOURCE_TONE[source]]}`}
        aria-label={`Provenance: ${SOURCE_LABEL[source]}`}
      >
        {label}
        {confirmed && <span className="text-precision">✓</span>}
      </summary>
      <div className="mt-1.5 min-w-[220px] border border-line-strong bg-card px-2.5 py-2">
        <dl className="space-y-0.5">
          {rows.map((r) => (
            <div key={r.label} className="flex items-baseline justify-between gap-3">
              <dt className="tech-label shrink-0">{r.label}</dt>
              <dd
                className={`min-w-0 text-right font-mono text-[11px] break-words ${
                  r.value === null ? "text-muted" : "text-platinum-dim"
                }`}
              >
                {r.value ?? "not recorded"}
              </dd>
            </div>
          ))}
        </dl>
        {/* Why several rows are empty for this class of value, rather than
            leaving a machinist to read a half-filled panel as a system that
            HAD the chain of custody and lost it. */}
        <p className="mt-2 border-t border-line pt-1.5 text-[10px] leading-snug text-muted">
          Instrument and uncertainty are recorded against a measurement, not against a stated value. Shop knowledge is
          scoped to a machine, tool and material, so it is not joined to a value here.
        </p>
      </div>
    </details>
  );
}

/** A labelled value with its provenance attached. The core readout of CANVAS. */
export function ValueRow({
  label,
  field,
  render,
  unit,
}: {
  label: string;
  field: Provenanced<unknown>;
  render?: (v: unknown) => string;
  unit?: string;
}) {
  const shown =
    field.value === null || field.value === undefined
      ? null
      : render
        ? render(field.value)
        : typeof field.value === "object"
          ? JSON.stringify(field.value)
          : String(field.value);

  return (
    <div className="d-row flex items-baseline justify-between gap-4 border-b border-line/60 py-2 last:border-0">
      <span className="tech-label shrink-0">{label}</span>
      {/* A div, not a span: the badge is a <details>, which is flow content
          and invalid inside a span. The row is already flex, so nothing about
          the layout changes. */}
      <div className="flex min-w-0 items-baseline gap-2">
        {shown === null ? (
          <span className="font-mono text-[12px] text-unknown">— not defined</span>
        ) : (
          <span className="font-mono text-[12px] break-words text-platinum">
            {shown}
            {unit && <span className="ml-1 text-muted">{unit}</span>}
          </span>
        )}
        <ProvenanceBadge field={field} compact />
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Data grid                                                           */
/* ------------------------------------------------------------------ */

export function DataRow({ label, value, tone }: { label: string; value: ReactNode; tone?: Tone }) {
  return (
    <div className="d-row flex items-baseline justify-between gap-4 border-b border-line/60 py-1.5 last:border-0">
      <span className="tech-label">{label}</span>
      <span className={`font-mono text-[12px] ${tone === "risk" ? "text-risk" : tone === "review" ? "text-review" : "text-platinum"}`}>
        {value}
      </span>
    </div>
  );
}

export function Table({ head, children }: { head: string[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left">
        <thead>
          <tr className="border-b border-line">
            {head.map((h) => (
              <th key={h} className="d-td tech-label px-3 py-2 font-normal whitespace-nowrap">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="font-mono text-[12px] text-platinum">{children}</tbody>
      </table>
    </div>
  );
}

export function Td({ children, className = "", muted }: { children: ReactNode; className?: string; muted?: boolean }) {
  return <td className={`d-td border-b border-line/50 px-3 py-2 ${muted ? "text-muted" : ""} ${className}`}>{children}</td>;
}

/* ------------------------------------------------------------------ */
/* Controls                                                            */
/* ------------------------------------------------------------------ */

export function Button({
  children,
  variant = "default",
  size = "md",
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "default" | "primary" | "ghost" | "danger"; size?: "sm" | "md" }) {
  return (
    <button className={`${buttonClass(variant, size)} ${className}`} {...props}>
      {children}
    </button>
  );
}

export function LinkButton({
  href,
  children,
  variant = "default",
  size = "md",
  className = "",
}: {
  href: string;
  children: ReactNode;
  variant?: "default" | "primary" | "ghost" | "danger";
  size?: "sm" | "md";
  className?: string;
}) {
  return (
    <Link href={href} className={`${buttonClass(variant, size)} ${className}`}>
      {children}
    </Link>
  );
}

/**
 * Controls are words, not machine values, so they are set in the grotesk at
 * 600. Monospace here was a large part of why the workspace measured 48%
 * monospace by character — a button label is prose in a box.
 */
export function buttonClass(variant: "default" | "primary" | "ghost" | "danger" = "default", size: "sm" | "md" = "md") {
  const base =
    "inline-flex items-center justify-center gap-2 border font-semibold uppercase tracking-[0.14em] transition-colors disabled:cursor-not-allowed disabled:opacity-40";
  const sizing = size === "sm" ? "px-2.5 py-1 text-[10px]" : "px-3.5 py-2 text-[11px]";
  const variants = {
    default: "border-line-strong text-platinum-dim hover:border-platinum-dim hover:text-white",
    primary: "border-precision bg-precision/10 text-precision-dim hover:bg-precision/20",
    ghost: "border-transparent text-muted hover:text-platinum",
    danger: "border-risk/50 text-risk hover:bg-risk/10",
  };
  return `${base} ${sizing} ${variants[variant]}`;
}

export function Field({
  label,
  hint,
  children,
  required,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  required?: boolean;
}) {
  return (
    <label className="block">
      <span className="tech-label flex items-center gap-1.5">
        {label}
        {required && <span className="text-precision">*</span>}
      </span>
      <div className="mt-1.5">{children}</div>
      {hint && <p className="mt-1 text-[11px] leading-relaxed text-muted">{hint}</p>}
    </label>
  );
}

export const inputClass =
  "w-full border border-line-strong bg-void px-2.5 py-1.5 font-mono text-[12px] text-platinum placeholder:text-muted/60";

/* ------------------------------------------------------------------ */
/* Empty states — manufacturing-specific, never generic                */
/* ------------------------------------------------------------------ */

export function EmptyState({
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action?: { label: string; href: string };
}) {
  return (
    <div className="datum-frame flex flex-col items-start gap-3 border border-dashed border-line-strong px-6 py-8">
      <h3 className="font-mono text-[12px] uppercase tracking-[0.18em] text-platinum-dim">{title}</h3>
      <p className="max-w-md text-[13px] leading-relaxed text-muted">{body}</p>
      {action && (
        <LinkButton href={action.href} size="sm">
          {action.label}
        </LinkButton>
      )}
    </div>
  );
}

/** Marks a capability that is not what it might look like. Used liberally. */
/**
 * An inline ⓘ disclosure for a panel's limits copy — the refactor-spec home
 * for honesty prose that crowded panels as always-open paragraphs.
 *
 * Two rules with teeth: the summary line names the limit in caps where the
 * user would look for it (the disclosure hides the explanation, never the
 * existence of the limit), and this is an expandable element in the page,
 * not a tooltip — a limit that changes what an operator would do is never
 * only in a tooltip.
 */
export function LimitsDisclosure({ label, children }: { label: string; children: ReactNode }) {
  return (
    <details className="group min-w-0">
      <summary className="flex cursor-pointer list-none items-center gap-1.5 text-[9.5px] font-semibold uppercase tracking-[0.12em] text-muted hover:text-platinum">
        <span
          aria-hidden
          className="flex h-[13px] w-[13px] shrink-0 items-center justify-center rounded-full border border-line-strong font-serif text-[9px] italic leading-none"
        >
          i
        </span>
        {label}
        <span className="text-muted group-open:hidden">▸</span>
        <span className="hidden text-muted group-open:inline">▾</span>
      </summary>
      <div className="mt-1.5 text-[11.5px] leading-relaxed text-muted">{children}</div>
    </details>
  );
}

export function DevLabel({ children = "Development" }: { children?: ReactNode }) {
  return (
    <span className="shrink-0 border border-review/40 px-1 py-[1px] text-[9px] font-semibold uppercase tracking-[0.14em] text-review">
      {children}
    </span>
  );
}

export function Notice({
  tone = "review",
  title,
  children,
}: {
  tone?: Tone;
  title: string;
  children?: ReactNode;
}) {
  const border = {
    pass: "border-l-pass",
    review: "border-l-review",
    risk: "border-l-risk",
    unknown: "border-l-unknown",
    precision: "border-l-precision",
    neutral: "border-l-line-strong",
  }[tone];
  return (
    <div className={`border border-line ${border} border-l-2 bg-raised px-4 py-3`}>
      <h4 className="text-[11px] font-semibold uppercase tracking-[0.16em] text-platinum">{title}</h4>
      {children && <div className="mt-1.5 text-[12px] leading-relaxed text-muted">{children}</div>}
    </div>
  );
}

/** The small XYZ triad used to anchor viewport and hero areas. */
export function AxisTriad({ className = "" }: { className?: string }) {
  return (
    <svg width="54" height="54" viewBox="0 0 54 54" className={className} aria-hidden="true">
      <g stroke="var(--c-line-strong)" strokeWidth="1">
        <line x1="14" y1="40" x2="46" y2="40" />
        <line x1="14" y1="40" x2="14" y2="8" />
        <line x1="14" y1="40" x2="2" y2="52" />
      </g>
      <g fill="var(--c-muted)" fontSize="7" fontFamily="var(--font-readout)">
        <text x="47" y="43">X</text>
        <text x="10" y="7">Z</text>
        <text x="0" y="46">Y</text>
      </g>
    </svg>
  );
}
