import { Config } from '@remotion/cli/config';

Config.setVideoImageFormat('jpeg');
Config.setOverwriteOutput(true);
Config.setChromiumOpenGlRenderer('swangle');

// This environment blocks remotion.media, so Remotion cannot fetch its own
// headless shell. Chromium and FFmpeg are already on the box for Playwright;
// point Remotion at those instead of downloading anything.
Config.setBrowserExecutable('/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell');
