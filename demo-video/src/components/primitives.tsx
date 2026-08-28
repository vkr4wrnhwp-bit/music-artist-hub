import React from 'react'
import { interpolate, spring, useCurrentFrame, useVideoConfig, Easing } from 'remotion'
import { brand } from '../config/brand'

/** Eased 0→1 over a window, with a hold. Used for every reveal in the film. */
export const useReveal = (delay = 0, dur = 18): number => {
  const f = useCurrentFrame()
  return interpolate(f, [delay, delay + dur], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.16, 1, 0.3, 1),
  })
}

export const useSpringIn = (delay = 0): number => {
  const f = useCurrentFrame()
  const { fps } = useVideoConfig()
  return spring({ frame: f - delay, fps, config: { damping: 200, mass: 0.6 } })
}

/** A word-mark set in the product's own colours. */
export const Wordmark: React.FC<{ size?: number; dim?: boolean }> = ({ size = 26, dim }) => (
  <div style={{ display: 'flex', alignItems: 'baseline', gap: 14 }}>
    <span style={{
      fontFamily: brand.font.display, fontWeight: 700, fontSize: size,
      letterSpacing: size * 0.09, color: dim ? brand.color.textFaint : brand.color.accent,
    }}>
      {brand.product.name}
    </span>
  </div>
)

/**
 * The two-part explanation system: an action label saying what is happening,
 * and a value line saying why the customer cares. Used identically in every
 * scene so the relationship between the two is learned once.
 */
export const ExplainBlock: React.FC<{
  action: string; value: string; delay?: number; accent?: 'accent' | 'ok' | 'danger'; width?: number
}> = ({ action, value, delay = 0, accent = 'accent', width = 1180 }) => {
  const a = useReveal(delay, 16)
  const b = useReveal(delay + 7, 18)
  const rule = useReveal(delay, 22)
  const hue = accent === 'ok' ? brand.color.ok : accent === 'danger' ? brand.color.danger : brand.color.accent
  return (
    <div style={{ width, display: 'flex', gap: 26 }}>
      <div style={{ width: 3, background: hue, transformOrigin: 'top', transform: `scaleY(${rule})`, borderRadius: 2 }} />
      <div>
        <div style={{
          fontFamily: brand.font.display, fontWeight: 700, fontSize: brand.type.action,
          letterSpacing: 0.4, lineHeight: 1.08, color: brand.color.text,
          opacity: a, transform: `translateY(${(1 - a) * 14}px)`, textWrap: 'balance',
        }}>
          {action}
        </div>
        <div style={{
          marginTop: 16, fontFamily: brand.font.display, fontWeight: 400,
          fontSize: brand.type.value, lineHeight: 1.42, color: brand.color.textDim,
          maxWidth: 860, opacity: b, transform: `translateY(${(1 - b) * 10}px)`,
        }}>
          {value}
        </div>
      </div>
    </div>
  )
}

/** A small monospace eyebrow, for scene-level orientation. */
export const Eyebrow: React.FC<{ children: React.ReactNode; delay?: number }> = ({ children, delay = 0 }) => {
  const o = useReveal(delay, 14)
  return (
    <div style={{
      fontFamily: brand.font.mono, fontWeight: 600, fontSize: brand.type.label,
      letterSpacing: 3.4, textTransform: 'uppercase', color: brand.color.textFaint, opacity: o,
    }}>
      {children}
    </div>
  )
}

/** Counts a currency figure up to its final value and holds it. */
export const MetricCounter: React.FC<{ value: string; caption: string; sub?: string; delay?: number }> = ({
  value, caption, sub, delay = 0,
}) => {
  const t = useReveal(delay, 30)
  const numeric = Number(value.replace(/[^0-9.]/g, ''))
  const shown = (numeric * t).toFixed(2)
  const o = useReveal(delay, 12)
  const s = useReveal(delay + 22, 16)
  return (
    <div style={{ opacity: o }}>
      <div style={{
        fontFamily: brand.font.display, fontWeight: 700, fontSize: brand.type.metric,
        color: brand.color.accent, letterSpacing: -2, lineHeight: 1,
        fontVariantNumeric: 'tabular-nums',
      }}>
        ${shown}
      </div>
      <div style={{
        marginTop: 10, fontFamily: brand.font.mono, fontWeight: 500, fontSize: 24,
        letterSpacing: 2.4, textTransform: 'uppercase', color: brand.color.textDim,
      }}>
        {caption}
      </div>
      {sub ? (
        <div style={{
          marginTop: 18, fontFamily: brand.font.mono, fontSize: 20, color: brand.color.ok,
          opacity: s, letterSpacing: 0.4,
        }}>
          {sub}
        </div>
      ) : null}
    </div>
  )
}
