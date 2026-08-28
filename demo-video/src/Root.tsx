import React from 'react';
import { Composition } from 'remotion';
import '@fontsource/archivo/600.css';
import '@fontsource/archivo/700.css';
import '@fontsource/ibm-plex-sans/400.css';
import '@fontsource/ibm-plex-sans/500.css';
import '@fontsource/ibm-plex-mono/500.css';
import { Film, filmDuration, FPS } from './compositions/Film';
import { salesSceneIds, socialSceneIds } from './script';

const L = { width: 1920, height: 1080 };
const V = { width: 1080, height: 1920 };

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="HeroLandscape" component={Film} fps={FPS} {...L}
      durationInFrames={filmDuration(FPS)}
      defaultProps={{ showCopy: true, vertical: false, pace: 1, withAudio: true }}
    />
    <Composition
      id="SalesLandscape" component={Film} fps={FPS} {...L}
      durationInFrames={filmDuration(FPS, salesSceneIds, 0.62)}
      defaultProps={{ sceneIds: salesSceneIds, showCopy: true, vertical: false, pace: 0.62, withAudio: true }}
    />
    <Composition
      id="SocialVertical" component={Film} fps={FPS} {...V}
      durationInFrames={filmDuration(FPS, socialSceneIds, 0.5)}
      defaultProps={{ sceneIds: socialSceneIds, showCopy: true, vertical: true, pace: 0.5, withAudio: true }}
    />
    <Composition
      id="CleanScreenOnly" component={Film} fps={FPS} {...L}
      durationInFrames={filmDuration(FPS)}
      defaultProps={{ showCopy: false, vertical: false, pace: 1, withAudio: false }}
    />
    <Composition
      id="HeroNoAudio" component={Film} fps={FPS} {...L}
      durationInFrames={filmDuration(FPS)}
      defaultProps={{ showCopy: true, vertical: false, pace: 1, withAudio: false }}
    />
  </>
);
