import type { Feature } from "@/lib/domain/features";
import type { DimensionRow, SpecimenView } from "@/lib/engines/specimen";

/**
 * ONE FEATURE, ISOLATED AND ENLARGED, WITH ITS DIMENSIONS ON IT
 *
 * The part thumbnail draws the whole part at 180×120 and a 0.201" hole in it is
 * four pixels. This draws the feature alone, filling the frame, with dimension
 * lines carrying the number — which is the difference between a picture of a
 * part and a drawing of a feature.
 *
 * Two views, and only where a second one says something: a section is a
 * different drawing for anything with depth and is the same drawing for a
 * chamfer, so it is not offered there rather than offered and empty.
 *
 * Free 3D orbit of an isolated solid is NOT this. That is stated on the page
 * rather than implied by a control that spins a flat drawing.
 */

const PAPER = "#fafaf8";
const INK = "#14181c";
const MUTED = "#9aa4ae";
const BLUE = "#0b72ff";
const RED = "#c8362b";

const W = 420;
const H = 300;
const PAD = 58;

const fmt = (n: number) => (Math.abs(n) >= 1 ? n.toFixed(3) : n.toFixed(4));

/** A dimension line with arrows and the value, drawn outside the geometry. */
function Dim({
  x1, y1, x2, y2, label, offset = 0, vertical = false, tone = INK,
}: {
  x1: number; y1: number; x2: number; y2: number; label: string; offset?: number; vertical?: boolean; tone?: string;
}) {
  const ax = vertical ? x1 + offset : x1;
  const bx = vertical ? x2 + offset : x2;
  const ay = vertical ? y1 : y1 + offset;
  const by = vertical ? y2 : y2 + offset;
  const mx = (ax + bx) / 2;
  const my = (ay + by) / 2;
  return (
    <g>
      {/* Extension lines back to the geometry, so the dimension is anchored. */}
      <line x1={x1} y1={y1} x2={ax} y2={ay} stroke={MUTED} strokeWidth={0.5} strokeDasharray="2 2" />
      <line x1={x2} y1={y2} x2={bx} y2={by} stroke={MUTED} strokeWidth={0.5} strokeDasharray="2 2" />
      <line x1={ax} y1={ay} x2={bx} y2={by} stroke={tone} strokeWidth={0.9} markerStart="url(#a)" markerEnd="url(#a)" />
      <text
        x={vertical ? mx + 6 : mx}
        y={vertical ? my : my - 4}
        fontSize={11}
        fontFamily="ui-monospace, monospace"
        fill={tone}
        textAnchor={vertical ? "start" : "middle"}
      >
        {label}
      </text>
    </g>
  );
}

export function FeatureSpecimen({
  feature,
  view,
  dimensions,
}: {
  feature: Feature;
  view: SpecimenView;
  dimensions: DimensionRow[];
}) {
  const f = feature as unknown as Record<string, number | undefined>;
  const measuredFor = (label: string) => dimensions.find((d) => d.label === label);

  /** The value to letter a dimension with: nominal, and measured beneath it. */
  const dimLabel = (label: string, nominal: number | undefined) => {
    if (nominal === undefined) return label;
    const m = measuredFor(label);
    if (!m || m.measured == null) return `${fmt(nominal)}`;
    return `${fmt(nominal)} / ${fmt(m.measured)} meas`;
  };
  const dimTone = (label: string) => {
    const m = measuredFor(label);
    return m?.verdict === "OUT_OF_TOLERANCE" ? RED : INK;
  };

  const frame = (children: React.ReactNode) => (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ background: PAPER }} className="h-full w-full" role="img" aria-label={`${feature.label}, ${view.toLowerCase()} view`}>
      <defs>
        <marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill={INK} />
        </marker>
        <pattern id="cut" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="6" stroke={MUTED} strokeWidth="1" />
        </pattern>
      </defs>
      {children}
      <text x={10} y={H - 10} fontSize={10} fontFamily="ui-monospace, monospace" fill={MUTED}>
        {view === "PLAN" ? "PLAN" : "SECTION"} · not to scale · dimensions in inches
      </text>
    </svg>
  );

  /* ---- Round features: bore, circular pocket, holes, boss ---- */
  const round = ["BORE", "CIRC_POCKET", "DRILLED_HOLE", "TAPPED_HOLE", "COUNTERBORE", "COUNTERSINK", "BOSS"];
  if (round.includes(feature.kind)) {
    const d = f.diameter ?? 1;
    const depth = f.depth ?? f.height ?? 0;

    if (view === "PLAN") {
      const r = (Math.min(W, H) - PAD * 2) / 2;
      const cx = W / 2;
      const cy = H / 2 - 6;
      return frame(
        <>
          <circle cx={cx} cy={cy} r={r} fill="none" stroke={INK} strokeWidth={1.6} />
          <line x1={cx - r - 14} y1={cy} x2={cx + r + 14} y2={cy} stroke={BLUE} strokeWidth={0.7} strokeDasharray="10 3 2 3" />
          <line x1={cx} y1={cy - r - 14} x2={cx} y2={cy + r + 14} stroke={BLUE} strokeWidth={0.7} strokeDasharray="10 3 2 3" />
          <Dim x1={cx - r} y1={cy} x2={cx + r} y2={cy} offset={r + 34} label={`⌀ ${dimLabel("Diameter", f.diameter)}`} tone={dimTone("Diameter")} />
        </>,
      );
    }

    // Section: the wall, the depth, and the bottom.
    const w = (W - PAD * 2) * 0.55;
    const h = depth > 0 ? Math.min(H - PAD * 2, (H - PAD * 2) * 0.7) : 20;
    const x = (W - w) / 2;
    const y = PAD;
    return frame(
      <>
        <rect x={x - 40} y={y} width={40} height={h} fill="url(#cut)" stroke={INK} strokeWidth={1.2} />
        <rect x={x + w} y={y} width={40} height={h} fill="url(#cut)" stroke={INK} strokeWidth={1.2} />
        <line x1={x} y1={y + h} x2={x + w} y2={y + h} stroke={INK} strokeWidth={1.6} />
        <line x1={W / 2} y1={y - 12} x2={W / 2} y2={y + h + 12} stroke={BLUE} strokeWidth={0.7} strokeDasharray="10 3 2 3" />
        <Dim x1={x} y1={y} x2={x + w} y2={y} offset={-26} label={`⌀ ${dimLabel("Diameter", f.diameter)}`} tone={dimTone("Diameter")} />
        {depth > 0 && (
          <Dim
            x1={x + w} y1={y} x2={x + w} y2={y + h} offset={54} vertical
            label={dimLabel("Depth", f.depth ?? f.height)}
            tone={dimTone("Depth")}
          />
        )}
      </>,
    );
  }

  /* ---- Rectangular pocket ---- */
  if (feature.kind === "RECT_POCKET") {
    const wIn = f.width ?? 1;
    const lIn = f.length ?? 1;
    if (view === "PLAN") {
      const k = Math.min((W - PAD * 2) / wIn, (H - PAD * 2) / lIn);
      const bw = wIn * k;
      const bh = lIn * k;
      const x = (W - bw) / 2;
      const y = (H - bh) / 2 - 6;
      const rr = (f.cornerRadius ?? 0) * k;
      return frame(
        <>
          <rect x={x} y={y} width={bw} height={bh} rx={rr} fill="none" stroke={INK} strokeWidth={1.6} />
          <Dim x1={x} y1={y} x2={x + bw} y2={y} offset={-26} label={dimLabel("Width, X", f.width)} tone={dimTone("Width, X")} />
          <Dim x1={x + bw} y1={y} x2={x + bw} y2={y + bh} offset={30} vertical label={dimLabel("Length, Y", f.length)} tone={dimTone("Length, Y")} />
          {(f.cornerRadius ?? 0) > 0 && (
            <text x={x + bw - rr} y={y + rr + 12} fontSize={10.5} fontFamily="ui-monospace, monospace" fill={MUTED}>
              R{fmt(f.cornerRadius ?? 0)}
            </text>
          )}
        </>,
      );
    }
    const bw = (W - PAD * 2) * 0.7;
    const bh = (H - PAD * 2) * 0.55;
    const x = (W - bw) / 2;
    const y = PAD;
    return frame(
      <>
        <rect x={x - 40} y={y} width={40} height={bh} fill="url(#cut)" stroke={INK} strokeWidth={1.2} />
        <rect x={x + bw} y={y} width={40} height={bh} fill="url(#cut)" stroke={INK} strokeWidth={1.2} />
        <line x1={x} y1={y + bh} x2={x + bw} y2={y + bh} stroke={INK} strokeWidth={1.6} />
        <Dim x1={x} y1={y} x2={x + bw} y2={y} offset={-26} label={dimLabel("Width, X", f.width)} tone={dimTone("Width, X")} />
        <Dim x1={x + bw} y1={y} x2={x + bw} y2={y + bh} offset={54} vertical label={dimLabel("Depth", f.depth)} tone={dimTone("Depth")} />
      </>,
    );
  }

  /* ---- Anything else: say so rather than draw a box and call it the part ---- */
  return frame(
    <text x={W / 2} y={H / 2} fontSize={12} fontFamily="ui-monospace, monospace" fill={MUTED} textAnchor="middle">
      no specimen drawing for {feature.kind.toLowerCase().replace(/_/g, " ")} yet
    </text>,
  );
}
