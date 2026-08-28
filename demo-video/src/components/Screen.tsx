import React from 'react';
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig, Easing } from 'remotion';
import { c, EASE } from '../theme';

export interface Focus { x: number; y: number; w: number; h: number }

/**
 * The application, treated as a photographed product: a controlled push toward
 * the region that matters, on a calm ground. No tilting, no floating panels —
 * the interface is the subject.
 */
export const Screen: React.FC<{
  shot: string;
  focus?: Focus;
  /** how far into the scene the move completes */
  settleAt?: number;
  dim?: number;
  /**
   * Size of the area the capture has to fill, when that is not the whole
   * frame — the vertical cut sets the product inside a card rather than
   * cropping a 16:10 capture to 9:16.
   */
  box?: { width: number; height: number };
  /** width / height of the capture; the tall variant is square, not 16:10 */
  sourceAspect?: number;
}> = ({ shot, focus, settleAt = 0.72, dim = 0, box, sourceAspect }) => {
  const frame = useCurrentFrame();
  const { durationInFrames, width: frameW, height: frameH } = useVideoConfig();
  const width = box?.width ?? frameW;
  const height = box?.height ?? frameH;

  // Fit the capture to the box width, then push toward the focus.
  const dispW = width;
  const dispH = width / (sourceAspect ?? 1440 / 900);

  const targetZoom = focus ? Math.min(2.1, Math.max(1, 1 / focus.w)) : 1.06;
  const startZoom = focus ? Math.max(1, targetZoom * 0.88) : 1.0;

  const p = interpolate(frame, [0, durationInFrames * settleAt], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.bezier(...EASE),
  });
  const zoom = startZoom + (targetZoom - startZoom) * p;

  // centre of interest in normalized image space
  const cx = focus ? focus.x + focus.w / 2 : 0.5;
  const cy = focus ? focus.y + focus.h / 2 : 0.42;
  const cxNow = 0.5 + (cx - 0.5) * p;
  const cyNow = 0.5 + (cy - 0.5) * p;

  const scaledW = dispW * zoom;
  const scaledH = dispH * zoom;
  // Clamp the pan so the capture always covers the frame. Without this an
  // off-centre focus rect slides the image off an edge and bares the ground —
  // which reads as a broken frame, not a composition.
  const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
  const left = clamp(width / 2 - scaledW * cxNow, width - scaledW, 0);
  const top = clamp(height / 2 - scaledH * cyNow, height - scaledH, 0);

  const enter = interpolate(frame, [0, 18], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(...EASE),
  });

  return (
    <AbsoluteFill style={{ background: c.ground, overflow: 'hidden' }}>
      <div style={{ position: 'absolute', left, top, width: scaledW, height: scaledH, opacity: enter }}>
        <Img src={staticFile(`recordings/${shot}.png`)} style={{ width: '100%', height: '100%', display: 'block' }} />
      </div>
      {/* a calm vignette keeps the eye centred; no glow, no gradient wash */}
      <AbsoluteFill style={{
        background: 'radial-gradient(120% 90% at 50% 45%, rgba(0,0,0,0) 45%, rgba(0,0,0,0.55) 100%)',
        pointerEvents: 'none',
      }} />
      {dim > 0 && <AbsoluteFill style={{ background: `rgba(6,8,10,${dim})` }} />}
    </AbsoluteFill>
  );
};
