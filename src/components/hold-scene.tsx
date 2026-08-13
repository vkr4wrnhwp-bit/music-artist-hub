/**
 * HOLD SCENE — the setup as a physical drawing, not a data table.
 *
 * Side elevation on the light work-window ground: vise jaws gripping the
 * stock, grip depth and stock projection dimensioned from their real
 * recorded values, the peak cutting force drawn where it acts when the
 * estimate exists. Server-rendered SVG; every number on it is a real
 * value or the drawing says what is missing instead of inventing one.
 */

const PAPER = "#fafaf8";
const INK = "#14181c";
const MUTED_INK = "#9aa4ae";
const JAW = "#6b7480";
const BLUE = "#0b72ff";

export function HoldScene({
  stockX,
  gripDepth,
  stockProjection,
  peakForceLbf,
}: {
  stockX: number | null;
  gripDepth: number | null;
  stockProjection: number | null;
  peakForceLbf: number | null;
}) {
  const W = 280, H = 190;
  if (stockX === null || gripDepth === null || stockProjection === null) {
    const missing = [
      stockX === null ? "stock" : null,
      gripDepth === null ? "grip depth" : null,
      stockProjection === null ? "stock projection" : null,
    ].filter(Boolean);
    return (
      <svg viewBox={`0 0 ${W} ${H}`} style={{ background: PAPER }} className="h-full w-full border border-line" role="img" aria-label="Hold scene unavailable">
        <text x={W / 2} y={H / 2 - 6} fontSize={9} fill={MUTED_INK} fontFamily="monospace" textAnchor="middle">
          cannot draw the hold —
        </text>
        <text x={W / 2} y={H / 2 + 8} fontSize={9} fill={MUTED_INK} fontFamily="monospace" textAnchor="middle">
          {missing.join(", ")} not recorded
        </text>
      </svg>
    );
  }

  const pad = 34;
  const stockH = gripDepth + stockProjection;
  // Scale to fit; jaws add fixed visual width either side.
  const jawW = 34;
  const k = Math.min((W - pad * 2 - jawW * 2) / stockX, (H - pad * 2) / stockH);
  const sw = stockX * k;
  const sh = stockH * k;
  const x0 = (W - sw) / 2;
  const yTop = (H - sh) / 2;
  const yJawTop = yTop + stockProjection * k; // jaw line = top of grip
  const yBottom = yTop + sh;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ background: PAPER }} className="h-full w-full border border-line" role="img" aria-label="Hold scene — side elevation">
      {/* Jaws — grip region only */}
      <rect x={x0 - jawW} y={yJawTop} width={jawW} height={yBottom - yJawTop} fill={JAW} opacity={0.55} />
      <rect x={x0 + sw} y={yJawTop} width={jawW} height={yBottom - yJawTop} fill={JAW} opacity={0.55} />
      {/* Stock */}
      <rect x={x0} y={yTop} width={sw} height={sh} fill="none" stroke={INK} strokeWidth={1.6} />
      {/* Jaw line across */}
      <line x1={x0 - jawW - 6} y1={yJawTop} x2={x0 + sw + jawW + 6} y2={yJawTop} stroke={MUTED_INK} strokeWidth={0.8} strokeDasharray="5 3" />
      {/* Projection dimension (right side, above jaw line) */}
      <line x1={x0 + sw + jawW + 12} y1={yTop} x2={x0 + sw + jawW + 12} y2={yJawTop} stroke={BLUE} strokeWidth={0.9} />
      <text x={x0 + sw + jawW + 16} y={(yTop + yJawTop) / 2 + 3} fontSize={9} fill={BLUE} fontFamily="monospace">
        {stockProjection.toFixed(3)}″
      </text>
      {/* Grip dimension (right side, below jaw line) */}
      <line x1={x0 + sw + jawW + 12} y1={yJawTop} x2={x0 + sw + jawW + 12} y2={yBottom} stroke={MUTED_INK} strokeWidth={0.9} />
      <text x={x0 + sw + jawW + 16} y={(yJawTop + yBottom) / 2 + 3} fontSize={9} fill={MUTED_INK} fontFamily="monospace">
        {gripDepth.toFixed(3)}″
      </text>
      {/* Clamp force arrows into the jaws */}
      <line x1={x0 - jawW - 4} y1={(yJawTop + yBottom) / 2} x2={x0 - 4} y2={(yJawTop + yBottom) / 2} stroke={JAW} strokeWidth={1.4} markerEnd="url(#holdArrow)" />
      <line x1={x0 + sw + jawW + 4} y1={(yJawTop + yBottom) / 2} x2={x0 + sw + 4} y2={(yJawTop + yBottom) / 2} stroke={JAW} strokeWidth={1.4} markerEnd="url(#holdArrow)" />
      {/* Peak cutting force where it acts — only when a real estimate exists */}
      {peakForceLbf !== null && (
        <g>
          <line x1={x0 + sw * 0.5} y1={yTop - 22} x2={x0 + sw * 0.5} y2={yTop - 4} stroke={BLUE} strokeWidth={1.6} markerEnd="url(#holdArrowBlue)" />
          <text x={x0 + sw * 0.5 + 6} y={yTop - 12} fontSize={9} fill={BLUE} fontFamily="monospace">
            {peakForceLbf.toFixed(0)} lbf peak
          </text>
        </g>
      )}
      <defs>
        <marker id="holdArrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 Z" fill={JAW} />
        </marker>
        <marker id="holdArrowBlue" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 Z" fill={BLUE} />
        </marker>
      </defs>
      <text x={W - 8} y={H - 8} fontSize={8.5} fill={MUTED_INK} fontFamily="monospace" textAnchor="end">
        side elevation · jaw line dashed
      </text>
    </svg>
  );
}
