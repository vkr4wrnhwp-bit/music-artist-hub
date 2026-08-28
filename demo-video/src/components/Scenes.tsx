import React from 'react'
import { interpolate, useCurrentFrame, useVideoConfig, Easing } from 'remotion'
import { brand } from '../config/brand'
import type { Scene } from '../config/film'
import { ScreenPlate, Ground } from './ScreenPlate'
import { ExplainBlock, Eyebrow, MetricCounter, Wordmark, useReveal } from './primitives'

const SANDBOX_NOTE = 'Sandbox capture · local ffmpeg provider · zero spend'

const Fill: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({ children, style }) => (
  <div style={{ position: 'absolute', inset: 0, ...style }}>{children}</div>
)

/** Fades the whole scene out so cuts never flash. */
const useOut = (frames = 10): number => {
  const f = useCurrentFrame()
  const { durationInFrames } = useVideoConfig()
  return interpolate(f, [durationInFrames - frames, durationInFrames], [1, 0], { extrapolateLeft: 'clamp' })
}

/** Opening title. Nothing moves except light. */
export const TitleScene: React.FC<{ scene: Scene }> = ({ scene }) => {
  const t = useReveal(6, 26)
  const sub = useReveal(20, 22)
  const rule = useReveal(14, 30)
  return (
    <Ground>
      <Fill style={{
        display: 'flex', flexDirection: 'column', justifyContent: 'center',
        padding: `0 ${brand.safe.x}px`, opacity: useOut(12),
      }}>
        <div style={{
          fontFamily: brand.font.display, fontWeight: 700, fontSize: brand.type.hero,
          letterSpacing: brand.type.hero * 0.05, color: brand.color.accent,
          opacity: t, transform: `translateY(${(1 - t) * 18}px)`,
        }}>
          {scene.action}
        </div>
        <div style={{ height: 2, width: 420 * rule, background: brand.color.accentDim, margin: '30px 0 26px' }} />
        <div style={{
          fontFamily: brand.font.mono, fontSize: 30, letterSpacing: 5,
          textTransform: 'uppercase', color: brand.color.textDim, opacity: sub,
        }}>
          {scene.value}
        </div>
      </Fill>
    </Ground>
  )
}

/**
 * A workflow beat.
 *
 * Two bands that never overlap: the interface owns the top, the words own the
 * bottom. An earlier version floated the copy over a scrim on top of the
 * interface, which left headlines sitting on review tiles.
 */
export const ScreenScene: React.FC<{ scene: Scene; index: number; total: number }> = ({ scene, index, total }) => {
  const { durationInFrames } = useVideoConfig()
  return (
    <Ground>
      <Fill style={{ display: 'flex', flexDirection: 'column', opacity: useOut() }}>
        {/* header band */}
        <div style={{
          flex: '0 0 74px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: `0 ${brand.safe.x}px`,
        }}>
          <Eyebrow>{`${String(index).padStart(2, '0')} / ${String(total).padStart(2, '0')}`}</Eyebrow>
          <div style={{ fontFamily: brand.font.mono, fontSize: 16, color: brand.color.textFaint, letterSpacing: 1.2 }}>
            {SANDBOX_NOTE}
          </div>
        </div>

        {/* the interface, with genuine margin on every side */}
        <div style={{ flex: 1, minHeight: 0, padding: `0 ${brand.safe.x}px` }}>
          <ScreenPlate
            clip={scene.clip!}
            durationInFrames={durationInFrames}
            from={scene.from}
            to={scene.to}
            startFromS={scene.startFromS}
          />
        </div>

        {/* the words, on clean ground */}
        <div style={{
          flex: '0 0 290px', display: 'flex', alignItems: 'center',
          padding: `0 ${brand.safe.x}px`,
        }}>
          <ExplainBlock action={scene.action!} value={scene.value!} delay={8} accent={scene.accent} />
        </div>
      </Fill>
    </Ground>
  )
}

/** The payoff: interface on one side, the number it produced on the other. */
export const MetricScene: React.FC<{ scene: Scene }> = ({ scene }) => {
  const { durationInFrames } = useVideoConfig()
  const f = useCurrentFrame()
  const slide = interpolate(f, [0, 26], [0, 1], { extrapolateRight: 'clamp', easing: Easing.bezier(0.16, 1, 0.3, 1) })
  return (
    <Ground>
      <Fill style={{ display: 'flex', flexDirection: 'row', alignItems: 'center', opacity: useOut() }}>
        <div style={{
          flex: '0 0 52%', height: '62%',
          paddingLeft: brand.safe.x * 0.6, paddingRight: 40,
          opacity: slide, transform: `translateX(${(1 - slide) * -36}px)`,
        }}>
          <ScreenPlate
            clip={scene.clip!}
            durationInFrames={durationInFrames}
            from={scene.from}
            to={scene.to}
            startFromS={scene.startFromS}
          />
        </div>
        <div style={{
          flex: 1, paddingRight: brand.safe.x,
          display: 'flex', flexDirection: 'column', gap: 42,
        }}>
          <MetricCounter {...scene.metric!} delay={14} />
          <ExplainBlock action={scene.action!} value={scene.value!} delay={30} width={620} />
        </div>
      </Fill>
    </Ground>
  )
}

/** Close: the promise, then the mark. */
export const CloseScene: React.FC<{ scene: Scene }> = ({ scene }) => {
  const a = useReveal(6, 24)
  const b = useReveal(24, 20)
  const rule = useReveal(16, 26)
  return (
    <Ground>
      <Fill style={{
        display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: `0 ${brand.safe.x}px`,
      }}>
        <div style={{
          fontFamily: brand.font.display, fontWeight: 700, fontSize: 62, lineHeight: 1.16,
          color: brand.color.text, maxWidth: 1320, opacity: a,
          transform: `translateY(${(1 - a) * 16}px)`, textWrap: 'balance',
        }}>
          {scene.action}
        </div>
        <div style={{ height: 2, width: 300 * rule, background: brand.color.accentDim, margin: '40px 0 32px' }} />
        <div style={{ opacity: b }}><Wordmark size={34} /></div>
        <div style={{
          marginTop: 18, fontFamily: brand.font.mono, fontSize: 22, color: brand.color.textDim,
          letterSpacing: 2, opacity: b,
        }}>
          {brand.product.cta}
        </div>
      </Fill>
    </Ground>
  )
}
