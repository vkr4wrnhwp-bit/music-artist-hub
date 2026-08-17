import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { silentLogger } from '@masterclip/shared'
import { contractSummary, runProviderContract, sampleRequest } from '@masterclip/provider-core'
import { probe } from '@masterclip/media-tools'
import { createMockProvider } from '../src/index.js'

let dir: string
const deps = () => ({ logger: silentLogger, sandbox: true, publicBaseUrl: 'http://localhost:4310', now: () => Date.now() })

beforeAll(async () => {
  dir = await mkdtemp(join(tmpdir(), 'masterclip-mock-test-'))
})
afterAll(async () => {
  await rm(dir, { recursive: true, force: true })
})

describe('provider contract', () => {
  it('passes the full battery including a real submit/poll/download round trip', async () => {
    const provider = createMockProvider({ ...deps(), workDir: join(dir, 'work'), latencyMs: 50, defectRate: 0, failureRate: 0 })
    const checks = await runProviderContract(provider, { submitAndPoll: true, destDir: join(dir, 'downloads'), pollTimeoutMs: 30_000 })
    const summary = contractSummary(checks)
    expect(summary.failures.map((f) => `${f.name}: ${f.detail}`)).toEqual([])
    expect(summary.failed).toBe(0)
    expect(summary.passed).toBeGreaterThan(10)
  })
})

describe('mock provider', () => {
  it('produces a genuinely decodable file at the requested geometry', async () => {
    const provider = createMockProvider({ ...deps(), workDir: join(dir, 'geo'), latencyMs: 0, defectRate: 0, failureRate: 0 })
    const request = sampleRequest({ providerId: 'mock', modelId: 'mock-standard', mode: 'text_to_video', durationSeconds: 4, resolution: '720p', aspectRatio: '9:16' })
    const submitted = await provider.submit(request)
    const status = await provider.getStatus(submitted.externalJobId)
    expect(status.state).toBe('succeeded')

    const assets = await provider.downloadOutputs({ externalJobId: submitted.externalJobId, outputs: status.outputs }, join(dir, 'geo-out'))
    const info = await probe(assets[0]?.localPath ?? '')
    // 720p vertical is 720 wide by 1280 tall — the label names the short edge.
    expect(info.video?.width).toBe(720)
    expect(info.video?.height).toBe(1280)
    expect(info.durationSeconds).toBeCloseTo(4, 0)
    expect(assets[0]?.sha256).toHaveLength(64)
  })

  it('is deterministic — the same request id always behaves identically', async () => {
    const make = () => createMockProvider({ ...deps(), workDir: join(dir, `det-${Math.random()}`), latencyMs: 0, defectRate: 1, failureRate: 0 })
    const request = sampleRequest({ requestId: 'job_fixed_seed', providerId: 'mock', modelId: 'mock-draft', mode: 'text_to_video', durationSeconds: 4, resolution: '480p' })
    const a = (await make().submit(request)).raw as { pattern: string }
    const b = (await make().submit(request)).raw as { pattern: string }
    expect(a.pattern).toBe(b.pattern)
    expect(a.pattern).not.toBe('motion')
  })

  it('emits defective renders at the configured rate, so QC has something to catch', async () => {
    const provider = createMockProvider({ ...deps(), workDir: join(dir, 'defects'), latencyMs: 0, defectRate: 1, failureRate: 0 })
    const patterns = new Set<string>()
    for (let i = 0; i < 12; i++) {
      const submitted = await provider.submit(
        sampleRequest({ requestId: `job_${i}`, providerId: 'mock', modelId: 'mock-draft', mode: 'text_to_video', durationSeconds: 4, resolution: '480p' }),
      )
      patterns.add((submitted.raw as { pattern: string }).pattern)
    }
    expect(patterns.has('motion')).toBe(false)
    expect(patterns.size).toBeGreaterThan(1)
  })

  it('reports a simulated provider-side failure as a retryable error', async () => {
    const provider = createMockProvider({ ...deps(), workDir: join(dir, 'fail'), latencyMs: 0, defectRate: 0, failureRate: 1 })
    const submitted = await provider.submit(sampleRequest({ providerId: 'mock', modelId: 'mock-draft', mode: 'text_to_video', durationSeconds: 4, resolution: '480p' }))
    const status = await provider.getStatus(submitted.externalJobId)
    expect(status.state).toBe('failed')
    expect(status.error?.retryable).toBe(true)
  })

  it('refuses a request its model cannot satisfy instead of rendering something else', async () => {
    const provider = createMockProvider({ ...deps(), workDir: join(dir, 'reject'), latencyMs: 0 })
    await expect(
      provider.submit(sampleRequest({ providerId: 'mock', modelId: 'mock-draft', mode: 'text_to_video', durationSeconds: 4, resolution: '2160p' })),
    ).rejects.toThrow(/mock rejected the request/)
  })

  it('prices with an exact quote bound to the request', async () => {
    const provider = createMockProvider({ ...deps(), workDir: join(dir, 'price'), latencyMs: 0 })
    const request = sampleRequest({ providerId: 'mock', modelId: 'mock-standard', mode: 'text_to_video', durationSeconds: 8, resolution: '720p' })
    const quote = await provider.quote(request)
    expect(quote.confidence).toBe('exact')
    expect(quote.source).toBe('provider_quote')
    expect(quote.estimatedMicros).toBe(400_000)
  })

  it('reports its own health honestly based on ffmpeg availability', async () => {
    const provider = createMockProvider({ ...deps(), workDir: join(dir, 'health'), latencyMs: 0 })
    const health = await provider.healthCheck()
    expect(health.status).toBe('healthy')
    expect(health.providerId).toBe('mock')
  })
})
