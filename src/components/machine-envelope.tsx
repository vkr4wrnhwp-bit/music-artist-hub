/**
 * MACHINE ENVELOPE — the working volume as a drawing.
 *
 * Top view on the light ground: the table in ink, the XY travel envelope
 * as a dashed precision-blue rectangle, both dimensioned from the real
 * profile values. Z travel is stated as text — a fake isometric would
 * add drama, not information. Server-rendered SVG.
 */

const PAPER = "#fafaf8";
const INK = "#14181c";
const MUTED_INK = "#9aa4ae";
const BLUE = "#0b72ff";

export function MachineEnvelope({
  travelsX,
  travelsY,
  travelsZ,
  tableX,
  tableY,
}: {
  travelsX: number;
  travelsY: number;
  travelsZ: number;
  tableX: number;
  tableY: number;
}) {
  const W = 280, H = 190, pad = 40;
  const spanX = Math.max(travelsX, tableX);
  const spanY = Math.max(travelsY, tableY);
  const k = Math.min((W - pad * 2) / spanX, (H - pad * 2) / spanY);
  const rect = (w: number, h: number) => ({
    x: (W - w * k) / 2,
    y: (H - h * k) / 2,
    w: w * k,
    h: h * k,
  });
  const table = rect(tableX, tableY);
  const travel = rect(travelsX, travelsY);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ background: PAPER }} className="h-full w-full border border-line" role="img" aria-label="Work envelope, top view">
      {/* Table */}
      <rect x={table.x} y={table.y} width={table.w} height={table.h} fill={INK} fillOpacity={0.06} stroke={INK} strokeWidth={1.4} />
      {/* Travel envelope */}
      <rect x={travel.x} y={travel.y} width={travel.w} height={travel.h} fill="none" stroke={BLUE} strokeWidth={1.2} strokeDasharray="6 4" />
      {/* X dimension (travel, below) */}
      <line x1={travel.x} y1={H - 18} x2={travel.x + travel.w} y2={H - 18} stroke={BLUE} strokeWidth={0.8} />
      <text x={W / 2} y={H - 6} fontSize={9} fill={BLUE} fontFamily="monospace" textAnchor="middle">
        X {travelsX}″
      </text>
      {/* Y dimension (travel, left) */}
      <line x1={16} y1={travel.y} x2={16} y2={travel.y + travel.h} stroke={BLUE} strokeWidth={0.8} />
      <text x={10} y={H / 2} fontSize={9} fill={BLUE} fontFamily="monospace" textAnchor="middle" transform={`rotate(-90 10 ${H / 2})`}>
        Y {travelsY}″
      </text>
      {/* Table dimension label */}
      <text x={table.x + 4} y={table.y + 12} fontSize={8.5} fill={MUTED_INK} fontFamily="monospace">
        table {tableX}″ × {tableY}″
      </text>
      {/* Z as text — stated, not staged */}
      <text x={W - 8} y={16} fontSize={9} fill={INK} fontFamily="monospace" textAnchor="end">
        Z {travelsZ}″
      </text>
    </svg>
  );
}
