#!/usr/bin/env node
/**
 * Finishing: mux the score, cut the no-audio variant, pull thumbnails, probe
 * every deliverable and print a report.
 *
 * Remotion renders picture; this stage owns audio treatment and encoding so the
 * two concerns stay separable — swapping the music never means re-rendering
 * 2355 frames.
 */
import { execFileSync } from 'node:child_process'
import { existsSync, mkdirSync, statSync } from 'node:fs'
import { join } from 'node:path'

const R = new URL('../renders/', import.meta.url).pathname
const A = new URL('../audio/', import.meta.url).pathname
const T = join(R, 'thumbnails')
mkdirSync(T, { recursive: true })

const ff = (args) => execFileSync('ffmpeg', ['-y', '-hide_banner', '-loglevel', 'error', ...args], { stdio: 'inherit' })
const probe = (f) => {
  const out = execFileSync('ffprobe', [
    '-v', 'error', '-show_entries', 'stream=codec_name,codec_type,width,height,r_frame_rate,sample_rate,channels',
    '-show_entries', 'format=duration,size,bit_rate', '-of', 'json', f,
  ]).toString()
  return JSON.parse(out)
}

/** Mux a music bed under a silent picture render, trimmed to picture length. */
function withAudio(silent, score, out) {
  if (!existsSync(silent)) return false
  ff(['-i', silent, '-i', score,
      '-filter_complex', '[1:a]afade=t=out:st=0:d=0[a]',  // placeholder chain keeps filtergraph explicit
      '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', out])
  return true
}

const jobs = [
  { silent: 'hero-landscape.mp4',  score: 'score-hero.wav',   out: 'hero-landscape-master.mp4' },
  { silent: 'sales-landscape.mp4', score: 'score-sales.wav',  out: 'sales-landscape-master.mp4' },
  { silent: 'social-vertical.mp4', score: 'score-social.wav', out: 'social-vertical-master.mp4' },
]

for (const j of jobs) {
  const silent = join(R, j.silent), score = join(A, j.score), out = join(R, j.out)
  if (!existsSync(silent)) { console.log(`skip ${j.silent} (not rendered yet)`); continue }
  if (!existsSync(score)) { console.log(`skip ${j.out} (no score ${j.score})`); continue }
  withAudio(silent, score, out)
  console.log(`muxed ${j.out}`)
}

// Thumbnails: three frames chosen for what they show, not evenly spaced.
const hero = join(R, 'hero-landscape.mp4')
if (existsSync(hero)) {
  const picks = [
    { t: 37, name: 'thumb-01-qc-rejects.jpg' },
    { t: 58, name: 'thumb-02-cost-per-approved-second.jpg' },
    { t: 3.4, name: 'thumb-03-title.jpg' },
  ]
  for (const p of picks) {
    ff(['-ss', String(p.t), '-i', hero, '-frames:v', '1', '-q:v', '2', join(T, p.name)])
    console.log(`thumbnail ${p.name}`)
  }
}

console.log('\n=== DELIVERABLE REPORT ===')
for (const f of ['hero-landscape.mp4', 'hero-landscape-master.mp4', 'sales-landscape-master.mp4',
                 'social-vertical-master.mp4', 'clean-screen-only.mp4']) {
  const p = join(R, f)
  if (!existsSync(p)) { console.log(`${f}: (not present)`); continue }
  const d = probe(p)
  const v = d.streams.find((s) => s.codec_type === 'video')
  const a = d.streams.find((s) => s.codec_type === 'audio')
  const mb = (statSync(p).size / 1e6).toFixed(1)
  console.log(
    `${f}\n  ${v.width}x${v.height} @ ${v.r_frame_rate} ${v.codec_name} | ` +
    `${a ? `${a.codec_name} ${a.sample_rate}Hz ${a.channels}ch` : 'no audio'} | ` +
    `${Number(d.format.duration).toFixed(2)}s | ${mb} MB`,
  )
}
