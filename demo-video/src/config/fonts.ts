import { continueRender, delayRender, staticFile } from 'remotion'

/**
 * Fonts are bundled rather than fetched, so a render is reproducible offline
 * and never depends on a font CDN being reachable.
 */
const faces = [
  { family: 'Archivo', weight: '400', file: 'fonts/Archivo-400.woff2' },
  { family: 'Archivo', weight: '600', file: 'fonts/Archivo-600.woff2' },
  { family: 'Archivo', weight: '700', file: 'fonts/Archivo-700.woff2' },
  { family: 'IBM Plex Mono', weight: '400', file: 'fonts/IBMPlexMono-400.woff2' },
  { family: 'IBM Plex Mono', weight: '500', file: 'fonts/IBMPlexMono-500.woff2' },
  { family: 'IBM Plex Mono', weight: '600', file: 'fonts/IBMPlexMono-600.woff2' },
]

let loaded = false
export function useBundledFonts(): void {
  if (loaded || typeof document === 'undefined') return
  loaded = true
  const handle = delayRender('bundled fonts')
  Promise.all(
    faces.map(async (f) => {
      const face = new FontFace(f.family, `url(${staticFile(f.file)}) format("woff2")`, { weight: f.weight })
      await face.load()
      ;(document.fonts as unknown as { add: (f: FontFace) => void }).add(face)
    }),
  )
    .then(() => continueRender(handle))
    .catch(() => continueRender(handle))
}
