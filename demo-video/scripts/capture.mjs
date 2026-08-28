/**
 * DETERMINISTIC CAPTURE RIG
 *
 * Drives the real application through a shot list and writes high-density
 * stills into public/recordings. Deterministic by construction: the app's data
 * is seeded, demo mode is set before first paint, and every shot waits for the
 * page to settle so nothing is captured mid-animation.
 *
 * Reuse: point APP at another product, rewrite the shot list, keep this file.
 */
import { createRequire } from 'node:module';
import { mkdirSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { APP, PERSONA, shots, variants } from './shots.trace.mjs';

// Playwright may be a local dependency or provided by the environment.
const require = createRequire(import.meta.url);
const loadChromium = () => {
  for (const id of ['playwright', '/opt/node22/lib/node_modules/playwright']) {
    try { return require(id).chromium; } catch { /* try next */ }
  }
  throw new Error('playwright not found — npm i -D playwright, or set it on the system');
};
const chromium = loadChromium();

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const OUT = join(ROOT, 'public', 'recordings');

// Capture larger than delivery so push-ins stay sharp: every variant is shot
// at 2x device scale, so a 1440x900 viewport yields 2880x1800.
const SCALE = 2;

const run = async () => {
  rmSync(OUT, { recursive: true, force: true });
  mkdirSync(OUT, { recursive: true });

  const browser = await chromium.launch();
  const errors = [];

  for (const variant of variants) {
    mkdirSync(join(OUT, variant.dir), { recursive: true });
    await captureVariant(browser, variant, errors);
  }

  console.log(errors.length ? `\npageerrors: ${errors.slice(0, 3).join(' | ')}` : '\npageerrors: none');
  await browser.close();
};

const captureVariant = async (browser, variant, errors) => {
  const ctx = await browser.newContext({
    viewport: variant.viewport,
    deviceScaleFactor: SCALE,
    reducedMotion: 'no-preference',
  });
  const page = await ctx.newPage();
  page.on('pageerror', (e) => errors.push(e.message));

  // demo mode + persona before first paint: no picker, no auth round trip,
  // and no chance of a half-rendered first frame
  await page.addInitScript(([p]) => {
    localStorage.setItem('mx-lab-demo-mode', '1');
    localStorage.setItem('mx-lab-user', p);
    localStorage.setItem('mx-lab-tutor', '0');
  }, [PERSONA]);

  for (const shot of shots) {
    // A hash-only change is a fragment navigation: the SPA stays mounted and
    // component state (the active session tab, for one) survives. Reload so
    // every shot renders from the route alone and captures are order-independent.
    await page.goto(APP + shot.route);
    await page.reload();
    await page.waitForLoadState('networkidle').catch(() => {});
    await page.waitForTimeout(shot.settle ?? 1200);
    if (shot.prep) await shot.prep(page);
    // settle scroll so framing is repeatable: the top of the page unless the
    // shot names the element it wants in frame
    if (shot.scrollTo) {
      // scrollIntoViewIfNeeded is a no-op when the element is already partly
      // visible, which is exactly the case worth reframing. Force it to the
      // top of the viewport, less a margin so the panel keeps its header.
      const target = page.locator(shot.scrollTo).first();
      await target.waitFor({ state: 'visible' });
      await target.evaluate((el, margin) => {
        el.scrollIntoView({ block: 'start' });
        window.scrollBy(0, -margin);
      }, shot.scrollMargin ?? 28);
    } else {
      await page.evaluate(() => window.scrollTo(0, 0));
    }
    await page.waitForTimeout(400);
    await page.screenshot({ path: join(OUT, variant.dir, `${shot.name}.png`) });
    console.log(`  ${variant.dir.padEnd(4)} ${shot.name.padEnd(11)} ${shot.route}`);
  }
  await ctx.close();
};

run();
