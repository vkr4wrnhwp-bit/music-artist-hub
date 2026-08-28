import React from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig, Easing } from 'remotion';
import { brand } from '../brand.config';
import { c, type as T, EASE } from '../theme';
import { Rule, TraceMark, TraceWordmark } from './Marks';

/** Opening: the mark draws, the wordmark arrives, the promise lands. */
export const TitleCard: React.FC = () => {
  const frame = useCurrentFrame();
  const { width } = useVideoConfig();
  // the vertical cut is 1080 wide; the lockup is sized for 1920, but scaling
  // it strictly by width leaves the mark too small to carry a 9:16 frame
  const k = Math.max(0.78, Math.min(1, width / 1920));
  const draw = interpolate(frame, [6, 52], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(...EASE) });
  const word = interpolate(frame, [46, 76], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(...EASE) });
  const tag = interpolate(frame, [66, 92], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(...EASE) });
  return (
    <AbsoluteFill style={{ background: c.ground, alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 26 }}>
        <TraceMark size={248 * k} progress={draw} />
        <div style={{ opacity: word, transform: `translateY(${(1 - word) * 14}px)` }}>
          <TraceWordmark height={104 * k} />
        </div>
        <div style={{ opacity: tag, ...T.caption, fontSize: 24 * k, color: c.ink2, letterSpacing: '0.34em' }}>{brand.tagline}</div>
      </div>
    </AbsoluteFill>
  );
};

/** A full-screen statement: the film's voice, used sparingly. */
export const StatementCard: React.FC<{ headline: string; why?: string }> = ({ headline, why }) => {
  const frame = useCurrentFrame();
  const { width } = useVideoConfig();
  const k = Math.min(1, width / 1920);
  const pad = Math.round(160 * Math.max(0.45, k));
  // Content rises from frame 0, not from a beat of empty ground: the scene
  // cross-dissolves in over six frames, and anything still invisible at the
  // end of that window leaves the frame bare.
  const a = interpolate(frame, [0, 20], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(...EASE) });
  const b = interpolate(frame, [12, 34], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(...EASE) });
  return (
    <AbsoluteFill style={{ background: c.ground, justifyContent: 'center', padding: `0 ${pad}px` }}>
      <div style={{ marginBottom: 34, opacity: a }}><Rule width={110} delay={0} /></div>
      <div style={{ ...T.headline, fontSize: Math.round(76 * Math.max(0.78, k)), color: c.ink, maxWidth: 1420, opacity: a, transform: `translateY(${(1 - a) * 18}px)` }}>
        {headline}
      </div>
      {why && (
        <div style={{ ...T.why, fontSize: Math.round(34 * Math.max(0.7, k)), color: c.ink2, marginTop: 26, opacity: b, transform: `translateY(${(1 - b) * 14}px)` }}>
          {why}
        </div>
      )}
    </AbsoluteFill>
  );
};

/** Closing: mark, promise, honest disclosure, where to go. */
export const EndCard: React.FC = () => {
  const frame = useCurrentFrame();
  const { width } = useVideoConfig();
  const k = Math.max(0.78, Math.min(1, width / 1920));
  const a = interpolate(frame, [0, 24], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(...EASE) });
  const b = interpolate(frame, [18, 46], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(...EASE) });
  const d = interpolate(frame, [40, 72], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(...EASE) });
  return (
    <AbsoluteFill style={{ background: c.ground, alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 22, opacity: a }}>
        <TraceMark size={176 * k} progress={1} />
        <TraceWordmark height={80 * k} />
        <div style={{ ...T.caption, fontSize: 22 * k, color: c.ink2, letterSpacing: '0.34em' }}>{brand.tagline}</div>
      </div>
      <div style={{ ...T.why, fontSize: Math.round(32 * Math.max(0.72, k)), color: c.ink, marginTop: 46, opacity: b, textAlign: 'center', padding: '0 64px' }}>
        Evidence, not opinion — on every change.
      </div>
      <div style={{ marginTop: 44, opacity: d, textAlign: 'center' }}>
        <div style={{ ...T.caption, color: c.accent, fontSize: 22 }}>{brand.callToAction}</div>
        <div style={{ ...T.why, fontSize: 19, color: c.muted, marginTop: 20, maxWidth: Math.min(1080, width - 140), lineHeight: 1.5, marginInline: 'auto' }}>
          {brand.disclosure}
        </div>
      </div>
    </AbsoluteFill>
  );
};
