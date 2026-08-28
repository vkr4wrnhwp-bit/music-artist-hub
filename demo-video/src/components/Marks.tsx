import React from 'react';
import { interpolate, useCurrentFrame, Easing } from 'remotion';
import { c, EASE } from '../theme';

/**
 * The TRACE circuit mark — the exact geometry the product ships
 * (mx-lab/apps/web/src/ui.tsx TraceIcon), scaled up for film.
 *
 * A thin outlined racetrack forming a leaning T: the top straight runs out to
 * a left hairpin and back, the return straight drops through a diagonal to a
 * bottom-left hairpin, and an S-curve descends from the top-right ring
 * carrying the orange sector. Both routes converge at the bottom ring.
 *
 * `progress` draws the routes on; the orange sector, kerb echo and rings
 * arrive last so the mark resolves rather than simply appearing.
 */
export const TraceMark: React.FC<{ size?: number; progress?: number }> = ({ size = 120, progress = 1 }) => {
  // The shipped mark is drawn at viewBox 100×80 with a 3.1 road over a 4.8
  // casing. Those weights are proportional, so they carry to any size.
  const casing = 'rgba(4,5,8,0.9)';
  const routeA = 'M 82.5 11.5 L 21 14 Q 10 14.5 10.5 20 Q 11 25.5 21 25.5 L 40 24.8 Q 47 24.5 44.5 30.5 L 32 52 Q 28.5 58 31.5 62 L 38 68.5 Q 42.5 72.5 48.5 72';
  const routeB = 'M 87 19.5 Q 84 27 76.5 30.5 Q 66 35 60 41.5 L 57.5 44.5';
  const routeC = 'M 50 53.5 Q 47 57.5 48.5 61.5 Q 50.5 66 54.5 68.7';

  // pathLength normalises every route to 0..1 so one progress value draws
  // them all at a consistent visual rate regardless of true arc length.
  const track = (d: string, w: number, color: string, key: string) => (
    <path
      key={key} d={d} fill="none" stroke={color} strokeWidth={w}
      strokeLinecap="round" strokeLinejoin="round"
      pathLength={1} strokeDasharray={1} strokeDashoffset={1 - progress}
    />
  );

  const late = interpolate(progress, [0.62, 1], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  return (
    <svg width={size} height={size * 0.8} viewBox="0 0 100 80" aria-label="TRACE" role="img">
      {[routeA, routeB, routeC].map((d, i) => track(d, 4.8, casing, `casing${i}`))}
      {[routeA, routeB, routeC].map((d, i) => track(d, 3.1, c.ink, `road${i}`))}
      <g style={{ opacity: late }}>
        {track('M 56 46.5 L 52 52', 4.6, c.accent, 'sector')}
        {track('M 53 56.5 Q 51.5 59.5 52.5 62.5', 1.4, c.accent, 'kerb')}
        <circle cx="89" cy="13" r="5" fill="none" stroke={c.accent} strokeWidth={4.6}
          pathLength={1} strokeDasharray={1} strokeDashoffset={1 - late} transform="rotate(-90 89 13)" />
        <circle cx="58" cy="71" r="5" fill="none" stroke={c.accent} strokeWidth={4.6}
          pathLength={1} strokeDasharray={1} strokeDashoffset={1 - late} transform="rotate(-90 58 71)" />
      </g>
    </svg>
  );
};

/**
 * The drawn wordmark — the shipped letterforms (ui.tsx TraceWordmark):
 * speed-cut italic, chevron A with no crossbar, E as three floating bars with
 * the long top one in orange.
 */
export const TraceWordmark: React.FC<{ height?: number; opacity?: number; color?: string }> = ({
  height = 64, opacity = 1, color = c.ink,
}) => (
  <svg height={height} width={height * 6} viewBox="0 0 600 100" style={{ opacity }} aria-label="TRACE" role="img">
    <g transform="translate(40 0) skewX(-22)">
      <path fill={color} d="M0 0 H92 V19 H56 V100 H34 V19 H0 Z" />
      <path fill={color} fillRule="evenodd" d="M112 0 H176 L190 13 V38 L176 51 H112 Z M133 18 V33 H168 V18 Z" />
      <path fill={color} d="M112 51 H133 V100 H112 Z" />
      <path fill={color} d="M148 51 H169 L194 100 H167 Z" />
      <path fill={color} d="M254 0 H278 L316 100 H292 L266 22 L240 100 H216 Z" />
      <path fill={color} d="M340 17 L357 0 H420 V19 H362 V81 H420 V100 H357 L340 83 Z" />
      <path fill={c.accent} d="M452 0 H548 V18 H452 Z" />
      <path fill={color} d="M446 41 H528 V59 H446 Z" />
      <path fill={color} d="M440 82 H532 V100 H440 Z" />
    </g>
  </svg>
);

/** A thin accent rule that draws in — the film's one recurring flourish. */
export const Rule: React.FC<{ width?: number; delay?: number }> = ({ width = 120, delay = 0 }) => {
  const frame = useCurrentFrame();
  const w = interpolate(frame - delay, [0, 30], [0, width], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(...EASE),
  });
  return <div style={{ width: w, height: 3, background: c.accent, borderRadius: 2 }} />;
};
