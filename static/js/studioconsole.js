/* Street Banker · Studio console — transport, waveform, A/B, meter.
 *
 * The workspace under the Mix and Master rooms. One engine, mounted by both
 * pages, so the transport genuinely is the same thing on both screens rather
 * than two lookalikes that drift.
 *
 * WHAT IT DOES, and the decisions behind it:
 *
 *   A/B is SEAMLESS, not stop-and-restart. Both buffers play as two source
 *   nodes started at the same context time; switching flips their gains with
 *   a 10 ms ramp (the de-zipper the Live engine uses). Stopping one and
 *   starting the other would add a gap right where somebody is trying to hear
 *   a half-dB difference.
 *
 *   Loudness matching uses MEASURED integrated loudness. When both buffers
 *   are loaded they are measured with SBLoudness (the Rack's BS.1770-4
 *   engine), and matching applies their difference to B. Comparing an
 *   unmatched master against its source is a volume test, not a listening
 *   test - louder reliably wins by being louder.
 *
 *   Mono check is a real down-mix. The output gain node is forced to one
 *   channel (channelCount 1, explicit), which is the Web Audio down-mix a
 *   phone speaker effectively performs. A stereo element that vanishes here
 *   vanishes there.
 *
 *   The meter reads the OUTPUT, after A/B, matching and mono - the signal
 *   actually being heard - and clip indication only lights at genuine
 *   over-range, because red is reserved for clipping.
 *
 * The maths lives in pure functions on the API so Node can check it without
 * an AudioContext: peaks for the waveform, the match gain, dBFS conversion,
 * timecode formatting, marker positioning.
 */
(function (root) {
  "use strict";

  // --- pure maths, checkable in Node -----------------------------------------

  /* Min/max per pixel column. A four-minute file is ~10 million samples and
     a canvas ~900 columns; drawing every sample costs a second and looks
     identical. */
  function peaks(data, width) {
    var out = new Array(width);
    var step = Math.max(1, Math.floor(data.length / width));
    for (var x = 0; x < width; x++) {
      var lo = 1.0, hi = -1.0;
      var start = x * step;
      var end = Math.min(data.length, start + step);
      for (var i = start; i < end; i++) {
        var v = data[i];
        if (v < lo) { lo = v; }
        if (v > hi) { hi = v; }
      }
      if (lo > hi) { lo = 0; hi = 0; }
      out[x] = [lo, hi];
    }
    return out;
  }

  /* Gain, in dB, that makes B sit at A's integrated loudness. */
  function matchGainDb(integratedA, integratedB) {
    if (typeof integratedA !== "number" || typeof integratedB !== "number") {
      return 0;
    }
    return integratedA - integratedB;
  }

  function dbfs(peak) {
    if (!(peak > 0)) { return -Infinity; }
    return 20 * Math.log(peak) / Math.LN10;
  }

  function fmtTime(seconds) {
    if (!(seconds >= 0) || !isFinite(seconds)) { return "0:00.0"; }
    var m = Math.floor(seconds / 60);
    var s = seconds - m * 60;
    var whole = Math.floor(s);
    var tenth = Math.floor((s - whole) * 10);
    return m + ":" + (whole < 10 ? "0" : "") + whole + "." + tenth;
  }

  /* Where a marker sits over the waveform, as a percentage. Clamped: a note
     at exactly the end must not render off the canvas. */
  function markerPct(at, duration) {
    if (!(duration > 0) || !(at >= 0)) { return 0; }
    var pct = (at / duration) * 100;
    return pct > 100 ? 100 : pct;
  }

  // --- the console -----------------------------------------------------------

  function create(opts) {
    opts = opts || {};
    var Ctx = root.AudioContext || root.webkitAudioContext;
    if (!Ctx) { return null; }

    var ctx = null;
    var bufA = null, bufB = null;
    var intA = null, intB = null;          // measured integrated loudness
    var srcA = null, srcB = null;
    var gA = null, gB = null, master = null, analyser = null;
    var playing = false;
    var usingB = false;
    var matched = false;
    var mono = false;
    var startedAt = 0;                     // ctx.currentTime when playback began
    var offset = 0;                        // seconds into the material
    var raf = null;
    var meterData = null;

    var listen = null;

    function ensure() {
      if (ctx) { return ctx; }
      ctx = new Ctx();
      master = ctx.createGain();
      analyser = ctx.createAnalyser();
      analyser.fftSize = 2048;
      meterData = new Float32Array(analyser.fftSize);
      /* The meter taps BEFORE the volume knob: master -> analyser -> listen.
         A monitor level is a comfort setting, and a meter that dropped when
         you turned the room down would be reading the knob, not the signal. */
      listen = ctx.createGain();
      master.connect(analyser);
      analyser.connect(listen);
      listen.connect(ctx.destination);
      return ctx;
    }

    function measure(buffer) {
      if (!root.SBLoudness) { return null; }
      try {
        var channels = [];
        for (var c = 0; c < buffer.numberOfChannels; c++) {
          channels.push(buffer.getChannelData(c));
        }
        return root.SBLoudness.analyse(channels, buffer.sampleRate).integrated;
      } catch (err) { return null; }
    }

    function load(url) {
      ensure();
      return fetch(url, { credentials: "same-origin" })
        .then(function (r) {
          if (!r.ok) { throw new Error("could not read the audio"); }
          return r.arrayBuffer();
        })
        .then(function (bytes) {
          return new Promise(function (resolve, reject) {
            ctx.decodeAudioData(bytes, resolve, reject);
          });
        });
    }

    function applyGains(ramp) {
      if (!gA || !gB) { return; }
      var now = ctx.currentTime;
      var bGain = 1;
      if (matched && intA !== null && intB !== null) {
        bGain = Math.pow(10, matchGainDb(intA, intB) / 20);
      }
      var tA = usingB ? 0 : 1;
      var tB = usingB ? bGain : 0;
      if (ramp) {
        gA.gain.cancelScheduledValues(now);
        gB.gain.cancelScheduledValues(now);
        gA.gain.setValueAtTime(gA.gain.value, now);
        gB.gain.setValueAtTime(gB.gain.value, now);
        gA.gain.linearRampToValueAtTime(tA, now + 0.01);
        gB.gain.linearRampToValueAtTime(tB, now + 0.01);
      } else {
        gA.gain.value = tA;
        gB.gain.value = tB;
      }
    }

    function stopNodes() {
      if (srcA) { try { srcA.onended = null; srcA.stop(); } catch (e) {} srcA = null; }
      if (srcB) { try { srcB.stop(); } catch (e) {} srcB = null; }
      /* The old gain pair must leave the graph, or every seek wires another
         two dead nodes into the master bus and holds their sources alive. */
      if (gA) { try { gA.disconnect(); } catch (e) {} gA = null; }
      if (gB) { try { gB.disconnect(); } catch (e) {} gB = null; }
    }

    function startAt(position) {
      stopNodes();
      gA = ctx.createGain();
      gB = ctx.createGain();
      gA.connect(master);
      gB.connect(master);
      srcA = ctx.createBufferSource();
      srcA.buffer = bufA;
      srcA.connect(gA);
      if (bufB) {
        srcB = ctx.createBufferSource();
        srcB.buffer = bufB;
        srcB.connect(gB);
      }
      applyGains(false);
      var when = ctx.currentTime + 0.03;   // one shared start time keeps A and B phase-locked
      srcA.start(when, position);
      if (srcB) { srcB.start(when, Math.min(position, bufB.duration)); }
      startedAt = when;
      offset = position;
      playing = true;
      /* The handler must know WHICH node ended. A seek stops the old node,
         and its onended fires after the new one is already running - judged
         against the new node's state it would kill playback and reset to
         zero. Captured per node, a stale ending is simply ignored. */
      (function (node) {
        node.onended = function () {
          if (playing && srcA === node) {
            playing = false;
            offset = 0;
            emit();
          }
        };
      })(srcA);
      tick();
    }

    function position() {
      if (!playing || !ctx) { return offset; }
      var pos = offset + (ctx.currentTime - startedAt);
      var dur = duration();
      return pos > dur ? dur : (pos < 0 ? 0 : pos);
    }

    function duration() {
      return bufA ? bufA.duration : 0;
    }

    function emit() {
      if (opts.onState) { opts.onState({ playing: playing, usingB: usingB,
                                         matched: matched, mono: mono }); }
    }

    function tick() {
      if (raf) { cancelAnimationFrame(raf); }
      function frame() {
        if (opts.onTime) { opts.onTime(position(), duration()); }
        if (opts.onLevel && analyser && playing) {
          analyser.getFloatTimeDomainData(meterData);
          var peak = 0;
          for (var i = 0; i < meterData.length; i++) {
            var a = meterData[i] < 0 ? -meterData[i] : meterData[i];
            if (a > peak) { peak = a; }
          }
          opts.onLevel(dbfs(peak), peak >= 0.999);
        }
        if (playing) { raf = requestAnimationFrame(frame); }
      }
      raf = requestAnimationFrame(frame);
    }

    var api = {
      loadA: function (url) {
        return load(url).then(function (buffer) {
          bufA = buffer;
          intA = measure(buffer);
          return buffer;
        });
      },
      loadB: function (url) {
        return load(url).then(function (buffer) {
          bufB = buffer;
          intB = measure(buffer);
          if (playing) { startAt(position()); }
          return buffer;
        });
      },
      clearB: function () {
        bufB = null; intB = null; usingB = false;
        if (playing) { startAt(position()); }
        emit();
      },
      play: function () {
        if (!bufA) { return; }
        ensure().resume();
        startAt(position());
        emit();
      },
      pause: function () {
        offset = position();
        playing = false;
        stopNodes();
        if (opts.onTime) { opts.onTime(offset, duration()); }
        emit();
      },
      toggle: function () { playing ? api.pause() : api.play(); },
      seek: function (seconds) {
        var dur = duration();
        var pos = seconds < 0 ? 0 : (seconds > dur ? dur : seconds);
        if (playing) { startAt(pos); } else { offset = pos; }
        if (opts.onTime) { opts.onTime(pos, dur); }
      },
      useB: function (on) {
        if (on && !bufB) { return; }
        usingB = !!on;
        applyGains(true);
        emit();
      },
      matchLoudness: function (on) {
        matched = !!on;
        applyGains(true);
        emit();
      },
      setMono: function (on) {
        mono = !!on;
        if (master) {
          /* Forcing the output gain to one explicit channel is the Web Audio
             down-mix - the same fold a phone speaker performs. */
          master.channelCount = mono ? 1 : 2;
          master.channelCountMode = mono ? "explicit" : "max";
        }
        emit();
      },
      setVolume: function (linear) {
        /* Monitoring level only, applied AFTER the meter tap - turning the
           room down changes what you hear, never what the meter reads. */
        if (listen) {
          var v = linear < 0 ? 0 : (linear > 1 ? 1 : linear);
          listen.gain.value = v;
        }
      },
      position: position,
      duration: duration,
      playing: function () { return playing; },
      hasB: function () { return !!bufB; },
      matchOffsetDb: function () { return matchGainDb(intA, intB); },
      integrated: function () { return { a: intA, b: intB }; },
      channelData: function () { return bufA ? bufA.getChannelData(0) : null; },
    };
    return api;
  }

  var api = {
    create: create,
    peaks: peaks,
    matchGainDb: matchGainDb,
    dbfs: dbfs,
    fmtTime: fmtTime,
    markerPct: markerPct,
  };
  if (typeof module !== "undefined" && module.exports) { module.exports = api; }
  root.SBConsole = api;
})(typeof self !== "undefined" ? self : this);
