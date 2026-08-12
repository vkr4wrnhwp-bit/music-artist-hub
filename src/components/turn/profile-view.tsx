import type { RotationalProfile } from "@/lib/manufacturing/turn/geometry";
import { profilePolyline, overallLength, maxDiameter } from "@/lib/manufacturing/turn/geometry";
import type { TurnMove } from "@/lib/manufacturing/turn/operations";

/**
 * PROFILE VIEW — the X/Z drawing a lathe hand actually reads.
 *
 * Server-rendered SVG: centerline (chain line), stock envelope, finished
 * profile mirrored about X0, Z0 datum, diameter labels, the selected
 * segment in precision blue, and the selected operation's toolpath.
 * Diameters label as diameters; the drawing mirrors as radii — the
 * machinist convention, not the graphics one.
 *
 * The 3D lathe view is DEVELOPMENT and says so where it would appear; this
 * profile view is the real, complete rendering.
 */
export function TurnProfileView({
  profile,
  selectedSegmentId,
  moves,
}: {
  profile: RotationalProfile;
  selectedSegmentId?: string | null;
  moves?: TurnMove[] | null;
}) {
  const L = Math.max(overallLength(profile), profile.stockLength);
  const D = Math.max(maxDiameter(profile), profile.stockDiameter);
  const W = 860;
  const H = 380;
  const padX = 60;
  const padY = 40;
  const sx = (W - 2 * padX) / L;
  const sy = (H - 2 * padY) / D;
  const s = Math.min(sx, sy);
  const cx = (z: number) => padX + z * s;
  const cy = (r: number) => H / 2 - r * s; // +r above centerline
  const cyM = (r: number) => H / 2 + r * s; // mirror

  const poly = profilePolyline(profile);
  const path = poly.map((p, i) => `${i === 0 ? "M" : "L"}${cx(p.z).toFixed(1)},${cy(p.r).toFixed(1)}`).join(" ");
  const mirror = poly.map((p, i) => `${i === 0 ? "M" : "L"}${cx(p.z).toFixed(1)},${cyM(p.r).toFixed(1)}`).join(" ");

  const sel = selectedSegmentId ? profile.segments.find((x) => x.id === selectedSegmentId) : null;

  // Explicit light paper, the same philosophy as the 3D work window: the
  // instrument is dark, the drawing is lit. Strokes are drawn for this
  // ground and do not follow the app theme.
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ background: "#fafaf8" }} className="w-full border border-line" role="img" aria-label="X/Z profile view">
      {/* Stock envelope */}
      <rect
        x={cx(0)}
        y={cy(profile.stockDiameter / 2)}
        width={profile.stockLength * s}
        height={profile.stockDiameter * s}
        fill="none"
        stroke="#9aa4ae"
        strokeDasharray="6 4"
        strokeWidth={1}
      />
      {/* Centerline — chain line, the lathe's one sacred reference */}
      <line x1={cx(-0.02 * L) - 14} y1={H / 2} x2={cx(L) + 14} y2={H / 2} stroke="#0b72ff" strokeWidth={1} strokeDasharray="14 4 3 4" opacity={0.7} />
      <text x={cx(L) + 16} y={H / 2 + 3} fontSize={9} fill="#5a616b" fontFamily="monospace">X0</text>
      {/* Z0 datum */}
      <line x1={cx(0)} y1={padY - 8} x2={cx(0)} y2={H - padY + 8} stroke="#0b72ff" strokeWidth={1.2} opacity={0.8} />
      <text x={cx(0) - 8} y={padY - 12} fontSize={10} fill="#0b72ff" fontFamily="monospace">Z0</text>

      {/* Finished profile, both halves */}
      <path d={path} fill="none" stroke="#14181c" strokeWidth={1.8} />
      <path d={mirror} fill="none" stroke="#14181c" strokeWidth={1.8} opacity={0.55} />

      {/* Selected segment */}
      {sel && !sel.internal && (
        <g>
          <rect
            x={cx(sel.zStart)}
            y={cy(Math.max(sel.diameterStart, sel.diameterEnd) / 2)}
            width={Math.max(2, (sel.zEnd - sel.zStart) * s)}
            height={Math.max(sel.diameterStart, sel.diameterEnd) * s}
            fill="#0b72ff"
            opacity={0.13}
          />
          <line x1={cx(sel.zStart)} y1={cy(sel.diameterStart / 2)} x2={cx(sel.zEnd)} y2={cy(sel.diameterEnd / 2)} stroke="#0b72ff" strokeWidth={2.6} />
          {/* Diameter callout — a diameter, never a radius */}
          <text x={cx((sel.zStart + sel.zEnd) / 2)} y={cy(Math.max(sel.diameterStart, sel.diameterEnd) / 2) - 8} fontSize={11} fill="#0b72ff" fontFamily="monospace" textAnchor="middle">
            ⌀{sel.diameterEnd.toFixed(4)}
          </text>
          <text x={cx(sel.zStart)} y={H - padY + 22} fontSize={9} fill="#0b72ff" fontFamily="monospace" textAnchor="middle">
            Z{sel.zStart.toFixed(3)}
          </text>
          <text x={cx(sel.zEnd)} y={H - padY + 22} fontSize={9} fill="#0b72ff" fontFamily="monospace" textAnchor="middle">
            Z{sel.zEnd.toFixed(3)}
          </text>
        </g>
      )}

      {/* Toolpath for the selected operation: rapids dashed grey, cuts blue */}
      {moves && moves.length > 1 && (
        <g>
          {moves.slice(1).map((m, i) => {
            const a = moves[i];
            return (
              <line
                key={i}
                x1={cx(a.z)}
                y1={cy(a.x / 2)}
                x2={cx(m.z)}
                y2={cy(m.x / 2)}
                stroke={m.kind === "RAPID" ? "#a8aeb6" : "#0b72ff"}
                strokeWidth={m.kind === "RAPID" ? 0.8 : 1.6}
                strokeDasharray={m.kind === "RAPID" ? "4 3" : undefined}
                opacity={m.kind === "RAPID" ? 0.7 : 0.9}
              />
            );
          })}
        </g>
      )}

      {/* Scale note */}
      <text x={W - padX} y={H - 10} fontSize={9} fill="#5a616b" fontFamily="monospace" textAnchor="end">
        stock ⌀{profile.stockDiameter.toFixed(3)} × {profile.stockLength.toFixed(2)} · Z toward tailstock →
      </text>
    </svg>
  );
}
