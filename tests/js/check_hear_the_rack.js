/* Node checks for the pure parts of static/js/hear-the-rack.js.
 *
 * The browser part needs an AudioContext and is not run here. What IS
 * checked is everything the sound and the light show depend on that can
 * be computed without one: the tube curve is the Rack's (verbatim
 * behaviour), the band table is the Rack's, the groove has a kick on
 * every one, the schedule is sorted and loops cleanly, and the bar-to-
 * bin map covers the spectrum without gaps.
 *
 * Usage: node check_hear_the_rack.js <path to hear-the-rack.js>
 */
"use strict";
const path = require("path");
const htr = require(path.resolve(process.argv[2]));

let failed = 0;
function check(name, ok, detail) {
  if (ok) { console.log("PASS " + name); }
  else { failed++; console.log("FAIL " + name + (detail ? " - " + detail : "")); }
}

/* --- the tube curve is the Rack's -------------------------------------- */
const c = htr.tubeCurve(3, 0.25);
check("tube curve has 2048 points", c.length === 2048);
let monotonic = true;
for (let i = 1; i < c.length; i++) { if (c[i] < c[i - 1]) { monotonic = false; break; } }
check("tube curve is monotonic", monotonic);
check("tube curve passes near zero at the centre", Math.abs(c[1023]) < 0.01, String(c[1023]));
/* rackdsp.js normalises by tanh(drive); with positive bias the top end
   overshoots unity slightly, exactly as the Rack does. */
const expectedTop = Math.tanh(3 * 1.25) / Math.tanh(3);
check("tube curve top matches the Rack's formula", Math.abs(c[2047] - expectedTop) < 1e-6, c[2047] + " vs " + expectedTop);
const expectedBottom = -Math.tanh(3 * (1 - 0.25 * 0.6)) / Math.tanh(3);
check("tube curve bottom matches the Rack's asymmetry", Math.abs(c[0] - expectedBottom) < 1e-6, c[0] + " vs " + expectedBottom);

/* --- the band table is the Rack's -------------------------------------- */
check("twelve bands", htr.EQ_BANDS.length === 12);
check("bands run 40 Hz to 14 kHz, low shelf to high shelf",
  htr.EQ_BANDS[0].f === 40 && htr.EQ_BANDS[0].type === "lowshelf" &&
  htr.EQ_BANDS[11].f === 14000 && htr.EQ_BANDS[11].type === "highshelf");
check("preset has a gain per band", htr.PRESET.eq.length === 12);

/* --- the groove ---------------------------------------------------------- */
for (let bar = 0; bar < htr.BARS; bar++) {
  const p = htr.pattern(bar);
  check("bar " + bar + " has sixteen steps", p.kick.length === 16 && p.snare.length === 16 && p.hat.length === 16);
  check("bar " + bar + " kicks on the one", p.kick[0] === 1);
  check("bar " + bar + " snares on two and four", p.snare[4] === 1 && p.snare[12] === 1);
}

/* --- the schedule --------------------------------------------------------- */
const ev = htr.schedule(10);
let sorted = true;
for (let i = 1; i < ev.length; i++) { if (ev[i].t < ev[i - 1].t) { sorted = false; break; } }
check("schedule is sorted", sorted);
check("schedule starts at loop start", ev[0].t === 10);
check("schedule ends inside the loop", ev[ev.length - 1].t < 10 + htr.LOOP_S);
check("four chord events, one per bar", ev.filter(e => e.kind === "chord").length === 4);
check("loop length is four bars at 92", Math.abs(htr.LOOP_S - (60 / 92) * 16) < 1e-9, String(htr.LOOP_S));

/* --- the spectrum map ----------------------------------------------------- */
const bins = htr.binMap(2048, 48000, 48);
check("48 bars", bins.length === 48);
let contiguous = true, rising = true;
for (let i = 1; i < bins.length; i++) {
  if (bins[i][0] < bins[i - 1][0]) rising = false;
  if (bins[i][0] > bins[i - 1][1]) contiguous = false;
}
check("bar bins rise with frequency", rising);
check("bar bins leave no gap", contiguous);
check("every bar reads at least one bin", bins.every(b => b[1] > b[0]));

if (failed) { console.log(failed + " FAILED"); process.exit(1); }
console.log("all checks passed");
