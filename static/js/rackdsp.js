/* The Rack — SB-1200. All DSP runs here in the browser via Web Audio;
   nothing is uploaded. Knobs, meters, and curves read/write one state
   object; buildChain() is shared by live playback and offline export. */
(function () {
  "use strict";
  var EQ_BANDS = [
    {f: 40, type: "lowshelf", label: "40"},
    {f: 80, type: "peaking", label: "80"},
    {f: 120, type: "peaking", label: "120"},
    {f: 250, type: "peaking", label: "250"},
    {f: 400, type: "peaking", label: "400"},
    {f: 630, type: "peaking", label: "630"},
    {f: 1000, type: "peaking", label: "1k"},
    {f: 1600, type: "peaking", label: "1.6k"},
    {f: 2500, type: "peaking", label: "2.5k"},
    {f: 4000, type: "peaking", label: "4k"},
    {f: 8000, type: "peaking", label: "8k"},
    {f: 14000, type: "highshelf", label: "14k"}
  ];
  var LANES = [
    {label: "Sub / 808",       lo: 30,   hi: 70,    color: "#c94f4f"},
    {label: "Kick",            lo: 40,   hi: 100,   color: "#e05252"},
    {label: "Bass",            lo: 50,   hi: 250,   color: "#e07a3c"},
    {label: "Synths",          lo: 60,   hi: 2500,  color: "#4fc9b0"},
    {label: "Toms",            lo: 80,   hi: 300,   color: "#e0a03c"},
    {label: "Piano / Keys",    lo: 90,   hi: 1800,  color: "#3cc96a"},
    {label: "Guitars",         lo: 100,  hi: 1200,  color: "#8fbf5f"},
    {label: "Vocals",          lo: 110,  hi: 1300,  color: "#5f9fd6"},
    {label: "Snare",           lo: 150,  hi: 400,   color: "#e0c452"},
    {label: "Strings / Horns", lo: 150,  hi: 2000,  color: "#5fb8d6"},
    {label: "Presence",        lo: 2000, hi: 5000,  color: "#9d7fd6"},
    {label: "Hi-Hats",         lo: 3000, hi: 10000, color: "#c97fd6"},
    {label: "Air / Cymbals",   lo: 6000, hi: 16000, color: "#d67fb8"}
  ];
  var CABS = {
    direct:    null,
    combo112:  {hp: 90, ls: [120, 0],  p1: [800, 2],    p2: [2200, 1.5], lp1: 5000, lp2: 5200, lp3: 5600},
    open212:   {hp: 75, ls: [120, 0],  p1: [450, -1.5], p2: [2800, 2],   lp1: 5500, lp2: 6000, lp3: 6400},
    closed412: {hp: 70, ls: [120, 2],  p1: [700, -2],   p2: [2500, 2.5], lp1: 3900, lp2: 4050, lp3: 4200},
    bass810:   {hp: 40, ls: [100, 3],  p1: [800, -1],   p2: [1600, 1],   lp1: 3400, lp2: 3600, lp3: 3900}
  };
  var MICS = {
    dynamic:   {presence: [4500, 3],  top: [10000, -1], body: [150, 0]},
    ribbon:    {presence: [3000, -1], top: [5000, -4],  body: [150, 1.5]},
    condenser: {presence: [3000, 0],  top: [10000, 1],  body: [150, 0]}
  };
  var DEF_CAB = {cab: "direct", mic: "dynamic", axis: "on", dist: 0, on: true};
  var PRESETS = {
    flat:   {eq: [0,0,0,0,0,0,0,0,0,0,0,0], q: 1, tube: {drive: 1, bias: 0, mix: 0}, comp: {thr: 0, ratio: 1, att: 0.01, rel: 0.25, makeup: 0}, out: 0, cab: {cab: "direct", mic: "dynamic", axis: "on", dist: 0, on: true}},
    warm:   {eq: [2,1,0,-1.5,0,0,0,0,0,0.5,1,0.5], q: 1, tube: {drive: 3, bias: 0.25, mix: 0.35}, comp: {thr: -18, ratio: 2, att: 0.03, rel: 0.3, makeup: 1}, out: 0, cab: {cab: "direct", mic: "dynamic", axis: "on", dist: 0, on: true}},
    vocal:  {eq: [0,0,0,-2,-1,-0.5,0,1,2.5,2,1.5,1], q: 1.2, tube: {drive: 2, bias: 0.15, mix: 0.2}, comp: {thr: -22, ratio: 3, att: 0.01, rel: 0.2, makeup: 2}, out: 0, cab: {cab: "direct", mic: "dynamic", axis: "on", dist: 0, on: true}},
    bass:   {eq: [2,2,-1,-2,-1,0,0,0,0,0,0,0], q: 1.4, tube: {drive: 2.5, bias: 0.2, mix: 0.25}, comp: {thr: -26, ratio: 4, att: 0.005, rel: 0.15, makeup: 2}, out: 0, cab: {cab: "direct", mic: "dynamic", axis: "on", dist: 0, on: true}},
    guitar: {eq: [0,0,0,0,0,0,0,0,0,0,0,0], q: 1, tube: {drive: 4.5, bias: 0.3, mix: 0.6}, comp: {thr: -20, ratio: 2.5, att: 0.02, rel: 0.2, makeup: 2}, out: 0, cab: {cab: "closed412", mic: "dynamic", axis: "on", dist: 0.15, on: true}}
  };
  var saved = window.__savedRack || null;
  var state = (saved && saved.eq && saved.eq.length === EQ_BANDS.length)
    ? saved : JSON.parse(JSON.stringify(PRESETS.flat));
  if (!state.cab) state.cab = JSON.parse(JSON.stringify(DEF_CAB));
  function ensureFx(s) {
    if (!s.dly) s.dly = {time: 0.3, fb: 0.3, tone: 5000, mix: 0};
    if (!s.rev) s.rev = {size: 1.6, damp: 5000, pre: 0.02, mix: 0};
    if (!s.sub) s.sub = {depth: 0, growl: 0, shake: 0};
  }
  ensureFx(state);
  state.bypass = false;
  // Per-module power. Off neutralizes that module's processing in BOTH the
  // live chain and the offline export while the knobs keep their positions.
  if (!state.mods) state.mods = {};
  function modOn(m) {
    if (m === "cab") return !!state.cab.on;
    return state.mods[m] !== false;
  }

  var ctx = null, buffer = null, playing = null;
  var live = null;
  var loadedName = "";

  // ---------- chain ----------
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

  function mulberry32(seed) {
    return function () {
      seed |= 0; seed = seed + 0x6D2B79F5 | 0;
      var t = Math.imul(seed ^ seed >>> 15, 1 | seed);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }

  function roomIR(ac) {
    var rate = ac.sampleRate, len = Math.floor(rate * 0.18);
    var buf = ac.createBuffer(2, len, rate);
    for (var ch = 0; ch < 2; ch++) {
      var d = buf.getChannelData(ch), rnd = mulberry32(1337 + ch);
      d[0] = 1;
      for (var r = 0; r < 14; r++) {
        var at = Math.floor((0.008 + rnd() * 0.05) * rate);
        if (at < len) d[at] += (rnd() * 2 - 1) * 0.4 * Math.pow(0.75, r);
      }
      var lp = 0;
      for (var i = 1; i < len; i++) {
        var decay = Math.pow(1 - i / len, 2.2);
        lp = lp * 0.82 + (rnd() * 2 - 1) * 0.18;
        d[i] += lp * 0.25 * decay;
      }
    }
    return buf;
  }

  function bq(ac, type, f, gain, q) {
    var n = ac.createBiquadFilter();
    n.type = type; n.frequency.value = f;
    if (gain !== undefined) n.gain.value = gain;
    if (q !== undefined) n.Q.value = q;
    return n;
  }

  function buildCabMic(ac) {
    var m = {
      moduleIn: ac.createGain(), moduleOut: ac.createGain(),
      thru: ac.createGain(), procIn: ac.createGain(),
      hp: bq(ac, "highpass", 10, undefined, 0.7),
      ls: bq(ac, "lowshelf", 120, 0),
      p1: bq(ac, "peaking", 800, 0, 1),
      p2: bq(ac, "peaking", 2500, 0, 1),
      lp1: bq(ac, "lowpass", 20000, undefined, 0.7),
      lp2: bq(ac, "lowpass", 20000, undefined, 0.7),
      lp3: bq(ac, "lowpass", 20000, undefined, 0.7),
      micPresence: bq(ac, "peaking", 4500, 0, 1.2),
      micTop: bq(ac, "highshelf", 10000, 0),
      micBody: bq(ac, "lowshelf", 150, 0),
      axisCut: bq(ac, "highshelf", 4000, 0),
      proxLS: bq(ac, "lowshelf", 120, 0),
      distHS: bq(ac, "highshelf", 8000, 0),
      conv: ac.createConvolver(),
      convWet: ac.createGain(), convDry: ac.createGain()
    };
    m.conv.buffer = roomIR(ac);
    m.convWet.gain.value = 0;
    var chain = [m.hp, m.ls, m.p1, m.p2, m.lp1, m.lp2, m.lp3, m.micPresence,
                 m.micTop, m.micBody, m.axisCut, m.proxLS, m.distHS];
    var node = m.procIn;
    chain.forEach(function (f) { node.connect(f); node = f; });
    node.connect(m.convDry); m.convDry.connect(m.moduleOut);
    node.connect(m.conv); m.conv.connect(m.convWet); m.convWet.connect(m.moduleOut);
    m.moduleIn.connect(m.thru); m.thru.connect(m.moduleOut);
    m.moduleIn.connect(m.procIn);
    m.cabFilters = chain;
    return m;
  }

  function voiceCabMic(m) {
    var c = state.cab;
    var active = c.on && c.cab !== "direct" && CABS[c.cab];
    m.thru.gain.value = active ? 0 : 1;
    m.procIn.gain.value = active ? 1 : 0;
    if (!active) { m.convWet.gain.value = 0; m.convDry.gain.value = 1; return; }
    var cab = CABS[c.cab], mic = MICS[c.mic] || MICS.dynamic;
    m.hp.frequency.value = cab.hp;
    m.ls.frequency.value = cab.ls[0]; m.ls.gain.value = cab.ls[1];
    m.p1.frequency.value = cab.p1[0]; m.p1.gain.value = cab.p1[1];
    m.p2.frequency.value = cab.p2[0]; m.p2.gain.value = cab.p2[1];
    m.lp1.frequency.value = cab.lp1; m.lp2.frequency.value = cab.lp2;
    m.lp3.frequency.value = cab.lp3;
    m.micPresence.frequency.value = mic.presence[0]; m.micPresence.gain.value = mic.presence[1];
    m.micTop.frequency.value = mic.top[0]; m.micTop.gain.value = mic.top[1];
    m.micBody.frequency.value = mic.body[0]; m.micBody.gain.value = mic.body[1];
    m.axisCut.gain.value = c.axis === "off" ? -3.5 : 0;
    m.proxLS.gain.value = (1 - c.dist) * 3;
    m.distHS.gain.value = -1.5 * c.dist;
    m.convWet.gain.value = 0.35 * c.dist;
    m.convDry.gain.value = 1 - 0.2 * c.dist;
  }

  function reverbIR(ac, size) {
    // Seeded decaying noise: the same space every render, live or offline.
    var rate = ac.sampleRate, len = Math.max(1, Math.floor(rate * size));
    var buf = ac.createBuffer(2, len, rate);
    for (var ch = 0; ch < 2; ch++) {
      var d = buf.getChannelData(ch), rnd = mulberry32(4242 + ch);
      for (var i = 0; i < len; i++) {
        d[i] = (rnd() * 2 - 1) * Math.pow(1 - i / len, 2.6);
      }
    }
    return buf;
  }

  function buildSub(ac) {
    // Foundation: protective HP + deep shelf + 42Hz room resonance in the
    // main path; a parallel band generates harmonics OF the sub region so
    // small speakers perceive lows they can't reproduce (psychoacoustics).
    var m = {inNode: ac.createGain(), outNode: ac.createGain(),
             protect: bq(ac, "highpass", 24, undefined, 0.7),
             depth: bq(ac, "lowshelf", 45, 0),
             shake: bq(ac, "peaking", 42, 0, 2.2),
             band: bq(ac, "lowpass", 120, undefined, 0.7),
             drive: ac.createWaveShaper(),
             growlHP: bq(ac, "highpass", 90, undefined, 0.7),
             growl: ac.createGain()};
    var n = 1024, c = new Float32Array(n);
    for (var i = 0; i < n; i++) {
      var x = (i / (n - 1)) * 2 - 1;
      // Asymmetric: odd AND even harmonics of the sub band, tube-style.
      c[i] = Math.tanh(3 * x + 1.1 * x * x) - Math.tanh(1.1 * (i === 0 ? 1 : 1)) * 0;
    }
    m.drive.curve = c; m.drive.oversample = "2x";
    m.growl.gain.value = 0;
    m.inNode.connect(m.protect); m.protect.connect(m.depth);
    m.depth.connect(m.shake); m.shake.connect(m.outNode);
    m.inNode.connect(m.band); m.band.connect(m.drive);
    m.drive.connect(m.growlHP); m.growlHP.connect(m.growl);
    m.growl.connect(m.outNode);
    return m;
  }

  function voiceSub(m) {
    var on = modOn("sub") ? 1 : 0;
    m.depth.gain.value = state.sub.depth * on;
    m.shake.gain.value = state.sub.shake * 8 * on;
    m.growl.gain.value = state.sub.growl * 0.7 * on;
  }

  function buildFx(ac) {
    var fx = {inNode: ac.createGain(), outNode: ac.createGain(),
              dDry: ac.createGain(), dWet: ac.createGain(),
              delay: ac.createDelay(2), fb: ac.createGain(),
              tone: bq(ac, "lowpass", 5000, undefined, 0.7),
              rDry: ac.createGain(), rWet: ac.createGain(),
              pre: ac.createDelay(0.2), conv: ac.createConvolver(),
              damp: bq(ac, "lowpass", 5000, undefined, 0.7), irSize: 0};
    var mid = ac.createGain();
    fx.inNode.connect(fx.dDry); fx.dDry.connect(mid);
    fx.inNode.connect(fx.delay);
    fx.delay.connect(fx.tone); fx.tone.connect(fx.fb); fx.fb.connect(fx.delay);
    fx.tone.connect(fx.dWet); fx.dWet.connect(mid);
    mid.connect(fx.rDry); fx.rDry.connect(fx.outNode);
    mid.connect(fx.pre); fx.pre.connect(fx.conv); fx.conv.connect(fx.damp);
    fx.damp.connect(fx.rWet); fx.rWet.connect(fx.outNode);
    return fx;
  }

  function voiceFx(fx, ac) {
    fx.delay.delayTime.value = state.dly.time;
    fx.fb.gain.value = state.dly.fb;
    fx.tone.frequency.value = state.dly.tone;
    fx.dWet.gain.value = modOn("dly") ? state.dly.mix : 0; fx.dDry.gain.value = 1;
    var sz = Math.round(state.rev.size * 10) / 10;
    if (fx.irSize !== sz) { fx.conv.buffer = reverbIR(ac, sz); fx.irSize = sz; }
    fx.pre.delayTime.value = state.rev.pre;
    fx.damp.frequency.value = state.rev.damp;
    fx.rWet.gain.value = modOn("rev") ? state.rev.mix : 0; fx.rDry.gain.value = 1;
  }

  function buildCenterMatrix(ac) {
    var split = ac.createChannelSplitter(2), merge = ac.createChannelMerger(2);
    var m = {input: split, output: merge,
             ll: ac.createGain(), rl: ac.createGain(),
             lr: ac.createGain(), rr: ac.createGain()};
    split.connect(m.ll, 0); split.connect(m.lr, 0);
    split.connect(m.rl, 1); split.connect(m.rr, 1);
    m.ll.connect(merge, 0, 0); m.rl.connect(merge, 0, 0);
    m.lr.connect(merge, 0, 1); m.rr.connect(merge, 0, 1);
    return m;
  }

  function voiceCenter(cm) {
    var mode = state.center || "normal";
    var v = mode === "solo"   ? [0.5, 0.5, 0.5, 0.5]
          : mode === "remove" ? [0.5, -0.5, -0.5, 0.5]
          : [1, 0, 0, 1];
    cm.ll.gain.value = v[0]; cm.rl.gain.value = v[1];
    cm.lr.gain.value = v[2]; cm.rr.gain.value = v[3];
  }

  function buildChain(ac, dest) {
    var input = ac.createGain();
    // Mono sources must duplicate to both channels before the mid/side split.
    input.channelCount = 2;
    input.channelCountMode = "explicit";
    var filters = EQ_BANDS.map(function (b, i) {
      var f = ac.createBiquadFilter();
      f.type = b.type; f.frequency.value = b.f;
      f.Q.value = state.q; f.gain.value = state.eq[i];
      return f;
    });
    var tube = ac.createWaveShaper();
    tube.curve = tubeCurve(state.tube.drive, state.tube.bias);
    tube.oversample = "4x";
    var wetTube = ac.createGain(); wetTube.gain.value = state.tube.mix;
    var dryTube = ac.createGain(); dryTube.gain.value = 1 - state.tube.mix;
    var cabMic = buildCabMic(ac);
    var comp = ac.createDynamicsCompressor();
    comp.threshold.value = state.comp.thr; comp.ratio.value = state.comp.ratio;
    comp.attack.value = state.comp.att; comp.release.value = state.comp.rel;
    comp.knee.value = 6;
    var makeup = ac.createGain();
    makeup.gain.value = Math.pow(10, state.comp.makeup / 20);
    var outGain = ac.createGain();
    outGain.gain.value = Math.pow(10, state.out / 20);

    var centerM = buildCenterMatrix(ac);
    voiceCenter(centerM);
    input.connect(centerM.input);
    var node = centerM.output;
    filters.forEach(function (f) { node.connect(f); node = f; });
    var sub = buildSub(ac);
    voiceSub(sub);
    node.connect(sub.inNode);
    node = sub.outNode;
    node.connect(tube); tube.connect(wetTube);
    node.connect(dryTube);
    var sum = ac.createGain();
    wetTube.connect(sum); dryTube.connect(sum);
    sum.connect(cabMic.moduleIn);
    voiceCabMic(cabMic);
    cabMic.moduleOut.connect(comp);
    comp.connect(makeup);
    var fx = buildFx(ac);
    voiceFx(fx, ac);
    makeup.connect(fx.inNode);
    fx.outNode.connect(outGain);
    outGain.connect(dest);
    return {input: input, filters: filters, tube: tube, wetTube: wetTube,
            dryTube: dryTube, cabMic: cabMic, comp: comp, makeup: makeup,
            outGain: outGain, out: outGain, centerM: centerM, fx: fx, sub: sub};
  }

  function ensureCtx() {
    if (!ctx) {
      ctx = new (window.AudioContext || window.webkitAudioContext)();
      live = buildChain(ctx, ctx.destination);
      live.analyser = ctx.createAnalyser();
      live.analyser.fftSize = 4096;
      live.analyser.smoothingTimeConstant = 0.8;
      live.outGain.connect(live.analyser);
      live.wet = ctx.createGain(); live.dry = ctx.createGain();
      live.dry.gain.value = 0;
      live.wet.connect(live.input);
      live.dry.connect(ctx.destination);
      live.dry.connect(live.analyser);
    }
    return ctx;
  }

  function updateGlow() {
    var el = document.getElementById("tube-glow");
    if (!el) return;
    var heat = modOn("tube")
      ? Math.min(1, ((state.tube.drive - 1) / 9) * (0.25 + 0.75 * state.tube.mix))
      : 0;
    el.style.opacity = (0.12 + 0.88 * heat).toFixed(2);
    el.style.boxShadow = "0 0 " + Math.round(3 + heat * 14) + "px rgba(255,156,63," + (heat * 0.7).toFixed(2) + ")";
  }

  /* Voice one chain (live or offline) from state, honoring module power.
     Off modules read as neutral: EQ gains 0, tube fully dry, comp 1:1 at
     0dB, sends muted, trim 0dB — knob positions stay untouched. */
  function voiceChain(c, ac) {
    var eqOn = modOn("eq"), tubeOn = modOn("tube"), compOn = modOn("comp");
    c.filters.forEach(function (f, i) {
      f.gain.value = eqOn ? state.eq[i] : 0; f.Q.value = state.q;
    });
    c.tube.curve = tubeCurve(state.tube.drive, state.tube.bias);
    c.wetTube.gain.value = tubeOn ? state.tube.mix : 0;
    c.dryTube.gain.value = tubeOn ? 1 - state.tube.mix : 1;
    voiceCabMic(c.cabMic);
    voiceCenter(c.centerM);
    voiceFx(c.fx, ac);
    voiceSub(c.sub);
    c.comp.threshold.value = compOn ? state.comp.thr : 0;
    c.comp.ratio.value = compOn ? state.comp.ratio : 1;
    c.comp.attack.value = state.comp.att;
    c.comp.release.value = state.comp.rel;
    c.makeup.gain.value = Math.pow(10, (compOn ? state.comp.makeup : 0) / 20);
    c.outGain.gain.value = Math.pow(10, (modOn("out") ? state.out : 0) / 20);
  }

  function applyState() {
    if (live) {
      voiceChain(live, ctx);
      live.wet.gain.value = state.bypass ? 0 : 1;
      live.dry.gain.value = state.bypass ? 1 : 0;
    }
    updateGlow();
    syncModButtons();
    eqCurveDirty = true;
  }

  // ---------- knob factory ----------
  function knobPt(r, aDeg) {
    var a = (aDeg - 90) * Math.PI / 180;
    return [40 + r * Math.cos(a), 40 + r * Math.sin(a)];
  }
  function knobArc(r, a0, a1) {
    var p0 = knobPt(r, a0), p1 = knobPt(r, a1);
    var large = Math.abs(a1 - a0) > 180 ? 1 : 0;
    var sweep = a1 > a0 ? 1 : 0;
    return "M" + p0[0].toFixed(2) + " " + p0[1].toFixed(2) +
           " A" + r + " " + r + " 0 " + large + " " + sweep + " " +
           p1[0].toFixed(2) + " " + p1[1].toFixed(2);
  }
  var knobUid = 0;

  // One floating readout shared by every knob: shows the exact value while
  // dragging or wheeling, fades when released.
  var knobTip = null, knobTipT = null;
  function showTip(x, y, text) {
    if (!knobTip) {
      knobTip = document.createElement("div");
      knobTip.style.cssText =
        "position:fixed;z-index:60;pointer-events:none;padding:3px 9px;" +
        "border:1px solid #8a6d1f;border-radius:4px;background:#141209;" +
        "color:#e8c667;font:700 12px/1.4 ui-monospace,monospace;" +
        "transform:translate(-50%,-135%);box-shadow:0 2px 8px rgba(0,0,0,.6);display:none;";
      document.body.appendChild(knobTip);
    }
    knobTip.textContent = text;
    knobTip.style.left = x + "px";
    knobTip.style.top = y + "px";
    knobTip.style.display = "block";
  }
  function hideTip() { if (knobTip) knobTip.style.display = "none"; }

  /* makeKnob: one rotary control. opts:
     min/max/def, bipolar (arc from 12 o'clock), size px, label, fmt(v),
     wheelStep, decimals, get(), set(v) -> writes state. Returns {el, sync}. */
  function makeKnob(opts) {
    var id = "kb" + (knobUid++);
    var col = document.createElement("div");
    col.className = "flex flex-col items-center";
    var val = document.createElement("div");
    val.className = "font-mono text-[10px] font-bold tabular-nums";
    var wrap = document.createElement("div");
    wrap.style.touchAction = "none";
    wrap.style.cursor = "ns-resize";
    wrap.innerHTML =
      '<svg viewBox="0 0 80 80" width="' + opts.size + '" height="' + opts.size + '">' +
      '<defs><radialGradient id="' + id + '" cx="0.35" cy="0.3" r="0.9">' +
      '<stop offset="0" stop-color="#f0dfa8"/><stop offset="0.45" stop-color="#d8b25a"/>' +
      '<stop offset="0.8" stop-color="#8a6d1f"/><stop offset="1" stop-color="#5c4715"/>' +
      '</radialGradient></defs>' +
      '<circle cx="40" cy="40" r="33" fill="none" stroke="#332e22" stroke-width="3" stroke-dasharray="1.8 3.95"/>' +
      '<path d="' + knobArc(29, -135, 135) + '" fill="none" stroke="#221e16" stroke-width="5" stroke-linecap="round"/>' +
      '<path class="k-glow" fill="none" stroke-width="9" stroke-linecap="round" opacity="0.22"/>' +
      '<path class="k-arc" fill="none" stroke-width="4.5" stroke-linecap="round"/>' +
      '<circle cx="40" cy="40" r="22" fill="url(#' + id + ')"/>' +
      '<circle cx="40" cy="40" r="22" fill="none" stroke="#1c1302" stroke-width="2"/>' +
      '<circle cx="40" cy="40" r="22" fill="none" stroke="rgba(255,255,255,0.14)" stroke-width="0.8"/>' +
      '<line class="k-ptr" x1="40" y1="40" x2="40" y2="21.5" stroke="#f7efd8" stroke-width="3" stroke-linecap="round"/>' +
      '<circle cx="40" cy="40" r="2.4" fill="#1c1302"/>' +
      '</svg>';
    var svg = wrap.firstChild;
    var ptr = svg.querySelector(".k-ptr");
    var arc = svg.querySelector(".k-arc");
    var glow = svg.querySelector(".k-glow");
    var lab = document.createElement("div");
    lab.className = "text-[9px] font-bold uppercase tracking-wide";
    lab.style.color = "#b3a684";  // readable on the dark wells
    lab.textContent = opts.label;

    function angleOf(v) {
      return -135 + (v - opts.min) / (opts.max - opts.min) * 270;
    }
    function paint() {
      var v = opts.get();
      var ang = angleOf(v);
      ptr.setAttribute("transform", "rotate(" + ang + " 40 40)");
      var from = opts.bipolar ? 0 : -135;
      var isCut = opts.bipolar && v < 0;
      var color = isCut ? "#e07a3c" : "#e8c667";
      var near = Math.abs(ang - from) < 1.5;
      if (near) {
        arc.setAttribute("d", ""); glow.setAttribute("d", "");
      } else {
        var d = ang > from ? knobArc(29, from, ang) : knobArc(29, ang, from);
        arc.setAttribute("d", d); arc.setAttribute("stroke", color);
        glow.setAttribute("d", d); glow.setAttribute("stroke", color);
      }
      val.textContent = opts.fmt(v);
      val.style.color = opts.bipolar
        ? (Math.abs(v) < 1e-6 ? "#9a8f78" : color) : "#e8c667";
    }
    function setVal(v) {
      v = Math.max(opts.min, Math.min(opts.max, v));
      v = Math.round(v / opts.wheelStep * 5) * opts.wheelStep / 5;   // fine grid
      v = Math.round(v * 1000) / 1000;
      if (v === opts.get()) return;
      opts.set(v);
      paint(); applyState();
    }
    var drag = null;
    function tipText() { return opts.label + "  " + opts.fmt(opts.get()); }
    wrap.addEventListener("pointerdown", function (e) {
      var r = wrap.getBoundingClientRect();
      drag = {y: e.clientY, v: opts.get(), tx: r.left + r.width / 2, ty: r.top};
      wrap.setPointerCapture(e.pointerId);
      showTip(drag.tx, drag.ty, tipText());
      e.preventDefault();
    });
    wrap.addEventListener("pointermove", function (e) {
      if (drag) {
        setVal(drag.v + (drag.y - e.clientY) * (opts.max - opts.min) / 200);
        showTip(drag.tx, drag.ty, tipText());
      }
    });
    wrap.addEventListener("pointerup", function () { drag = null; hideTip(); });
    wrap.addEventListener("pointercancel", function () { drag = null; hideTip(); });
    wrap.addEventListener("dblclick", function () { setVal(opts.def); });
    wrap.addEventListener("wheel", function (e) {
      e.preventDefault();
      setVal(opts.get() + (e.deltaY < 0 ? opts.wheelStep : -opts.wheelStep));
      var r = wrap.getBoundingClientRect();
      showTip(r.left + r.width / 2, r.top, tipText());
      clearTimeout(knobTipT);
      knobTipT = setTimeout(hideTip, 700);
    }, {passive: false});
    paint();
    col.appendChild(val); col.appendChild(wrap); col.appendChild(lab);
    return {el: col, sync: paint};
  }

  // ---------- EQ + module knobs ----------
  var eqWrap = document.getElementById("rk-eq");
  function renderEq() {
    eqWrap.innerHTML = "";
    EQ_BANDS.forEach(function (b, i) {
      var k = makeKnob({
        min: -12, max: 12, def: 0, bipolar: true,
        size: eqWrap.dataset.ksize ? +eqWrap.dataset.ksize : 58,
        label: b.label, wheelStep: 0.5,
        fmt: function (v) { return (v > 0 ? "+" : "") + (v === 0 ? "0.0" : v.toFixed(1)); },
        get: function () { return state.eq[i]; },
        set: function (v) { state.eq[i] = v; }
      });
      eqWrap.appendChild(k.el);
    });
  }
  document.getElementById("rk-eq-flat").addEventListener("click", function () {
    state.eq = state.eq.map(function () { return 0; });
    renderEq(); applyState();
  });

  var MOD_KNOBS = [
    {kn: "drive",  min: 1, max: 10, def: 2, size: 64, label: "Drive", wheelStep: 0.1,
     fmt: function (v) { return v.toFixed(1); },
     get: function () { return state.tube.drive; }, set: function (v) { state.tube.drive = v; }},
    {kn: "bias",   min: 0, max: 0.6, def: 0.2, size: 64, label: "Bias", wheelStep: 0.02,
     fmt: function (v) { return v.toFixed(2); },
     get: function () { return state.tube.bias; }, set: function (v) { state.tube.bias = v; }},
    {kn: "mix",    min: 0, max: 1, def: 0.3, size: 64, label: "Mix", wheelStep: 0.05,
     fmt: function (v) { return Math.round(v * 100) + "%"; },
     get: function () { return state.tube.mix; }, set: function (v) { state.tube.mix = v; }},
    {kn: "dist",   min: 0, max: 1, def: 0, size: 60, label: "Distance", wheelStep: 0.05,
     fmt: function (v) { return Math.round(v * 100) + "%"; },
     get: function () { return state.cab.dist; }, set: function (v) { state.cab.dist = v; }},
    {kn: "thr",    min: -60, max: 0, def: -24, size: 62, label: "Threshold", wheelStep: 1,
     fmt: function (v) { return Math.round(v) + " dB"; },
     get: function () { return state.comp.thr; }, set: function (v) { state.comp.thr = v; }},
    {kn: "ratio",  min: 1, max: 20, def: 3, size: 62, label: "Ratio", wheelStep: 0.5,
     fmt: function (v) { return v + ":1"; },
     get: function () { return state.comp.ratio; }, set: function (v) { state.comp.ratio = v; }},
    {kn: "att",    min: 0.001, max: 0.3, def: 0.01, size: 62, label: "Attack", wheelStep: 0.005,
     fmt: function (v) { return Math.round(v * 1000) + " ms"; },
     get: function () { return state.comp.att; }, set: function (v) { state.comp.att = v; }},
    {kn: "rel",    min: 0.05, max: 1, def: 0.25, size: 62, label: "Release", wheelStep: 0.05,
     fmt: function (v) { return Math.round(v * 1000) + " ms"; },
     get: function () { return state.comp.rel; }, set: function (v) { state.comp.rel = v; }},
    {kn: "makeup", min: 0, max: 12, def: 0, size: 62, label: "Makeup", wheelStep: 0.5,
     fmt: function (v) { return "+" + v + " dB"; },
     get: function () { return state.comp.makeup; }, set: function (v) { state.comp.makeup = v; }},
    {kn: "sdepth", min: 0, max: 9, def: 0, size: 62, label: "Depth", wheelStep: 0.5,
     fmt: function (v) { return "+" + v.toFixed(1) + " dB"; },
     get: function () { return state.sub.depth; }, set: function (v) { state.sub.depth = v; }},
    {kn: "sgrowl", min: 0, max: 1, def: 0, size: 62, label: "Growl", wheelStep: 0.05,
     fmt: function (v) { return Math.round(v * 100) + "%"; },
     get: function () { return state.sub.growl; }, set: function (v) { state.sub.growl = v; }},
    {kn: "sshake", min: 0, max: 1, def: 0, size: 62, label: "Shake", wheelStep: 0.05,
     fmt: function (v) { return Math.round(v * 100) + "%"; },
     get: function () { return state.sub.shake; }, set: function (v) { state.sub.shake = v; }},
    {kn: "dtime",  min: 0.02, max: 1.2, def: 0.3, size: 60, label: "Time", wheelStep: 0.01,
     fmt: function (v) { return Math.round(v * 1000) + " ms"; },
     get: function () { return state.dly.time; }, set: function (v) { state.dly.time = v; }},
    {kn: "dfb",    min: 0, max: 0.85, def: 0.3, size: 60, label: "Feedback", wheelStep: 0.05,
     fmt: function (v) { return Math.round(v * 100) + "%"; },
     get: function () { return state.dly.fb; }, set: function (v) { state.dly.fb = v; }},
    {kn: "dtone",  min: 500, max: 12000, def: 5000, size: 60, label: "Tone", wheelStep: 250,
     fmt: function (v) { return v >= 1000 ? (v / 1000).toFixed(1) + "k" : Math.round(v); },
     get: function () { return state.dly.tone; }, set: function (v) { state.dly.tone = v; }},
    {kn: "dmix",   min: 0, max: 1, def: 0, size: 60, label: "Mix", wheelStep: 0.05,
     fmt: function (v) { return Math.round(v * 100) + "%"; },
     get: function () { return state.dly.mix; }, set: function (v) { state.dly.mix = v; }},
    {kn: "rsize",  min: 0.3, max: 5, def: 1.6, size: 60, label: "Size", wheelStep: 0.1,
     fmt: function (v) { return v.toFixed(1) + " s"; },
     get: function () { return state.rev.size; }, set: function (v) { state.rev.size = v; }},
    {kn: "rdamp",  min: 1000, max: 12000, def: 5000, size: 60, label: "Damping", wheelStep: 250,
     fmt: function (v) { return (v / 1000).toFixed(1) + "k"; },
     get: function () { return state.rev.damp; }, set: function (v) { state.rev.damp = v; }},
    {kn: "rpre",   min: 0, max: 0.08, def: 0.02, size: 60, label: "Pre-delay", wheelStep: 0.005,
     fmt: function (v) { return Math.round(v * 1000) + " ms"; },
     get: function () { return state.rev.pre; }, set: function (v) { state.rev.pre = v; }},
    {kn: "rmix",   min: 0, max: 1, def: 0, size: 60, label: "Mix", wheelStep: 0.05,
     fmt: function (v) { return Math.round(v * 100) + "%"; },
     get: function () { return state.rev.mix; }, set: function (v) { state.rev.mix = v; }},
    {kn: "out",    min: -24, max: 12, def: 0, size: 68, label: "Gain", bipolar: true, wheelStep: 0.5,
     fmt: function (v) { return (v > 0 ? "+" : "") + v + " dB"; },
     get: function () { return state.out; }, set: function (v) { state.out = v; }}
  ];
  var modKnobRefs = [];
  MOD_KNOBS.forEach(function (spec) {
    var mount = document.querySelector('[data-kn="' + spec.kn + '"]');
    if (!mount) return;
    if (mount.dataset.ksize) spec = Object.assign({}, spec, {size: +mount.dataset.ksize});
    var k = makeKnob(spec);
    mount.appendChild(k.el);
    modKnobRefs.push(k);
  });
  var qMount = document.getElementById("kn-q");
  var qKnob = makeKnob({
    min: 0.4, max: 3, def: 1, label: "Q", wheelStep: 0.1,
    size: qMount.dataset.ksize ? +qMount.dataset.ksize : 44,
    fmt: function (v) { return v.toFixed(1); },
    get: function () { return state.q; }, set: function (v) { state.q = v; }
  });
  qMount.appendChild(qKnob.el);
  modKnobRefs.push(qKnob);

  function syncAll() {
    renderEq();
    modKnobRefs.forEach(function (k) { k.sync(); });
    document.getElementById("rk-cab-on").checked = !!state.cab.on;
    document.getElementById("rk-cab-cab").value = state.cab.cab;
    document.getElementById("rk-cab-mic").value = state.cab.mic;
    document.querySelectorAll("input[name=rk-axis]").forEach(function (el) {
      el.checked = el.value === state.cab.axis;
    });
    setCenterButtons();
  }

  // ---------- transport ----------
  var fileInput = document.getElementById("rk-file");
  var playBtn = document.getElementById("rk-play");
  var abBtn = document.getElementById("rk-ab");
  var exportBtn = document.getElementById("rk-export");
  var statusEl = document.getElementById("rk-status");
  var scopeLamp = document.getElementById("scope-lamp");

  function loadFile(file) {
    ensureCtx().resume();
    file.arrayBuffer().then(function (ab) { return ctx.decodeAudioData(ab); })
      .then(function (buf) {
        buffer = buf;
        loadedName = file.name.replace(/\.[^.]+$/, "");
        document.getElementById("rk-fileinfo").textContent =
          file.name + " — " + buf.duration.toFixed(1) + "s · " +
          buf.numberOfChannels + "ch · " + buf.sampleRate + "Hz";
        playBtn.disabled = abBtn.disabled = exportBtn.disabled = false;
        renderWave();
      })
      .catch(function () { statusEl.textContent = "Couldn't decode that file."; });
  }
  fileInput.addEventListener("change", function () {
    if (fileInput.files[0]) loadFile(fileInput.files[0]);
  });
  document.addEventListener("dragover", function (e) { e.preventDefault(); });
  document.addEventListener("drop", function (e) {
    e.preventDefault();
    if (e.dataTransfer.files[0]) loadFile(e.dataTransfer.files[0]);
  });

  var stems = [];

  function stemGainValue(st) {
    var anySolo = stems.some(function (s) { return s.solo; });
    if (anySolo) return st.solo ? st.gain : 0;
    return st.mute ? 0 : st.gain;
  }
  function refreshStemGains() {
    stems.forEach(function (st) {
      if (st.playGain) st.playGain.gain.value = stemGainValue(st);
    });
  }

  function stop() {
    if (playing) {
      (Array.isArray(playing) ? playing : [playing]).forEach(function (s) {
        try { s.stop(); } catch (e) {}
      });
      playing = null;
    }
    stems.forEach(function (st) { st.playGain = null; });
    playBtn.textContent = "Play";
    scopeLamp.classList.remove("grn");
  }
  // Playback tracks its position so the waveform scrubber can seek.
  var playT0 = 0, playOffset = 0;

  function duration() {
    if (stems.length) {
      return Math.max.apply(null, stems.map(function (s) { return s.buffer.duration; }));
    }
    return buffer ? buffer.duration : 0;
  }

  function startPlayback(offset) {
    ensureCtx().resume();
    var loop = document.getElementById("rk-loop").checked;
    offset = Math.max(0, Math.min(offset || 0, Math.max(0, duration() - 0.05)));
    if (stems.length) {
      var t0 = ctx.currentTime + 0.06;
      var sources = [];
      stems.forEach(function (st) {
        var src = ctx.createBufferSource();
        src.buffer = st.buffer; src.loop = loop;
        var gn = ctx.createGain();
        gn.gain.value = stemGainValue(st);
        st.playGain = gn;
        src.connect(gn); gn.connect(live.wet); gn.connect(live.dry);
        src.start(t0, Math.min(offset, Math.max(0, st.buffer.duration - 0.01)));
        sources.push(src);
      });
      sources[0].onended = function () { if (playing === sources) stop(); };
      playing = sources;
      playT0 = t0;
    } else {
      var src = ctx.createBufferSource();
      src.buffer = buffer;
      src.loop = loop;
      src.connect(live.wet); src.connect(live.dry);
      src.onended = function () { if (playing === src) stop(); };
      src.start(0, offset);
      playing = src;
      playT0 = ctx.currentTime;
    }
    playOffset = offset;
    playBtn.textContent = "Stop";
    scopeLamp.classList.add("grn");
  }

  function playPos() {
    if (!playing || !ctx) return 0;
    var d = duration();
    if (!d) return 0;
    var p = playOffset + (ctx.currentTime - playT0);
    return document.getElementById("rk-loop").checked ? p % d : Math.min(p, d);
  }

  function seek(t) {
    if (!buffer && !stems.length) return;
    if (playing) stop();
    startPlayback(t);
  }

  playBtn.addEventListener("click", function () {
    if (playing) { stop(); return; }
    startPlayback(0);
  });
  abBtn.addEventListener("click", function () {
    state.bypass = !state.bypass;
    abBtn.textContent = "Bypass: " + (state.bypass ? "ON (raw)" : "OFF");
    abBtn.classList.toggle("sw-lit", state.bypass);
    applyState();
  });

  // ---------- stem deck UI ----------
  var stemsWrap = document.getElementById("rk-stems");

  function renderStems() {
    stemsWrap.innerHTML = "";
    if (!stems.length) {
      stemsWrap.innerHTML = '<p class="text-[11px] text-gray-600">No stems loaded. ' +
        'Add your vocal, drums, bass, and music bounces — then mute what ' +
        "shouldn't be in the mix and export.</p>";
      return;
    }
    stems.forEach(function (st, i) {
      var row = document.createElement("div");
      row.className = "flex flex-wrap items-center gap-2 rounded border px-3 py-2 " +
        (st.solo ? "border-[#c9a24a]/50 bg-[#c9a24a]/10"
                 : st.mute ? "border-white/5 bg-black/20 opacity-60"
                 : "border-white/10 bg-black/30");
      var name = document.createElement("span");
      name.className = "min-w-0 flex-1 truncate text-xs font-bold";
      name.textContent = st.name;
      var dur = document.createElement("span");
      dur.className = "text-[10px] tabular-nums text-gray-600";
      dur.textContent = st.buffer.duration.toFixed(1) + "s";
      var gain = document.createElement("input");
      gain.type = "range"; gain.min = 0; gain.max = 1.2; gain.step = 0.02;
      gain.value = st.gain;
      gain.className = "w-28 accent-[#c9a24a]";
      gain.addEventListener("input", function () {
        st.gain = parseFloat(gain.value); refreshStemGains();
      });
      var mute = document.createElement("button");
      mute.textContent = "M"; mute.title = "Mute";
      mute.className = "sw h-7 w-7 text-[11px] " + (st.mute ? "sw-lit" : "");
      mute.addEventListener("click", function () {
        st.mute = !st.mute; if (st.mute) st.solo = false;
        renderStems(); refreshStemGains();
      });
      var solo = document.createElement("button");
      solo.textContent = "S"; solo.title = "Solo";
      solo.className = "sw h-7 w-7 text-[11px] " + (st.solo ? "sw-lit" : "");
      solo.addEventListener("click", function () {
        st.solo = !st.solo; if (st.solo) st.mute = false;
        renderStems(); refreshStemGains();
      });
      var rm = document.createElement("button");
      rm.textContent = "×"; rm.title = "Remove stem";
      rm.className = "sw h-7 w-7 text-sm text-gray-500";
      rm.addEventListener("click", function () {
        stop(); stems.splice(i, 1); renderStems(); syncDeckInfo(); renderWave();
      });
      row.appendChild(name); row.appendChild(dur); row.appendChild(gain);
      row.appendChild(mute); row.appendChild(solo); row.appendChild(rm);
      stemsWrap.appendChild(row);
    });
  }

  function syncDeckInfo() {
    if (stems.length) {
      document.getElementById("rk-fileinfo").textContent =
        stems.length + " stem" + (stems.length > 1 ? "s" : "") +
        " loaded — deck mode: Play mixes them through the rack.";
      playBtn.disabled = abBtn.disabled = exportBtn.disabled = false;
    } else if (buffer) {
      playBtn.disabled = abBtn.disabled = exportBtn.disabled = false;
    } else {
      document.getElementById("rk-fileinfo").textContent =
        "No file loaded — drop a WAV/MP3 anywhere on this page.";
      playBtn.disabled = abBtn.disabled = exportBtn.disabled = true;
    }
  }

  document.getElementById("rk-stems-file").addEventListener("change", function (e) {
    var files = Array.prototype.slice.call(e.target.files || []);
    if (!files.length) return;
    ensureCtx().resume();
    Promise.all(files.map(function (f) {
      return f.arrayBuffer()
        .then(function (ab) { return ctx.decodeAudioData(ab); })
        .then(function (buf) { return {name: f.name, buffer: buf, gain: 1, mute: false, solo: false, playGain: null}; })
        .catch(function () { return null; });
    })).then(function (loaded) {
      var ok = loaded.filter(Boolean);
      stems = stems.concat(ok).slice(0, 8);
      if (loaded.length !== ok.length) statusEl.textContent = "Some files couldn't be decoded.";
      stop(); renderStems(); syncDeckInfo(); renderWave();
    });
    e.target.value = "";
  });

  function setCenterButtons() {
    document.querySelectorAll(".rk-center").forEach(function (x) {
      x.classList.toggle("sw-lit", x.dataset.center === (state.center || "normal"));
    });
  }
  document.querySelectorAll(".rk-center").forEach(function (b) {
    b.addEventListener("click", function () {
      state.center = b.dataset.center;
      setCenterButtons();
      applyState();
    });
  });

  // ---------- per-module power + A/B compare ----------
  var MOD_KEYS = {tube: ["tube"], eq: ["eq", "q"], sub: ["sub"], comp: ["comp"],
                  cab: ["cab"], dly: ["dly"], rev: ["rev"], out: ["out"]};

  function modSlice(m) {
    var o = {};
    MOD_KEYS[m].forEach(function (k) { o[k] = JSON.parse(JSON.stringify(state[k])); });
    return o;
  }
  var cmpA = {};  // per-module snapshot: the "other side" of A/B
  var cmpSide = {};  // which side each module is showing: "A" (yours) or "B" (stored)
  function syncAbLeds() {
    document.querySelectorAll(".rk-ledwrap").forEach(function (wsp) {
      var side = cmpSide[wsp.dataset.mod] || "A";
      wsp.querySelector(".rk-la").classList.toggle("on", side === "A");
      wsp.querySelector(".rk-lb").classList.toggle("on", side === "B");
    });
  }
  function resetCompare() {
    Object.keys(MOD_KEYS).forEach(function (m) { cmpA[m] = modSlice(m); });
    cmpSide = {};
    document.querySelectorAll(".rk-cmp").forEach(function (b) {
      b.classList.remove("sw-lit");
    });
    syncAbLeds();
  }
  function syncModButtons() {
    document.querySelectorAll(".rk-pwr").forEach(function (b) {
      var on = modOn(b.dataset.mod);
      b.classList.toggle("sw-lit", on);
      b.textContent = on ? "ON" : "OFF";
    });
  }
  document.querySelectorAll(".rk-pwr").forEach(function (b) {
    b.addEventListener("click", function () {
      var m = b.dataset.mod;
      if (m === "cab") state.cab.on = !state.cab.on;
      else state.mods[m] = state.mods[m] === false;
      syncAll(); applyState();
    });
  });
  document.querySelectorAll(".rk-cmp").forEach(function (b) {
    b.addEventListener("click", function () {
      var m = b.dataset.mod;
      var cur = modSlice(m);
      MOD_KEYS[m].forEach(function (k) { state[k] = cmpA[m][k]; });
      cmpA[m] = cur;
      cmpSide[m] = cmpSide[m] === "B" ? "A" : "B";
      b.classList.toggle("sw-lit");
      syncAbLeds();
      syncAll(); applyState();
    });
  });

  document.querySelectorAll(".rk-preset").forEach(function (b) {
    b.addEventListener("click", function () {
      var p = JSON.parse(JSON.stringify(PRESETS[b.dataset.preset]));
      p.bypass = state.bypass;
      p.center = state.center || "normal";
      p.mods = state.mods;
      state = p; ensureFx(state); syncAll(); applyState();
      resetCompare();
      statusEl.textContent = "Preset loaded.";
    });
  });
  document.getElementById("rk-save").addEventListener("click", function () {
    fetch("/rack/save", {method: "POST", headers: {"Content-Type": "application/json"},
                         body: JSON.stringify(state)})
      .then(function (r) { return r.json(); })
      .then(function (d) { statusEl.textContent = d.ok ? "Rack saved — loads with the page." : "Save failed."; })
      .catch(function () { statusEl.textContent = "Save failed."; });
  });

  // ---------- cab & mic selectors ----------
  document.getElementById("rk-cab-on").addEventListener("change", function (e) {
    state.cab.on = e.target.checked; applyState();
  });
  document.getElementById("rk-cab-cab").addEventListener("change", function (e) {
    state.cab.cab = e.target.value; applyState();
  });
  document.getElementById("rk-cab-mic").addEventListener("change", function (e) {
    state.cab.mic = e.target.value; applyState();
  });
  document.querySelectorAll("input[name=rk-axis]").forEach(function (el) {
    el.addEventListener("change", function () {
      state.cab.axis = el.value; applyState();
    });
  });

  // ---------- transport dock: waveform scrubber + proxies ----------
  var waveCache = null;

  function renderWave() {
    var wc = document.getElementById("rk-wave");
    if (!wc) return;
    var buf = stems.length
      ? stems.reduce(function (a, s) {
          return s.buffer.duration > a.buffer.duration ? s : a;
        }, stems[0]).buffer
      : buffer;
    var wg = wc.getContext("2d");
    var W = wc.width = wc.clientWidth || 300, H = wc.height = wc.clientHeight || 40;
    wg.clearRect(0, 0, W, H);
    if (!buf) { waveCache = null; return; }
    var d = buf.getChannelData(0), step = Math.max(1, Math.floor(d.length / W));
    var hop = Math.max(1, Math.floor(step / 24));
    wg.strokeStyle = "rgba(216,178,90,0.8)"; wg.lineWidth = 1;
    wg.beginPath();
    for (var x = 0; x < W; x++) {
      var mn = 0, mx = 0;
      for (var j = x * step; j < (x + 1) * step && j < d.length; j += hop) {
        var v = d[j];
        if (v < mn) mn = v; if (v > mx) mx = v;
      }
      wg.moveTo(x + 0.5, H / 2 - mx * H * 0.48);
      wg.lineTo(x + 0.5, H / 2 - mn * H * 0.48 + 0.5);
    }
    wg.stroke();
    waveCache = wg.getImageData(0, 0, W, H);
  }
  var waveEl = document.getElementById("rk-wave");
  if (waveEl) {
    waveEl.addEventListener("click", function (e) {
      var d = duration();
      if (!d) return;
      var r = waveEl.getBoundingClientRect();
      seek((e.clientX - r.left) / r.width * d);
    });
  }
  function mmss(s) {
    s = Math.max(0, Math.floor(s));
    return Math.floor(s / 60) + ":" + ("0" + (s % 60)).slice(-2);
  }
  var dockPlay = document.getElementById("rk-play2"),
      dockAb = document.getElementById("rk-ab2"),
      dockExp = document.getElementById("rk-export2");
  if (dockPlay) dockPlay.addEventListener("click", function () { playBtn.click(); });
  if (dockAb) dockAb.addEventListener("click", function () { abBtn.click(); });
  if (dockExp) dockExp.addEventListener("click", function () { exportBtn.click(); });

  // ---------- SB-11 snippet finder: real energy scan, honest hooks ----------
  function scanHooks(len) {
    var buf = buffer || (stems.length
      ? stems.reduce(function (a, s) {
          return s.buffer.duration > a.buffer.duration ? s : a;
        }, stems[0]).buffer
      : null);
    if (!buf || buf.duration <= len + 1) return null;
    var d = buf.getChannelData(0), rate = buf.sampleRate;
    var hop = Math.floor(rate / 4);  // 0.25s frames
    var frames = Math.floor(d.length / hop);
    var rms = new Float32Array(frames);
    for (var f = 0; f < frames; f++) {
      var s = 0, base = f * hop;
      for (var j = 0; j < hop; j += 16) {
        var v = d[base + j];
        s += v * v;
      }
      rms[f] = s;
    }
    var win = Math.round(len * 4), best = 0, run = 0;
    for (f = 0; f < win && f < frames; f++) run += rms[f];
    var bestSum = run;
    for (f = win; f < frames; f++) {
      run += rms[f] - rms[f - win];
      if (run > bestSum) { bestSum = run; best = f - win + 1; }
    }
    return {start: best / 4, len: len};
  }
  var hookPreviewT = null;
  function previewHook(h) {
    seek(h.start);
    clearTimeout(hookPreviewT);
    hookPreviewT = setTimeout(function () { if (playing) stop(); }, h.len * 1000 + 100);
  }
  function exportHookWav(h) {
    if (!buffer && !stems.length) return;
    statusEl.textContent = "Rendering snippet…";
    var rate = stems.length ? stems[0].buffer.sampleRate : buffer.sampleRate;
    var oc = new OfflineAudioContext(2, Math.floor(h.len * rate), rate);
    var chain = buildChain(oc, oc.destination);
    voiceChain(chain, oc);
    if (stems.length) {
      stems.forEach(function (st) {
        var src = oc.createBufferSource();
        src.buffer = st.buffer;
        var gn = oc.createGain();
        gn.gain.value = stemGainValue(st);
        src.connect(gn); gn.connect(chain.input);
        src.start(0, Math.min(h.start, Math.max(0, st.buffer.duration - 0.01)), h.len);
      });
    } else {
      var src = oc.createBufferSource();
      src.buffer = buffer;
      src.connect(chain.input);
      src.start(0, h.start, h.len);
    }
    oc.startRendering().then(function (rendered) {
      var a = document.createElement("a");
      a.download = (loadedName || "hook") + "-" + h.len + "s.wav";
      a.href = URL.createObjectURL(encodeWav(rendered));
      a.click();
      statusEl.textContent = "Snippet WAV downloaded — processed through the rack.";
    }).catch(function () { statusEl.textContent = "Snippet render failed."; });
  }
  function renderHookVideo(h) {
    if (!window.MediaRecorder) {
      statusEl.textContent = "This browser can't record video — use the WAV export.";
      return;
    }
    ensureCtx().resume();
    var vc = document.createElement("canvas");
    vc.width = 720; vc.height = 1280;
    var vg = vc.getContext("2d");
    var dest = ctx.createMediaStreamDestination();
    live.outGain.connect(dest);
    var tracks = vc.captureStream(30).getVideoTracks()
      .concat(dest.stream.getAudioTracks());
    var rec;
    try { rec = new MediaRecorder(new MediaStream(tracks), {mimeType: "video/webm"}); }
    catch (e) { rec = new MediaRecorder(new MediaStream(tracks)); }
    var chunks = [];
    rec.ondataavailable = function (e) { if (e.data.size) chunks.push(e.data); };
    rec.onstop = function () {
      try { live.outGain.disconnect(dest); } catch (e) {}
      var a = document.createElement("a");
      a.download = (loadedName || "hook") + "-" + h.len + "s-vertical.webm";
      a.href = URL.createObjectURL(new Blob(chunks, {type: "video/webm"}));
      a.click();
      statusEl.textContent = "Vertical video downloaded (WebM — phone editors convert to MP4).";
      if (playing) stop();
    };
    var vFreq = new Uint8Array(live.analyser.frequencyBinCount);
    var t0 = performance.now();
    function frame() {
      if (rec.state !== "recording") return;
      vg.fillStyle = "#0a0908"; vg.fillRect(0, 0, 720, 1280);
      live.analyser.getByteFrequencyData(vFreq);
      var bars = 48, cx = 360, cy = 560, R = 200;
      for (var b = 0; b < bars; b++) {
        var bin = Math.floor(Math.pow(b / bars, 1.6) * (vFreq.length * 0.6));
        var e2 = vFreq[bin] / 255;
        var a2 = (b / bars) * Math.PI * 2 - Math.PI / 2;
        vg.strokeStyle = "rgba(216,178,90," + (0.3 + e2 * 0.7).toFixed(2) + ")";
        vg.lineWidth = 7;
        vg.beginPath();
        vg.moveTo(cx + Math.cos(a2) * R, cy + Math.sin(a2) * R);
        vg.lineTo(cx + Math.cos(a2) * (R + 14 + e2 * 130),
                  cy + Math.sin(a2) * (R + 14 + e2 * 130));
        vg.stroke();
      }
      vg.textAlign = "center";
      vg.fillStyle = "#e8c667";
      vg.font = "900 44px Arial";
      vg.fillText((loadedName || "Untitled").slice(0, 24).toUpperCase(), 360, 1080);
      vg.fillStyle = "#8a7c5d";
      vg.font = "700 18px Arial";
      vg.fillText("STREET BANKER · ROYALTY SWEEP", 360, 1118);
      var prog = Math.min(1, (performance.now() - t0) / (h.len * 1000));
      vg.fillStyle = "rgba(255,255,255,0.12)"; vg.fillRect(60, 1180, 600, 6);
      vg.fillStyle = "#e8c667"; vg.fillRect(60, 1180, 600 * prog, 6);
      requestAnimationFrame(frame);
    }
    seek(h.start);
    rec.start();
    statusEl.textContent = "Recording " + h.len + "s vertical video — keep this tab visible…";
    frame();
    setTimeout(function () { if (rec.state === "recording") rec.stop(); }, h.len * 1000 + 200);
  }
  var hookBtn = document.getElementById("rk-hook-scan");
  if (hookBtn) hookBtn.addEventListener("click", function () {
    var wrap2 = document.getElementById("rk-hooks");
    wrap2.innerHTML = "";
    [15, 30].forEach(function (L) {
      var h = scanHooks(L);
      if (!h) return;
      var row = document.createElement("div");
      row.className = "flex flex-wrap items-center gap-2 rounded border border-white/10 bg-black/30 px-3 py-2";
      var lab2 = document.createElement("span");
      lab2.className = "min-w-0 flex-1 text-xs font-bold";
      lab2.textContent = "Best " + L + "s hook · starts at " + mmss(h.start);
      row.appendChild(lab2);
      [["Preview", function () { previewHook(h); }],
       ["Snippet WAV", function () { exportHookWav(h); }],
       ["Vertical video", function () { renderHookVideo(h); }]].forEach(function (bd) {
        var btn = document.createElement("button");
        btn.className = "sw px-2.5 py-1 text-[10px]";
        btn.textContent = bd[0];
        btn.addEventListener("click", bd[1]);
        row.appendChild(btn);
      });
      wrap2.appendChild(row);
    });
    if (!wrap2.children.length) {
      wrap2.innerHTML = '<p class="text-[11px] text-gray-600">Load a track longer than ~16 seconds first.</p>';
    }
  });

  // ---------- Rack -> Smart Link handoff ----------
  var rolloutBtn = document.getElementById("rk-rollout");
  if (rolloutBtn) rolloutBtn.addEventListener("click", function () {
    var facts = [];
    var d = duration();
    if (d) facts.push(mmss(d));
    var pk = document.getElementById("rk-peakdb").textContent;
    if (pk && pk !== "−∞") facts.push("peak " + pk);
    if (stems.length) facts.push(stems.length + " stems");
    window.location = "/links/new?title=" + encodeURIComponent(loadedName || "") +
      "&rack=" + encodeURIComponent("bounced through The Rack" +
        (facts.length ? " — " + facts.join(" · ") : ""));
  });

  // ---------- focus mode: hide the app sidebar while dialing in ----------
  var focusBtn = document.getElementById("rk-focus");
  var sideEl = document.querySelector("aside");
  function setFocus(onF) {
    if (sideEl) sideEl.style.display = onF ? "none" : "";
    if (focusBtn) {
      focusBtn.classList.toggle("sw-lit", onF);
      focusBtn.textContent = onF ? "Exit focus" : "Focus mode";
    }
    try { localStorage.setItem("rkFocus", onF ? "1" : ""); } catch (e) {}
  }
  if (focusBtn) {
    focusBtn.addEventListener("click", function () {
      setFocus(!(sideEl && sideEl.style.display === "none"));
    });
    try { if (localStorage.getItem("rkFocus")) setFocus(true); } catch (e) {}
  }

  // ---------- scope ----------
  var canvas = document.getElementById("rk-scope");
  var g = canvas.getContext("2d");
  var eqCurveDirty = true, eqCurve = null, cabCurve = null;
  var FMIN = 20, FMAX = 20000;
  // Screen mode: the canvas lives inside the photo chassis window — it tracks
  // its slot height, drops the label gutter, and draws slim unlabeled lanes
  // (the lane legend renders in HTML under the chassis instead).
  var SCREEN = canvas.hasAttribute("data-screen");
  var GUT = SCREEN ? 14 : 108;
  var selLane = -1, laneHitRects = [];
  var zeroCache = 0, spanCache = 1, nodeDrag = -1, nodeMoved = false;
  canvas.style.touchAction = "none";
  var vuPos = 0;
  function fx(f, w) {
    return GUT + Math.log(f / FMIN) / Math.log(FMAX / FMIN) * (w - GUT - 10);
  }

  function responseOf(filters) {
    var n = 200, freqs = new Float32Array(n),
        mag = new Float32Array(n), ph = new Float32Array(n),
        total = new Float32Array(n).fill(0);
    for (var i = 0; i < n; i++) freqs[i] = FMIN * Math.pow(FMAX / FMIN, i / (n - 1));
    filters.forEach(function (f) {
      f.getFrequencyResponse(freqs, mag, ph);
      for (var i = 0; i < n; i++) total[i] += 20 * Math.log10(mag[i] || 1e-6);
    });
    return {freqs: freqs, db: total};
  }

  function laneBar(x1, y, x2, h, style) {
    g.fillStyle = style;
    if (g.roundRect) {
      g.beginPath(); g.roundRect(x1, y, Math.max(2, x2 - x1), h, 4); g.fill();
    } else {
      g.fillRect(x1, y, Math.max(2, x2 - x1), h);
    }
  }

  var freqData = null, timeData = null;
  function draw() {
    requestAnimationFrame(draw);
    var w = canvas.clientWidth;
    if (canvas.width !== w) canvas.width = w;
    if (SCREEN) {
      var chh = canvas.clientHeight;
      if (chh && canvas.height !== chh) canvas.height = chh;
    }
    var h = canvas.height;
    // In screen mode the lane block adapts to the window height; labels
    // draw in-canvas whenever the lanes are tall enough to carry them.
    var laneH = SCREEN
      ? Math.max(7, Math.min(15, Math.floor(h * 0.52 / LANES.length)))
      : 15;
    var laneLabels = !SCREEN || laneH >= 10;
    GUT = SCREEN ? (laneLabels ? 84 : 14) : 108;
    var lanesTop = h - LANES.length * laneH - (SCREEN ? 6 : 10);
    g.clearRect(0, 0, w, h);

    var binHz = ctx ? ctx.sampleRate / (live.analyser.fftSize) : 0;
    if (live && playing) {
      if (!freqData) { freqData = new Uint8Array(live.analyser.frequencyBinCount);
                       timeData = new Uint8Array(live.analyser.fftSize); }
      live.analyser.getByteFrequencyData(freqData);
      live.analyser.getByteTimeDomainData(timeData);
    }

    g.font = "9px Arial";
    [50, 100, 250, 500, 1000, 2500, 6000, 12000].forEach(function (f) {
      var x = fx(f, w);
      g.fillStyle = "rgba(150,140,120,0.14)";
      g.fillRect(x, 22, 1, h - 30);
      g.fillStyle = "rgba(150,140,120,0.6)";
      g.fillText(f >= 1000 ? (f / 1000) + "k" : f, x + 3, 16);
    });

    if (freqData && playing) {
      g.beginPath();
      for (var px = GUT; px <= w - 10; px += 2) {
        var f = FMIN * Math.pow(FMAX / FMIN, (px - GUT) / (w - GUT - 10));
        var bin = Math.min(freqData.length - 1, Math.round(f / binHz));
        var v = freqData[bin] / 255;
        var y = lanesTop - 8 - v * (lanesTop - 34);
        px === GUT ? g.moveTo(px, y) : g.lineTo(px, y);
      }
      g.strokeStyle = "rgba(232,198,103,0.85)"; g.lineWidth = 1.4; g.stroke();
      g.lineTo(w - 10, lanesTop - 8); g.lineTo(GUT, lanesTop - 8); g.closePath();
      var grad = g.createLinearGradient(0, 22, 0, lanesTop - 8);
      grad.addColorStop(0, "rgba(232,198,103,0.42)");
      grad.addColorStop(1, "rgba(232,198,103,0.04)");
      g.fillStyle = grad; g.fill();
    }

    if (eqCurveDirty && live) {
      eqCurve = responseOf(live.filters);
      var cc = state.cab;
      cabCurve = (cc.on && cc.cab !== "direct")
        ? responseOf(live.cabMic.cabFilters) : null;
      eqCurveDirty = false;
    }
    var zero = (lanesTop - 8) * 0.55, span = (lanesTop - 8) * 0.35 / 12;
    if (cabCurve) {
      g.beginPath();
      for (var ci = 0; ci < cabCurve.freqs.length; ci++) {
        var cxp = fx(cabCurve.freqs[ci], w);
        var cyp = zero - Math.max(-14, Math.min(14, cabCurve.db[ci])) * span;
        ci === 0 ? g.moveTo(cxp, cyp) : g.lineTo(cxp, cyp);
      }
      g.setLineDash([5, 4]);
      g.strokeStyle = "rgba(216,178,90,0.8)"; g.lineWidth = 1.2; g.stroke();
      g.setLineDash([]);
    }
    if (eqCurve) {
      g.beginPath();
      for (var i = 0; i < eqCurve.freqs.length; i++) {
        var x = fx(eqCurve.freqs[i], w);
        var y = zero - eqCurve.db[i] * span;
        i === 0 ? g.moveTo(x, y) : g.lineTo(x, y);
      }
      g.strokeStyle = "#f3ead2"; g.lineWidth = 1.5; g.stroke();
      g.strokeStyle = "rgba(255,255,255,0.1)"; g.lineWidth = 1;
      g.beginPath(); g.moveTo(GUT, zero); g.lineTo(w - 10, zero); g.stroke();
      // Draggable band nodes riding the curve: grab one and pull.
      zeroCache = zero; spanCache = span;
      EQ_BANDS.forEach(function (b, ni) {
        var nx = fx(b.f, w), ny = zero - state.eq[ni] * span;
        g.beginPath();
        g.arc(nx, ny, ni === nodeDrag ? 6 : 4.5, 0, 6.2832);
        g.fillStyle = ni === nodeDrag ? "#f3ead2" : "rgba(232,198,103,0.92)";
        g.fill();
        g.strokeStyle = "#1c1302"; g.lineWidth = 1.2; g.stroke();
      });
    }

    g.strokeStyle = "rgba(201,162,74,0.25)";
    g.beginPath(); g.moveTo(0, lanesTop - 2); g.lineTo(w, lanesTop - 2); g.stroke();

    LANES.forEach(function (lane, li) {
      var y = lanesTop + 4 + li * laneH;
      var x1 = fx(lane.lo, w), x2 = fx(lane.hi, w);
      var energy = 0;
      if (freqData && playing && binHz) {
        var b1 = Math.max(0, Math.floor(lane.lo / binHz));
        var b2 = Math.min(freqData.length - 1, Math.ceil(lane.hi / binHz));
        var sum = 0;
        for (var b = b1; b <= b2; b++) sum += freqData[b];
        energy = (sum / (b2 - b1 + 1)) / 255;
      }
      laneHitRects[li] = [y, laneH];
      if (laneLabels) {
        g.fillStyle = li === selLane ? "#e8c667"
          : energy > 0.04 ? lane.color : "rgba(160,150,130,0.55)";
        g.font = (SCREEN ? "bold 8px" : "bold 9px") + " Arial";
        g.textAlign = "right";
        g.fillText(lane.label.toUpperCase(), GUT - 10, y + laneH - (SCREEN ? 3 : 6));
        g.textAlign = "left";
      }
      var bo = SCREEN ? 1 : 2, bh = laneH - (SCREEN ? 3 : 6);
      laneBar(x1, y + bo, x2, bh, lane.color + "26");
      if (energy > 0.04) {
        var alpha = Math.round(Math.min(1, energy * 1.6) * 200 + 55)
          .toString(16).padStart(2, "0");
        laneBar(x1, y + bo, x1 + (x2 - x1) * Math.min(1, energy * 1.3), bh,
                lane.color + alpha);
      }
      if (li === selLane) {
        g.fillStyle = "rgba(232,198,103,0.09)";
        g.fillRect(2, y - 1, w - 4, laneH + 2);
        g.strokeStyle = "#e8c667"; g.lineWidth = 1.4;
        g.strokeRect(x1 - 2, y + bo - 2, (x2 - x1) + 4, bh + 4);
      }
    });

    // VU needle: fast attack, slow release, like the real thing.
    var target = (live && playing) ? Math.min(20, -(live.comp.reduction || 0)) : 0;
    vuPos += (target - vuPos) * (target > vuPos ? 0.45 : 0.07);
    var needle = document.getElementById("rk-vu-needle");
    if (needle) {
      needle.setAttribute("transform",
        "rotate(" + (-46 + (vuPos / 20) * 92).toFixed(1) + " 100 100)");
      document.getElementById("rk-grdb").textContent = vuPos.toFixed(1) + " dB";
    }
    // Compressor-side gain reduction bar (same real reduction value)
    var grBar = document.getElementById("rk-gr");
    if (grBar) {
      grBar.style.width = Math.min(100, vuPos / 20 * 100) + "%";
      document.getElementById("rk-grdb2").textContent =
        vuPos > 0.05 ? "−" + vuPos.toFixed(1) + " dB" : "0.0 dB";
    }
    // Transport dock: mirror state, playhead, clock
    if (dockPlay) {
      dockPlay.textContent = playing ? "Stop" : "Play";
      dockPlay.disabled = playBtn.disabled;
      dockAb.textContent = abBtn.textContent;
      dockAb.disabled = abBtn.disabled;
      dockAb.classList.toggle("sw-lit", state.bypass);
      dockExp.disabled = exportBtn.disabled;
      if (rolloutBtn) rolloutBtn.disabled = playBtn.disabled;
      var wc2 = document.getElementById("rk-wave");
      if (wc2 && waveCache) {
        var wg2 = wc2.getContext("2d");
        wg2.putImageData(waveCache, 0, 0);
        var dtot = duration();
        if (dtot) {
          var phx = playPos() / dtot * wc2.width;
          wg2.fillStyle = "#e8c667";
          wg2.fillRect(phx - 1, 0, 2, wc2.height);
        }
      }
      var timeEl = document.getElementById("rk-time");
      if (timeEl) {
        var dtt = duration();
        timeEl.textContent = mmss(playPos()) + " / " + mmss(dtt);
      }
      var pk2 = document.getElementById("rk-peak2");
      if (pk2) pk2.style.width = document.getElementById("rk-peak").style.width;
    }
    if (live && playing && timeData) {
      var peak = 0;
      for (var t = 0; t < timeData.length; t += 4) {
        peak = Math.max(peak, Math.abs(timeData[t] - 128) / 128);
      }
      document.getElementById("rk-peak").style.width = Math.min(100, peak * 100) + "%";
      document.getElementById("rk-peakdb").textContent =
        peak > 0.001 ? (20 * Math.log10(peak)).toFixed(1) + " dB" : "−∞";
    }
  }

  // ---------- WAV export ----------
  function encodeWav(rendered) {
    var ch = rendered.numberOfChannels, len = rendered.length, rate = rendered.sampleRate;
    var bytes = 44 + len * ch * 2;
    var ab = new ArrayBuffer(bytes), dv = new DataView(ab);
    function str(o, s) { for (var i = 0; i < s.length; i++) dv.setUint8(o + i, s.charCodeAt(i)); }
    str(0, "RIFF"); dv.setUint32(4, bytes - 8, true); str(8, "WAVE");
    str(12, "fmt "); dv.setUint32(16, 16, true); dv.setUint16(20, 1, true);
    dv.setUint16(22, ch, true); dv.setUint32(24, rate, true);
    dv.setUint32(28, rate * ch * 2, true); dv.setUint16(32, ch * 2, true);
    dv.setUint16(34, 16, true); str(36, "data"); dv.setUint32(40, len * ch * 2, true);
    var offset = 44;
    var chans = [];
    for (var c = 0; c < ch; c++) chans.push(rendered.getChannelData(c));
    for (var i = 0; i < len; i++) {
      for (var c2 = 0; c2 < ch; c2++) {
        var v = Math.max(-1, Math.min(1, chans[c2][i]));
        dv.setInt16(offset, v < 0 ? v * 32768 : v * 32767, true);
        offset += 2;
      }
    }
    return new Blob([ab], {type: "audio/wav"});
  }

  exportBtn.addEventListener("click", function () {
    if (!buffer && !stems.length) return;
    statusEl.textContent = "Rendering…";
    var rate = stems.length ? stems[0].buffer.sampleRate : buffer.sampleRate;
    var len = stems.length
      ? Math.max.apply(null, stems.map(function (s) { return s.buffer.length; }))
      : buffer.length;
    var oc = new OfflineAudioContext(2, len, rate);
    var chain = buildChain(oc, oc.destination);
    voiceChain(chain, oc);  // export honors module power exactly like live
    if (stems.length) {
      stems.forEach(function (st) {
        var src = oc.createBufferSource();
        src.buffer = st.buffer;
        var gn = oc.createGain();
        gn.gain.value = stemGainValue(st);
        src.connect(gn); gn.connect(chain.input);
        src.start();
      });
    } else {
      var src = oc.createBufferSource();
      src.buffer = buffer;
      src.connect(chain.input);
      src.start();
    }
    oc.startRendering().then(function (rendered) {
      var a = document.createElement("a");
      a.download = stems.length ? "rack-stem-bounce.wav" : "rack-processed.wav";
      a.href = URL.createObjectURL(encodeWav(rendered));
      a.click();
      statusEl.textContent = "WAV exported — processed copy downloaded.";
    }).catch(function () { statusEl.textContent = "Render failed — try again."; });
  });

  // ---------- zone select: click an instrument lane, trim just its range ----------
  function zoneBands(lane) {
    // The EQ bands whose centers sit inside the lane's frequency range;
    // if none do, the single nearest band takes the trim.
    var idx = [];
    EQ_BANDS.forEach(function (b, i) {
      if (b.f >= lane.lo && b.f <= lane.hi) idx.push(i);
    });
    if (!idx.length) {
      var c = Math.sqrt(lane.lo * lane.hi), best = 0, bd = Infinity;
      EQ_BANDS.forEach(function (b, i) {
        var d = Math.abs(Math.log(b.f / c));
        if (d < bd) { bd = d; best = i; }
      });
      idx.push(best);
    }
    return idx;
  }
  function zoneTrim(delta) {
    if (selLane < 0) return;
    zoneBands(LANES[selLane]).forEach(function (i) {
      state.eq[i] = Math.max(-12, Math.min(12, +(state.eq[i] + delta).toFixed(1)));
    });
    renderEq(); applyState(); syncZoneUI();
  }
  function syncZoneUI() {
    var strip = document.getElementById("rk-zone");
    if (!strip) return;
    if (selLane < 0) { strip.style.display = "none"; return; }
    strip.style.display = "flex";
    var lane = LANES[selLane];
    var idx = zoneBands(lane);
    document.getElementById("rk-zone-name").textContent = lane.label;
    document.getElementById("rk-zone-name").style.color = lane.color;
    document.getElementById("rk-zone-bands").textContent =
      idx.map(function (i) {
        var v = state.eq[i];
        return EQ_BANDS[i].label + "Hz " + (v > 0 ? "+" : "") + v.toFixed(1);
      }).join(" · ");
  }
  function nodeAt(x, y) {
    var w = canvas.width, best = -1, bd = 144; // 12px grab radius
    EQ_BANDS.forEach(function (b, i) {
      var dx = x - fx(b.f, w), dy = y - (zeroCache - state.eq[i] * spanCache);
      var dd = dx * dx + dy * dy;
      if (dd < bd) { bd = dd; best = i; }
    });
    return best;
  }
  canvas.addEventListener("pointerdown", function (e) {
    var r = canvas.getBoundingClientRect();
    if (!r.width) return;
    var x = (e.clientX - r.left) * (canvas.width / r.width);
    var y = (e.clientY - r.top) * (canvas.height / r.height);
    var n = nodeAt(x, y);
    if (n >= 0) {
      nodeDrag = n; nodeMoved = false;
      canvas.setPointerCapture(e.pointerId);
      e.preventDefault();
    }
  });
  canvas.addEventListener("pointermove", function (e) {
    if (nodeDrag < 0) return;
    var r = canvas.getBoundingClientRect();
    var y = (e.clientY - r.top) * (canvas.height / r.height);
    var v = Math.max(-12, Math.min(12, (zeroCache - y) / spanCache));
    state.eq[nodeDrag] = Math.round(v * 10) / 10;
    nodeMoved = true;
    showTip(e.clientX, e.clientY - 16,
            EQ_BANDS[nodeDrag].label + "Hz  " +
            (state.eq[nodeDrag] > 0 ? "+" : "") + state.eq[nodeDrag].toFixed(1) + " dB");
    applyState();
  });
  canvas.addEventListener("pointerup", function () {
    if (nodeDrag >= 0 && nodeMoved) { renderEq(); syncZoneUI(); }
    nodeDrag = -1;
    hideTip();
  });
  canvas.addEventListener("click", function (e) {
    if (nodeMoved) { nodeMoved = false; return; }  // a node drag, not a lane pick
    var r = canvas.getBoundingClientRect();
    if (!r.width) return;
    var y = (e.clientY - r.top) * (canvas.height / r.height);
    var hit = -1;
    laneHitRects.forEach(function (lr, i) {
      if (lr && y >= lr[0] && y <= lr[0] + lr[1]) hit = i;
    });
    selLane = hit === selLane ? -1 : hit;
    syncZoneUI();
  });
  var zm = document.getElementById("rk-zone-minus"),
      zp = document.getElementById("rk-zone-plus"),
      zz = document.getElementById("rk-zone-zero"),
      zc = document.getElementById("rk-zone-clear");
  if (zm) zm.addEventListener("click", function () { zoneTrim(-1); });
  if (zp) zp.addEventListener("click", function () { zoneTrim(1); });
  if (zz) zz.addEventListener("click", function () {
    if (selLane < 0) return;
    zoneBands(LANES[selLane]).forEach(function (i) { state.eq[i] = 0; });
    renderEq(); applyState(); syncZoneUI();
  });
  if (zc) zc.addEventListener("click", function () { selLane = -1; syncZoneUI(); });

  window.__rackTest = {buildChain: buildChain, encodeWav: encodeWav,
                       tubeCurve: tubeCurve, roomIR: roomIR,
                       state: function () { return state; },
                       stems: function () { return stems; },
                       addStem: function (s) { stems.push(s); renderStems(); syncDeckInfo(); },
                       stemGainValue: stemGainValue,
                       modOn: modOn, voiceChain: voiceChain,
                       zoneBands: zoneBands, zoneTrim: zoneTrim,
                       setLane: function (i) { selLane = i; syncZoneUI(); },
                       lanes: LANES, applyState: applyState,
                       seek: seek, playPos: playPos, duration: duration,
                       renderWave: renderWave, bands: EQ_BANDS};
  syncAll();
  renderStems();
  updateGlow();
  resetCompare();
  syncModButtons();
  draw();
})();
