import { type Db, insertRow, toNum, toStr } from '@masterclip/database'
import { newId, systemClock, type Clock, type MicroUsd } from '@masterclip/shared'

export type LedgerEntryType = 'estimate' | 'charge' | 'refund' | 'adjustment' | 'qc' | 'agent'

export interface LedgerEntry {
  orgId: string
  projectId?: string | null
  sceneId?: string | null
  shotId?: string | null
  batchId?: string | null
  jobId?: string | null
  attemptId?: string | null
  outputId?: string | null
  providerId: string
  modelId: string
  entryType: LedgerEntryType
  micros: MicroUsd
  credits?: number | null
  billableSeconds?: number | null
  quoteId?: string | null
  externalRequestId?: string | null
  sandbox: boolean
  note?: string
  createdBy: string
}

export interface SpendWindow {
  since?: string
  until?: string
  /** Sandbox spend is simulated; it is excluded by default. */
  includeSandbox?: boolean
}

/**
 * Append-only cost ledger.
 *
 * Nothing updates or deletes a row here. `estimate` rows are written before a
 * submission and `charge` rows after, so the variance between what we expected
 * to pay and what we were actually billed is a query, not a guess.
 */
export class CostLedger {
  constructor(
    private readonly db: Db,
    private readonly clock: Clock = systemClock,
  ) {}

  async append(entry: LedgerEntry): Promise<string> {
    const id = newId('ledg', this.clock.now())
    await insertRow(this.db, 'cost_ledger', {
      id,
      org_id: entry.orgId,
      project_id: entry.projectId ?? null,
      scene_id: entry.sceneId ?? null,
      shot_id: entry.shotId ?? null,
      batch_id: entry.batchId ?? null,
      job_id: entry.jobId ?? null,
      attempt_id: entry.attemptId ?? null,
      output_id: entry.outputId ?? null,
      provider_id: entry.providerId,
      model_id: entry.modelId,
      entry_type: entry.entryType,
      micros: Math.round(entry.micros),
      credits: entry.credits ?? null,
      billable_seconds: entry.billableSeconds ?? null,
      quote_id: entry.quoteId ?? null,
      external_request_id: entry.externalRequestId ?? null,
      sandbox: entry.sandbox ? 1 : 0,
      note: entry.note ?? '',
      created_by: entry.createdBy,
      created_at: this.clock.isoNow(),
    })
    return id
  }

  /**
   * Actual spend for a scope. Only `charge`/`refund`/`adjustment` count —
   * estimates are intentions, and summing them would double-bill every job.
   */
  async spend(scope: 'org' | 'project' | 'scene' | 'shot' | 'batch', scopeId: string, window: SpendWindow = {}): Promise<MicroUsd> {
    const column = { org: 'org_id', project: 'project_id', scene: 'scene_id', shot: 'shot_id', batch: 'batch_id' }[scope]
    const clauses = [`${column} = ?`, `entry_type IN ('charge','refund','adjustment','qc','agent')`]
    const params: Array<string | number> = [scopeId]
    if (!window.includeSandbox) clauses.push('sandbox = 0')
    if (window.since) {
      clauses.push('created_at >= ?')
      params.push(window.since)
    }
    if (window.until) {
      clauses.push('created_at < ?')
      params.push(window.until)
    }
    const row = await this.db.get<{ total: number | null }>(
      `SELECT SUM(micros) AS total FROM cost_ledger WHERE ${clauses.join(' AND ')}`,
      params,
    )
    return toNum(row?.total, 0)
  }

  /** Live (non-sandbox) spend across every org. Backs the hard live-spend cap. */
  async totalLiveSpend(): Promise<MicroUsd> {
    const row = await this.db.get<{ total: number | null }>(
      `SELECT SUM(micros) AS total FROM cost_ledger WHERE sandbox = 0 AND entry_type IN ('charge','refund','adjustment','qc','agent')`,
    )
    return toNum(row?.total, 0)
  }

  async byProvider(projectId: string, window: SpendWindow = {}): Promise<Array<{ providerId: string; modelId: string; micros: MicroUsd; entries: number }>> {
    const clauses = ['project_id = ?', `entry_type IN ('charge','refund','adjustment')`]
    const params: Array<string | number> = [projectId]
    if (!window.includeSandbox) clauses.push('sandbox = 0')
    const rows = await this.db.query<{ provider_id: string; model_id: string; total: number; n: number }>(
      `SELECT provider_id, model_id, SUM(micros) AS total, COUNT(*) AS n
         FROM cost_ledger WHERE ${clauses.join(' AND ')}
         GROUP BY provider_id, model_id ORDER BY total DESC`,
      params,
    )
    return rows.map((r) => ({ providerId: toStr(r.provider_id), modelId: toStr(r.model_id), micros: toNum(r.total), entries: toNum(r.n) }))
  }

  async byDay(orgId: string, days = 30, includeSandbox = false): Promise<Array<{ day: string; micros: MicroUsd }>> {
    const since = new Date(this.clock.now() - days * 86_400_000).toISOString()
    const rows = await this.db.query<{ day: string; total: number }>(
      `SELECT substr(created_at, 1, 10) AS day, SUM(micros) AS total
         FROM cost_ledger
        WHERE org_id = ? AND created_at >= ? AND entry_type IN ('charge','refund','adjustment')
          ${includeSandbox ? '' : 'AND sandbox = 0'}
        GROUP BY substr(created_at, 1, 10) ORDER BY day ASC`,
      [orgId, since],
    )
    return rows.map((r) => ({ day: toStr(r.day), micros: toNum(r.total) }))
  }

  /** Estimate-vs-charge variance for a job, used to catch mispriced adapters. */
  async variance(jobId: string): Promise<{ estimated: MicroUsd; charged: MicroUsd; deltaMicros: MicroUsd }> {
    const rows = await this.db.query<{ entry_type: string; total: number }>(
      `SELECT entry_type, SUM(micros) AS total FROM cost_ledger WHERE job_id = ? GROUP BY entry_type`,
      [jobId],
    )
    const estimated = toNum(rows.find((r) => toStr(r.entry_type) === 'estimate')?.total, 0)
    const charged = toNum(rows.find((r) => toStr(r.entry_type) === 'charge')?.total, 0)
    return { estimated, charged, deltaMicros: charged - estimated }
  }

  async entriesFor(projectId: string, limit = 500): Promise<Array<Record<string, unknown>>> {
    return this.db.query(`SELECT * FROM cost_ledger WHERE project_id = ? ORDER BY created_at DESC LIMIT ${Math.floor(limit)}`, [
      projectId,
    ])
  }
}
