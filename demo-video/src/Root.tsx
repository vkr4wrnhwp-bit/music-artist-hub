import React from 'react'
import { Composition } from 'remotion'
import { Film, totalFrames } from './compositions/Film'
import { FPS, salesOrder, salesDurations, socialOrder, socialDurations } from './config/film'

export const Root: React.FC = () => (
  <>
    <Composition
      id="HeroLandscape" component={Film}
      durationInFrames={totalFrames()} fps={FPS} width={1920} height={1080}
      defaultProps={{}}
    />
    <Composition
      id="SalesLandscape" component={Film}
      durationInFrames={totalFrames(salesOrder, salesDurations)} fps={FPS} width={1920} height={1080}
      defaultProps={{ order: salesOrder, durations: salesDurations }}
    />
    <Composition
      id="SocialVertical" component={Film}
      durationInFrames={totalFrames(socialOrder, socialDurations)} fps={FPS} width={1080} height={1920}
      defaultProps={{ order: socialOrder, durations: socialDurations, vertical: true }}
    />
    <Composition
      id="CleanScreenOnly" component={Film}
      durationInFrames={totalFrames()} fps={FPS} width={1920} height={1080}
      defaultProps={{ clean: true }}
    />
  </>
)
