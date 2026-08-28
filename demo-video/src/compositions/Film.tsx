import React from 'react'
import { AbsoluteFill, Sequence, useVideoConfig } from 'remotion'
import { brand } from '../config/brand'
import { scenes as allScenes, FPS, type Scene } from '../config/film'
import { useBundledFonts } from '../config/fonts'
import { TitleScene, ScreenScene, MetricScene, CloseScene } from '../components/Scenes'
import { ScreenPlate, Ground } from '../components/ScreenPlate'

export interface FilmProps {
  /** Scene ids to include, in order. Omit for the full hero cut. */
  order?: readonly string[]
  /** Per-scene duration overrides, seconds. */
  durations?: Record<string, number>
  /** Strip every explanatory overlay — the clean deliverable. */
  clean?: boolean
  /** Recompose for a vertical frame instead of cropping the landscape cut. */
  vertical?: boolean
}

export const pickScenes = (order?: readonly string[], durations?: Record<string, number>): Scene[] => {
  const base = order ? order.map((id) => allScenes.find((s) => s.id === id)!).filter(Boolean) : allScenes
  return base.map((s) => ({ ...s, durationS: durations?.[s.id] ?? s.durationS }))
}

export const totalFrames = (order?: readonly string[], durations?: Record<string, number>): number =>
  Math.round(pickScenes(order, durations).reduce((n, s) => n + s.durationS, 0) * FPS)

/** Vertical scenes stack the interface over the copy rather than letterboxing it. */
const VerticalScene: React.FC<{ scene: Scene; index: number; total: number }> = ({ scene }) => {
  const { durationInFrames } = useVideoConfig()
  if (scene.kind === 'close') return <CloseScene scene={scene} />
  return (
    <Ground>
      <AbsoluteFill style={{ flexDirection: 'column', justifyContent: 'center', gap: 64, paddingTop: 40 }}>
        {/* Tall enough to own the frame: an earlier pass left ~470px of dead
            air top and bottom, which reads as a landscape cut dropped into a
            vertical canvas rather than a composition made for it. */}
        <div style={{ width: '100%', height: 900, padding: '0 32px' }}>
          <ScreenPlate
            clip={scene.clip!}
            durationInFrames={durationInFrames}
            from={scene.from}
            to={scene.to}
            startFromS={scene.startFromS}
          />
        </div>
        <div style={{ padding: '0 64px' }}>
          <div style={{
            fontFamily: brand.font.display, fontWeight: 700, fontSize: 60, lineHeight: 1.1,
            color: brand.color.text, textWrap: 'balance',
          }}>
            {scene.action}
          </div>
          <div style={{
            marginTop: 22, fontFamily: brand.font.display, fontSize: 34, lineHeight: 1.38,
            color: brand.color.textDim,
          }}>
            {scene.value}
          </div>
          {scene.metric ? (
            <div style={{
              marginTop: 34, fontFamily: brand.font.display, fontWeight: 700,
              fontSize: 108, color: brand.color.accent, letterSpacing: -1,
            }}>
              {scene.metric.value}
              <span style={{ fontFamily: brand.font.mono, fontSize: 26, color: brand.color.textDim, letterSpacing: 2, marginLeft: 18 }}>
                / APPROVED SEC
              </span>
            </div>
          ) : null}
        </div>
      </AbsoluteFill>
    </Ground>
  )
}

export const Film: React.FC<FilmProps> = ({ order, durations, clean, vertical }) => {
  useBundledFonts()
  const list = pickScenes(order, durations)
  let at = 0
  return (
    <AbsoluteFill style={{ background: brand.color.bg }}>
      {list.map((scene, i) => {
        const frames = Math.round(scene.durationS * FPS)
        const from = at
        at += frames
        return (
          <Sequence key={scene.id} from={from} durationInFrames={frames} name={scene.id}>
            {clean ? (
              scene.clip ? (
                <Ground>
                  <div style={{ position: 'absolute', inset: 0, padding: 92 }}>
                    <ScreenPlate
                      clip={scene.clip}
                      durationInFrames={frames}
                      from={scene.from}
                      to={scene.to}
                      startFromS={scene.startFromS}
                    />
                  </div>
                </Ground>
              ) : (
                <Ground />
              )
            ) : vertical ? (
              <VerticalScene scene={scene} index={i + 1} total={list.length} />
            ) : scene.kind === 'title' ? (
              <TitleScene scene={scene} />
            ) : scene.kind === 'close' ? (
              <CloseScene scene={scene} />
            ) : scene.kind === 'metric' ? (
              <MetricScene scene={scene} />
            ) : (
              <ScreenScene scene={scene} index={i + 1} total={list.length} />
            )}
          </Sequence>
        )
      })}
    </AbsoluteFill>
  )
}
