#!/usr/bin/env node
/**
 * Records the hero workflow as discrete video segments.
 *
 * Two passes. The setup pass builds real state — signs up, writes a shot,
 * prices the matrix, submits a batch, and waits for the worker and QC to
 * finish — with no recording, so none of that waiting reaches the film. The
 * capture pass then replays each beat into its own recorded context, which
 * keeps segments short and independently re-shootable.
 *
 * Everything shown is genuine: real MP4s from ffmpeg, real ffprobe QC verdicts,
 * a real ledger. Only the sandbox's visual style is art-directed.
 */
import { chromium } from '/home/user/music-artist-hub/masterclip-os/node_modules/playwright-core/index.mjs'
import { mkdir, writeFile, readdir, rename } from 'node:fs/promises'
import { join } from 'node:path'

const BASE = `http://127.0.0.1:${process.env.DEMO_PORT ?? 4410}`
const OUT = new URL('../recordings/', import.meta.url).pathname
const EXEC = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
const VIEWPORT = { width: 1920, height: 1080 }

const EMAIL = 'producer@summitarts.demo'
const PASSWORD = 'demo-capture-password-2026'

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

/** Moves the pointer along an eased path so the cursor never teleports. */
async function glide(page, to, steps = 26) {
  await page.mouse.move(to.x, to.y, { steps })
}
async function centreOf(locator) {
  const b = await locator.boundingBox()
  if (!b) throw new Error('element has no box')
  return { x: b.x + b.width / 2, y: b.y + b.height / 2 }
}
async function clickDeliberately(page, locator, settle = 700) {
  await locator.scrollIntoViewIfNeeded().catch(() => {})
  await glide(page, await centreOf(locator))
  await sleep(320)            // slow before the decision
  await locator.click()
  await sleep(settle)         // hold so the response is visible
}

async function launch() {
  return chromium.launch({ executablePath: EXEC, args: ['--force-color-profile=srgb', '--font-render-hinting=none'] })
}

// ---------------------------------------------------------------- setup pass
async function setup(browser) {
  const ctx = await browser.newContext({ viewport: VIEWPORT, baseURL: BASE })
  const page = await ctx.newPage()

  await page.goto('/')
  await page.getByRole('button', { name: 'First run? Create the org' }).click()
  await page.getByLabel('Your name').fill('Ava Mercer')
  await page.getByLabel('Organization').fill('Summit Arts')
  await page.getByLabel('Email').fill(EMAIL)
  await page.getByLabel(/^Password/).fill(PASSWORD)
  await page.getByRole('button', { name: 'Create account' }).click()
  await page.getByRole('heading', { name: 'Dashboard' }).waitFor()

  await page.getByPlaceholder('Neon Rain — single').fill('Neon Rain')
  await page.getByRole('button', { name: 'Create project' }).click()
  await page.getByRole('heading', { name: 'Neon Rain' }).waitFor()
  const projectId = page.url().split('/project/')[1] ?? ''

  await page.getByRole('button', { name: 'New shot' }).click()
  await page.getByRole('button', { name: 'Save version' }).waitFor()
  const shotId = (page.url().split('/shot/')[1] ?? '').split('?')[0] ?? ''

  await page.getByLabel('Title').fill('Nova under the sign')
  await page.getByLabel('Duration (s)').fill('4')
  await page.getByLabel('Resolution').selectOption('480p')
  await page.getByRole('button', { name: 'Save version' }).click()
  await sleep(1200)

  await page.locator('select[multiple]').selectOption(['mock|mock-standard'])
  await page.getByLabel('Seeds / variations per model').fill('8')
  await page.getByRole('button', { name: 'Price this matrix' }).click()
  await page.getByText('candidates', { exact: true }).waitFor({ timeout: 30_000 })
  await page.getByRole('button', { name: /Submit \d+ renders/ }).click()
  await page.getByText(/queued \d+ render/).waitFor({ timeout: 60_000 })

  process.stderr.write('setup: batch queued, waiting for the worker…\n')
  const deadline = Date.now() + 600_000
  while (Date.now() < deadline) {
    const r = await page.request.get(`/api/shots/${shotId}/outputs`)
    const { outputs } = await r.json()
    if (outputs.length >= 6) break
    await sleep(4000)
  }
  await sleep(18_000) // let QC + proxies + contact sheets land
  const state = await ctx.storageState()
  await ctx.close()
  return { projectId, shotId, state }
}

// -------------------------------------------------------------- capture pass
async function segment(browser, state, name, fn) {
  const ctx = await browser.newContext({
    viewport: VIEWPORT, baseURL: BASE, storageState: state,
    recordVideo: { dir: OUT, size: VIEWPORT },
  })
  const page = await ctx.newPage()
  await page.addStyleTag({ content: '*{caret-color:transparent!important}' }).catch(() => {})
  await fn(page)
  await ctx.close()
  const files = (await readdir(OUT)).filter((f) => f.endsWith('.webm'))
  const newest = files.map((f) => ({ f, t: f })).sort().at(-1)
  if (newest) await rename(join(OUT, newest.f), join(OUT, `${name}.webm`))
  process.stderr.write(`captured ${name}\n`)
}

async function main() {
  await mkdir(OUT, { recursive: true })
  const browser = await launch()
  const { projectId, shotId, state } = await setup(browser)
  process.stderr.write(`setup complete: project=${projectId} shot=${shotId}\n`)

  await segment(browser, state, '02-shot-spec', async (page) => {
    await page.goto(`/#/shot/${shotId}`); await sleep(2600)
    await page.mouse.move(960, 300, { steps: 20 }); await sleep(1800)
  })

  await segment(browser, state, '03-matrix-priced', async (page) => {
    await page.goto(`/#/shot/${shotId}`); await sleep(1400)
    await page.locator('select[multiple]').selectOption(['mock|mock-standard'])
    await page.getByLabel('Seeds / variations per model').fill('8')
    await sleep(500)
    await clickDeliberately(page, page.getByRole('button', { name: 'Price this matrix' }), 2800)
    await sleep(2200)
  })

  await segment(browser, state, '04-queue', async (page) => {
    await page.goto(`/#/queue/${projectId}`); await sleep(3600)
    await page.mouse.wheel(0, 240); await sleep(2200)
  })

  await segment(browser, state, '05-review-qc', async (page) => {
    await page.goto(`/#/shot/${shotId}/review`); await sleep(3000)
    await page.getByRole('button', { name: 'Play all' }).click().catch(() => {})
    await sleep(4200)
    await page.mouse.wheel(0, 420); await sleep(3200)
  })

  await segment(browser, state, '06-approve', async (page) => {
    await page.goto(`/#/shot/${shotId}/review`); await sleep(2600)
    const approve = page.getByRole('button', { name: 'Approve' }).first()
    await clickDeliberately(page, approve, 2400)
    await sleep(1600)
  })

  await segment(browser, state, '07-cost-lab', async (page) => {
    await page.goto(`/#/costs/${projectId}`); await sleep(2000)
    await clickDeliberately(page, page.getByRole('button', { name: 'Compare' }), 2600)
    await sleep(2400)
  })

  await segment(browser, state, '08-masters', async (page) => {
    await page.goto(`/#/shot/${shotId}/review`); await sleep(1600)
    const promote = page.getByRole('button', { name: 'Promote' }).first()
    if (await promote.isVisible().catch(() => false)) { await clickDeliberately(page, promote, 2200) }
    await page.goto(`/#/masters/${projectId}`); await sleep(3400)
  })

  await browser.close()
  await writeFile(join(OUT, 'manifest.json'), JSON.stringify({ projectId, shotId, viewport: VIEWPORT, base: BASE }, null, 2))
  process.stderr.write('capture complete\n')
}
main().catch((e) => { console.error(e); process.exit(1) })
