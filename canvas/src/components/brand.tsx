import Link from "next/link";

/**
 * Brand marks.
 *
 * The mark is the machine coordinate system: framing corners, a datum
 * crosshair, and the origin square. It is not a picture of a mill — CANVAS is
 * about the decision, not the machine.
 */

export function DatumMark({ size = 28, className = "" }: { size?: number; className?: string }) {
  const s = size;
  const c = s / 2;
  const arm = s * 0.34;
  const bracket = s * 0.2;
  const inset = s * 0.12;
  return (
    <svg width={s} height={s} viewBox={`0 0 ${s} ${s}`} className={className} aria-hidden="true">
      {/* framing corners */}
      <g stroke="currentColor" strokeWidth={s * 0.055} fill="none" opacity={0.75}>
        <path d={`M${inset} ${inset + bracket} L${inset} ${inset} L${inset + bracket} ${inset}`} />
        <path d={`M${s - inset - bracket} ${inset} L${s - inset} ${inset} L${s - inset} ${inset + bracket}`} />
        <path d={`M${s - inset} ${s - inset - bracket} L${s - inset} ${s - inset} L${s - inset - bracket} ${s - inset}`} />
        <path d={`M${inset + bracket} ${s - inset} L${inset} ${s - inset} L${inset} ${s - inset - bracket}`} />
      </g>
      {/* datum crosshair */}
      <g stroke="var(--c-blue)" strokeWidth={s * 0.05}>
        <line x1={c - arm} y1={c} x2={c + arm} y2={c} />
        <line x1={c} y1={c - arm} x2={c} y2={c + arm} />
      </g>
      {/* origin */}
      <rect
        x={c - s * 0.085}
        y={c - s * 0.085}
        width={s * 0.17}
        height={s * 0.17}
        fill="none"
        stroke="var(--c-blue)"
        strokeWidth={s * 0.05}
      />
    </svg>
  );
}

/** Wordmark. The A has no crossbar — it reads as an axis, not a letter. */
export function Wordmark({ className = "", size = 20 }: { className?: string; size?: number }) {
  return (
    <span
      className={`font-sans font-light text-platinum ${className}`}
      style={{ fontSize: size, letterSpacing: "0.34em", lineHeight: 1 }}
    >
      C<span>A</span>NV<span style={{ color: "var(--c-blue)" }}>A</span>S
    </span>
  );
}

export function BrandLockup({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="flex items-center gap-3 text-platinum-dim transition-colors hover:text-platinum">
      <DatumMark size={26} />
      <span className="flex flex-col gap-1">
        <Wordmark size={15} />
        <span className="tech-label" style={{ fontSize: 8, letterSpacing: "0.22em" }}>
          Precision Manufacturing Intelligence
        </span>
      </span>
    </Link>
  );
}
