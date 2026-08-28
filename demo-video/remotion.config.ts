import { Config } from '@remotion/cli/config'

/**
 * This sandbox ships Chromium with old headless mode removed, which is the mode
 * Remotion's bundled launcher asks for. The `chrome-headless-shell` binary
 * beside it is the standalone implementation of exactly that mode, so pointing
 * at it is the supported fix rather than a workaround.
 *
 * On a normal machine leave BROWSER_EXECUTABLE unset and Remotion resolves its
 * own browser.
 */
const HEADLESS_SHELL = '/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell'
if (process.env.REMOTION_BROWSER_EXECUTABLE ?? HEADLESS_SHELL) {
  Config.setBrowserExecutable(process.env.REMOTION_BROWSER_EXECUTABLE ?? HEADLESS_SHELL)
}

Config.setVideoImageFormat('jpeg')
Config.setOverwriteOutput(true)
Config.setChromiumOpenGlRenderer('swangle')
