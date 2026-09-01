/* The mastering chain, checked against signals whose right answer is known.
 *
 * DSP fails silently: a shelf at the wrong gain, a limiter that lets one
 * transient through, a saturator that colours at mix zero - none of it
 * throws, all of it ships. So every stage here is driven with synthesized
 * material and measured, using the same BS.1770-4 engine the product uses.
 *
 *     node tests/js/check_masterchain.js
 */
"use strict";

const M = require("../../static/js/masterchain.js");
const L = require("../../static/js/loudness.js");

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

function sine(freq, seconds, rate, amp) {
  const n = Math.floor(seconds * rate);
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    out[i] = amp * Math.sin(2 * Math.PI * freq * i / rate);
  }
  return out;
}

function rms(data) {
  let sum = 0;
  for (let i = 0; i < data.length; i++) { sum += data[i] * data[i]; }
  return Math.sqrt(sum / data.length);
}

function db(ratio) { return 20 * Math.log(ratio) / Math.LN10; }

const RATE = 44100;

// --- shelves, against the cookbook's own promise -----------------------------

check("a +6 dB low shelf boosts 40 Hz by ~6 dB", () => {
  const src = sine(40, 1, RATE, 0.1);
  const out = M.biquad(src, M.shelfCoeffs("low", RATE, 120, 6));
  const gain = db(rms(out.subarray(RATE / 4)) / rms(src.subarray(RATE / 4)));
  if (Math.abs(gain - 6) > 0.5) { throw new Error("gain " + gain.toFixed(2)); }
});

check("the same shelf leaves 5 kHz within a quarter dB", () => {
  const src = sine(5000, 1, RATE, 0.1);
  const out = M.biquad(src, M.shelfCoeffs("low", RATE, 120, 6));
  const gain = db(rms(out.subarray(RATE / 4)) / rms(src.subarray(RATE / 4)));
  if (Math.abs(gain) > 0.25) { throw new Error("gain " + gain.toFixed(2)); }
});

check("a -3 dB high shelf cuts 12 kHz by ~3 dB and spares 200 Hz", () => {
  const hi = sine(12000, 1, RATE, 0.1);
  const lo = sine(200, 1, RATE, 0.1);
  const c = M.shelfCoeffs("high", RATE, 9000, -3);
  const gHi = db(rms(M.biquad(hi, c).subarray(RATE / 4)) / rms(hi.subarray(RATE / 4)));
  const gLo = db(rms(M.biquad(lo, c).subarray(RATE / 4)) / rms(lo.subarray(RATE / 4)));
  if (Math.abs(gHi + 3) > 0.5) { throw new Error("hi " + gHi.toFixed(2)); }
  if (Math.abs(gLo) > 0.25) { throw new Error("lo " + gLo.toFixed(2)); }
});

check("a peaking bell hits its centre and spares an octave out", () => {
  const at = sine(3000, 1, RATE, 0.1);
  const off = sine(750, 1, RATE, 0.1);
  const c = M.peakingCoeffs(RATE, 3000, 1.0, 4);
  const gAt = db(rms(M.biquad(at, c).subarray(RATE / 4)) / rms(at.subarray(RATE / 4)));
  const gOff = db(rms(M.biquad(off, c).subarray(RATE / 4)) / rms(off.subarray(RATE / 4)));
  if (Math.abs(gAt - 4) > 0.5) { throw new Error("centre " + gAt.toFixed(2)); }
  if (Math.abs(gOff) > 1.0) { throw new Error("octave " + gOff.toFixed(2)); }
});

// --- saturation --------------------------------------------------------------

check("saturation at mix 0 is bit-identical to the input", () => {
  const src = sine(220, 0.5, RATE, 0.5);
  const out = M.saturate(src, 1.6, 0);
  for (let i = 0; i < src.length; i++) {
    if (out[i] !== src[i]) { throw new Error("differs at " + i); }
  }
});

check("saturation adds odd harmonics a pure sine did not have", () => {
  // A tanh curve on a 220 Hz sine puts energy at 660 Hz. Measure it with a
  // goertzel-style correlation - if the third harmonic is not there, the
  // "colour" stage is a wire.
  const src = sine(220, 1, RATE, 0.6);
  const out = M.saturate(src, 2.5, 1.0);
  function tone(data, freq) {
    let re = 0, im = 0;
    for (let i = 0; i < data.length; i++) {
      const w = 2 * Math.PI * freq * i / RATE;
      re += data[i] * Math.cos(w);
      im += data[i] * Math.sin(w);
    }
    return Math.sqrt(re * re + im * im) / data.length;
  }
  const before = tone(src, 660);
  const after = tone(out, 660);
  if (after < before * 10 || after < 1e-4) {
    throw new Error("third harmonic " + after.toExponential(2));
  }
});

check("saturation is slope-unity: quiet material keeps its level", () => {
  // The defect this pins down: a tanh normalised by tanh(drive) has unity
  // PEAK but a small-signal gain of drive/tanh(drive) - a hidden boost that
  // turns every warm A/B into a volume test. Slope-unity means a -40 dBFS
  // signal passes within a tenth of a dB at FULL wet.
  const quiet = sine(220, 1, RATE, 0.01);
  const out = M.saturate(quiet, 1.6, 1.0);
  const drift = db(rms(out) / rms(quiet));
  if (Math.abs(drift) > 0.1) { throw new Error("drift " + drift.toFixed(2) + " dB"); }
});

// --- the limiter -------------------------------------------------------------

check("driven 12 dB over, not one sample escapes the ceiling", () => {
  const hot = [sine(220, 1, RATE, 0.9), sine(220, 1, RATE, 0.9)];
  // +12 dB drive
  const driven = hot.map(ch => ch.map ? ch : ch);
  const boosted = hot.map(ch => {
    const out = new Float32Array(ch.length);
    for (let i = 0; i < ch.length; i++) { out[i] = ch[i] * 4.0; }
    return out;
  });
  const res = M.limit(boosted, -1.0, RATE, 60);
  const ceiling = Math.pow(10, -1.0 / 20) + 1e-6;
  for (const ch of res.channels) {
    for (let i = 0; i < ch.length; i++) {
      if (Math.abs(ch[i]) > ceiling) { throw new Error("escape at " + i); }
    }
  }
  if (res.maxReductionDb > -6) {
    throw new Error("reported only " + res.maxReductionDb.toFixed(1) + " dB GR");
  }
});

check("a signal under the ceiling passes essentially untouched", () => {
  const quiet = [sine(220, 1, RATE, 0.2)];
  const res = M.limit(quiet, -1.0, RATE, 60);
  const drift = db(rms(res.channels[0]) / rms(quiet[0]));
  if (Math.abs(drift) > 0.1) { throw new Error("drifted " + drift.toFixed(3) + " dB"); }
});

check("the channels are linked - a one-sided peak ducks both sides", () => {
  const left = sine(220, 0.5, RATE, 0.2);
  const right = sine(220, 0.5, RATE, 0.2);
  // a burst only on the left
  for (let i = 4410; i < 4630; i++) { left[i] = 1.6; }
  const res = M.limit([left, right], -1.0, RATE, 60);
  // during the burst, the right channel must be reduced too
  const before = rms(right.subarray(4410, 4630));
  const during = rms(res.channels[1].subarray(4410, 4630));
  if (during >= before * 0.95) { throw new Error("right side not ducked"); }
});

// --- the directions, end to end ----------------------------------------------

function stereoMix() {
  // A -20ish LUFS bed with a hot transient every half second: the material a
  // plain gain-to-target cannot handle (the peaks cap it early) and a
  // limiter can.
  const seconds = 6;
  const n = seconds * RATE;
  const l = new Float32Array(n), r = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const bed = 0.12 * Math.sin(2 * Math.PI * 220 * i / RATE)
              + 0.05 * Math.sin(2 * Math.PI * 3000 * i / RATE);
    l[i] = bed; r[i] = bed;
  }
  for (let b = 0; b * RATE / 2 < n - 200; b++) {
    const start = Math.floor(b * RATE / 2);
    for (let i = 0; i < 150; i++) {
      const burst = 0.85 * Math.exp(-i / 40);
      l[start + i] += burst; r[start + i] += burst;
    }
  }
  return [l, r];
}

check("clean lands on the target when headroom allows, and reports it", () => {
  const soft = [sine(220, 4, RATE, 0.05), sine(220, 4, RATE, 0.05)];
  const res = M.render("clean", "medium", soft, RATE, -16, -1, L);
  if (res.report.outLufs === null
      || Math.abs(res.report.outLufs - -16) > 0.6) {
    throw new Error("landed at " + res.report.outLufs);
  }
});

check("warm actually warms: low end up, top eased, measured", () => {
  const lo = [sine(80, 2, RATE, 0.2)];
  const hi = [sine(11000, 2, RATE, 0.2)];
  // Run only the tonal stage by comparing direction output at same target.
  const wLo = M.render("warm", "strong", lo, RATE, -20, -1, L);
  const cLo = M.render("clean", "strong", lo, RATE, -20, -1, L);
  const wHi = M.render("warm", "strong", hi, RATE, -20, -1, L);
  const cHi = M.render("clean", "strong", hi, RATE, -20, -1, L);
  // Both land near -20 LUFS; warmth shows as the RATIO of how much gain the
  // loudness stage had to add: a boosted low end needs LESS make-up gain.
  if (!(wLo.report.gainDb < cLo.report.gainDb - 0.5)) {
    throw new Error("low shelf did nothing measurable");
  }
  if (!(wHi.report.gainDb > cHi.report.gainDb + 0.2)) {
    throw new Error("high shelf did nothing measurable");
  }
});

check("competitive beats clean on peaky material, which is its whole claim", () => {
  const mix = stereoMix();
  const clean = M.render("clean", "medium",
                         mix.map(c => new Float32Array(c)), RATE, -12, -1, L);
  const comp = M.render("competitive", "medium",
                        mix.map(c => new Float32Array(c)), RATE, -12, -1, L);
  if (clean.report.outLufs === null || comp.report.outLufs === null) {
    throw new Error("unmeasured render");
  }
  if (!(comp.report.outLufs > clean.report.outLufs + 1.0)) {
    throw new Error("competitive " + comp.report.outLufs.toFixed(1)
                    + " vs clean " + clean.report.outLufs.toFixed(1));
  }
  if (!(comp.report.maxReductionDb < -1)) {
    throw new Error("no gain reduction reported");
  }
});

check("every direction's true peak is MEASURED under the ceiling", () => {
  const mix = stereoMix();
  for (const key of ["clean", "warm", "competitive"]) {
    const res = M.render(key, "strong",
                         mix.map(c => new Float32Array(c)), RATE, -10, -1, L);
    if (res.report.outTp !== null && res.report.outTp > -0.85) {
      throw new Error(key + " true peak " + res.report.outTp.toFixed(2));
    }
  }
});

check("the report carries the numbers a change report needs", () => {
  const res = M.render("warm", "medium", stereoMix(), RATE, -14, -1, L);
  for (const k of ["direction", "intensity", "moves", "inLufs", "outLufs",
                   "inTp", "outTp", "gainDb", "basis"]) {
    if (!(k in res.report)) { throw new Error("missing " + k); }
  }
  if (!res.report.moves.length) { throw new Error("warm reported no moves"); }
});

check("an unknown direction is refused, not guessed at", () => {
  let threw = false;
  try { M.render("shiny", "medium", stereoMix(), RATE, -14, -1, L); }
  catch (e) { threw = true; }
  if (!threw) { throw new Error("accepted a direction that does not exist"); }
});

console.log("");
console.log(passed + " passed, " + failed + " failed");
process.exit(failed ? 1 : 0);
