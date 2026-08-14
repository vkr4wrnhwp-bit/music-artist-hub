import type { Feature, Stock } from "@/lib/domain/features";
import type { RotationalProfile } from "@/lib/manufacturing/turn/geometry";
import { profilePolyline } from "@/lib/manufacturing/turn/geometry";

/**
 * PART THUMBNAILS — real geometry, never blank icons.
 *
 * Mill parts render as a top-view drawing from their actual features
 * (stock outline, bores, holes, pockets, slots); turned parts render as
 * their actual revolved profile silhouette. Server-rendered SVG on the
 * light work-window ground: the library shows parts, not rows.
 */

const PAPER = "#fafaf8";
const INK = "#14181c";
const MUTED_INK = "#9aa4ae";
const BLUE = "#0b72ff";

export function MillPartThumb({ features, stock }: { features: Feature[]; stock: Stock | null }) {
  const W = 180, H = 120, pad = 12;
  const sx = stock?.x ?? 6;
  const sy = stock?.y ?? 4;
  const k = Math.min((W - pad * 2) / sx, (H - pad * 2) / sy);
  const ox = (W - sx * k) / 2;
  const oy = (H - sy * k) / 2;
  // Program XY zero at stock centre — same convention the analyzer states.
  const X = (v: number) => ox + (v + sx / 2) * k;
  const Y = (v: number) => oy + (sy / 2 - v) * k;

  // No geometry yet: an empty stock outline looks like a finished blank
  // plate, which is a lie. Say what the tile actually knows.
  if (features.length === 0) {
    return (
      <svg viewBox={`0 0 ${W} ${H}`} style={{ background: PAPER }} className="h-full w-full" role="img" aria-label="No geometry yet">
        {stock && <rect x={ox} y={oy} width={sx * k} height={sy * k} fill="none" stroke={MUTED_INK} strokeWidth={1} strokeDasharray="5 4" />}
        <text x={W / 2} y={H / 2 + 3} fontSize={9} fill={MUTED_INK} fontFamily="monospace" textAnchor="middle">
          {stock ? "stock only — no geometry yet" : "no geometry yet"}
        </text>
      </svg>
    );
  }

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ background: PAPER }} className="h-full w-full" role="img" aria-label="Part top view">
      <rect x={ox} y={oy} width={sx * k} height={sy * k} fill="none" stroke={INK} strokeWidth={1.4} />
      {features.map((f) => {
        if (f.kind === "CIRC_POCKET" || f.kind === "BORE") {
          return <circle key={f.id} cx={X(f.centerX)} cy={Y(f.centerY)} r={(f.diameter / 2) * k} fill="none" stroke={f.critical ? BLUE : INK} strokeWidth={f.critical ? 1.4 : 1} />;
        }
        if (f.kind === "DRILLED_HOLE" || f.kind === "TAPPED_HOLE" || f.kind === "COUNTERBORE" || f.kind === "COUNTERSINK") {
          return (
            <g key={f.id}>
              <circle cx={X(f.centerX)} cy={Y(f.centerY)} r={Math.max(1.5, (f.diameter / 2) * k)} fill="none" stroke={f.critical ? BLUE : MUTED_INK} strokeWidth={1} />
              <line x1={X(f.centerX) - 3} y1={Y(f.centerY)} x2={X(f.centerX) + 3} y2={Y(f.centerY)} stroke={MUTED_INK} strokeWidth={0.6} />
              <line x1={X(f.centerX)} y1={Y(f.centerY) - 3} x2={X(f.centerX)} y2={Y(f.centerY) + 3} stroke={MUTED_INK} strokeWidth={0.6} />
            </g>
          );
        }
        if (f.kind === "RECT_POCKET") {
          return <rect key={f.id} x={X(f.centerX) - (f.width / 2) * k} y={Y(f.centerY) - (f.length / 2) * k} width={f.width * k} height={f.length * k} rx={f.cornerRadius * k} fill="none" stroke={f.critical ? BLUE : INK} strokeWidth={1} />;
        }
        if (f.kind === "SLOT") {
          return <line key={f.id} x1={X(f.startX)} y1={Y(f.startY)} x2={X(f.endX)} y2={Y(f.endY)} stroke={f.critical ? BLUE : INK} strokeWidth={Math.max(2, f.width * k)} strokeLinecap="round" opacity={0.35} />;
        }
        return null;
      })}
    </svg>
  );
}

export function TurnPartThumb({ profile }: { profile: RotationalProfile }) {
  const W = 180, H = 120, pad = 14;
  const poly = profilePolyline(profile);
  if (poly.length < 2) {
    return (
      <svg viewBox={`0 0 ${W} ${H}`} style={{ background: PAPER }} className="h-full w-full" role="img" aria-label="No profile yet">
        <text x={W / 2} y={H / 2} fontSize={9} fill={MUTED_INK} fontFamily="monospace" textAnchor="middle">no profile yet</text>
      </svg>
    );
  }
  const L = Math.max(...poly.map((p) => p.z), profile.stockLength);
  const R = Math.max(...poly.map((p) => p.r), profile.stockDiameter / 2);
  const k = Math.min((W - pad * 2) / L, (H - pad * 2) / (R * 2));
  const X = (z: number) => pad + z * k;
  const Y = (r: number) => H / 2 - r * k;
  const YM = (r: number) => H / 2 + r * k;
  // Closed silhouette: profile out, mirror back.
  const d =
    poly.map((p, i) => `${i === 0 ? "M" : "L"}${X(p.z).toFixed(1)},${Y(p.r).toFixed(1)}`).join(" ") +
    " " +
    [...poly].reverse().map((p) => `L${X(p.z).toFixed(1)},${YM(p.r).toFixed(1)}`).join(" ") +
    " Z";
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ background: PAPER }} className="h-full w-full" role="img" aria-label="Turned part profile">
      <line x1={pad - 6} y1={H / 2} x2={W - pad + 6} y2={H / 2} stroke={BLUE} strokeWidth={0.8} strokeDasharray="8 3 2 3" opacity={0.5} />
      <path d={d} fill={INK} fillOpacity={0.82} stroke={INK} strokeWidth={1} />
    </svg>
  );
}
