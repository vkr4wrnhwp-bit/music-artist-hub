/**
 * BRAND TOKENS — the only file that should change when this engine is pointed
 * at a different product.
 *
 * Every colour here is lifted verbatim from the application's own
 * `apps/web/src/styles.css`, so the film cannot drift from the product.
 */
export const brand = {
  product: {
    name: 'MASTERCLIP OS',
    tagline: 'cinematic render factory',
    promise: 'One shot spec. Every provider. One honest number.',
    cta: 'masterclip.onrender.com',
  },

  // Verbatim from apps/web/src/styles.css
  color: {
    bg: '#0a0b0d',
    panel: '#16191e',
    raised: '#121418',
    input: '#0e1013',
    border: '#23282f',
    borderStrong: '#333a44',
    accent: '#d8a657',
    accentDim: '#8a6a37',
    text: '#e8eaed',
    textDim: '#9aa3ae',
    textFaint: '#666e79',
    ok: '#6fbf73',
    warn: '#e0a83c',
    danger: '#e05c5c',
    info: '#6aa9d8',
  },

  font: {
    display: '"Archivo", "Helvetica Neue", Arial, sans-serif',
    mono: '"IBM Plex Mono", ui-monospace, Menlo, monospace',
  },

  // One disciplined scale, used everywhere.
  type: {
    hero: 108,
    title: 64,
    action: 46,
    value: 27,
    label: 20,
    metric: 132,
  },

  radius: 8,
  safe: { x: 132, y: 96 },
} as const

export type Brand = typeof brand
