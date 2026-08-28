import React from 'react';
import { AbsoluteFill, Audio, Easing, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { scenes as allScenes, type Scene } from '../script';
import { brand } from '../brand.config';
import { c, EASE } from '../theme';
import { Copy } from '../components/Copy';
import { Screen } from '../components/Screen';
import { EndCard, StatementCard, TitleCard } from '../components/Cards';
import { TraceMark } from '../components/Marks';

export interface FilmProps {
  /** which scenes to include, in order; omit for the full hero film */
  sceneIds?: string[];
  /** hide the explanation layer for the clean master */
  showCopy?: boolean;
  /** vertical recomposition */
  vertical?: boolean;
  /** scale every scene's duration (used by the cutdowns) */
  pace?: number;
  withAudio?: boolean;
}

export const pickScenes = (ids?: string[]): Scene[] =>
  ids ? (ids.map((id) => allScenes.find((s) => s.id === id)).filter(Boolean) as Scene[]) : allScenes;

/**
 * Sum the *rounded* per-scene lengths, exactly as the sequences below lay them
 * out. Rounding the total instead lands a frame short on the cutdowns, which
 * clips the last frame of the end card.
 */
export const sceneFrames = (s: Scene, fps: number, pace = 1) => Math.round(s.seconds * pace * fps);

export const filmDuration = (fps: number, ids?: string[], pace = 1) =>
  pickScenes(ids).reduce((n, s) => n + sceneFrames(s, fps, pace), 0);

export const Film: React.FC<FilmProps> = ({
  sceneIds, showCopy = true, vertical = false, pace = 1, withAudio = true,
}) => {
  const { fps } = useVideoConfig();
  const list = pickScenes(sceneIds);
  let cursor = 0;

  return (
    <AbsoluteFill style={{ background: c.ground }}>
      {withAudio && <Audio src={staticFile('audio/bed.wav')} volume={0.5} />}
      {list.map((s, i) => {
        const dur = sceneFrames(s, fps, pace);
        // Scenes overlap by a few frames and the incoming one fades up over
        // that window. Without it every cut lands on a frame of bare ground —
        // each scene paints an opaque background and its content starts at
        // zero opacity — which reads as a dropped frame, not as an edit.
        const lead = i === 0 ? 0 : OVERLAP;
        const from = cursor - lead;
        cursor += dur;
        return (
          <Sequence key={s.id} from={from} durationInFrames={dur + lead} name={s.id}>
            <SceneFade frames={lead}>
            {s.kind === 'title' && <TitleCard />}
            {s.kind === 'end' && <EndCard />}
            {s.kind === 'statement' && (
              <StatementCard headline={s.headline ?? ''} why={s.why} />
            )}
            {s.kind === 'screen' && s.shot && (
              vertical
                ? <VerticalScene scene={s} showCopy={showCopy} />
                : (
                  <AbsoluteFill>
                    <Screen
                      shot={`wide/${s.shot}`}
                      focus={s.focus}
                      dim={showCopy && s.copyAt === 'bottom' ? 0.12 : 0}
                    />
                    {showCopy && (
                      <>
                        {/* a controlled scrim so type never sits on busy interface */}
                        <AbsoluteFill style={{ background: scrim(s.copyAt, false), pointerEvents: 'none' }} />
                        <Copy
                          label={s.label}
                          headline={s.headline}
                          why={s.why}
                          at={s.copyAt ?? 'right'}
                          delay={10}
                        />
                      </>
                    )}
                  </AbsoluteFill>
                )
            )}
            </SceneFade>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

/**
 * The vertical cut is composed for its frame, not cropped out of the wide one.
 * A 16:10 capture cannot cover 9:16 without throwing away two thirds of the
 * width, so the product sits in a card on a branded canvas: mark and eyebrow
 * above, the interface in the middle at a size where its type still reads,
 * the headline below on clean ground.
 */
/** frames of cross-dissolve between scenes */
const OVERLAP = 6;

/**
 * Fades a whole scene up over the overlap window. It has to wrap the scene
 * rather than live inside it: each scene paints its own opaque ground, so
 * fading only the contents would still hide the outgoing scene instantly.
 */
const SceneFade: React.FC<{ frames: number; children: React.ReactNode }> = ({ frames, children }) => {
  const frame = useCurrentFrame();
  const o = frames === 0 ? 1 : interpolate(frame, [0, frames], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(...EASE),
  });
  return <AbsoluteFill style={{ opacity: o }}>{children}</AbsoluteFill>;
};

// The portrait capture is square (1080x1080 CSS at 2x). The card shows its
// full width — cropping horizontally would slice the metric columns, which is
// the one thing the vertical cut must not do.
const CARD_W = 1080;
const CARD_H = 820;
const TALL_SOURCE_ASPECT = 1;
// The top and bottom of a 9:16 frame belong to the platform's own chrome, so
// the composition keeps roughly the first 8% and last 15% clear of content.
const MARK_TOP = 150;
const CARD_TOP = 360;

const VerticalScene: React.FC<{ scene: Scene; showCopy: boolean }> = ({ scene, showCopy }) => {
  const frame = useCurrentFrame();
  const enter = interpolate(frame, [0, 22], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(...EASE),
  });
  return (
    <AbsoluteFill style={{ background: c.ground }}>
      {showCopy && (
        <div style={{ position: 'absolute', top: MARK_TOP, left: 72, opacity: enter }}>
          <TraceMark size={116} progress={1} />
        </div>
      )}
      <div style={{
        position: 'absolute', top: CARD_TOP, left: 0, width: CARD_W, height: CARD_H,
        overflow: 'hidden', opacity: enter,
        borderTop: `1px solid ${c.surface}`, borderBottom: `1px solid ${c.surface}`,
      }}>
        <Screen
          shot={`tall/${scene.shot}`}
          focus={scene.focusTall ?? { x: 0, y: 0, w: 1, h: 0.76 }}
          box={{ width: CARD_W, height: CARD_H }}
          sourceAspect={TALL_SOURCE_ASPECT}
        />
        {/* the card is a window onto a longer page — fade its lower edge so it
            reads as one, rather than as a chart chopped in half */}
        <AbsoluteFill style={{
          background: `linear-gradient(to top, ${c.ground} 0%, rgba(11,13,16,0) 16%)`,
          pointerEvents: 'none',
        }} />
      </div>
      {showCopy && (
        <div style={{ position: 'absolute', left: 0, right: 0, top: CARD_TOP + CARD_H + 72, bottom: 0 }}>
          <Copy label={scene.label} headline={scene.headline} why={scene.why} at="top" delay={12} />
        </div>
      )}
    </AbsoluteFill>
  );
};

/**
 * The band the copy sits on. It reaches the ground colour outright across the
 * area the text occupies, then falls away — a partly transparent scrim lets
 * interface text show through behind the headline, which reads as a rendering
 * fault rather than a layer.
 */
const scrim = (at: Scene['copyAt'], vertical: boolean) => {
  const g = c.ground;
  if (vertical || at === 'bottom') {
    return `linear-gradient(to top, ${g} 0%, ${g} 28%, rgba(11,13,16,0.55) 38%, rgba(11,13,16,0) 52%)`;
  }
  const dir = at === 'left' ? 'to right' : 'to left';
  return `linear-gradient(${dir}, ${g} 0%, ${g} 36%, rgba(11,13,16,0.5) 48%, rgba(11,13,16,0) 64%)`;
};

export const FPS = brand.fps;
