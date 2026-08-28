import React from 'react'
import { OffthreadVideo, interpolate, useCurrentFrame, Easing, staticFile } from 'remotion'
import { brand } from '../config/brand'

export interface PlateMove { scale: number; x: number; y: number }

/**
 * The captured interface, treated as a photographed object: seated on the
 * product's own ground, given a hairline border and a contact shadow, and moved
 * with one slow motivated push across the scene.
 *
 * Sized by its parent rather than by AbsoluteFill, so it composes predictably
 * inside grids and columns. An earlier version used AbsoluteFill and escaped
 * its container whenever the parent was not itself positioned — which silently
 * produced an empty half-frame in the metric scene.
 *
 * The move happens INSIDE the frame, so the plate's edges stay fixed and the
 * push reads as a camera move rather than the object sliding around.
 */
export const ScreenPlate: React.FC<{
  clip: string
  durationInFrames: number
  from?: PlateMove
  to?: PlateMove
  startFromS?: number
  radius?: number
}> = ({ clip, durationInFrames, from, to, startFromS = 0, radius = brand.radius }) => {
  const f = useCurrentFrame()
  const a = from ?? { scale: 1, x: 0, y: 0 }
  const b = to ?? a
  const e = interpolate(f, [0, durationInFrames], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.4, 0, 0.2, 1),
  })
  const scale = a.scale + (b.scale - a.scale) * e
  const x = a.x + (b.x - a.x) * e
  const y = a.y + (b.y - a.y) * e
  const fade = interpolate(f, [0, 12], [0, 1], { extrapolateRight: 'clamp' })

  return (
    <div style={{
      position: 'relative', width: '100%', height: '100%',
      display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: fade,
    }}>
      <div style={{
        position: 'relative',
        // Height drives and width follows, so the plate always keeps 16:9 and
        // sits inside its band with visible margin. Setting width:100% here
        // instead let the box become 2.3:1 and silently cropped the interface.
        height: '100%', width: 'auto', aspectRatio: '16 / 9',
        maxWidth: '100%',
        borderRadius: radius,
        overflow: 'hidden',
        border: `1px solid ${brand.color.borderStrong}`,
        boxShadow: '0 50px 120px -35px rgba(0,0,0,0.9), 0 0 0 1px rgba(255,255,255,0.025)',
        background: brand.color.bg,
      }}>
        <div style={{
          position: 'absolute', inset: 0,
          transform: `scale(${scale}) translate(${x}px, ${y}px)`,
          transformOrigin: 'center center',
        }}>
          <OffthreadVideo
            src={staticFile(`recordings/${clip}`)}
            startFrom={Math.round(startFromS * 30)}
            muted
            style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
          />
        </div>
      </div>
    </div>
  )
}

/** A quiet ground: the product's background with a barely-there accent bloom. */
export const Ground: React.FC<{ children?: React.ReactNode }> = ({ children }) => (
  <div style={{ position: 'absolute', inset: 0, background: brand.color.bg }}>
    <div style={{
      position: 'absolute', inset: 0,
      background: `radial-gradient(1200px 700px at 20% 14%, ${brand.color.accentDim}12, transparent 60%)`,
    }} />
    {children}
  </div>
)
