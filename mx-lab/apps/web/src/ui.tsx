import React, { useEffect, useRef, useState } from 'react';
import type { Provenance, ReadinessStatus } from '@mxlab/domain';
import { useApp } from './state';

// ------------------------------------------------------------ pills & badges

export function Pill({ tone, children }: { tone: 'good' | 'warning' | 'serious' | 'critical' | 'neutral' | 'sim'; children: React.ReactNode }) {
  return (
    <span className={`pill ${tone}`}>
      {tone !== 'sim' && <span className="dot" aria-hidden />}
      {tone === 'sim' && '⚠ '}
      {children}
    </span>
  );
}

export function readinessTone(s: ReadinessStatus): 'good' | 'warning' | 'serious' | 'critical' | 'neutral' {
  switch (s) {
    case 'Ready for Test': return 'good';
    case 'Awaiting Approval': case 'Competition Review Required': return 'warning';
    case 'Maintenance Required': case 'Sensor Fault': return 'serious';
    case 'Not Inventoried': case 'Identity Incomplete': case 'Hardware Unknown': case 'Map Unknown': return 'critical';
    default: return 'neutral';
  }
}

export function Prov({ p }: { p: Provenance }) {
  const cls = p === 'AI INFERENCE' ? 'prov ai' : p === 'SIMULATION' ? 'prov sim' : 'prov';
  return <span className={cls}>{p}</span>;
}

export function Panel({ title, children, actions }: { title?: string; children: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <section className="panel">
      {title && (
        <h3 style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>{title}</span>
          {actions}
        </h3>
      )}
      <div className="panel-b">{children}</div>
    </section>
  );
}

export function Help({ id, children }: { id: string; children: React.ReactNode }) {
  const { tutor } = useApp();
  if (!tutor) return null;
  return (
    <div className="tutor-tip" data-tutor={id}>
      <b>Tutor · </b>{children}
    </div>
  );
}

// ------------------------------------------------------------ heat colors

function hexToRgb(h: string): [number, number, number] {
  const n = parseInt(h.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
const lin = (c: number) => { c /= 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
const unlin = (c: number) => Math.round(Math.min(1, Math.max(0, c <= 0.0031308 ? c * 12.92 : 1.055 * c ** (1 / 2.4) - 0.055)) * 255);
function toLab([r, g, b]: [number, number, number]) {
  const [lr, lg, lb] = [lin(r), lin(g), lin(b)];
  const l = Math.cbrt(0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb);
  const m = Math.cbrt(0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb);
  const s = Math.cbrt(0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb);
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ] as [number, number, number];
}
function fromLab([L, a, b2]: [number, number, number]) {
  const l = (L + 0.3963377774 * a + 0.2158037573 * b2) ** 3;
  const m = (L - 0.1055613458 * a - 0.0638541728 * b2) ** 3;
  const s = (L - 0.0894841775 * a - 1.291485548 * b2) ** 3;
  return `rgb(${unlin(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s)},${unlin(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s)},${unlin(-0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s)})`;
}
export function mixHex(a: string, b: string, t: number): string {
  const A = toLab(hexToRgb(a));
  const B = toLab(hexToRgb(b));
  return fromLab([A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t, A[2] + (B[2] - A[2]) * t]);
}
export function themeHeat() {
  const cs = getComputedStyle(document.documentElement);
  return {
    pos: cs.getPropertyValue('--heat-pos').trim(),
    neg: cs.getPropertyValue('--heat-neg').trim(),
    mid: cs.getPropertyValue('--heat-mid').trim(),
    ink: cs.getPropertyValue('--ink').trim(),
    muted: cs.getPropertyValue('--muted').trim(),
    hairline: cs.getPropertyValue('--hairline').trim(),
    accent: cs.getPropertyValue('--accent').trim(),
  };
}
export function heatColor(v: number, range: number, th: ReturnType<typeof themeHeat>): string {
  const t = Math.sign(v) * Math.abs(v / range) ** 0.75;
  return t >= 0 ? mixHex(th.mid, th.pos, Math.min(1, t)) : mixHex(th.mid, th.neg, Math.min(1, -t));
}
export function inkFor(rgb: string): string {
  const m = rgb.match(/(\d+),(\d+),(\d+)/);
  if (!m) return 'var(--ink)';
  const lum = 0.2126 * lin(+m[1]) + 0.7152 * lin(+m[2]) + 0.0722 * lin(+m[3]);
  return lum > 0.35 ? '#14130f' : '#f4f3ee';
}

// ------------------------------------------------------------ line chart

export interface Series { id: string; label: string; unit: string; values: number[]; emphasis?: boolean }

export function LineChart({ t, series, height = 170, markers }: {
  t: number[];
  series: Series[];
  height?: number;
  markers?: Array<{ tS: number; label: string }>;
}) {
  const W = 760;
  const PL = 46;
  const PR = 10;
  const PT = 10;
  const PB = 22;
  const boxRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const th = themeHeat();

  // downsample to ~700 points
  const step = Math.max(1, Math.floor(t.length / 700));
  const idx: number[] = [];
  for (let i = 0; i < t.length; i += step) idx.push(i);

  const tMin = t[0] ?? 0;
  const tMax = t[t.length - 1] ?? 1;
  const x = (sec: number) => PL + ((sec - tMin) / Math.max(1e-6, tMax - tMin)) * (W - PL - PR);

  // normalize each series to its own 0..1 within shared plot (multi-unit safe)
  const scaled = series.map((s) => {
    const lo = Math.min(...s.values);
    const hi = Math.max(...s.values);
    return { ...s, lo, hi, y: (v: number) => PT + (1 - (v - lo) / Math.max(1e-6, hi - lo)) * (height - PT - PB) };
  });

  const colors = [th.accent, th.neg, th.muted, th.pos];

  const onMove = (e: React.PointerEvent) => {
    const rect = boxRef.current!.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * W;
    const sec = tMin + ((px - PL) / (W - PL - PR)) * (tMax - tMin);
    let best = 0;
    let bd = Infinity;
    for (const i of idx) {
      const d = Math.abs(t[i] - sec);
      if (d < bd) { bd = d; best = i; }
    }
    setHover(best);
  };

  return (
    <div className="chart-box">
      <svg
        ref={boxRef}
        viewBox={`0 0 ${W} ${height}`}
        role="img"
        onPointerMove={onMove}
        onPointerLeave={() => setHover(null)}
      >
        {[0.25, 0.5, 0.75].map((f) => (
          <line key={f} x1={PL} x2={W - PR} y1={PT + f * (height - PT - PB)} y2={PT + f * (height - PT - PB)} stroke={th.hairline} strokeWidth={1} />
        ))}
        <line x1={PL} x2={W - PR} y1={height - PB} y2={height - PB} stroke={th.muted} strokeWidth={1} />
        {[0, 0.25, 0.5, 0.75, 1].map((f) => {
          const sec = tMin + f * (tMax - tMin);
          return (
            <text key={f} x={x(sec)} y={height - 8} textAnchor="middle" fontSize={10} fill={th.muted} fontFamily="ui-monospace, Menlo, monospace">
              {Math.round(sec)}s
            </text>
          );
        })}
        {(markers ?? []).map((m, i) => (
          <g key={i}>
            <line x1={x(m.tS)} x2={x(m.tS)} y1={PT} y2={height - PB} stroke={th.neg} strokeWidth={1.5} strokeDasharray="4 3" />
            <text x={x(m.tS) + 3} y={PT + 10} fontSize={10} fill={th.neg} fontFamily="ui-monospace, Menlo, monospace">▲{m.label}</text>
          </g>
        ))}
        {scaled.map((s, si) => (
          <path
            key={s.id}
            d={idx.map((i, k) => `${k ? 'L' : 'M'}${x(t[i]).toFixed(1)} ${s.y(s.values[i]).toFixed(1)}`).join(' ')}
            fill="none"
            stroke={colors[si % colors.length]}
            strokeWidth={s.emphasis ? 2 : 1.4}
            strokeOpacity={s.emphasis === false ? 0.6 : 1}
            strokeLinejoin="round"
          />
        ))}
        {hover !== null && (
          <g>
            <line x1={x(t[hover])} x2={x(t[hover])} y1={PT} y2={height - PB} stroke={th.muted} strokeWidth={1} strokeDasharray="3 3" />
            {scaled.map((s, si) => (
              <circle key={s.id} cx={x(t[hover])} cy={s.y(s.values[hover])} r={3.5} fill={colors[si % colors.length]} />
            ))}
          </g>
        )}
      </svg>
      {hover !== null && (
        <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', fontSize: 12.5, padding: '4px 2px', color: 'var(--ink-2)' }} className="mono">
          <span>t={t[hover].toFixed(1)}s</span>
          {series.map((s, si) => (
            <span key={s.id}>
              <span style={{ display: 'inline-block', width: 14, height: 2, background: colors[si % colors.length], verticalAlign: 'middle', marginRight: 4 }} />
              {s.label}: <b>{s.values[hover]}{s.unit}</b>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------ misc

export function fmtSigned(v: number, digits = 1): string {
  const s = v.toFixed(digits).replace('-', '−');
  return v > 0 ? `+${s}` : s;
}

export function download(name: string, text: string, type: string): void {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type }));
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
}

export function useThemeVersion(): number {
  const [v, setV] = useState(0);
  useEffect(() => {
    const mq = matchMedia('(prefers-color-scheme: dark)');
    const bump = () => setV((x) => x + 1);
    mq.addEventListener('change', bump);
    const mo = new MutationObserver(bump);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => { mq.removeEventListener('change', bump); mo.disconnect(); };
  }, []);
  return v;
}
