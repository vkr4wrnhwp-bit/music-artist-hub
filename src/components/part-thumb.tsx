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

/**
 * Which features this top view can actually draw. A face, a chamfer or a
 * fillet has no outline in plan, so it renders as nothing — and a highlight
 * pointing at nothing would recede every feature the operator CAN see while
 * emphasising an empty space. Callers ask before they claim to be pointing.
 */
const DRAWN_IN_TOP_VIEW = [
  "CIRC_POCKET",
  "BORE",
  "DRILLED_HOLE",
  "TAPPED_HOLE",
  "COUNTERBORE",
  "COUNTERSINK",
  "RECT_POCKET",
  "SLOT",
];

export function drawnInTopView(f: Pick<Feature, "kind">): boolean {
  return DRAWN_IN_TOP_VIEW.includes(f.kind);
}

export function MillPartThumb({
  features,
  stock,
  highlightFeatureId = null,
}: {
  features: Feature[];
  stock: Stock | null;
  /**
   * Draw one feature at full strength and recede the rest, so a page can show
   * which feature it is talking about. The emphasis is opacity on the whole
   * feature, never a colour change: BLUE means critical here, and a highlight
   * must not make an ordinary feature read as a critical one.
   *
   * This is the geometry CANVAS holds. It is not a marker on a photograph —
   * nothing calibrates an uploaded photo to part coordinates.
   */
  highlightFeatureId?: string | null;
}) {
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
  // plate, which is a lie. Hand the slot to PartThumbEmpty instead.
  if (features.length === 0) return <PartThumbEmpty stock={stock} />;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ background: PAPER }} className="h-full w-full" role="img" aria-label="Part top view">
      <rect x={ox} y={oy} width={sx * k} height={sy * k} fill="none" stroke={INK} strokeWidth={1.4} />
      {features.map((f) => {
        // A highlight naming a feature with no outline in plan is ignored
        // rather than honoured: honouring it would dim all eight features the
        // operator can see in order to emphasise nothing.
        const highlight = features.some((x) => x.id === highlightFeatureId && drawnInTopView(x))
          ? highlightFeatureId
          : null;
        const shape = (() => {
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
        })();
        if (shape === null || highlight === null) return shape;
        return (
          <g key={f.id} opacity={f.id === highlight ? 1 : 0.2}>
            {shape}
          </g>
        );
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

/**
 * THE SLOT WHEN THERE IS NOTHING TO DRAW.
 *
 * A part with no features has no top view, and the tile used to say so in
 * 9px grey — true, dead, and easy to read as "this part is broken". It is a
 * third of the library on a young shop's first week.
 *
 * WHY IT DOES NOT SAY "COMING SOON"
 *
 * Because nothing is coming. The tile is empty for a reason that belongs to
 * THIS part — nobody has added geometry, or defined stock, or measured the
 * profile — and every one of those is an action the shop takes, not one
 * CANVAS is going to ship. "Coming soon" would move the responsibility onto
 * a feature that does not exist and hide the thing they can actually do.
 *
 * So the slot carries the action. Dashed stock where stock is known, the
 * part's own next step where it is not.
 */
export function PartThumbEmpty({ stock, action }: { stock: Stock | null; action?: string }) {
  const W = 180, H = 120, pad = 12;
  const sx = stock?.x ?? 6;
  const sy = stock?.y ?? 4;
  const k = Math.min((W - pad * 2) / sx, (H - pad * 2) / sy);
  const ox = (W - sx * k) / 2;
  const oy = (H - sy * k) / 2;
  const label = (action ?? (stock ? "Add geometry" : "Define stock")).toUpperCase();

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ background: PAPER }} className="h-full w-full" role="img" aria-label={label}>
      {/* Stock, dashed, because it is known and the part inside it is not. */}
      {stock && <rect x={ox} y={oy} width={sx * k} height={sy * k} fill="none" stroke={MUTED_INK} strokeWidth={1} strokeDasharray="5 4" />}
      {/* A centre mark, at the program origin the drawn tile uses. Small: it
          locates the empty tile in the same frame as a full one, so the two
          do not read as different kinds of picture. */}
      <g stroke={MUTED_INK} strokeWidth={0.9}>
        <path d={`M${W / 2 - 9} ${H / 2 - 14} H${W / 2 + 9}`} />
        <path d={`M${W / 2} ${H / 2 - 23} V${H / 2 - 5}`} />
      </g>
      <text x={W / 2} y={H / 2 + 14} fontSize={9} fill={INK} fontFamily="monospace" letterSpacing="1.4" textAnchor="middle">
        {label}
      </text>
    </svg>
  );
}

/**
 * A PHOTOGRAPH OF THE PART, LABELLED AS ONE.
 *
 * When a shop has photographed a part but not modelled it, the photograph is
 * the best picture of it that exists — better than an empty frame, and it is
 * what somebody walking past the screen would recognise.
 *
 * It carries a tag, always. A photograph in the same slot that elsewhere
 * holds CANVAS's own geometry would otherwise read as geometry, and a
 * machinist would take the tile as evidence the part is modelled. It is not:
 * nothing calibrates an uploaded photo to part coordinates, no dimension
 * comes off it, and the tag says which of the two they are looking at.
 */
export function PartPhotoThumb({ src, alt }: { src: string; alt: string }) {
  return (
    <div className="relative h-full w-full overflow-hidden" style={{ background: PAPER }}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt={alt} className="h-full w-full object-cover" />
      <span
        className="absolute bottom-0 left-0 px-1.5 py-0.5 font-mono text-[8.5px] uppercase tracking-[0.14em]"
        style={{ background: INK, color: PAPER }}
      >
        Photo &mdash; not geometry
      </span>
    </div>
  );
}
