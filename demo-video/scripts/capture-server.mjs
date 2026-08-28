#!/usr/bin/env node
/**
 * Boots MASTERCLIP OS for demonstration capture.
 *
 * Identical to the e2e server except for MOCK_GOOD_PATTERN, which art-directs
 * the sandbox's non-defective takes. Defect selection is untouched, so the QC
 * beat in the film is a real rejection of a real broken file.
 *
 * Throwaway database, no provider keys, sandbox mode: nothing here can spend.
 */
import { mkdtempSync, existsSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { spawn } from 'node:child_process'
import { join } from 'node:path'

const APP = process.env.MASTERCLIP_ROOT ?? join(process.cwd(), '..', 'masterclip-os')
const scratch = mkdtempSync(join(tmpdir(), 'masterclip-demo-'))
const port = process.env.DEMO_PORT ?? '4410'

const webDist = join(APP, 'apps/web/dist')
if (!existsSync(join(webDist, 'index.html'))) {
  console.error('web build missing — run `pnpm -F @masterclip/web build` in masterclip-os first')
  process.exit(1)
}

const env = {
  ...process.env,
  NODE_ENV: 'development',
  MASTERCLIP_MODE: 'sandbox',
  LOG_LEVEL: 'warn',
  API_PORT: port,
  API_HOST: '127.0.0.1',
  SQLITE_PATH: join(scratch, 'demo.sqlite'),
  STORAGE_LOCAL_ROOT: join(scratch, 'storage'),
  ASSET_SIGNING_SECRET: 'demo-capture-asset-signing-secret',
  SESSION_SECRET: 'demo-capture-session-secret',
  WEB_ROOT: webDist,
  MOCK_GOOD_PATTERN: 'cinematic',
  // No provider is configured. The film shows the sandbox and says so.
  MUAPI_API_KEY: '', GOOGLE_API_KEY: '', FAL_KEY: '', RUNWAY_API_KEY: '',
  LUMA_API_KEY: '', REPLICATE_API_TOKEN: '', ANTHROPIC_API_KEY: '',
}

const tsx = join(APP, 'node_modules/tsx/dist/cli.mjs')
const children = [
  spawn(process.execPath, [tsx, 'apps/api/src/main.ts'], { cwd: APP, stdio: 'inherit', env }),
  spawn(process.execPath, [tsx, 'apps/worker/src/main.ts'], { cwd: APP, stdio: 'inherit', env }),
]
const stop = (sig) => { for (const c of children) c.kill(sig) }
process.on('SIGTERM', () => stop('SIGTERM'))
process.on('SIGINT', () => stop('SIGINT'))
children[0].on('exit', (code) => { stop('SIGTERM'); process.exit(code ?? 0) })
console.error(`demo server on http://127.0.0.1:${port}  (scratch: ${scratch})`)
