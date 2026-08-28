import React from 'react';
import { interpolate, useCurrentFrame, Easing } from 'remotion';
import { c, type as T, EASE } from '../theme';

/**
 * The explanation system: a mono label (what the system is doing), a display
 * headline, and one line of why it matters. Never more than two levels of text
 * on screen at once.
 */
export const Copy: React.FC<{
  label?: string;
  headline?: string;
  why?: string;
  at?: 'left' | 'right' | 'bottom' | 'top';
  width?: number;
  delay?: number;
}> = ({ label, headline, why, at = 'right', width, delay = 0 }) => {
  const frame = useCurrentFrame();
  const rise = (i: number) => {
    const t = interpolate(frame - delay - i * 5, [0, 26], [0, 1], {
      extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
      easing: Easing.bezier(...EASE),
    });
    return { opacity: t, transform: `translateY(${(1 - t) * 22}px)` };
  };

  const bottom = at === 'bottom' || at === 'top';
  const box: React.CSSProperties = at === 'top'
    ? { position: 'absolute', left: 72, right: 72, top: 0, width: 'auto' }
    : at === 'bottom'
    ? { position: 'absolute', left: 96, right: 96, bottom: 84, width: 'auto' }
    : {
        position: 'absolute', top: '50%', transform: 'translateY(-50%)',
        [at]: 88, width: width ?? 560,
      } as React.CSSProperties;

  return (
    <div style={{ ...box, textAlign: 'left' }}>
      {label && (
        <div style={{ ...rise(0), marginBottom: 18, display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ width: 8, height: 8, borderRadius: 8, background: c.accent, flex: '0 0 auto' }} />
          <span style={{ ...T.eyebrow, color: c.ink2 }}>{label}</span>
        </div>
      )}
      {headline && (
        <div style={{ ...(bottom ? T.headlineSm : T.headlineSm), color: c.ink, ...rise(1), marginBottom: why ? 16 : 0, maxWidth: bottom ? 1360 : undefined }}>
          {headline}
        </div>
      )}
      {why && (
        <div style={{ ...T.why, color: c.ink2, ...rise(2), maxWidth: bottom ? 1180 : undefined }}>{why}</div>
      )}
    </div>
  );
};
