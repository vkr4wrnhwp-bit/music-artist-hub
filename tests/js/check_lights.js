/* Light Studio engine checks - known by construction.
   node check_lights.js  (exits non-zero on failure) */
const E = require("../../static/js/lights-engine.js");

let fails = 0;
function ok(name, cond, detail) {
  console.log((cond ? "PASS  " : "FAIL  ") + name + (detail ? "   " + detail : ""));
  if (!cond) fails++;
}

// groups
ok("all of 6", E.membersOf("all", 6).join() === "1,2,3,4,5,6");
ok("odd/even of 5", E.membersOf("odd", 5).join() === "1,3,5" && E.membersOf("even", 5).join() === "2,4");
ok("pair1 of 6 is outermost", E.membersOf("pair1", 6).join() === "1,6");
ok("pair3 of 5 is the centre bar alone", E.membersOf("pair3", 5).join() === "3");
ok("mirror of 2 in 6 is 5; centre has none", E.mirrorOf(2, 6) === 5 && E.mirrorOf(3, 5) === null);
ok("group options count", E.groupOptions(6).length === 3 + 3 + 6);

// lighting resolver: fade maths
const show = {bars: 2, chans: 4, cues: [
  {t: 0, group: "all", color: "#ff0000", intensity: 100, fade: 1},
  {t: 10, group: "b1", color: "#0000ff", intensity: 50, fade: 2}]};
let L = E.lightingAt(show, 0.5);
ok("half way through a 1s fade from black to red", L[0].rgb[0] === 128 && Math.abs(L[0].inten - 0.5) < 1e-9, JSON.stringify(L[0]));
L = E.lightingAt(show, 11);
ok("bar 1 half way red->blue at 50%", L[0].rgb[0] === 128 && L[0].rgb[2] === 128 && Math.abs(L[0].inten - 0.75) < 1e-9, JSON.stringify(L[0]));
ok("bar 2 untouched by a b1 cue", L[1].rgb[0] === 255 && L[1].inten === 1);
ok("before the first cue everything is dark", E.lightingAt({bars: 3, cues: [{t: 5, group: "all", color: "#ffffff", intensity: 100, fade: 0}]}, 1).every(x => x.inten === 0));

// ENTTEC framing
const pkt = E.dmxFrame({bars: 1, chans: 4}, [{rgb: [10, 20, 30], inten: 1}]);
ok("packet start/label/length/end", pkt[0] === 0x7E && pkt[1] === 6 && pkt[2] === (513 & 255) && pkt[3] === (513 >> 8) && pkt[pkt.length - 1] === 0xE7, Array.from(pkt.slice(0, 4)).join());
ok("start code 0 then dimmer+RGB", pkt[4] === 0 && pkt[5] === 255 && pkt[6] === 10 && pkt[7] === 20 && pkt[8] === 30);
const pkt3 = E.dmxFrame({bars: 1, chans: 3}, [{rgb: [200, 100, 0], inten: 0.5}]);
ok("3ch scales colour by intensity", pkt3[5] === 100 && pkt3[6] === 50 && pkt3[7] === 0);
ok("packet length is 5 + 513", pkt.length === 518);

// timecode
ok("fmtTimecode", E.fmtTimecode(65.257) === "1:05.25" && E.fmtTimecode(0) === "0:00.00", E.fmtTimecode(65.257));
ok("fmtClock", E.fmtClock(125.04) === "2:05.0");

// peaks on a known signal: 1 kHz tone at 0.5 amplitude, 1 s, 100 buckets
const RATE = 8000;
const tone = new Float32Array(RATE);
for (let i = 0; i < RATE; i++) tone[i] = 0.5 * Math.sin(2 * Math.PI * 1000 * i / RATE);
const pk = E.peaks(tone, RATE, 0, 1, 100);
ok("peaks max ~0.5 and min ~-0.5 in every bucket", Array.from(pk.max).every(v => v > 0.45 && v <= 0.5) && Array.from(pk.min).every(v => v < -0.45 && v >= -0.5));
const half = E.peaks(tone, RATE, 0.5, 1, 10);
ok("window peaks same amplitude", half.max[3] > 0.45);
const silent = E.peaks(new Float32Array(RATE), RATE, 0, 1, 10);
ok("silence is flat", silent.max.every(v => v === 0) && silent.min.every(v => v === 0));

// beats: click track at 120 BPM, 20 s, clicks 30 ms long with decay
const SR = 22050, DUR = 20, BPM = 120;
const clicks = new Float32Array(SR * DUR);
for (let b = 0.25; b < DUR; b += 60 / BPM) {
  const s0 = Math.floor(b * SR);
  for (let i = 0; i < SR * 0.03; i++) clicks[s0 + i] = Math.sin(i * 0.9) * Math.exp(-i / (SR * 0.01));
}
const det = E.detectBeats(clicks, SR);
ok("detects ~120 BPM", Math.abs(det.bpm - 120) < 1.5, "bpm=" + det.bpm);
ok("phase near the first click", det.offset < 0.3 || Math.abs(det.offset - 0.25) < 0.06 || Math.abs(det.offset - 0.75) < 0.06, "offset=" + det.offset);
ok("beat list spans the track", det.beats.length > 30 && det.beats[det.beats.length - 1] < DUR);
const det2 = E.detectBeats(new Float32Array(SR * 2), SR);
ok("too short / silent -> no tempo, no crash", det2.bpm === 0 && det2.beats.length === 0);

// snap & tap
ok("snapToBeat lands on the grid", E.snapToBeat(1.1, 120, 0.25) === 1.25 && E.snapToBeat(0.9, 120, 0.25) === 0.75);
ok("snap with no bpm is identity", E.snapToBeat(1.1, 0, 0) === 1.1);
ok("tap tempo from 8 taps at 0.5s = 120", E.tapTempo([0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5]) === 120);
ok("tap tempo ignores a long gap", E.tapTempo([0, 0.5, 10, 10.5, 11]) === 120);
ok("nearestCue within tolerance", E.nearestCue([{t: 1}, {t: 5}], 5.2, 0.5).t === 5 && E.nearestCue([{t: 1}], 5, 0.5) === null);
ok("isBlackout", E.isBlackout({color: "#000000", intensity: 80}) && E.isBlackout({color: "#ff0000", intensity: 0}) && !E.isBlackout({color: "#ff0000", intensity: 1}));
ok("six looks, last is blackout", E.LOOKS.length === 6 && E.LOOKS[5].key === "blackout");

console.log(fails ? ("\n" + fails + " FAILED") : "\nall passed");
process.exit(fails ? 1 : 0);
