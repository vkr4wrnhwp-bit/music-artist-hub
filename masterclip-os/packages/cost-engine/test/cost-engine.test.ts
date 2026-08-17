import { beforeEach, describe, expect, it } from 'vitest'
import { createTestDb, insertRow, type Db } from '@masterclip/database'
import { fixedClock, loadConfig, usdToMicros } from '@masterclip/shared'
import { estimateFromFormula, perSecondUsd, quoteFromProvider, sampleRequest } from '@masterclip/provider-core'
import { BudgetStore, CostController, CostLedger, MetricsService, windowBounds } from '../src/index.js'

let db: Db
const clock = fixedClock(Date.UTC(2026, 7, 17, 12, 0, 0))
const ORG = 'org_test'
const PROJECT = 'proj_test'
const SHOT = 'shot_test'

beforeEach(async () => {
  db = await createTestDb()
  await insertRow(db, 'orgs', { id: ORG, name: 'Test', created_at: clock.isoNow() })
  await insertRow(db, 'projects', {
    id: PROJECT,
    org_id: ORG,
    name: 'P',
    slug: 'p',
    brief: '',
    style_bible: '{}',
    status: 'active',
    created_at: clock.isoNow(),
    updated_at: clock.isoNow(),
    archived_at: null,
  })
})

function config(overrides: Record<string, string> = {}) {
  return loadConfig({ NODE_ENV: 'test', MASTERCLIP_MODE: 'live', LIVE_SPEND_CAP_USD: '2', ...overrides }, true)
}

function quoteFor(usd: number, seconds = 8) {
  const request = sampleRequest({ durationSeconds: seconds, maxCostMicros: usdToMicros(5), sandbox: false })
  return { request, quote: quoteFromProvider({ providerId: 'mock', request, micros: usdToMicros(usd), nowMs: clock.now(), raw: {} }) }
}

describe('append-only ledger', () => {
  it('sums only charges, never estimates', async () => {
    const ledger = new CostLedger(db, clock)
    const base = { orgId: ORG, projectId: PROJECT, shotId: SHOT, providerId: 'mock', modelId: 'm', sandbox: false, createdBy: 'test' }
    await ledger.append({ ...base, entryType: 'estimate', micros: usdToMicros(1) })
    await ledger.append({ ...base, entryType: 'charge', micros: usdToMicros(0.9) })
    await ledger.append({ ...base, entryType: 'refund', micros: usdToMicros(-0.4) })

    expect(await ledger.spend('project', PROJECT)).toBe(usdToMicros(0.5))
    const variance = await ledger.variance('')
    expect(variance.estimated).toBe(0)
  })

  it('keeps sandbox spend out of live totals by default', async () => {
    const ledger = new CostLedger(db, clock)
    const base = { orgId: ORG, projectId: PROJECT, providerId: 'mock', modelId: 'm', createdBy: 'test' }
    await ledger.append({ ...base, entryType: 'charge', micros: usdToMicros(50), sandbox: true })
    await ledger.append({ ...base, entryType: 'charge', micros: usdToMicros(1), sandbox: false })

    expect(await ledger.totalLiveSpend()).toBe(usdToMicros(1))
    expect(await ledger.spend('project', PROJECT)).toBe(usdToMicros(1))
    expect(await ledger.spend('project', PROJECT, { includeSandbox: true })).toBe(usdToMicros(51))
  })

  it('reports estimate-versus-charge variance per job', async () => {
    const ledger = new CostLedger(db, clock)
    const base = { orgId: ORG, projectId: PROJECT, jobId: 'job_1', providerId: 'mock', modelId: 'm', sandbox: false, createdBy: 'test' }
    await ledger.append({ ...base, entryType: 'estimate', micros: usdToMicros(0.4) })
    await ledger.append({ ...base, entryType: 'charge', micros: usdToMicros(0.55) })
    const variance = await ledger.variance('job_1')
    expect(variance.deltaMicros).toBe(usdToMicros(0.15))
  })
})

describe('budget enforcement', () => {
  it('authorizes a render inside every cap', async () => {
    const controller = new CostController(db, config(), clock)
    const { request, quote } = quoteFor(0.4)
    const result = await controller.authorize({ orgId: ORG, projectId: PROJECT, shotId: SHOT, request, quote, tier: 'standard', humanApproved: true })
    expect(result.allowed).toBe(true)
  })

  it("refuses a render above the shot's own max_cost_usd", async () => {
    const controller = new CostController(db, config(), clock)
    const request = sampleRequest({ durationSeconds: 8, maxCostMicros: usdToMicros(0.25), sandbox: false })
    const quote = quoteFromProvider({ providerId: 'mock', request, micros: usdToMicros(0.4), nowMs: clock.now(), raw: {} })
    const result = await controller.authorize({ orgId: ORG, projectId: PROJECT, shotId: SHOT, request, quote, tier: 'standard', humanApproved: true })
    expect(result.allowed).toBe(false)
    expect(result.denials.map((d) => d.code)).toContain('budget.shot_cap')
  })

  it('refuses once the per-shot budget is consumed', async () => {
    const controller = new CostController(db, config(), clock)
    await controller.budgetStore.set({ ...(await controller.budgetStore.ensureDefaults('project', PROJECT)), perShotCapMicros: usdToMicros(1) })
    await controller.costLedger.append({
      orgId: ORG,
      projectId: PROJECT,
      shotId: SHOT,
      providerId: 'mock',
      modelId: 'm',
      entryType: 'charge',
      micros: usdToMicros(0.9),
      sandbox: false,
      createdBy: 'test',
    })

    const { request, quote } = quoteFor(0.4)
    const result = await controller.authorize({ orgId: ORG, projectId: PROJECT, shotId: SHOT, request, quote, tier: 'standard', humanApproved: true })
    expect(result.allowed).toBe(false)
    expect(result.denials.map((d) => d.code)).toContain('budget.shot_cap')
  })

  it('enforces the global live-spend cap regardless of project budgets', async () => {
    const controller = new CostController(db, config({ LIVE_SPEND_CAP_USD: '2' }), clock)
    await controller.costLedger.append({
      orgId: ORG,
      projectId: PROJECT,
      providerId: 'mock',
      modelId: 'm',
      entryType: 'charge',
      micros: usdToMicros(1.9),
      sandbox: false,
      createdBy: 'test',
    })

    const { request, quote } = quoteFor(0.4)
    const result = await controller.authorize({ orgId: ORG, projectId: PROJECT, shotId: SHOT, request, quote, tier: 'standard', humanApproved: true })
    expect(result.allowed).toBe(false)
    expect(result.denials.map((d) => d.code)).toContain('spend.live_cap')
    expect(result.denials.find((d) => d.code === 'spend.live_cap')?.message).toMatch(/LIVE_SPEND_CAP_USD/)
  })

  it('blocks every billable submission while the mode is sandbox', async () => {
    const controller = new CostController(db, config({ MASTERCLIP_MODE: 'sandbox' }), clock)
    const { request, quote } = quoteFor(0.4)
    const result = await controller.authorize({ orgId: ORG, projectId: PROJECT, shotId: SHOT, request, quote, tier: 'standard', humanApproved: true })
    expect(result.denials.map((d) => d.code)).toContain('mode.sandbox_required')
  })

  it('requires human approval for premium renders', async () => {
    const controller = new CostController(db, config(), clock)
    const { request, quote } = quoteFor(0.4)
    const denied = await controller.authorize({ orgId: ORG, projectId: PROJECT, shotId: SHOT, request, quote, tier: 'premium' })
    expect(denied.allowed).toBe(false)
    expect(denied.requiresHumanApproval).toBe(true)

    const approved = await controller.authorize({ orgId: ORG, projectId: PROJECT, shotId: SHOT, request, quote, tier: 'premium', humanApproved: true })
    expect(approved.allowed).toBe(true)
  })

  it('refuses a stale quote', async () => {
    const controller = new CostController(db, config(), clock)
    const { request, quote } = quoteFor(0.4)
    const result = await controller.authorize({
      orgId: ORG,
      projectId: PROJECT,
      shotId: SHOT,
      request,
      quote,
      tier: 'standard',
      humanApproved: true,
      nowMs: clock.now() + 20 * 60_000,
    })
    expect(result.denials.map((d) => d.code)).toContain('quote.expired')
  })

  it('refuses a live submission whose price is unknown', async () => {
    const controller = new CostController(db, config(), clock)
    const request = sampleRequest({ durationSeconds: 8, maxCostMicros: usdToMicros(5), sandbox: false })
    const quote = estimateFromFormula(
      'mock',
      request,
      { ...perSecondUsd(0, { retrievedAt: '2026-08-17', sourceUrl: 'x' }), basis: 'unknown' },
      clock.now(),
    )
    const result = await controller.authorize({ orgId: ORG, projectId: PROJECT, shotId: SHOT, request, quote, tier: 'standard', humanApproved: true })
    expect(result.allowed).toBe(false)
    expect(result.denials.map((d) => d.message).join(' ')).toMatch(/no confident price/)
  })

  it('warns before it denies, at the configured threshold', async () => {
    const controller = new CostController(db, config(), clock)
    await controller.budgetStore.set({ ...(await controller.budgetStore.ensureDefaults('project', PROJECT)), perShotCapMicros: usdToMicros(1), warnThresholdPct: 50 })
    const { request, quote } = quoteFor(0.6)
    const result = await controller.authorize({ orgId: ORG, projectId: PROJECT, shotId: SHOT, request, quote, tier: 'standard', humanApproved: true })
    expect(result.allowed).toBe(true)
    expect(result.warnings.join(' ')).toMatch(/shot budget at/)
  })
})

describe('budget windows', () => {
  it('computes UTC day and month boundaries', () => {
    const bounds = windowBounds(Date.UTC(2026, 7, 17, 23, 59, 59))
    expect(bounds.dayStart).toBe('2026-08-17T00:00:00.000Z')
    expect(bounds.monthStart).toBe('2026-08-01T00:00:00.000Z')
  })

  it('persists and reloads a budget', async () => {
    const store = new BudgetStore(db, clock)
    const budget = await store.ensureDefaults('project', PROJECT)
    await store.set({ ...budget, dailyCapMicros: usdToMicros(12.5), maxPremiumAttempts: 1 })
    const reloaded = await store.get('project', PROJECT)
    expect(reloaded?.dailyCapMicros).toBe(usdToMicros(12.5))
    expect(reloaded?.maxPremiumAttempts).toBe(1)
  })
})

describe('metrics', () => {
  it('returns null rather than a fabricated cost when nothing is approved', async () => {
    const metrics = new MetricsService(db, clock)
    const result = await metrics.projectMetrics(PROJECT)
    expect(result.costPerApprovedSecond).toBeNull()
    expect(result.approvalRate).toBeNull()
    expect(result.submittedCount).toBe(0)
  })
})
