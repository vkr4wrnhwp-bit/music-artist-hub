/* The WAV writer, checked against the format's own rules.
 *
 * A wrong encoder does not crash. It produces a file that opens, plays at the
 * right length, and is subtly wrong - channels swapped, a header that says
 * one thing while the data says another, or truncation noise sitting on the
 * quietest bar of the record. None of that shows up in a Python test, so it
 * is checked here, in Node, by reading the bytes back.
 *
 *     node tests/js/check_wavwrite.js
 */
"use strict";

const W = require("../../static/js/wavwrite.js");

let passed = 0;
let failed = 0;

function check(label, fn) {
  try {
    fn();
    console.log("PASS  " + label);
    passed++;
  } catch (err) {
    console.log("FAIL  " + label + "  -> " + String(err.message).split("\n")[0]);
    failed++;
  }
}

function eq(got, want, what) {
  if (got !== want) {
    throw new Error((what || "value") + ": got " + got + ", want " + want);
  }
}

function tone(n, amp, freq, rate) {
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    out[i] = amp * Math.sin(2 * Math.PI * (freq || 220) * i / (rate || 44100));
  }
  return out;
}

// --- the header says what the data is ----------------------------------------

check("RIFF/WAVE header and a 16-bit PCM fmt chunk", () => {
  const res = W.encode([tone(100, 0.5)], 44100, 16, false);
  const v = new DataView(res.buffer);
  const tag = (o) => String.fromCharCode(v.getUint8(o), v.getUint8(o + 1),
                                         v.getUint8(o + 2), v.getUint8(o + 3));
  eq(tag(0), "RIFF", "RIFF tag");
  eq(tag(8), "WAVE", "WAVE tag");
  eq(tag(12), "fmt ", "fmt tag");
  eq(tag(36), "data", "data tag");
  eq(v.getUint16(20, true), 1, "format code (1 = PCM)");
  eq(v.getUint16(34, true), 16, "bit depth");
});

check("32-bit writes IEEE float, not PCM", () => {
  const res = W.encode([tone(50, 0.5)], 48000, 32, false);
  eq(new DataView(res.buffer).getUint16(20, true), 3, "format code (3 = float)");
});

check("byte rate and block align agree with channels, rate and depth", () => {
  const res = W.encode([tone(64, 0.2), tone(64, 0.2)], 48000, 24, false);
  const v = new DataView(res.buffer);
  eq(v.getUint16(22, true), 2, "channel count");
  eq(v.getUint32(24, true), 48000, "sample rate");
  eq(v.getUint32(28, true), 48000 * 2 * 3, "byte rate");
  eq(v.getUint16(32, true), 2 * 3, "block align");
});

check("the declared sizes match the buffer that was produced", () => {
  const frames = 128, channels = 2, depth = 16;
  const res = W.encode([tone(frames, 0.3), tone(frames, 0.3)], 44100, depth, false);
  const v = new DataView(res.buffer);
  const dataBytes = frames * channels * (depth / 8);
  eq(v.getUint32(40, true), dataBytes, "data chunk size");
  eq(v.getUint32(4, true), 36 + dataBytes, "RIFF size");
  eq(res.buffer.byteLength, 44 + dataBytes, "total length");
});

// --- interleaving -------------------------------------------------------------

check("frames are interleaved L,R and not concatenated", () => {
  const left = new Float32Array([1, 1, 1, 1]);
  const right = new Float32Array([-1, -1, -1, -1]);
  const res = W.encode([left, right], 44100, 16, false);
  const v = new DataView(res.buffer);
  // Frame 0 must be (+full, -full), not (+full, +full).
  if (v.getInt16(44, true) <= 0) { throw new Error("first sample is not left"); }
  if (v.getInt16(46, true) >= 0) { throw new Error("second sample is not right"); }
});

// --- clipping is reported, not hidden -----------------------------------------

check("over-range input is clamped and COUNTED", () => {
  const hot = new Float32Array([2, -2, 0.1, 0]);
  const res = W.encode([hot], 44100, 16, false);
  eq(res.clipped, 2, "clipped sample count");
  const v = new DataView(res.buffer);
  eq(v.getInt16(44, true), 32767, "positive clamp");
  if (v.getInt16(46, true) > -32767) { throw new Error("negative did not clamp"); }
});

check("in-range audio reports no clipping", () => {
  eq(W.encode([tone(500, 0.9)], 44100, 16, false).clipped, 0, "clipped");
});

check("clamping never wraps a positive peak to a negative one", () => {
  const res = W.encode([new Float32Array([5])], 44100, 16, false);
  if (new DataView(res.buffer).getInt16(44, true) < 0) {
    throw new Error("positive over-range wrapped negative");
  }
});

// --- dither ------------------------------------------------------------------

check("dither is refused on 32-bit float, where nothing is being reduced", () => {
  const flat = new Float32Array(2000).fill(0.25);
  const a = W.encode([flat], 44100, 32, true);
  const b = W.encode([flat], 44100, 32, true);
  const va = new DataView(a.buffer), vb = new DataView(b.buffer);
  for (let i = 0; i < 200; i++) {
    if (va.getFloat32(44 + i * 4, true) !== vb.getFloat32(44 + i * 4, true)) {
      throw new Error("float output differs between runs - it was dithered");
    }
  }
});

check("dither perturbs a 16-bit reduction of a constant level", () => {
  const flat = new Float32Array(4000).fill(0.2000015);
  const res = W.encode([flat], 44100, 16, true);
  const v = new DataView(res.buffer);
  const seen = new Set();
  for (let i = 0; i < 2000; i++) { seen.add(v.getInt16(44 + i * 2, true)); }
  if (seen.size < 2) {
    throw new Error("every sample identical - dither did nothing");
  }
});

check("without dither the same constant level is bit-identical", () => {
  const flat = new Float32Array(500).fill(0.2000015);
  const res = W.encode([flat], 44100, 16, false);
  const v = new DataView(res.buffer);
  const first = v.getInt16(44, true);
  for (let i = 1; i < 400; i++) {
    if (v.getInt16(44 + i * 2, true) !== first) {
      throw new Error("undithered output is not constant");
    }
  }
});

// --- gain ---------------------------------------------------------------------

check("a 0 dB gain changes nothing", () => {
  const src = tone(200, 0.5);
  const res = W.applyGain([src], 0);
  for (let i = 0; i < src.length; i++) {
    if (Math.abs(res.channels[i === 0 ? 0 : 0][i] - src[i]) > 1e-6) {
      throw new Error("0 dB altered the samples");
    }
  }
});

check("-6 dB halves the amplitude, to within a rounding error", () => {
  const res = W.applyGain([new Float32Array([1])], -6.0206);
  const got = res.channels[0][0];
  if (Math.abs(got - 0.5) > 0.001) { throw new Error("got " + got); }
});

check("the peak after gain is reported, in dB", () => {
  const res = W.applyGain([new Float32Array([0.5, -0.25])], 0);
  if (Math.abs(res.peak - 0.5) > 1e-6) { throw new Error("peak " + res.peak); }
  if (Math.abs(res.peakDb - (-6.0206)) > 0.01) {
    throw new Error("peakDb " + res.peakDb);
  }
});

check("silence reports -Infinity rather than 0 dB", () => {
  const res = W.applyGain([new Float32Array(10)], 0);
  if (res.peakDb !== -Infinity) { throw new Error("peakDb " + res.peakDb); }
});

check("an unsupported bit depth is refused rather than guessed at", () => {
  let threw = false;
  try { W.encode([tone(10, 0.1)], 44100, 12, false); } catch (e) { threw = true; }
  if (!threw) { throw new Error("12-bit was accepted"); }
});

console.log("");
console.log(passed + " passed, " + failed + " failed");
process.exit(failed ? 1 : 0);
