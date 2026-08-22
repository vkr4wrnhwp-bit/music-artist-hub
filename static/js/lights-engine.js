/* Light Studio engine — the parts with no DOM, no Web Audio and no serial
   port, so they can be proved in Node (tests/js/check_lights.js) the same
   way the rack's DSP is: groups, the fade/lighting resolver, the ENTTEC
   DMX framing, waveform peaks, onset/BPM detection, beat snapping and
   the timecode formatter. lights.js is the browser around this. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) { module.exports = factory(); }
  else { root.LightsEngine = factory(); }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // ---------- groups ----------
  function membersOf(group, bars) {
    var out = [], i;
    group = group || "all";
    if (group === "all") { for (i = 1; i <= bars; i++) out.push(i); }
    else if (group === "odd") { for (i = 1; i <= bars; i += 2) out.push(i); }
    else if (group === "even") { for (i = 2; i <= bars; i += 2) out.push(i); }
    else if (group.indexOf("pair") === 0) {
      var k = parseInt(group.slice(4), 10);
      if (k >= 1 && k <= Math.floor(bars / 2)) out.push(k, bars + 1 - k);
      if (bars % 2 && k === Math.ceil(bars / 2)) out.push(k);
    } else if (group.indexOf("b") === 0) {
      var n = parseInt(group.slice(1), 10);
      if (n >= 1 && n <= bars) out.push(n);
    }
    return out;
  }
  function groupOptions(bars) {
    var opts = [["all", "All bars", "Every bar together"],
                ["odd", "Odd side", "Bars 1, 3, 5… — one side of a split look"],
                ["even", "Even side", "Bars 2, 4, 6… — the other side"]];
    for (var k = 1; k <= Math.ceil(bars / 2); k++) {
      var partner = bars + 1 - k;
      opts.push(["pair" + k, "Pair " + k,
                 partner === k ? "The centre bar on its own" : "Bars " + k + " & " + partner + ", outermost in"]);
    }
    for (var n = 1; n <= bars; n++) opts.push(["b" + n, "Bar " + n, "Just this one"]);
    return opts;
  }
  function groupLabel(group, bars) {
    var opts = groupOptions(bars);
    for (var i = 0; i < opts.length; i++) if (opts[i][0] === group) return opts[i][1];
    return group;
  }
  function mirrorOf(bar, bars) {
    var m = bars + 1 - bar;
    return m === bar ? null : m;
  }

  function hexRgb(hex) {
    var m = /^#?([0-9a-f]{6})$/i.exec(hex || "#000000");
    var v = parseInt(m ? m[1] : "000000", 16);
    return [v >> 16 & 255, v >> 8 & 255, v & 255];
  }
  function isBlackout(cue) {
    return !cue.intensity || hexRgb(cue.color).join(",") === "0,0,0";
  }

  // ---------- lighting resolver ----------
  function lightingAt(show, t) {
    // Per fixture: latest cue at or before t, faded in from the look before it.
    var bars = show.bars, out = [];
    var sorted = (show.cues || []).slice().sort(function (a, b) { return a.t - b.t; });
    for (var f = 1; f <= bars; f++) {
      var seq = sorted.filter(function (c) {
        return membersOf(c.group, bars).indexOf(f) >= 0;
      });
      var prev = {rgb: [0, 0, 0], inten: 0}, cur = null, before = prev;
      for (var i = 0; i < seq.length; i++) {
        if (seq[i].t <= t) { before = cur || prev; cur = seq[i]; }
        else break;
      }
      if (!cur) { out.push({rgb: [0, 0, 0], inten: 0}); continue; }
      var target = {rgb: hexRgb(cur.color), inten: (cur.intensity || 0) / 100};
      var from = cur === seq[0] ? {rgb: [0, 0, 0], inten: 0}
        : {rgb: hexRgb(before.color || "#000000"),
           inten: (before.intensity || 0) / 100};
      var k = Math.min(1, (t - cur.t) / Math.max(0.01, cur.fade || 0.01));
      out.push({
        rgb: [0, 1, 2].map(function (ci) {
          return Math.round(from.rgb[ci] + (target.rgb[ci] - from.rgb[ci]) * k);
        }),
        inten: from.inten + (target.inten - from.inten) * k
      });
    }
    return out;
  }

  // ---------- ENTTEC USB Pro framing ----------
  function dmxFrame(show, looks) {
    var data = new Uint8Array(513);        // start code + 512 channels
    var ch = 1;
    looks.forEach(function (look) {
      if (show.chans === 4) {
        data[ch++] = Math.round(look.inten * 255);
        data[ch++] = look.rgb[0]; data[ch++] = look.rgb[1]; data[ch++] = look.rgb[2];
      } else {
        data[ch++] = Math.round(look.rgb[0] * look.inten);
        data[ch++] = Math.round(look.rgb[1] * look.inten);
        data[ch++] = Math.round(look.rgb[2] * look.inten);
      }
    });
    var len = data.length;
    var pkt = new Uint8Array(5 + len);
    pkt[0] = 0x7E; pkt[1] = 6; pkt[2] = len & 255; pkt[3] = len >> 8;
    pkt.set(data, 4); pkt[4 + len] = 0xE7;
    return pkt;
  }

  // ---------- timecode ----------
  function fmtClock(t) {
    var m = Math.floor(t / 60), s = (t - m * 60);
    return m + ":" + (s < 10 ? "0" : "") + s.toFixed(1);
  }
  function fmtTimecode(t) {
    // M:SS.hh — what the big transport digits show.
    t = Math.max(0, t || 0);
    var m = Math.floor(t / 60), s = Math.floor(t - m * 60), h = Math.floor((t - m * 60 - s) * 100);
    return m + ":" + (s < 10 ? "0" : "") + s + "." + (h < 10 ? "0" : "") + h;
  }

  // ---------- waveform peaks ----------
  function peaks(channel, sampleRate, startSec, endSec, buckets) {
    // Max and min sample per horizontal bucket of the visible window.
    var n = channel.length;
    var s0 = Math.max(0, Math.floor(startSec * sampleRate));
    var s1 = Math.min(n, Math.ceil(endSec * sampleRate));
    var max = new Float32Array(buckets), min = new Float32Array(buckets);
    if (s1 <= s0 || buckets <= 0) return {max: max, min: min};
    var per = (s1 - s0) / buckets;
    var step = Math.max(1, Math.floor(per / 400));   // sample at most ~400 points per bucket
    for (var b = 0; b < buckets; b++) {
      var a = s0 + Math.floor(b * per), z = Math.min(s1, s0 + Math.floor((b + 1) * per));
      var hi = -1, lo = 1;
      if (z <= a) z = a + 1;
      for (var i = a; i < z && i < n; i += step) {
        var v = channel[i];
        if (v > hi) hi = v;
        if (v < lo) lo = v;
      }
      max[b] = hi === -1 ? 0 : hi; min[b] = lo === 1 ? 0 : lo;
    }
    return {max: max, min: min};
  }

  // ---------- onsets & tempo ----------
  function onsetEnvelope(mono, sampleRate, hop) {
    // Half-wave-rectified energy flux on short frames: a cheap onset
    // strength curve that is good enough to find a pulse.
    hop = hop || 512;
    var frames = Math.floor(mono.length / hop);
    var env = new Float32Array(frames);
    var prev = 0;
    for (var f = 0; f < frames; f++) {
      var e = 0, base = f * hop;
      for (var i = 0; i < hop; i++) { var v = mono[base + i]; e += v * v; }
      e = Math.sqrt(e / hop);
      env[f] = Math.max(0, e - prev);
      prev = e;
    }
    // normalise
    var mx = 0;
    for (var j = 0; j < frames; j++) if (env[j] > mx) mx = env[j];
    if (mx > 0) for (var k = 0; k < frames; k++) env[k] /= mx;
    return {env: env, hop: hop, rate: sampleRate / hop};
  }

  function detectBeats(mono, sampleRate, opts) {
    opts = opts || {};
    var minBpm = opts.minBpm || 60, maxBpm = opts.maxBpm || 200;
    var oe = onsetEnvelope(mono, sampleRate, opts.hop || 512);
    var env = oe.env, rate = oe.rate, n = env.length;
    if (n < rate * 4) return {bpm: 0, offset: 0, beats: [], confidence: 0};
    // autocorrelation over the lag range
    var minLag = Math.max(2, Math.floor(rate * 60 / maxBpm)), maxLag = Math.ceil(rate * 60 / minBpm);
    var best = 0, bestLag = 0, second = 0, ac = {};
    for (var lag = minLag - 1; lag <= maxLag + 1; lag++) {
      var s = 0;
      for (var i = lag; i < n; i++) s += env[i] * env[i - lag];
      // mild preference for lags near 120 BPM, like a listener's prior
      var bpmHere = 60 * rate / lag;
      var prior = Math.exp(-Math.pow(Math.log(bpmHere / 120), 2) / 0.8);
      s *= prior;
      ac[lag] = s;
      if (lag < minLag || lag > maxLag) continue;
      if (s > best) { second = best; best = s; bestLag = lag; }
      else if (s > second) second = s;
    }
    if (!bestLag) return {bpm: 0, offset: 0, beats: [], confidence: 0};
    // The true period is rarely a whole number of frames (120 BPM at 43 fps
    // is 21.5): refine the peak to a fraction of a lag by fitting a parabola
    // through its neighbours, else the tempo is off by a couple of percent.
    var l0 = ac[bestLag - 1] || 0, l1 = ac[bestLag], l2 = ac[bestLag + 1] || 0;
    var denom = l0 - 2 * l1 + l2;
    var frac = denom !== 0 ? 0.5 * (l0 - l2) / denom : 0;
    if (!(frac > -1 && frac < 1)) frac = 0;
    var lagF0 = bestLag + frac;
    var bpm = 60 * rate / lagF0;
    bpm = Math.round(bpm * 10) / 10;
    var period = 60 / bpm;                 // seconds
    // phase: which offset within one period lines up with the most onset energy
    var lagF = period * rate, bestOff = 0, bestSum = -1;
    var steps = Math.max(8, Math.round(lagF));
    for (var st = 0; st < steps; st++) {
      var off = st / steps * lagF, sum = 0;
      for (var p = off; p < n; p += lagF) sum += env[Math.floor(p)] || 0;
      if (sum > bestSum) { bestSum = sum; bestOff = off; }
    }
    var offset = bestOff / rate;
    var duration = mono.length / sampleRate;
    var beats = [];
    for (var b = offset; b < duration; b += period) beats.push(Math.round(b * 1000) / 1000);
    return {bpm: bpm, offset: Math.round(offset * 1000) / 1000, beats: beats,
            confidence: second > 0 ? Math.min(1, (best - second) / best + 0.2) : 1};
  }

  function snapToBeat(t, bpm, offset) {
    if (!bpm) return t;
    var period = 60 / bpm;
    var k = Math.round((t - (offset || 0)) / period);
    return Math.max(0, Math.round(((offset || 0) + k * period) * 1000) / 1000);
  }

  function tapTempo(taps) {
    // taps: ascending timestamps in seconds; BPM from the mean interval of
    // the last eight, ignoring gaps over two seconds (a new phrase).
    if (!taps || taps.length < 2) return 0;
    var recent = taps.slice(-8), ivs = [];
    for (var i = 1; i < recent.length; i++) {
      var d = recent[i] - recent[i - 1];
      if (d > 0.2 && d < 2) ivs.push(d);
    }
    if (!ivs.length) return 0;
    var mean = ivs.reduce(function (a, b) { return a + b; }, 0) / ivs.length;
    return Math.round(600 / mean) / 10;
  }

  function nearestCue(cues, t, tol) {
    var best = null, bd = tol;
    (cues || []).forEach(function (c) {
      var d = Math.abs(c.t - t);
      if (d <= bd) { bd = d; best = c; }
    });
    return best;
  }

  var LOOKS = [
    {key: "amber", name: "Amber wash", color: "#ffb347", intensity: 85, fade: 1.0},
    {key: "blue", name: "Cold blue", color: "#3b82f6", intensity: 80, fade: 1.0},
    {key: "red", name: "Red alert", color: "#ff2d2d", intensity: 90, fade: 0.3},
    {key: "white", name: "White full", color: "#ffffff", intensity: 100, fade: 0.2},
    {key: "violet", name: "Violet haze", color: "#8b5cf6", intensity: 70, fade: 1.5},
    {key: "blackout", name: "Blackout", color: "#000000", intensity: 0, fade: 0.1}
  ];

  return {
    membersOf: membersOf, groupOptions: groupOptions, groupLabel: groupLabel, mirrorOf: mirrorOf,
    hexRgb: hexRgb, isBlackout: isBlackout, lightingAt: lightingAt, dmxFrame: dmxFrame,
    fmtClock: fmtClock, fmtTimecode: fmtTimecode, peaks: peaks,
    onsetEnvelope: onsetEnvelope, detectBeats: detectBeats, snapToBeat: snapToBeat,
    tapTempo: tapTempo, nearestCue: nearestCue, LOOKS: LOOKS
  };
});
