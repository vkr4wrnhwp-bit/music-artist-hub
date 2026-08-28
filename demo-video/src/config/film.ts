/**
 * THE FILM — scene data.
 *
 * Copy, timing and footage live here; the components render it. Retargeting the
 * engine to another product means rewriting this file and brand.ts, not the
 * composition code.
 *
 * Every metric quoted below was read off the running application during
 * capture. Nothing is invented.
 */
export interface Scene {
  id: string
  /** Seconds. */
  durationS: number
  clip?: string
  /** Where the plate starts and ends: scale + offset, for a controlled push. */
  from?: { scale: number; x: number; y: number }
  to?: { scale: number; x: number; y: number }
  /** Trim into the source clip, seconds. */
  startFromS?: number
  action?: string
  value?: string
  kind?: 'title' | 'screen' | 'metric' | 'close'
  metric?: { value: string; caption: string; sub?: string }
  accent?: 'accent' | 'ok' | 'danger'
}

const push = (s: number, x = 0, y = 0) => ({ scale: s, x, y })

export const scenes: Scene[] = [
  {
    id: 'title',
    kind: 'title',
    durationS: 5.5,
    action: 'MASTERCLIP OS',
    value: 'Cinematic render factory',
  },
  {
    id: 'shot-spec',
    kind: 'screen',
    durationS: 8,
    clip: '02-shot-spec.mp4',
    startFromS: 0.6,
    from: push(1.0), to: push(1.05, -12, -6),
    action: 'ONE CANONICAL SHOT',
    value: 'Lighting, lens, continuity and rights are written once — every provider renders the same intent.',
  },
  {
    id: 'matrix',
    kind: 'screen',
    durationS: 9.5,
    clip: '03-matrix-priced.mp4',
    startFromS: 1.2,
    from: push(1.01), to: push(1.09, -26, 16),
    action: 'PRICED BEFORE YOU SPEND',
    value: 'You approve a number, not an invoice you find out about afterwards.',
  },
  {
    id: 'queue',
    kind: 'screen',
    durationS: 8,
    clip: '04-queue.mp4',
    startFromS: 0.8,
    from: push(1.03, 0, -8), to: push(1.03, 0, 12),
    action: 'BATCH DISPATCHED',
    value: 'Generation never blocks the desk. A worker carries it from here.',
  },
  {
    id: 'qc',
    kind: 'screen',
    durationS: 12,
    clip: '05-review-qc.mp4',
    startFromS: 5.5,
    from: push(1.04, 0, 0), to: push(1.18, 74, 22),
    action: 'DEFECTS REJECTED AUTOMATICALLY',
    value: 'A black, frozen or duplicate take never costs a human a minute of attention.',
    accent: 'danger',
  },
  {
    id: 'approve',
    kind: 'screen',
    durationS: 11,
    clip: '06-approve.mp4',
    startFromS: 2.2,
    from: push(1.10, -58, 8), to: push(1.15, -70, 4),
    action: 'ONE DECISION PER TAKE',
    value: 'Rejection reasons feed model routing, so the next batch starts better than the last.',
    accent: 'ok',
  },
  {
    id: 'cost',
    kind: 'metric',
    durationS: 11,
    clip: '07-cost-lab.mp4',
    startFromS: 5.4,
    from: push(1.02), to: push(1.09, 0, -22),
    action: 'COST PER APPROVED SECOND',
    value: 'Not cost per render — the only number that reflects footage you can actually ship.',
    metric: { value: '$1.20', caption: 'per approved second', sub: '12 takes auto-rejected · $2.40 spend avoided' },
  },
  {
    id: 'masters',
    kind: 'screen',
    durationS: 7.5,
    clip: '08-masters.mp4',
    startFromS: 5.5,
    from: push(1.02), to: push(1.08, 0, -16),
    action: 'PACKAGED WITH ITS PROVENANCE',
    value: 'Every delivery carries the spec, the seed, the QC record and the cost that produced it.',
  },
  {
    id: 'close',
    kind: 'close',
    durationS: 6,
    action: 'ONE SHOT SPEC. EVERY PROVIDER. ONE HONEST NUMBER.',
    value: 'MASTERCLIP OS',
  },
]

/** Sales cutdown: problem, differentiator, outcome. */
export const salesOrder = ['title', 'matrix', 'qc', 'cost', 'close'] as const
export const salesDurations: Record<string, number> = {
  title: 2.5, matrix: 7, qc: 9, cost: 7, close: 4.5,
}

/** Social: the differentiator and the payoff only. */
export const socialOrder = ['qc', 'cost', 'close'] as const
export const socialDurations: Record<string, number> = { qc: 6, cost: 5, close: 4 }

export const FPS = 30
