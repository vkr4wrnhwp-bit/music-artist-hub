import { z } from 'zod'
import { registerSecret } from './redact.js'
import { usdToMicros, type MicroUsd } from './money.js'

const bool = (dflt: boolean) =>
  z
    .string()
    .optional()
    .transform((v) => (v === undefined || v === '' ? dflt : /^(1|true|yes|on)$/i.test(v)))

const num = (dflt: number) =>
  z
    .string()
    .optional()
    .transform((v) => (v === undefined || v === '' ? dflt : Number(v)))
    .pipe(z.number().finite())

const EnvSchema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  LOG_LEVEL: z.enum(['debug', 'info', 'warn', 'error']).default('info'),

  // --- runtime posture -----------------------------------------------------
  /**
   * `sandbox` is the default and the safe state: adapters must use provider
   * sandbox/test modes and no request may be billed. `live` is opt-in and still
   * capped by LIVE_SPEND_CAP_USD.
   */
  MASTERCLIP_MODE: z.enum(['sandbox', 'live']).default('sandbox'),
  LIVE_SPEND_CAP_USD: num(2),

  API_HOST: z.string().default('127.0.0.1'),
  API_PORT: num(4310),
  WEB_PORT: num(4311),
  /** Externally reachable origin, used to build provider webhook callback URLs. */
  PUBLIC_BASE_URL: z.string().default(''),

  // --- persistence ---------------------------------------------------------
  DB_DRIVER: z.enum(['sqlite', 'postgres']).default('sqlite'),
  DATABASE_URL: z.string().default(''),
  SQLITE_PATH: z.string().default('var/masterclip.sqlite'),

  STORAGE_DRIVER: z.enum(['local', 's3']).default('local'),
  STORAGE_LOCAL_ROOT: z.string().default('var/storage'),
  S3_ENDPOINT: z.string().default(''),
  S3_REGION: z.string().default('us-east-1'),
  S3_BUCKET: z.string().default(''),
  S3_ACCESS_KEY_ID: z.string().default(''),
  S3_SECRET_ACCESS_KEY: z.string().default(''),
  S3_FORCE_PATH_STYLE: bool(true),

  // --- secrets -------------------------------------------------------------
  SESSION_SECRET: z.string().default(''),
  ASSET_SIGNING_SECRET: z.string().default(''),
  /** Shared secret for our own outbound->inbound webhook URL signing. */
  WEBHOOK_SECRET: z.string().default(''),
  SECRETS_ENCRYPTION_KEY: z.string().default(''),

  // --- providers -----------------------------------------------------------
  MUAPI_API_KEY: z.string().default(''),
  MUAPI_BASE_URL: z.string().default('https://api.muapi.ai'),
  MUAPI_SANDBOX: bool(true),

  GOOGLE_API_KEY: z.string().default(''),
  GOOGLE_BASE_URL: z.string().default('https://generativelanguage.googleapis.com'),

  FAL_KEY: z.string().default(''),
  FAL_BASE_URL: z.string().default('https://queue.fal.run'),

  RUNWAY_API_KEY: z.string().default(''),
  RUNWAY_BASE_URL: z.string().default('https://api.dev.runwayml.com'),
  RUNWAY_API_VERSION: z.string().default('2024-11-06'),

  LUMA_API_KEY: z.string().default(''),
  LUMA_BASE_URL: z.string().default('https://api.lumalabs.ai'),

  REPLICATE_API_TOKEN: z.string().default(''),
  REPLICATE_BASE_URL: z.string().default('https://api.replicate.com'),

  /** Self-hosted ComfyUI (or compatible) HTTP endpoint. */
  COMFYUI_BASE_URL: z.string().default(''),
  COMFYUI_API_KEY: z.string().default(''),

  ANTHROPIC_API_KEY: z.string().default(''),
  ANTHROPIC_BASE_URL: z.string().default('https://api.anthropic.com'),
  /** Model used for reasoning-heavy producer agents. */
  ANTHROPIC_MODEL: z.string().default('claude-sonnet-5'),
  /** Cheaper model used for first-pass visual QC over extracted frames. */
  ANTHROPIC_QC_MODEL: z.string().default('claude-haiku-4-5'),

  // --- media ---------------------------------------------------------------
  FFMPEG_PATH: z.string().default('ffmpeg'),
  FFPROBE_PATH: z.string().default('ffprobe'),

  // --- worker --------------------------------------------------------------
  WORKER_CONCURRENCY: num(4),
  WORKER_POLL_INTERVAL_MS: num(1000),
  JOB_LEASE_SECONDS: num(120),
  PROVIDER_POLL_INTERVAL_MS: num(5000),
  PROVIDER_JOB_TIMEOUT_MS: num(20 * 60_000),
})

export type RawEnv = z.infer<typeof EnvSchema>

export interface AppConfig extends RawEnv {
  liveSpendCapMicros: MicroUsd
  isSandbox: boolean
  isTest: boolean
}

let cached: AppConfig | null = null

export function loadConfig(source: NodeJS.ProcessEnv = process.env, force = false): AppConfig {
  if (cached && !force) return cached
  const parsed = EnvSchema.safeParse(source)
  if (!parsed.success) {
    const issues = parsed.error.issues.map((i) => `${i.path.join('.')}: ${i.message}`).join('; ')
    throw new Error(`invalid environment configuration: ${issues}`)
  }
  const env = parsed.data
  for (const key of [
    'MUAPI_API_KEY',
    'GOOGLE_API_KEY',
    'FAL_KEY',
    'RUNWAY_API_KEY',
    'LUMA_API_KEY',
    'REPLICATE_API_TOKEN',
    'ANTHROPIC_API_KEY',
    'S3_SECRET_ACCESS_KEY',
    'SESSION_SECRET',
    'ASSET_SIGNING_SECRET',
    'WEBHOOK_SECRET',
    'SECRETS_ENCRYPTION_KEY',
    'COMFYUI_API_KEY',
  ] as const) {
    registerSecret(env[key])
  }
  cached = {
    ...env,
    liveSpendCapMicros: usdToMicros(env.LIVE_SPEND_CAP_USD),
    isSandbox: env.MASTERCLIP_MODE === 'sandbox',
    isTest: env.NODE_ENV === 'test',
  }
  return cached
}

export function resetConfigCache(): void {
  cached = null
}
