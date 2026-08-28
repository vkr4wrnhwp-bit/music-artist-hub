#!/usr/bin/env node
/**
 * Minimal MP4 probe — reports duration, dimensions, frame rate, track codecs
 * and file size straight out of the container boxes.
 *
 *   node scripts/probe-mp4.mjs renders/*.mp4
 *
 * There is no ffprobe in this environment (the only ffmpeg on the box is a
 * stripped Playwright build with H.264 disabled), so QC reads the boxes.
 */
import { openSync, readSync, closeSync, statSync } from 'node:fs';

const readBoxes = (fd, start, end, want, out = {}) => {
  let pos = start;
  while (pos < end - 8) {
    const head = Buffer.alloc(8);
    readSync(fd, head, 0, 8, pos);
    let size = head.readUInt32BE(0);
    const type = head.toString('latin1', 4, 8);
    let headLen = 8;
    if (size === 1) {
      const big = Buffer.alloc(8);
      readSync(fd, big, 0, 8, pos + 8);
      size = Number(big.readBigUInt64BE(0));
      headLen = 16;
    } else if (size === 0) {
      size = end - pos;
    }
    if (size < headLen) break;
    if (want.containers.has(type)) {
      readBoxes(fd, pos + headLen, pos + size, want, out);
    } else if (want.leaves.has(type)) {
      const body = Buffer.alloc(Math.min(size - headLen, 4096));
      readSync(fd, body, 0, body.length, pos + headLen);
      (out[type] ??= []).push(body);
    }
    pos += size;
  }
  return out;
};

const want = {
  containers: new Set(['moov', 'trak', 'mdia', 'minf', 'stbl', 'edts']),
  leaves: new Set(['mvhd', 'tkhd', 'mdhd', 'hdlr', 'stsd', 'stts']),
};

const probe = (file) => {
  const fd = openSync(file, 'r');
  const size = statSync(file).size;
  const boxes = readBoxes(fd, 0, size, want);
  closeSync(fd);

  const mvhd = boxes.mvhd?.[0];
  const v = mvhd.readUInt8(0);
  const timescale = v === 1 ? mvhd.readUInt32BE(20) : mvhd.readUInt32BE(12);
  const dur = v === 1 ? Number(mvhd.readBigUInt64BE(24)) : mvhd.readUInt32BE(16);
  const seconds = dur / timescale;

  // widest tkhd is the video track; dimensions are 16.16 fixed point
  const dims = (boxes.tkhd ?? []).map((b) => {
    const version = b.readUInt8(0);
    const off = version === 1 ? 84 : 72;
    return { w: b.readUInt32BE(off) / 65536, h: b.readUInt32BE(off + 4) / 65536 };
  }).filter((d) => d.w > 0 && d.h > 0);

  const codecs = (boxes.stsd ?? []).map((b) => b.toString('latin1', 12, 16));

  // stts: sample deltas in the media timescale -> frame rate
  const rates = [];
  (boxes.stts ?? []).forEach((b, i) => {
    const count = b.readUInt32BE(4);
    if (!count) return;
    const delta = b.readUInt32BE(12);
    const mdhd = boxes.mdhd?.[i];
    if (!mdhd || !delta) return;
    const mv = mdhd.readUInt8(0);
    const ts = mv === 1 ? mdhd.readUInt32BE(20) : mdhd.readUInt32BE(12);
    rates.push(ts / delta);
  });

  const d = dims[0] ?? { w: 0, h: 0 };
  const fps = rates.find((r) => r > 5 && r < 121);
  return {
    file,
    size: `${(size / 1048576).toFixed(1)} MB`,
    dimensions: `${d.w}x${d.h}`,
    duration: `${seconds.toFixed(2)}s`,
    fps: fps ? fps.toFixed(2) : 'n/a',
    tracks: codecs.join(', ') || 'n/a',
  };
};

const files = process.argv.slice(2);
if (!files.length) {
  console.error('usage: node scripts/probe-mp4.mjs <file.mp4> [...]');
  process.exit(1);
}
console.table(files.map(probe));
