/* Hear the Rack — the homepage's one hands-on moment.
 *
 * Press play and a house loop plays through the Rack's own stages: the
 * twelve-band EQ (same band table as /rack), the tube (same transfer
 * curve, copied verbatim from rackdsp.js), the compressor, and the
 * output trim - in miniature, the full desk being /rack itself. The
 * analyzer strip stops being a drawing and becomes a live spectrum of
 * the audio actually playing, and a row of eight lamps runs a light
 * show cued to the loop's beat grid.
 *
 * What is true and what is said: the loop is synthesized in this file
 * at runtime - nothing is uploaded, nothing is fetched, nothing is
 * anyone's record - and the page says so. Every cue is scheduled from
 * the loop's known tempo, not "detected". The Rack toggle really
 * bypasses the chain, so the difference heard is the difference made.
 *
 * Nothing here touches the six faders: those are the visitor's
 * strategic priorities, and no amount of audio can tell you your rights
 * position. The faders stay theirs; the sound becomes real.
 *
 * Respects prefers-reduced-motion (no light cues, the strip still
 * shows the live spectrum), the browser's autoplay rule (nothing plays
 * without a click), and photosensitivity (no cue flashes faster than
 * the kick, ~1.5/s at this tempo).
 */
(function (root) {
  "use strict";

  /* ------------------------------------------------------------------ */
  /* Pure parts, checked by tests/js/check_hear_the_rack.js              */
  /* ------------------------------------------------------------------ */
  var BPM = 92, BARS = 4, STEPS = 16;          /* 16th-note grid, four bars */
  var STEP_S = 60 / BPM / 4;
  var LOOP_S = STEP_S * STEPS * BARS;

  /* The Rack's band table, verbatim (rackdsp.js EQ_BANDS). */
  var EQ_BANDS = [
    {f: 40, type: "lowshelf"}, {f: 80, type: "peaking"}, {f: 120, type: "peaking"},
    {f: 250, type: "peaking"}, {f: 400, type: "peaking"}, {f: 630, type: "peaking"},
    {f: 1000, type: "peaking"}, {f: 1600, type: "peaking"}, {f: 2500, type: "peaking"},
    {f: 4000, type: "peaking"}, {f: 8000, type: "peaking"}, {f: 14000, type: "highshelf"}
  ];
  /* The Rack's "warm" preset: gains per band, tube, compressor, trim. */
  var PRESET = {
    eq: [2, 1, 0, -1.5, 0, 0, 0, 0, 0, 0.5, 1, 0.5], q: 1,
    tube: {drive: 3, bias: 0.25, mix: 0.35},
    comp: {thr: -18, ratio: 2, att: 0.03, rel: 0.3, makeup: 1},
    out: 0
  };

  /* The Rack's tube transfer curve, copied verbatim from rackdsp.js. */
  function tubeCurve(drive, bias) {
    var n = 2048, c = new Float32Array(n);
    var norm = Math.tanh(drive);
    for (var i = 0; i < n; i++) {
      var x = (i / (n - 1)) * 2 - 1;
      var d = x >= 0 ? drive * (1 + bias) : drive * (1 - bias * 0.6);
      c[i] = Math.tanh(d * x) / norm;
    }
    return c;
  }

  /* C minor, four bars: i - VI - III - VII. Frequencies, not names, so
     the voices need no lookup. */
  var CHORDS = [
    {root: 65.41, tones: [130.81, 155.56, 196.00]},   /* Cm  */
    {root: 51.91, tones: [103.83, 130.81, 155.56]},   /* Ab  */
    {root: 77.78, tones: [155.56, 196.00, 233.08]},   /* Eb  */
    {root: 58.27, tones: [116.54, 146.83, 174.61]}    /* Bb  */
  ];

  /* One bar of the groove, as 16th-note hits. Kick on the one, always -
     the light show's downbeat depends on it. Velocities 0..1. */
  function pattern(bar) {
    var kick = [1, 0, 0, 0, 0, 0, 0.9, 0, 0, 0, 1, 0, 0, 0, 0, 0];
    var snare = [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0];
    var hat = [0.7, 0, 0.5, 0, 0.7, 0, 0.5, 0.35, 0.7, 0, 0.5, 0, 0.7, 0, 0.5, 0.35];
    if (bar === 3) {                      /* the turnaround: a pickup */
      kick = [1, 0, 0, 0, 0, 0, 0.9, 0, 0, 0, 1, 0, 0, 0.8, 0, 0];
      snare = [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0.6];
    }
    var bass = [1, 0, 0, 0, 0, 0, 0.8, 0, 0, 0, 1, 0, 0, 0, 0.6, 0];
    return {kick: kick, snare: snare, hat: hat, bass: bass};
  }

  /* Every event of the loop as absolute times from loopStart. Sorted,
     so the scheduler can walk it with one cursor. */
  function schedule(loopStart) {
    var events = [];
    for (var bar = 0; bar < BARS; bar++) {
      var p = pattern(bar), chord = CHORDS[bar];
      events.push({t: loopStart + bar * STEPS * STEP_S, kind: "chord", chord: chord, bar: bar});
      for (var s = 0; s < STEPS; s++) {
        var t = loopStart + (bar * STEPS + s) * STEP_S;
        if (p.kick[s]) events.push({t: t, kind: "kick", v: p.kick[s], step: s, bar: bar});
        if (p.snare[s]) events.push({t: t, kind: "snare", v: p.snare[s], step: s, bar: bar});
        if (p.hat[s]) events.push({t: t, kind: "hat", v: p.hat[s], step: s, bar: bar});
        if (p.bass[s]) events.push({t: t, kind: "bass", v: p.bass[s], step: s, bar: bar, chord: chord});
      }
    }
    events.sort(function (a, b) { return a.t - b.t; });
    return events;
  }

  /* 48 bars over 40 Hz..16 kHz, log-spaced: which FFT bins feed which
     bar. Pure so the mapping is testable without an AudioContext. */
  function binMap(fftSize, sampleRate, bars) {
    var binHz = sampleRate / fftSize, out = [];
    for (var i = 0; i < bars; i++) {
      var lo = 40 * Math.pow(16000 / 40, i / bars);
      var hi = 40 * Math.pow(16000 / 40, (i + 1) / bars);
      var a = Math.max(1, Math.floor(lo / binHz)), b = Math.max(a + 1, Math.ceil(hi / binHz));
      out.push([a, b]);
    }
    return out;
  }

  var pure = {BPM: BPM, BARS: BARS, STEPS: STEPS, STEP_S: STEP_S, LOOP_S: LOOP_S,
              EQ_BANDS: EQ_BANDS, PRESET: PRESET, tubeCurve: tubeCurve,
              pattern: pattern, schedule: schedule, binMap: binMap};
  if (typeof module !== "undefined" && module.exports) { module.exports = pure; }
  if (typeof document === "undefined") { return; }

  /* ------------------------------------------------------------------ */
  /* The browser part                                                     */
  /* ------------------------------------------------------------------ */
  var section = document.getElementById("artist-eq");
  var playBtn = document.getElementById("sbeq-htr-play");
  var rackBtn = document.getElementById("sbeq-htr-rack");
  var status = document.getElementById("sbeq-htr-status");
  var lights = document.getElementById("sbeq-lights");
  if (!section || !playBtn || !rackBtn) { return; }

  var AC = root.AudioContext || root.webkitAudioContext;
  if (!AC) {
    playBtn.disabled = true;
    rackBtn.disabled = true;
    if (status) { status.textContent = "Needs Web Audio - this browser has none."; }
    return;
  }

  var reduced = false;
  try { reduced = root.matchMedia && root.matchMedia("(prefers-reduced-motion: reduce)").matches; }
  catch (e) { /* animate */ }

  var ac = null, chain = null, playing = false, loopStart = 0, timer = null;
  var events = [], cursor = 0, noiseBuf = null, rafId = null, lastStep = -1;

  function say(text) { if (status) { status.textContent = text; } }

  function track(name, detail) {
    try {
      if (typeof root.gtag === "function") { root.gtag("event", name, detail || {}); }
      else if (root.dataLayer && root.dataLayer.push) { root.dataLayer.push(Object.assign({event: name}, detail || {})); }
    } catch (e) { /* never break the page for analytics */ }
  }

  /* --- the Rack's stages, in miniature ------------------------------- */
  function buildChain(ctx) {
    var input = ctx.createGain();
    var node = input;
    var eqNodes = EQ_BANDS.map(function (b, i) {
      var f = ctx.createBiquadFilter();
      f.type = b.type; f.frequency.value = b.f; f.Q.value = PRESET.q;
      f.gain.value = PRESET.eq[i];
      node.connect(f); node = f;
      return f;
    });
    var tubeDry = ctx.createGain(), tubeWet = ctx.createGain(), tubeSum = ctx.createGain();
    var shaper = ctx.createWaveShaper();
    shaper.curve = tubeCurve(PRESET.tube.drive, PRESET.tube.bias);
    shaper.oversample = "2x";
    tubeDry.gain.value = 1 - PRESET.tube.mix;
    tubeWet.gain.value = PRESET.tube.mix;
    node.connect(tubeDry); node.connect(shaper); shaper.connect(tubeWet);
    tubeDry.connect(tubeSum); tubeWet.connect(tubeSum);
    var comp = ctx.createDynamicsCompressor();
    comp.threshold.value = PRESET.comp.thr; comp.ratio.value = PRESET.comp.ratio;
    comp.attack.value = PRESET.comp.att; comp.release.value = PRESET.comp.rel;
    comp.knee.value = 6;
    var makeup = ctx.createGain();
    makeup.gain.value = Math.pow(10, PRESET.comp.makeup / 20);
    var out = ctx.createGain();
    out.gain.value = Math.pow(10, PRESET.out / 20);
    tubeSum.connect(comp); comp.connect(makeup); makeup.connect(out);
    return {input: input, output: out, eq: eqNodes};
  }

  function build() {
    ac = new AC();
    var bus = ac.createGain(); bus.gain.value = 0.9;
    var rack = buildChain(ac);
    var wet = ac.createGain(), dry = ac.createGain(), sum = ac.createGain();
    wet.gain.value = 1; dry.gain.value = 0;
    bus.connect(rack.input); rack.output.connect(wet);
    bus.connect(dry);
    wet.connect(sum); dry.connect(sum);
    var analyser = ac.createAnalyser();
    analyser.fftSize = 2048; analyser.smoothingTimeConstant = 0.72;
    /* A safety limiter, so the bypass jump can never clip the output. */
    var lim = ac.createDynamicsCompressor();
    lim.threshold.value = -3; lim.ratio.value = 20; lim.attack.value = 0.002; lim.release.value = 0.08; lim.knee.value = 0;
    var master = ac.createGain(); master.gain.value = 0.7;
    sum.connect(analyser); analyser.connect(lim); lim.connect(master); master.connect(ac.destination);
    noiseBuf = ac.createBuffer(1, ac.sampleRate * 0.4, ac.sampleRate);
    var d = noiseBuf.getChannelData(0);
    for (var i = 0; i < d.length; i++) { d[i] = Math.random() * 2 - 1; }
    chain = {bus: bus, wet: wet, dry: dry, analyser: analyser, master: master,
             bins: binMap(analyser.fftSize, ac.sampleRate, 48),
             data: new Uint8Array(analyser.frequencyBinCount)};
  }

  /* --- the voices ----------------------------------------------------- */
  function env(param, t, peak, a, dcy, floor) {
    param.cancelScheduledValues(t);
    param.setValueAtTime(0.0001, t);
    param.linearRampToValueAtTime(peak, t + a);
    param.exponentialRampToValueAtTime(floor || 0.0001, t + a + dcy);
  }
  function kick(t, v) {
    var o = ac.createOscillator(), g = ac.createGain();
    o.type = "sine";
    o.frequency.setValueAtTime(150, t);
    o.frequency.exponentialRampToValueAtTime(44, t + 0.11);
    env(g.gain, t, 0.95 * v, 0.004, 0.32);
    o.connect(g); g.connect(chain.bus);
    o.start(t); o.stop(t + 0.4);
  }
  function snare(t, v) {
    var n = ac.createBufferSource(), bp = ac.createBiquadFilter(), g = ac.createGain();
    n.buffer = noiseBuf;
    bp.type = "bandpass"; bp.frequency.value = 1900; bp.Q.value = 0.9;
    env(g.gain, t, 0.55 * v, 0.003, 0.16);
    n.connect(bp); bp.connect(g); g.connect(chain.bus);
    n.start(t); n.stop(t + 0.25);
    var o = ac.createOscillator(), og = ac.createGain();
    o.type = "triangle"; o.frequency.setValueAtTime(210, t);
    o.frequency.exponentialRampToValueAtTime(140, t + 0.06);
    env(og.gain, t, 0.35 * v, 0.002, 0.09);
    o.connect(og); og.connect(chain.bus);
    o.start(t); o.stop(t + 0.15);
  }
  function hat(t, v) {
    var n = ac.createBufferSource(), hp = ac.createBiquadFilter(), g = ac.createGain();
    n.buffer = noiseBuf;
    hp.type = "highpass"; hp.frequency.value = 7400;
    env(g.gain, t, 0.22 * v, 0.001, 0.045);
    n.connect(hp); hp.connect(g); g.connect(chain.bus);
    n.start(t); n.stop(t + 0.08);
  }
  function bass(t, v, chord) {
    var o1 = ac.createOscillator(), o2 = ac.createOscillator(), sub = ac.createOscillator();
    var lp = ac.createBiquadFilter(), g = ac.createGain();
    o1.type = "sawtooth"; o2.type = "sawtooth"; sub.type = "sine";
    o1.frequency.value = chord.root; o2.frequency.value = chord.root; o2.detune.value = 7;
    sub.frequency.value = chord.root / 2;
    lp.type = "lowpass"; lp.Q.value = 5;
    lp.frequency.setValueAtTime(900, t);
    lp.frequency.exponentialRampToValueAtTime(240, t + 0.25);
    env(g.gain, t, 0.5 * v, 0.006, 0.42);
    o1.connect(lp); o2.connect(lp); lp.connect(g); sub.connect(g); g.connect(chain.bus);
    [o1, o2, sub].forEach(function (o) { o.start(t); o.stop(t + 0.5); });
  }
  function pad(t, chord) {
    var lp = ac.createBiquadFilter(), g = ac.createGain();
    lp.type = "lowpass"; lp.Q.value = 0.8;
    lp.frequency.setValueAtTime(700, t);
    lp.frequency.linearRampToValueAtTime(1600, t + STEP_S * STEPS * 0.5);
    lp.frequency.linearRampToValueAtTime(700, t + STEP_S * STEPS);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.linearRampToValueAtTime(0.13, t + 0.25);
    g.gain.setValueAtTime(0.13, t + STEP_S * STEPS - 0.15);
    g.gain.linearRampToValueAtTime(0.0001, t + STEP_S * STEPS + 0.02);
    chord.tones.forEach(function (f, i) {
      [-6, 6].forEach(function (cents) {
        var o = ac.createOscillator();
        o.type = i === 1 ? "triangle" : "sawtooth";
        o.frequency.value = f; o.detune.value = cents;
        o.connect(lp);
        o.start(t); o.stop(t + STEP_S * STEPS + 0.05);
      });
    });
    lp.connect(g); g.connect(chain.bus);
  }

  /* --- the scheduler: 100 ms of lookahead, every 25 ms --------------- */
  function tick() {
    var horizon = ac.currentTime + 0.1;
    while (true) {
      if (cursor >= events.length) {
        loopStart += LOOP_S;
        events = schedule(loopStart);
        cursor = 0;
      }
      var e = events[cursor];
      if (e.t > horizon) { break; }
      if (e.kind === "kick") kick(e.t, e.v);
      else if (e.kind === "snare") snare(e.t, e.v);
      else if (e.kind === "hat") hat(e.t, e.v);
      else if (e.kind === "bass") bass(e.t, e.v, e.chord);
      else if (e.kind === "chord") pad(e.t, e.chord);
      cursor++;
    }
  }

  /* --- the light show, cued from the grid ---------------------------- */
  var lamps = lights ? lights.querySelectorAll("i") : [];
  /* A cue changes the rig; between cues the rig HOLDS, the way a chase
     does - the lamps are not switched off on every 16th. Cues land on
     the one (full, then alternating by bar), the two and the four (the
     centre pair) and the off-beats three (the outer pair), so nothing
     changes faster than the kick. */
  function cue(step, bar) {
    if (!lamps.length || reduced) { return; }
    var one = step === 0, backbeat = step === 4 || step === 12, three = step === 8;
    if (!one && !backbeat && !three) { return; }
    for (var i = 0; i < lamps.length; i++) {
      var on;
      if (one) { on = bar === 0 ? true : (i % 2 === bar % 2); }
      else if (backbeat) { on = (i === 3 || i === 4); }
      else { on = (i === 0 || i === lamps.length - 1); }
      lamps[i].classList.toggle("is-on", on);
    }
    section.classList.toggle("is-downbeat", one);
  }

  /* --- the strip becomes a real spectrum ----------------------------- */
  var levels = new Float32Array(48), frames = 0;
  function frame() {
    rafId = null;
    if (!playing) { return; }
    /* Observable state for the tests and for anyone debugging with the
       inspector: frames drawn, the context's state, the last error. */
    frames++;
    section.setAttribute("data-frames", String(frames));
    section.setAttribute("data-ac", ac.state);
    try { drawLive(); }
    catch (e) { section.setAttribute("data-htr-error", String(e && e.message || e)); }
    rafId = root.requestAnimationFrame(frame);
  }
  function drawLive() {
    chain.analyser.getByteFrequencyData(chain.data);
    for (var i = 0; i < 48; i++) {
      var b = chain.bins[i], sum = 0;
      for (var k = b[0]; k < b[1]; k++) { sum += chain.data[k]; }
      var mean = sum / (b[1] - b[0]) / 255;
      levels[i] = Math.max(0, Math.min(1, Math.pow(mean, 0.85)));
    }
    if (root.SBEQ && root.SBEQ.analyzer) { root.SBEQ.analyzer.setLive(levels); }
    /* Where the loop is, as a step 0..63 - written to the section so
       the light show is observable without an AudioContext in hand. */
    var pos = ac.currentTime - loopStart;
    if (pos < 0) { pos += LOOP_S; }             /* tick() advances loopStart ~100 ms early */
    var step = Math.floor((pos % LOOP_S) / STEP_S);
    if (step !== lastStep) {
      lastStep = step;
      section.setAttribute("data-step", String(step));
      cue(step % STEPS, Math.floor(step / STEPS));
    }
  }

  /* --- controls ------------------------------------------------------- */
  function start() {
    if (!ac) { build(); }
    if (ac.state === "suspended") { ac.resume(); }
    playing = true;
    loopStart = ac.currentTime + 0.05;
    events = schedule(loopStart);
    cursor = 0; lastStep = -1;
    timer = root.setInterval(tick, 25);
    tick();
    playBtn.setAttribute("aria-pressed", "true");
    playBtn.textContent = "Stop";
    rackBtn.disabled = false;
    section.classList.add("is-playing");
    say(reduced ? "Playing. Light cues are off for reduced motion."
                : "Playing - toggle the Rack to hear what its stages do.");
    if (rafId === null) { rafId = root.requestAnimationFrame(frame); }
    track("hear_the_rack_played", {});
  }
  function stop() {
    playing = false;
    if (timer) { root.clearInterval(timer); timer = null; }
    if (rafId !== null && root.cancelAnimationFrame) { root.cancelAnimationFrame(rafId); rafId = null; }
    if (ac) { ac.suspend(); }
    if (root.SBEQ && root.SBEQ.analyzer) { root.SBEQ.analyzer.setLive(null); }
    for (var i = 0; i < lamps.length; i++) { lamps[i].classList.remove("is-on"); }
    section.classList.remove("is-playing", "is-downbeat");
    playBtn.setAttribute("aria-pressed", "false");
    playBtn.textContent = "Hear the Rack";
    say("");
  }
  playBtn.addEventListener("click", function () { if (playing) { stop(); } else { start(); } });

  var rackOn = true;
  rackBtn.addEventListener("click", function () {
    rackOn = !rackOn;
    var t = ac.currentTime;
    chain.wet.gain.cancelScheduledValues(t);
    chain.dry.gain.cancelScheduledValues(t);
    chain.wet.gain.setTargetAtTime(rackOn ? 1 : 0, t, 0.02);
    chain.dry.gain.setTargetAtTime(rackOn ? 0 : 1, t, 0.02);
    rackBtn.setAttribute("aria-pressed", rackOn ? "true" : "false");
    rackBtn.textContent = rackOn ? "Rack on" : "Rack off";
    section.classList.toggle("is-bypassed", !rackOn);
    say(rackOn ? "Rack in: EQ, tube and compressor on the loop."
               : "Rack out: the loop, dry.");
    track("hear_the_rack_toggled", {rack: rackOn ? "on" : "off"});
  });

  /* Leaving the section, or the tab, stops the sound. Nothing plays
     to an empty room. */
  document.addEventListener("visibilitychange", function () { if (document.hidden && playing) { stop(); } });
  if ("IntersectionObserver" in root) {
    new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (!e.isIntersecting && playing) { stop(); } });
    }, {threshold: 0}).observe(section);
  }
})(typeof window !== "undefined" ? window : this);
