"use client";

import { useState, useRef, useCallback } from "react";
import { Button, Field, inputClass } from "@/components/ui";
import { sketchToSegments, type SketchPoint } from "@/lib/geometry/sketch";

/**
 * DRAWING THE PART.
 *
 * A shop that has a DXF imports it. A shop working from a napkin, a sample or
 * a phone photo has nothing to import, and typing a width and a length is how
 * every part in CANVAS ended up a rectangle. This is the other way in.
 *
 * IT IS A DRAWING, NOT A SKETCH SOLVER
 *
 * No constraints, no dimensions driving geometry, no parametric relationships.
 * Points are typed as coordinates and clicked on a grid that snaps to them,
 * and a corner is either sharp or has a radius somebody entered. That is a
 * smaller thing than CAD and it is stated as one — a machinist who needs
 * constraint solving needs CAD, and CANVAS reads its DXF.
 *
 * WHAT IT REFUSES TO DO IS CLOSE THE SHAPE FOR YOU
 *
 * The loop closes when the last point meets the first, which is a thing the
 * person doing the drawing decides. Everything else — winding, ordering,
 * whether the boundary is really closed — is settled by the same engine the
 * DXF goes through, so a drawn part and an imported part are the same part.
 */

const GRID = 0.25;
const VIEW = 520;

export function ProfileSketch({
  onSave,
  saving,
  problem,
}: {
  onSave: (segments: unknown[], depth: string) => void;
  saving: boolean;
  problem?: string | null;
}) {
  const [pts, setPts] = useState<SketchPoint[]>([]);
  const [scale, setScale] = useState(40); // pixels per inch
  const [snap, setSnap] = useState(true);
  const [typedX, setTypedX] = useState("");
  const [typedY, setTypedY] = useState("");
  const [typedR, setTypedR] = useState("0");
  // Not in a drawing. The person drawing it knows how thick the part is.
  const [depth, setDepth] = useState("");
  const svgRef = useRef<SVGSVGElement>(null);

  const toPart = (px: number, py: number) => {
    const x = (px - VIEW / 2) / scale;
    const y = (VIEW / 2 - py) / scale;
    return snap ? { x: Math.round(x / GRID) * GRID, y: Math.round(y / GRID) * GRID } : { x, y };
  };
  const toPx = (x: number, y: number) => ({ px: VIEW / 2 + x * scale, py: VIEW / 2 - y * scale });

  const click = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      const box = svgRef.current?.getBoundingClientRect();
      if (!box) return;
      const p = toPart(((e.clientX - box.left) / box.width) * VIEW, ((e.clientY - box.top) / box.height) * VIEW);
      setPts((prev) => [...prev, { ...p, r: 0 }]);
    },
    [scale, snap],
  );

  const addTyped = () => {
    const x = Number(typedX);
    const y = Number(typedY);
    const r = Number(typedR || "0");
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(r) || r < 0) return;
    setPts((prev) => [...prev, { x, y, r }]);
    setTypedX("");
    setTypedY("");
    setTypedR("0");
  };

  const built = sketchToSegments(pts);

  const bounds = pts.length
    ? {
        w: Math.max(...pts.map((p) => p.x)) - Math.min(...pts.map((p) => p.x)),
        h: Math.max(...pts.map((p) => p.y)) - Math.min(...pts.map((p) => p.y)),
      }
    : null;

  const grid: React.ReactElement[] = [];
  for (let g = -10; g <= 10; g++) {
    const { px } = toPx(g, 0);
    const { py } = toPx(0, g);
    if (px >= 0 && px <= VIEW) grid.push(<line key={`v${g}`} x1={px} y1={0} x2={px} y2={VIEW} stroke={g === 0 ? "#3d4450" : "#23272e"} strokeWidth={g === 0 ? 1 : 0.5} />);
    if (py >= 0 && py <= VIEW) grid.push(<line key={`h${g}`} x1={0} y1={py} x2={VIEW} y2={py} stroke={g === 0 ? "#3d4450" : "#23272e"} strokeWidth={g === 0 ? 1 : 0.5} />);
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-24">
          <Field label="X">
            <input className={inputClass} value={typedX} onChange={(e) => setTypedX(e.target.value)} inputMode="decimal" />
          </Field>
        </div>
        <div className="w-24">
          <Field label="Y">
            <input className={inputClass} value={typedY} onChange={(e) => setTypedY(e.target.value)} inputMode="decimal" />
          </Field>
        </div>
        <div className="w-24">
          <Field label="Corner R" hint="0 is sharp">
            <input className={inputClass} value={typedR} onChange={(e) => setTypedR(e.target.value)} inputMode="decimal" />
          </Field>
        </div>
        <Button type="button" size="sm" onClick={addTyped}>
          Add point
        </Button>
        <div className="w-32">
          <Field label="Profile depth" required hint="How deep it is cut.">
            <input className={inputClass} value={depth} onChange={(e) => setDepth(e.target.value)} inputMode="decimal" placeholder="0.750" />
          </Field>
        </div>
        <Button type="button" size="sm" variant="ghost" onClick={() => setPts((p) => p.slice(0, -1))} disabled={pts.length === 0}>
          Undo
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={() => setPts([])} disabled={pts.length === 0}>
          Clear
        </Button>
        <label className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.12em] text-muted">
          <input type="checkbox" checked={snap} onChange={(e) => setSnap(e.target.checked)} />
          Snap {GRID}&quot;
        </label>
        <label className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.12em] text-muted">
          Zoom
          <input type="range" min={10} max={120} value={scale} onChange={(e) => setScale(Number(e.target.value))} />
        </label>
      </div>

      <svg
        ref={svgRef}
        viewBox={`0 0 ${VIEW} ${VIEW}`}
        className="w-full max-w-[560px] cursor-crosshair border border-line bg-void"
        onClick={click}
      >
        {grid}
        {pts.map((p, i) => {
          const next = pts[(i + 1) % pts.length];
          if (pts.length < 2) return null;
          const a = toPx(p.x, p.y);
          const b = toPx(next.x, next.y);
          // Straight through the points, so what is drawn is what was clicked.
          // The fillets are computed on save and shown by the numbers, not by
          // a preview that could disagree with them.
          return <line key={`e${i}`} x1={a.px} y1={a.py} x2={b.px} y2={b.py} stroke="#4d8fd6" strokeWidth={1.5} />;
        })}
        {pts.map((p, i) => {
          const { px, py } = toPx(p.x, p.y);
          return (
            <g key={`p${i}`}>
              <rect x={px - 3} y={py - 3} width={6} height={6} fill={i === 0 ? "#4d8fd6" : "#c9ced6"} />
              {p.r > 0 && (
                <text x={px + 6} y={py - 5} fill="#8b939e" fontSize={9} fontFamily="monospace">
                  R{p.r}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      <div className="flex flex-wrap items-center gap-4 font-mono text-[11px] text-muted">
        <span>{pts.length} points</span>
        {bounds && (
          <span>
            {bounds.w.toFixed(3)}&quot; × {bounds.h.toFixed(3)}&quot; over the points
          </span>
        )}
        <span>Click the grid or type coordinates. The outline closes from the last point back to the first.</span>
      </div>

      {(built.error || problem) && (
        <p className="border border-line border-l-2 border-l-risk bg-raised px-3 py-2 text-[12px] text-platinum">
          {problem ?? built.error}
        </p>
      )}

      <Button
        type="button"
        variant="primary"
        size="sm"
        disabled={saving || built.error !== null || !(Number(depth) > 0)}
        onClick={() => onSave(built.segments, depth)}
      >
        {saving ? "Reading the outline…" : "Propose this outline"}
      </Button>
      <p className="text-[11px] leading-relaxed text-muted">
        This is a drawing surface, not a sketch solver: no constraints, no dimensions driving geometry. It becomes a
        proposal, and the outline is checked for closure and direction before anybody accepts it.
      </p>
    </div>
  );
}
