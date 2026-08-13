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
    hairline: cs.getPropertyValue('--divider').trim(),
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
  return lum > 0.35 ? '#14100c' : '#f4f5f6';
}

// ------------------------------------------------------------ TRACE brand
// Reference 01 logo lock: track-line T icon with orange nodes + angular
// wordmark. One-color white wordmark is a sanctioned brand application.

export function TraceIcon({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" aria-label="TRACE" role="img">
      <path
        d="M 30 24 L 72 17 M 30 24 Q 22 26 23 34 L 24 40 Q 25 46 33 45 L 44 44 L 40 68"
        fill="none" stroke="#f4f5f6" strokeWidth="9" strokeLinecap="round" strokeLinejoin="round"
      />
      <path d="M 44 44 L 42 56" fill="none" stroke="#ff6a00" strokeWidth="9" strokeLinecap="round" />
      <circle cx="78" cy="16" r="8" fill="#ff6a00" />
      <circle cx="78" cy="16" r="3.2" fill="#0b0d10" />
      <circle cx="39" cy="75" r="8" fill="#ff6a00" />
      <circle cx="39" cy="75" r="3.2" fill="#0b0d10" />
    </svg>
  );
}

export function TraceLogo({ tagline = false }: { tagline?: boolean }) {
  return (
    <span className="brandlock">
      <TraceIcon />
      <span>
        <span className="wordmark">TRACE</span>
        {tagline && (
          <span style={{ display: 'block', fontSize: 8.5, letterSpacing: '0.3em', color: 'var(--muted)', textTransform: 'uppercase', marginTop: 2 }}>
            Telemetry &amp; Tuning
          </span>
        )}
      </span>
    </span>
  );
}

// ------------------------------------------------------------ shell pieces

export function EmptyState({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="empty">
      <h4>{title}</h4>
      {children && <p>{children}</p>}
    </div>
  );
}

export function Drawer({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  return (
    <>
      <div className="drawer-scrim" onClick={onClose} />
      <div className="drawer" role="dialog" aria-label={title}>
        <h3 style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          {title}
          <button className="btn small ghost" onClick={onClose} aria-label="Close">✕</button>
        </h3>
        {children}
      </div>
    </>
  );
}

// ------------------------------------------------------------ command palette

export function CommandPalette({ search, onClose }: {
  search: (q: string) => Array<{ kind: string; id: string; title: string; detail: string; href: string }>;
  onClose: () => void;
}) {
  const [q, setQ] = useState('');
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const hits = q.trim().length >= 2 ? search(q) : [];

  useEffect(() => { inputRef.current?.focus(); }, []);
  useEffect(() => { setActive(0); }, [q]);

  const go = (href: string) => { onClose(); window.location.hash = href.slice(1); };

  return (
    <>
      <div className="drawer-scrim" onClick={onClose} />
      <div role="dialog" aria-label="Search TRACE" style={{
        position: 'fixed', top: '12vh', left: '50%', transform: 'translateX(-50%)',
        width: 'min(620px, 94vw)', zIndex: 80, background: 'var(--raised)',
        borderRadius: 14, boxShadow: 'var(--shadow)', padding: 14, maxHeight: '68vh',
        display: 'flex', flexDirection: 'column',
      }}>
        <input
          ref={inputRef}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search bikes, riders, sessions, maps, components, decisions…"
          aria-label="Search"
          style={{ background: 'var(--overlay)', border: 0, borderRadius: 9, padding: '12px 14px', fontSize: 15, width: '100%' }}
          onKeyDown={(e) => {
            if (e.key === 'Escape') onClose();
            else if (e.key === 'ArrowDown') { e.preventDefault(); setActive(Math.min(active + 1, hits.length - 1)); }
            else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(Math.max(active - 1, 0)); }
            else if (e.key === 'Enter' && hits[active]) go(hits[active].href);
          }}
        />
        <div style={{ overflowY: 'auto', marginTop: 8 }}>
          {hits.map((h, i) => (
            <button key={`${h.kind}-${h.id}`}
              onClick={() => go(h.href)}
              onMouseEnter={() => setActive(i)}
              style={{
                display: 'flex', gap: 12, alignItems: 'baseline', width: '100%', textAlign: 'left',
                padding: '9px 12px', borderRadius: 8, fontSize: 13.5,
                background: i === active ? 'var(--overlay)' : 'transparent',
              }}>
              <span style={{
                flex: '0 0 86px', fontSize: 10, fontWeight: 800, letterSpacing: '0.08em',
                textTransform: 'uppercase', color: i === active ? 'var(--accent)' : 'var(--muted)',
              }}>{h.kind}</span>
              <span style={{ fontWeight: 650, minWidth: 0 }}>{h.title}</span>
              <span style={{ color: 'var(--muted)', fontSize: 12.5, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{h.detail}</span>
            </button>
          ))}
          {q.trim().length >= 2 && hits.length === 0 && (
            <p className="hint" style={{ padding: '10px 12px' }}>No records match “{q}”.</p>
          )}
          {q.trim().length < 2 && (
            <p className="hint" style={{ padding: '10px 12px' }}>Type to search everything — ↑↓ to move, Enter to open, Esc to close.</p>
          )}
        </div>
      </div>
    </>
  );
}

/** simple line icons for the tab bar — no clip-art */
export function AreaIcon({ area }: { area: string }) {
  const p: Record<string, React.ReactNode> = {
    garage: <path d="M3 10.5 12 4l9 6.5M5.5 9.5V20h13V9.5M9.5 20v-6h5v6" />,
    sessions: <><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2.5" /></>,
    tune: <><path d="M4 8h10M18 8h2M4 16h4M12 16h8" /><circle cx="16" cy="8" r="2.2" /><circle cx="10" cy="16" r="2.2" /></>,
    analyze: <path d="M4 19V5M4 19h16M7.5 15l3.5-4 3 2.5L18.5 8" />,
    more: <><circle cx="6" cy="12" r="1.6" /><circle cx="12" cy="12" r="1.6" /><circle cx="18" cy="12" r="1.6" /></>,
  };
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      {p[area]}
    </svg>
  );
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

  // TRACE chart convention: orange = current/selected, light gray = baseline
  const colors = [th.accent, '#a8adb5', '#6ea8e8', '#4f8fd6'];

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
