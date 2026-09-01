/* The Studio console's maths, checked in Node.
 *
 * The audio graph itself needs a browser, but every number the graph is fed
 * comes from these pure functions - and a wrong one fails silently: a waveform
 * that draws mirrored, a "loudness matched" A/B that is 3 dB off, a marker
 * pinned past the end of the canvas. None of that throws. So it is checked
 * here, against arithmetic that has a right answer.
 *
 *     node tests/js/check_studioconsole.js
 */
"use strict";

const C = require("../../static/js/studioconsole.js");

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

function near(got, want, eps, what) {
  if (Math.abs(got - want) > (eps || 1e-9)) {
    throw new Error((what || "value") + ": got " + got + ", want " + want);
  }
}

// --- peaks -------------------------------------------------------------------

check("peaks returns one [lo, hi] pair per column", () => {
  const data = new Float32Array(1000).fill(0.5);
  const out = C.peaks(data, 10);
  if (out.length !== 10) { throw new Error("length " + out.length); }
  near(out[0][0], 0.5, 1e-6, "lo");
  near(out[0][1], 0.5, 1e-6, "hi");
});

check("peaks keeps the extremes, not the average", () => {
  // One +1 spike and one -1 spike in an otherwise silent column: averaging
  // would report ~0 and the transient would vanish from the picture.
  const data = new Float32Array(100);
  data[3] = 1.0;
  data[7] = -1.0;
  const out = C.peaks(data, 1);
  near(out[0][1], 1.0, 1e-6, "hi kept the spike");
  near(out[0][0], -1.0, 1e-6, "lo kept the spike");
});

check("peaks of silence is [0, 0], not [1, -1]", () => {
  const out = C.peaks(new Float32Array(50), 5);
  near(out[0][0], 0, 1e-9, "lo");
  near(out[0][1], 0, 1e-9, "hi");
});

check("more columns than samples does not crash or invert", () => {
  const out = C.peaks(new Float32Array([0.5, -0.5]), 10);
  if (out.length !== 10) { throw new Error("length"); }
  for (const [lo, hi] of out) {
    if (lo > hi) { throw new Error("inverted column"); }
  }
});

// --- loudness matching -------------------------------------------------------

check("match gain is the difference of the integrated readings", () => {
  // A at -14, B at -10: B is 4 LU hotter and must come DOWN 4 dB.
  near(C.matchGainDb(-14, -10), -4, 1e-9);
  near(C.matchGainDb(-14, -20), 6, 1e-9);
  near(C.matchGainDb(-14, -14), 0, 1e-9);
});

check("an unmeasured side matches at 0 dB rather than NaN", () => {
  near(C.matchGainDb(null, -10), 0, 1e-9);
  near(C.matchGainDb(-14, undefined), 0, 1e-9);
});

// --- dBFS --------------------------------------------------------------------

check("full scale is 0 dBFS, half scale is -6.02", () => {
  near(C.dbfs(1.0), 0, 1e-9);
  near(C.dbfs(0.5), -6.0206, 0.001);
});

check("silence is -Infinity, not 0 or an error", () => {
  if (C.dbfs(0) !== -Infinity) { throw new Error("got " + C.dbfs(0)); }
});

// --- timecode ----------------------------------------------------------------

check("timecode formats minutes, seconds and tenths", () => {
  if (C.fmtTime(0) !== "0:00.0") { throw new Error(C.fmtTime(0)); }
  if (C.fmtTime(61.25) !== "1:01.2") { throw new Error(C.fmtTime(61.25)); }
  if (C.fmtTime(599.96) !== "9:59.9") { throw new Error(C.fmtTime(599.96)); }
});

check("garbage time renders as zero, not NaN:NaN", () => {
  if (C.fmtTime(NaN) !== "0:00.0") { throw new Error(C.fmtTime(NaN)); }
  if (C.fmtTime(-5) !== "0:00.0") { throw new Error(C.fmtTime(-5)); }
  if (C.fmtTime(Infinity) !== "0:00.0") { throw new Error(C.fmtTime(Infinity)); }
});

// --- markers -----------------------------------------------------------------

check("a marker at half the duration sits at 50%", () => {
  near(C.markerPct(30, 60), 50, 1e-9);
});

check("a marker at the exact end is clamped to 100%, not past it", () => {
  near(C.markerPct(60, 60), 100, 1e-9);
  near(C.markerPct(90, 60), 100, 1e-9, "past the end clamps");
});

check("a marker against zero duration is 0, not NaN%", () => {
  near(C.markerPct(10, 0), 0, 1e-9);
});

// --- the module itself -------------------------------------------------------

check("the module loads headless and create() declines without Web Audio", () => {
  // In Node there is no AudioContext; create() must return null rather than
  // throw, because the page checks the return and says so.
  if (C.create({}) !== null) { throw new Error("created without an AudioContext"); }
});

console.log("");
console.log(passed + " passed, " + failed + " failed");
process.exit(failed ? 1 : 0);
