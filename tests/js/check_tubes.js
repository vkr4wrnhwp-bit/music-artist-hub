/* The faceplate says V1 adds even harmonics and V2 adds odd ones. That is
   a measurable claim, so measure it: push a clean sine through each curve
   and look at where the energy lands. Reuses the FFT from tempokey.js. */
const T = require("../../static/js/tubes.js");
const TK = require("../../static/js/tempokey.js");

let fails = 0;
function ok(name, cond, detail) {
  console.log((cond ? "PASS  " : "FAIL  ") + name + (detail ? "   " + detail : ""));
  if (!cond) { fails++; }
}

const RATE = 48000, FFTN = 8192;

/* Apply a waveshaper table the way Web Audio does: the curve is sampled
   across [-1, 1] with linear interpolation between entries. */
function shape(curve, x) {
  const n = curve.length;
  const t = (Math.max(-1, Math.min(1, x)) + 1) / 2 * (n - 1);
  const i = Math.floor(t), f = t - i;
  const a = curve[i], b = i + 1 < n ? curve[i + 1] : a;
  return a + (b - a) * f;
}

/* Harmonic amplitudes of a shaped sine, normalised to the fundamental.
   The test tone divides the FFT length exactly, so each harmonic lands in
   one bin and no window is needed. */
function harmonics(curve, amp) {
  const cycles = 64;                       // integer cycles in the frame
  const freq = cycles * RATE / FFTN;
  const re = new Float32Array(FFTN), im = new Float32Array(FFTN);
  for (let i = 0; i < FFTN; i++) {
    re[i] = shape(curve, amp * Math.sin(2 * Math.PI * freq * i / RATE));
  }
  TK._fft(re, im);
  const mag = (h) => {
    const b = cycles * h;
    return b < FFTN / 2 ? Math.hypot(re[b], im[b]) : 0;
  };
  const f = mag(1) || 1e-12;
  return {h2: mag(2) / f, h3: mag(3) / f, h4: mag(4) / f, h5: mag(5) / f,
          dc: Math.hypot(re[0], im[0]) / FFTN / (amp || 1)};
}

console.log("=== V1 Triode: asymmetric, so EVEN harmonics dominate ===");
const tri = T.triodeCurve(0.8);
const th = harmonics(tri, 0.7);
ok("triode puts more 2nd harmonic than 3rd", th.h2 > th.h3,
   "h2 " + th.h2.toFixed(4) + " vs h3 " + th.h3.toFixed(4));
ok("triode's 2nd harmonic is actually present (> 1%)", th.h2 > 0.01,
   "h2 " + (th.h2 * 100).toFixed(2) + "%");
ok("triode is genuinely asymmetric: f(-x) !== -f(x)",
   Math.abs(shape(tri, 0.6) + shape(tri, -0.6)) > 0.02,
   "f(0.6)+f(-0.6) = " + (shape(tri, 0.6) + shape(tri, -0.6)).toFixed(4));

console.log("\n=== V2 Pentode: odd-symmetric, so ONLY odd harmonics ===");
const pen = T.pentodeCurve(0.8);
const ph = harmonics(pen, 0.7);
ok("pentode puts more 3rd harmonic than 2nd", ph.h3 > ph.h2,
   "h3 " + ph.h3.toFixed(4) + " vs h2 " + ph.h2.toFixed(4));
ok("pentode's even harmonics are negligible (< 0.1%)",
   ph.h2 < 0.001 && ph.h4 < 0.001,
   "h2 " + (ph.h2 * 100).toFixed(4) + "% h4 " + (ph.h4 * 100).toFixed(4) + "%");
ok("pentode is odd-symmetric to within rounding",
   Math.abs(shape(pen, 0.6) + shape(pen, -0.6)) < 1e-3,
   "f(0.6)+f(-0.6) = " + (shape(pen, 0.6) + shape(pen, -0.6)).toExponential(2));
ok("pentode adds more 3rd harmonic than triode does", ph.h3 > th.h3,
   "pentode " + ph.h3.toFixed(4) + " vs triode " + th.h3.toFixed(4));
ok("triode adds more 2nd harmonic than pentode does", th.h2 > ph.h2,
   "triode " + th.h2.toFixed(4) + " vs pentode " + ph.h2.toFixed(4));

console.log("\n=== V3 Tape / V5 Iron ===");
const tape = T.tapeCurve(0.8), iron = T.ironCurve(0.8);
ok("tape is odd-symmetric", Math.abs(shape(tape, 0.6) + shape(tape, -0.6)) < 1e-3);
ok("tape compresses: doubling the input less than doubles the output",
   shape(tape, 0.8) / shape(tape, 0.4) < 1.9,
   "ratio " + (shape(tape, 0.8) / shape(tape, 0.4)).toFixed(3));
ok("iron is gentler than tape at the same amount",
   shape(iron, 0.4) < shape(tape, 0.4),
   "iron " + shape(iron, 0.4).toFixed(4) + " vs tape " + shape(tape, 0.4).toFixed(4));
ok("iron still colours: 3rd harmonic present",
   harmonics(iron, 0.7).h3 > 0.005,
   (harmonics(iron, 0.7).h3 * 100).toFixed(2) + "%");

console.log("\n=== Every curve is safe and well-behaved ===");
const all = {triode: tri, pentode: pen, tape: tape, iron: iron};
Object.keys(all).forEach(function (name) {
  const c = all[name];
  let inRange = true, monotonic = true;
  for (let i = 0; i < c.length; i++) {
    if (!(c[i] >= -1 && c[i] <= 1) || !isFinite(c[i])) { inRange = false; }
    if (i && c[i] < c[i - 1] - 1e-6) { monotonic = false; }
  }
  ok(name + " stays inside [-1, 1] with no NaNs", inRange);
  ok(name + " is monotonic (shaping, never folding)", monotonic);
  ok(name + " maps full scale to full scale", Math.abs(c[c.length - 1] - 1) < 0.02,
     "top = " + c[c.length - 1].toFixed(4));
});

console.log("\n=== amount 0 must be truly transparent ===");
[["triode", T.triodeCurve], ["pentode", T.pentodeCurve],
 ["tape", T.tapeCurve], ["iron", T.ironCurve]].forEach(function (pair) {
  const c = pair[1](0);
  let maxErr = 0;
  for (let i = 0; i < c.length; i++) {
    const x = (i / (c.length - 1)) * 2 - 1;
    maxErr = Math.max(maxErr, Math.abs(c[i] - x));
  }
  ok(pair[0] + " at amount 0 is the identity", maxErr < 1e-6,
     "max deviation " + maxErr.toExponential(2));
  const h = harmonics(c, 0.7);
  ok(pair[0] + " at amount 0 adds no harmonics",
     h.h2 < 1e-4 && h.h3 < 1e-4,
     "h2 " + h.h2.toExponential(1) + " h3 " + h.h3.toExponential(1));
});

console.log("\n=== V4 Flutter and V6 Vari-Mu parameters ===");
const f0 = T.flutterParams(0), f1 = T.flutterParams(1);
ok("flutter at 0 has no depth", f0.wowDepth === 0 && f0.flutterDepth === 0);
ok("wow is slower than flutter", f1.wowHz < f1.flutterHz,
   f1.wowHz + " Hz vs " + f1.flutterHz + " Hz");
ok("wow swings wider than flutter", f1.wowDepth > f1.flutterDepth,
   (f1.wowDepth * 1000).toFixed(2) + " ms vs "
     + (f1.flutterDepth * 1000).toFixed(2) + " ms");
ok("modulation never asks for a negative delay",
   f1.base - f1.wowDepth - f1.flutterDepth > 0,
   "min delay " + ((f1.base - f1.wowDepth - f1.flutterDepth) * 1000).toFixed(2) + " ms");
const v1 = T.variMuParams(1), v0 = T.variMuParams(0);
ok("vari-mu attack is slow enough to be program-dependent", v1.attack >= 0.02,
   v1.attack + " s");
ok("vari-mu release is long", v1.release >= 0.3, v1.release + " s");
ok("more amount means a lower threshold and higher ratio",
   v1.threshold < v0.threshold && v1.ratio > v0.ratio,
   v0.threshold + "dB/" + v0.ratio + ":1 -> " + v1.threshold + "dB/" + v1.ratio + ":1");

console.log("\n=== Glow is a meter, not decoration ===");
ok("silence leaves the tube dark", T.glow(0, 1) === 0);
ok("a stage turned off stays dark however loud the input", T.glow(0.9, 0) === 0);
ok("louder input glows brighter", T.glow(0.5, 1) > T.glow(0.05, 1),
   T.glow(0.05, 1).toFixed(3) + " -> " + T.glow(0.5, 1).toFixed(3));
ok("glow never exceeds 1", T.glow(1, 1) <= 1, T.glow(1, 1).toFixed(3));
ok("a lower amount glows dimmer at the same level",
   T.glow(0.5, 0.3) < T.glow(0.5, 1));
ok("no gain reduction leaves the vari-mu dark", T.glowFromReduction(0, 1) === 0);
ok("more gain reduction glows brighter",
   T.glowFromReduction(-9, 1) > T.glowFromReduction(-2, 1),
   T.glowFromReduction(-2, 1).toFixed(3) + " -> "
     + T.glowFromReduction(-9, 1).toFixed(3));
ok("gain-reduction glow is capped at 1", T.glowFromReduction(-40, 1) <= 1);

console.log("\n=== The manifest matches the implementations ===");
ok("there are exactly six stages", T.STAGES.length === 6, T.STAGES.length + "");
ok("tubes are numbered V1..V6",
   T.STAGES.map(s => s.tube).join(",") === "V1,V2,V3,V4,V5,V6");
ok("every stage key is unique",
   new Set(T.STAGES.map(s => s.key)).size === 6);
ok("every stage is either a curve, a modulator or a compressor",
   T.STAGES.every(s => s.curve || s.mod || s.comp));
ok("only the asymmetric stage asks for DC blocking",
   T.STAGES.filter(s => s.dc).map(s => s.key).join(",") === "triode");

console.log("\n" + (fails ? fails + " FAILED" : "all checks passed"));
process.exit(fails ? 1 : 0);
