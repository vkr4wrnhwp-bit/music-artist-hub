/* Light Studio — cue timeline locked to the song, waveform lane with
   draggable cue flags, hi-DPI canvas stage preview (simulation), and real
   DMX output to an ENTTEC USB Pro over Web Serial. Audio stays in the
   browser; saving stores the cue list, rig layout and timing only.
   The maths lives in lights-engine.js so it can be tested without a DOM. */
(function () {
  "use strict";
  var E = window.LightsEngine;
  var $ = function (id) { return document.getElementById(id); };
  var saved = window.__savedShow || null;
  var lib = window.__lightsLibrary || {shows: [], tracks: [], tour_shows: []};
  var show = (saved && saved.cues) ? saved : {name: "", bars: 6, chans: 4, cues: []};
  show.bars = Math.max(2, Math.min(10, show.bars || 6));
  show.chans = show.chans === 3 ? 3 : 4;
  show.cues.forEach(function (c) { if (typeof c.note !== "string") c.note = ""; });

  // ---------- state ----------
  var ctx = null, buffer = null, playing = false, startAt = 0, playOffset = 0, runStart = null, scrubT = 0, src = null;
  var port = null, writer = null, lastDmx = 0, dmxWrites = 0, dmxFps = 0, dmxSec = 0;
  var selectedCue = null, selectedBar = null, hoverBar = null, hoverGroup = null, defaultGroup = "all";
  var dirty = false, saveTimer = null, beatGrid = true, taps = [];
  var DPR = function () { return Math.max(1, Math.min(3, window.devicePixelRatio || 1)); };

  function ensureCtx() {
    if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
    return ctx;
  }
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
  function isTyping(t) {
    var tag = ((t && t.tagName) || "").toLowerCase();
    return tag === "input" || tag === "textarea" || tag === "select" || (t && t.isContentEditable);
  }
  function duration() { return buffer ? buffer.duration : 0; }

  // ---------- transport ----------
  var playBtn = $("lx-play"), clockEl = $("lx-clock"), totalEl = $("lx-clock-total"), infoEl = $("lx-fileinfo");
  function now() {
    if (buffer && playing) return Math.min(buffer.duration, ctx.currentTime - startAt + playOffset);
    if (runStart !== null) return (performance.now() - runStart) / 1000;
    return scrubT;
  }
  function stopSource() {
    if (src) { try { src.onended = null; src.stop(); } catch (e) {} src = null; }
  }
  function startPlayback(offset) {
    ensureCtx().resume();
    stopSource();
    var s = ctx.createBufferSource();
    s.buffer = buffer; s.connect(ctx.destination);
    s.onended = function () { if (src === s) { playing = false; src = null; scrubT = buffer.duration; paintTransport(); } };
    src = s;
    s.start(0, clamp(offset, 0, Math.max(0, buffer.duration - 0.01)));
    startAt = ctx.currentTime; playOffset = offset; playing = true; runStart = null;
    paintTransport();
  }
  function stopAll() {
    if (playing) scrubT = now();
    stopSource();
    playing = false; runStart = null;
    paintTransport();
  }
  function seek(t) {
    t = clamp(t, 0, duration() || 1e9);
    if (playing) startPlayback(t);
    else { scrubT = t; if (runStart !== null) runStart = performance.now() - t * 1000; }
  }
  function togglePlay() {
    if (playing || runStart !== null) { stopAll(); return; }
    if (!buffer) return;
    startPlayback(scrubT >= buffer.duration - 0.05 ? 0 : scrubT);
  }
  function paintTransport() {
    var live = playing || runStart !== null;
    playBtn.textContent = live ? "Stop" : "Play";
    playBtn.setAttribute("aria-pressed", live ? "true" : "false");
    var canCue = !!buffer || runStart !== null;
    $("lx-add").disabled = !canCue; $("lx-blackout").disabled = !canCue;
    $("lx-add").title = canCue ? "C" : "Load a song first — then cues land at the playhead";
    $("lx-blackout").title = canCue ? "B" : "Load a song first";
    $("lx-cue-hint").hidden = canCue;
    // phone dock mirrors the transport
    $("lx-dock-play").textContent = live ? "Stop" : "Play"; $("lx-dock-play").disabled = !buffer;
    $("lx-dock-add").disabled = !canCue; $("lx-dock-black").disabled = !canCue;
  }
  playBtn.addEventListener("click", togglePlay);
  $("lx-dock-play").addEventListener("click", togglePlay);
  $("lx-dock-add").addEventListener("click", function () { $("lx-add").click(); });
  $("lx-dock-black").addEventListener("click", function () { $("lx-blackout").click(); });
  $("lx-run").addEventListener("click", function () {
    if (runStart !== null || playing) { stopAll(); return; }
    runStart = performance.now() - scrubT * 1000;
    paintTransport();
  });
  function loadBuffer(buf, name) {
    buffer = buf; scrubT = 0; stopSource(); playing = false; runStart = null;
    show.name = show.name || String(name || "").replace(/\.[^.]+$/, "");
    $("lx-show-name").value = show.name;
    infoEl.innerHTML = "<b>" + esc(name || "song") + "</b> — " + E.fmtClock(buf.duration) + ", " +
      buf.numberOfChannels + " ch · stays on this machine";
    totalEl.textContent = "of " + E.fmtTimecode(buf.duration);
    playBtn.disabled = false;
    view.start = 0; view.end = buf.duration; invalidatePeaks();
    paintTransport();
    setTimeout(detectBeats, 50);
  }
  $("lx-file").addEventListener("change", function (e) {
    var f = e.target.files[0];
    if (!f) return;
    ensureCtx().resume();
    infoEl.innerHTML = "<b>Decoding " + esc(f.name) + "…</b>";
    f.arrayBuffer().then(function (ab) { return ctx.decodeAudioData(ab); })
      .then(function (buf) { loadBuffer(buf, f.name); })
      .catch(function () {
        infoEl.innerHTML = "<b>Could not decode that file.</b> Try an MP3, WAV, M4A or OGG.";
      });
  });
  function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;"); }

  // ---------- waveform lane ----------
  var wave = $("lx-wave"), wg = wave.getContext("2d");
  var view = {start: 0, end: 0};
  var peakCanvas = null, peakKey = "";
  var waveCss = {w: 0, h: 112};
  function waveSize() {
    var w = wave.clientWidth, d = DPR();
    if (w && (waveCss.w !== w || wave.width !== Math.round(w * d))) {
      waveCss.w = w;
      wave.width = Math.round(w * d); wave.height = Math.round(waveCss.h * d);
      invalidatePeaks();
    }
    wg.setTransform(d, 0, 0, d, 0, 0);
  }
  function invalidatePeaks() { peakKey = ""; }
  function tToX(t) { return (t - view.start) / Math.max(0.001, view.end - view.start) * waveCss.w; }
  function xToT(x) { return view.start + x / Math.max(1, waveCss.w) * (view.end - view.start); }
  function ensurePeaks() {
    var key = [view.start.toFixed(4), view.end.toFixed(4), waveCss.w].join("|");
    if (key === peakKey && peakCanvas) return;
    peakKey = key;
    var d = DPR(), w = waveCss.w, h = waveCss.h;
    peakCanvas = document.createElement("canvas");
    peakCanvas.width = Math.round(w * d); peakCanvas.height = Math.round(h * d);
    var pg = peakCanvas.getContext("2d");
    pg.setTransform(d, 0, 0, d, 0, 0);
    pg.fillStyle = "#070708"; pg.fillRect(0, 0, w, h);
    var ch0 = buffer.getChannelData(0);
    var pk = E.peaks(ch0, buffer.sampleRate, view.start, view.end, w);
    if (buffer.numberOfChannels > 1) {
      var pk2 = E.peaks(buffer.getChannelData(1), buffer.sampleRate, view.start, view.end, w);
      for (var i = 0; i < w; i++) { pk.max[i] = Math.max(pk.max[i], pk2.max[i]); pk.min[i] = Math.min(pk.min[i], pk2.min[i]); }
    }
    var mid = h / 2, amp = (h / 2) - 6;
    var grad = pg.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, "rgba(232,198,103,0.95)"); grad.addColorStop(0.5, "rgba(201,162,74,0.75)"); grad.addColorStop(1, "rgba(232,198,103,0.95)");
    pg.fillStyle = grad;
    for (var x = 0; x < w; x++) {
      var top = mid - pk.max[x] * amp, bot = mid - pk.min[x] * amp;
      if (bot - top < 1) { top = mid - 0.5; bot = mid + 0.5; }
      pg.fillRect(x, top, 1, bot - top);
    }
    pg.fillStyle = "rgba(255,255,255,0.08)"; pg.fillRect(0, mid, w, 1);
  }
  function drawWave(t) {
    waveSize();
    var w = waveCss.w, h = waveCss.h;
    if (!w) return;
    if (!buffer) {
      wg.fillStyle = "#070708"; wg.fillRect(0, 0, w, h);
      wg.fillStyle = "#8b857b"; wg.font = "600 12px -apple-system, Segoe UI, Roboto, sans-serif"; wg.textAlign = "center";
      wg.fillText("Load a song — its waveform lands here; click to seek, wheel to zoom, drag a cue flag to retime it.", w / 2, h / 2 + 4);
      wg.textAlign = "left";
      return;
    }
    ensurePeaks();
    wg.drawImage(peakCanvas, 0, 0, w, h);
    // beat grid
    if (show.bpm && beatGrid) {
      var period = 60 / show.bpm, off = show.beatOffset || 0;
      var first = off + Math.ceil((view.start - off) / period) * period;
      var span = view.end - view.start;
      var every = span > 90 ? 4 : 1;
      wg.strokeStyle = "rgba(255,255,255,0.10)"; wg.lineWidth = 1;
      for (var b = first, n = Math.round((first - off) / period); b <= view.end; b += period, n++) {
        if (n % every) continue;
        var bx = Math.round(tToX(b)) + 0.5;
        wg.beginPath(); wg.moveTo(bx, n % 4 === 0 ? 2 : h * 0.35); wg.lineTo(bx, h - 2); wg.stroke();
      }
    }
    // cue flags
    var sorted = show.cues.slice().sort(function (a, b) { return a.t - b.t; });
    sorted.forEach(function (c) {
      if (c.t < view.start - 1 || c.t > view.end + 1) return;
      var x = Math.round(tToX(c.t)) + 0.5, black = E.isBlackout(c), sel = c === selectedCue;
      wg.lineWidth = sel ? 2.5 : 1.5;
      wg.strokeStyle = black ? "rgba(240,165,142,0.95)" : (sel ? "#ffffff" : "rgba(232,198,103,0.95)");
      wg.beginPath(); wg.moveTo(x, 12); wg.lineTo(x, h - 2); wg.stroke();
      if (black) {
        // blackout: dark diamond, warm outline, a cross through it
        wg.fillStyle = "#111"; wg.beginPath(); wg.moveTo(x, 2); wg.lineTo(x + 8, 10); wg.lineTo(x, 18); wg.lineTo(x - 8, 10); wg.closePath(); wg.fill(); wg.stroke();
        wg.beginPath(); wg.moveTo(x - 3, 7); wg.lineTo(x + 3, 13); wg.moveTo(x + 3, 7); wg.lineTo(x - 3, 13); wg.stroke();
      } else {
        wg.fillStyle = c.color || "#d8b25a";
        wg.beginPath(); wg.moveTo(x, 2); wg.lineTo(x + 12, 2); wg.lineTo(x + 12, 11); wg.lineTo(x, 16); wg.closePath(); wg.fill();
        wg.strokeStyle = sel ? "#ffffff" : "rgba(0,0,0,0.7)"; wg.lineWidth = sel ? 2 : 1; wg.stroke();
      }
      if (sel && c.note) {
        wg.fillStyle = "rgba(0,0,0,0.75)"; wg.font = "600 11px -apple-system, Segoe UI, Roboto, sans-serif";
        var tw = wg.measureText(c.note).width + 10;
        wg.fillRect(x + 14, 4, tw, 16); wg.fillStyle = "#EEE8DC"; wg.fillText(c.note, x + 19, 16);
      }
    });
    // playhead
    var px = tToX(t);
    if (px >= -1 && px <= w + 1) {
      wg.strokeStyle = "#fff4d0"; wg.lineWidth = 2;
      wg.beginPath(); wg.moveTo(px, 0); wg.lineTo(px, h); wg.stroke();
      wg.fillStyle = "#fff4d0"; wg.beginPath(); wg.moveTo(px - 6, h); wg.lineTo(px + 6, h); wg.lineTo(px, h - 8); wg.closePath(); wg.fill();
    }
    // scale
    wg.fillStyle = "rgba(238,232,220,0.6)"; wg.font = "600 10px ui-monospace, Menlo, Consolas, monospace";
    wg.fillText(E.fmtClock(view.start), 4, h - 4);
    wg.textAlign = "right"; wg.fillText(E.fmtClock(view.end), w - 4, h - 4); wg.textAlign = "left";
  }
  function cueAtX(x) {
    var best = null, bd = 9;
    show.cues.forEach(function (c) { var d = Math.abs(tToX(c.t) - x); if (d < bd) { bd = d; best = c; } });
    return best;
  }
  var wDrag = null, wSeeking = false, pinch = {};
  wave.addEventListener("pointerdown", function (e) {
    if (!buffer) return;
    var r = wave.getBoundingClientRect(), x = e.clientX - r.left;
    pinch[e.pointerId] = {x: e.clientX};
    if (Object.keys(pinch).length === 2) { wDrag = null; wSeeking = false; pinch.base = null; return; }
    var c = cueAtX(x);
    wave.setPointerCapture(e.pointerId);
    if (c) { wDrag = c; selectCue(c); wave.style.cursor = "grabbing"; }
    else { wSeeking = true; seek(xToT(x)); }
    e.preventDefault();
  });
  wave.addEventListener("pointermove", function (e) {
    var r = wave.getBoundingClientRect(), x = e.clientX - r.left;
    if (pinch[e.pointerId]) pinch[e.pointerId].x = e.clientX;
    var ids = Object.keys(pinch).filter(function (k) { return k !== "base"; });
    if (ids.length === 2) {
      var dist = Math.abs(pinch[ids[0]].x - pinch[ids[1]].x);
      if (!pinch.base) pinch.base = {dist: dist, start: view.start, end: view.end};
      else if (pinch.base.dist > 10) {
        var mid = xToT((pinch[ids[0]].x + pinch[ids[1]].x) / 2 - r.left);
        zoomTo((pinch.base.end - pinch.base.start) * pinch.base.dist / Math.max(10, dist), mid);
      }
      return;
    }
    if (wDrag) {
      var t = clamp(xToT(x), 0, duration());
      if (show.snap && show.bpm) t = E.snapToBeat(t, show.bpm, show.beatOffset);
      wDrag.t = Math.round(t * 100) / 100; markDirty(); renderCues(false);
    } else if (wSeeking) { seek(xToT(x)); }
    else { wave.style.cursor = cueAtX(x) ? "grab" : "crosshair"; }
  });
  function wUp(e) { delete pinch[e.pointerId]; if (Object.keys(pinch).filter(function (k) { return k !== "base"; }).length < 2) pinch.base = null; if (wDrag) { wDrag = null; renderCues(); } wSeeking = false; wave.style.cursor = "crosshair"; }
  wave.addEventListener("pointerup", wUp); wave.addEventListener("pointercancel", wUp);
  wave.addEventListener("wheel", function (e) {
    if (!buffer) return;
    e.preventDefault();
    var r = wave.getBoundingClientRect(), x = e.clientX - r.left;
    if (e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
      var span0 = view.end - view.start, shift = (e.deltaX || e.deltaY) / waveCss.w * span0;
      panTo(view.start + shift);
    } else {
      zoomTo((view.end - view.start) * Math.exp(e.deltaY * 0.0018), xToT(x));
    }
  }, {passive: false});
  function zoomTo(span, anchorT) {
    var dur = duration(); span = clamp(span, Math.min(2, dur), dur);
    var frac = (anchorT - view.start) / Math.max(0.001, view.end - view.start);
    var start = clamp(anchorT - frac * span, 0, dur - span);
    view.start = start; view.end = start + span; invalidatePeaks();
  }
  function panTo(start) {
    var span = view.end - view.start, dur = duration();
    view.start = clamp(start, 0, Math.max(0, dur - span)); view.end = view.start + span; invalidatePeaks();
  }
  $("lx-zoom-fit").addEventListener("click", function () { if (buffer) { view.start = 0; view.end = buffer.duration; invalidatePeaks(); } });

  // ---------- beats ----------
  function detectBeats() {
    if (!buffer) return;
    var n = buffer.length, mono = new Float32Array(n), chs = buffer.numberOfChannels;
    for (var c = 0; c < chs; c++) { var d = buffer.getChannelData(c); for (var i = 0; i < n; i++) mono[i] += d[i] / chs; }
    var res = E.detectBeats(mono, buffer.sampleRate);
    if (res.bpm) { show.bpm = res.bpm; show.beatOffset = res.offset; markDirty(); }
    paintBeats(res.bpm ? "detected" : "not found");
  }
  function paintBeats(how) {
    $("lx-bpm").textContent = show.bpm ? show.bpm.toFixed(1) : "—";
    $("lx-bpm-how").textContent = show.bpm ? (how || "") : (how || "");
    $("lx-snap").setAttribute("aria-pressed", show.snap ? "true" : "false");
    $("lx-snap").disabled = !show.bpm;
  }
  $("lx-detect").addEventListener("click", detectBeats);
  $("lx-snap").addEventListener("click", function () { show.snap = !show.snap; markDirty(); paintBeats(); });
  $("lx-grid").addEventListener("click", function () { beatGrid = !beatGrid; $("lx-grid").setAttribute("aria-pressed", beatGrid ? "true" : "false"); });
  $("lx-tap").addEventListener("click", function () {
    var t = performance.now() / 1000;
    if (taps.length && t - taps[taps.length - 1] > 2) taps = [];
    taps.push(t);
    var bpm = E.tapTempo(taps);
    if (bpm) {
      show.bpm = bpm;
      var period = 60 / bpm, ph = now();
      show.beatOffset = Math.round((ph - Math.floor(ph / period) * period) * 1000) / 1000;
      markDirty(); paintBeats("tapped");
    } else { $("lx-bpm-how").textContent = "tap again…"; }
  });

  // ---------- stage preview (hi-DPI, responsive, audience view) ----------
  var stage = $("lx-stage"), g = stage.getContext("2d"), stageWrap = $("lx-stage-wrap");
  var barRects = [], stageCss = {w: 0, h: 0};
  var bgImg = new Image();
  bgImg.src = "/static/img/stage-bg.jpg";
  function hz(n) { var x = Math.sin(n * 12.9898) * 43758.5453; return x - Math.floor(x); }
  function stageSize() {
    var w = stageWrap.clientWidth, d = DPR();
    if (!w) return false;
    var h = Math.max(200, Math.round(w * 400 / 798));
    if (stageCss.w !== w || stageCss.h !== h || stage.width !== Math.round(w * d)) {
      stageCss = {w: w, h: h};
      stage.width = Math.round(w * d); stage.height = Math.round(h * d);
      stage.style.height = h + "px";
    }
    g.setTransform(d, 0, 0, d, 0, 0);
    return true;
  }
  function barPos(i, bars) {
    var key = String(i);
    if (show.pos && show.pos[key]) return show.pos[key];
    var top = Math.ceil(bars / 2);
    if (i <= top) return [0.15 + 0.7 * ((i - 0.5) / top), 0.12];
    var n = i - top, count = bars - top;
    return [0.17 + 0.66 * ((n - 0.5) / count), 0.78];
  }
  function drawStage(t) {
    if (!stageSize()) return;
    var w = stageCss.w, h = stageCss.h;
    var bgReady = bgImg.complete && bgImg.naturalWidth > 0;
    if (bgReady) {
      var scale = Math.max(w / bgImg.naturalWidth, h / bgImg.naturalHeight);
      var iw = bgImg.naturalWidth * scale, ih = bgImg.naturalHeight * scale;
      g.drawImage(bgImg, (w - iw) / 2, (h - ih) / 2, iw, ih);
      var vg = g.createLinearGradient(0, 0, 0, h);
      vg.addColorStop(0, "rgba(5,5,6,0.35)"); vg.addColorStop(0.4, "rgba(5,5,6,0)"); vg.addColorStop(1, "rgba(5,5,6,0.25)");
      g.fillStyle = vg; g.fillRect(0, 0, w, h);
    } else {
      var bgg = g.createLinearGradient(0, 0, 0, h);
      bgg.addColorStop(0, "#08080a"); bgg.addColorStop(1, "#111014");
      g.fillStyle = bgg; g.fillRect(0, 0, w, h);
      g.fillStyle = "#0d0c10"; g.fillRect(w * 0.1, h * 0.08, w * 0.8, h * 0.5);
      g.strokeStyle = "#1d1a22";
      for (var cx = w * 0.12; cx < w * 0.88; cx += 26) { g.beginPath(); g.moveTo(cx, h * 0.08); g.lineTo(cx, h * 0.58); g.stroke(); }
      g.fillStyle = "#17150f"; g.beginPath();
      g.moveTo(w * 0.13, h * 0.58); g.lineTo(w * 0.87, h * 0.58); g.lineTo(w * 0.97, h * 0.9); g.lineTo(w * 0.03, h * 0.9);
      g.closePath(); g.fill(); g.strokeStyle = "#2c2820"; g.stroke();
    }
    g.fillStyle = "rgba(239,230,205,0.55)";
    g.font = "bold " + Math.round(h * 0.06) + "px 'Arial Narrow', Arial";
    g.textAlign = "center"; g.fillText((show.name || "YOUR SET").toUpperCase(), w / 2, h * 0.1); g.textAlign = "left";

    var looks = E.lightingAt(show, t), bars = show.bars, sc = w / 798;
    barRects = [];
    g.save(); g.globalCompositeOperation = "lighter";
    var WIDTHS = [1, 0.62, 0.3], ALPHAS = [0.16, 0.24, 0.4];
    for (var i = 1; i <= bars; i++) {
      var p = barPos(i, bars), bx = p[0] * w, by = p[1] * h, look = looks[i - 1], col = look.rgb, a = look.inten;
      if (a <= 0.02) continue;
      var vert = (show.rot || {})[String(i)] === 90, c3;
      if (vert) {
        var ex = bx < w / 2 ? bx + w * 0.42 : bx - w * 0.42;
        for (c3 = 0; c3 < 3; c3++) {
          var hw = 60 * sc * WIDTHS[c3], hgrad = g.createLinearGradient(bx, by, ex, by);
          hgrad.addColorStop(0, "rgba(" + col.join(",") + "," + (ALPHAS[c3] * a).toFixed(3) + ")"); hgrad.addColorStop(1, "rgba(" + col.join(",") + ",0)");
          g.fillStyle = hgrad; g.beginPath();
          g.moveTo(bx, by - 16 * sc * WIDTHS[c3]); g.lineTo(bx, by + 16 * sc * WIDTHS[c3]); g.lineTo(ex, by + hw); g.lineTo(ex, by - hw); g.closePath(); g.fill();
        }
        for (var k = 0; k < 7; k++) {
          var pr = (hz(i * 97 + k) + t * 0.02 * (0.5 + hz(i + k))) % 1, px = bx + (ex - bx) * pr, py = by + (hz(i * 31 + k) - 0.5) * 2 * (16 + 44 * pr) * sc;
          g.fillStyle = "rgba(" + col.join(",") + "," + (0.35 * a * (1 - pr)).toFixed(3) + ")"; g.beginPath(); g.arc(px, py, 1.6, 0, 7); g.fill();
        }
      } else {
        var down = p[1] < 0.5, ly = down ? h * 0.86 : h * 0.1;
        for (c3 = 0; c3 < 3; c3++) {
          var lw = 70 * sc * WIDTHS[c3], grad = g.createLinearGradient(bx, by, bx, ly);
          grad.addColorStop(0, "rgba(" + col.join(",") + "," + (ALPHAS[c3] * a).toFixed(3) + ")"); grad.addColorStop(1, "rgba(" + col.join(",") + ",0)");
          g.fillStyle = grad; g.beginPath();
          g.moveTo(bx - 16 * sc * WIDTHS[c3], by); g.lineTo(bx + 16 * sc * WIDTHS[c3], by); g.lineTo(bx + lw, ly); g.lineTo(bx - lw, ly); g.closePath(); g.fill();
        }
        for (var k2 = 0; k2 < 7; k2++) {
          var pr2 = (hz(i * 53 + k2) + t * 0.02 * (0.5 + hz(i * 7 + k2))) % 1, py2 = by + (ly - by) * pr2, px2 = bx + (hz(i * 17 + k2) - 0.5) * 2 * (16 + 54 * pr2) * sc;
          g.fillStyle = "rgba(" + col.join(",") + "," + (0.35 * a * (1 - pr2)).toFixed(3) + ")"; g.beginPath(); g.arc(px2, py2, 1.6, 0, 7); g.fill();
        }
        if (down) {
          var pool = g.createRadialGradient(bx, h * 0.8, 4, bx, h * 0.8, 90 * sc);
          pool.addColorStop(0, "rgba(" + col.join(",") + "," + (0.4 * a).toFixed(3) + ")"); pool.addColorStop(1, "rgba(" + col.join(",") + ",0)");
          g.fillStyle = pool; g.beginPath(); g.ellipse(bx, h * 0.8, 95 * sc, 28 * sc, 0, 0, 7); g.fill();
          var refl = g.createLinearGradient(bx, h * 0.8, bx, h * 0.98);
          refl.addColorStop(0, "rgba(" + col.join(",") + "," + (0.12 * a).toFixed(3) + ")"); refl.addColorStop(1, "rgba(" + col.join(",") + ",0)");
          g.fillStyle = refl; g.fillRect(bx - 24 * sc, h * 0.8, 48 * sc, h * 0.18);
        }
      }
    }
    g.restore();

    if (!bgReady) {
      g.fillStyle = "#0b0a08"; g.strokeStyle = "#332d20";
      g.fillRect(w * 0.42, h * 0.5, w * 0.16, h * 0.09); g.strokeRect(w * 0.42, h * 0.5, w * 0.16, h * 0.09);
      g.beginPath(); g.arc(w * 0.5, h * 0.51, h * 0.045, 0, 7); g.fill(); g.stroke();
      g.fillRect(w * 0.2, h * 0.52, w * 0.07, h * 0.11); g.fillRect(w * 0.73, h * 0.52, w * 0.07, h * 0.11);
    }

    // Fixtures on top, with hover / selected / mirror / group states
    var hoverMembers = hoverGroup ? E.membersOf(hoverGroup, bars) : [];
    var mirror = hoverBar ? E.mirrorOf(hoverBar, bars) : null;
    for (var j = 1; j <= bars; j++) {
      var p2 = barPos(j, bars), x2 = p2[0] * w, y2 = p2[1] * h, lk = looks[j - 1];
      var vert2 = (show.rot || {})[String(j)] === 90;
      var bw = (vert2 ? 10 : 54) * sc, bh = (vert2 ? 54 : 10) * sc;
      bw = Math.max(bw, vert2 ? 8 : 36); bh = Math.max(bh, vert2 ? 36 : 8);
      var isSel = selectedBar === j, isHov = hoverBar === j, isMir = mirror === j, inGroup = hoverMembers.indexOf(j) >= 0;
      if (isSel || isHov || isMir || inGroup) {
        g.save();
        g.strokeStyle = isSel ? "#ffffff" : (isMir ? "rgba(232,198,103,0.9)" : (inGroup ? "rgba(232,198,103,0.95)" : "rgba(255,255,255,0.7)"));
        g.lineWidth = isSel ? 2.5 : 1.5;
        if (isMir) g.setLineDash([4, 3]);
        g.shadowColor = isSel || inGroup ? "#e8c667" : "#ffffff"; g.shadowBlur = isSel ? 18 : 10;
        g.strokeRect(x2 - bw / 2 - 7, y2 - bh / 2 - 7, bw + 14, bh + 14);
        g.restore();
      }
      g.save();
      g.shadowColor = "rgb(" + lk.rgb.join(",") + ")"; g.shadowBlur = 26 * lk.inten;
      g.fillStyle = "#1a1712"; g.fillRect(x2 - bw / 2, y2 - bh / 2, bw, bh);
      g.restore();
      g.lineWidth = 4; g.strokeStyle = "rgba(0,0,0,0.85)"; g.strokeRect(x2 - bw / 2, y2 - bh / 2, bw, bh);
      g.lineWidth = 1.5; g.strokeStyle = isSel ? "#ffffff" : "#d8b25a"; g.strokeRect(x2 - bw / 2, y2 - bh / 2, bw, bh);
      g.lineWidth = 1;
      var cells = 6, step = (vert2 ? bh : bw) / cells;
      for (var s2 = 0; s2 < cells; s2++) {
        g.fillStyle = lk.inten > 0.02 ? "rgba(" + lk.rgb.join(",") + "," + (0.25 + 0.75 * lk.inten).toFixed(2) + ")" : "#26221a";
        g.beginPath();
        if (vert2) g.arc(x2, y2 - bh / 2 + step * (s2 + 0.5), Math.min(2.6, step * 0.3), 0, 7);
        else g.arc(x2 - bw / 2 + step * (s2 + 0.5), y2, Math.min(2.6, step * 0.3), 0, 7);
        g.fill();
      }
      if (lk.inten > 0.02) {
        g.save(); g.globalCompositeOperation = "lighter";
        var bloom = g.createRadialGradient(x2, y2, 1, x2, y2, (30 + 26 * lk.inten) * sc);
        bloom.addColorStop(0, "rgba(" + lk.rgb.join(",") + "," + (0.5 * lk.inten).toFixed(3) + ")"); bloom.addColorStop(1, "rgba(" + lk.rgb.join(",") + ",0)");
        g.fillStyle = bloom; g.beginPath(); g.arc(x2, y2, (30 + 26 * lk.inten) * sc, 0, 7); g.fill(); g.restore();
      }
      g.fillStyle = isSel ? "#e8c667" : "rgba(0,0,0,0.75)";
      g.fillRect(x2 - bw / 2 - 4, y2 - bh / 2 - 17, 15, 13);
      g.fillStyle = isSel ? "#1c1302" : "#e8c667"; g.font = "bold 10px Arial";
      g.fillText(String(j), x2 - bw / 2 - 1, y2 - bh / 2 - 7);
      // hit box: at least 44px square around the fixture
      var hx = Math.max(44, bw + 20), hy = Math.max(44, bh + 20);
      barRects.push({i: j, x: x2 - hx / 2, y: y2 - hy / 2, w: hx, h: hy});
    }
  }
  function barAt(mx, my) {
    for (var k = barRects.length - 1; k >= 0; k--) {
      var b = barRects[k];
      if (mx >= b.x && mx <= b.x + b.w && my >= b.y && my <= b.y + b.h) return b.i;
    }
    return null;
  }
  var dragBar = null, dragMoved = false;
  stage.addEventListener("pointerdown", function (e) {
    var r = stage.getBoundingClientRect(), b = barAt(e.clientX - r.left, e.clientY - r.top);
    if (b) { dragBar = b; dragMoved = false; stage.setPointerCapture(e.pointerId); e.preventDefault(); }
    else { selectBar(null); }
  });
  stage.addEventListener("pointermove", function (e) {
    var r = stage.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
    if (dragBar === null) {
      var hb = barAt(mx, my);
      if (hb !== hoverBar) { hoverBar = hb; stage.style.cursor = hb ? "grab" : "default"; }
      return;
    }
    dragMoved = true; stage.style.cursor = "grabbing";
    show.pos = show.pos || {};
    show.pos[String(dragBar)] = [clamp(mx / r.width, 0.03, 0.97), clamp(my / stageCss.h, 0.04, 0.92)];
    markDirty();
  });
  function stageUp() { if (dragBar !== null) { selectBar(dragBar); dragBar = null; stage.style.cursor = "grab"; } }
  stage.addEventListener("pointerup", stageUp); stage.addEventListener("pointercancel", stageUp);
  stage.addEventListener("pointerleave", function () { hoverBar = null; });
  stage.addEventListener("dblclick", function (e) {
    var r = stage.getBoundingClientRect(), b = barAt(e.clientX - r.left, e.clientY - r.top);
    if (b) { setRot(b, (show.rot || {})[String(b)] === 90 ? 0 : 90); selectBar(b); }
  });
  function setRot(bar, deg) { show.rot = show.rot || {}; show.rot[String(bar)] = deg; markDirty(); paintBarCtl(); }
  function selectBar(b) { selectedBar = b; paintBarCtl(); }
  function paintBarCtl() {
    var box = $("lx-barctl");
    if (!selectedBar) { box.hidden = true; return; }
    box.hidden = false;
    var rot = (show.rot || {})[String(selectedBar)] === 90;
    $("lx-barctl-name").textContent = "Bar " + selectedBar + (E.mirrorOf(selectedBar, show.bars) ? " · mirror of bar " + E.mirrorOf(selectedBar, show.bars) : " · centre");
    $("lx-or-hung").setAttribute("aria-pressed", rot ? "false" : "true");
    $("lx-or-side").setAttribute("aria-pressed", rot ? "true" : "false");
  }
  $("lx-or-hung").addEventListener("click", function () { if (selectedBar) setRot(selectedBar, 0); });
  $("lx-or-side").addEventListener("click", function () { if (selectedBar) setRot(selectedBar, 90); });
  $("lx-bar-deselect").addEventListener("click", function () { selectBar(null); });
  function nudge(dx, dy) {
    if (!selectedBar) return;
    var p = barPos(selectedBar, show.bars).slice();
    show.pos = show.pos || {};
    show.pos[String(selectedBar)] = [clamp(p[0] + dx, 0.03, 0.97), clamp(p[1] + dy, 0.04, 0.92)];
    markDirty();
  }
  stage.addEventListener("keydown", function (e) {
    var st = e.shiftKey ? 0.05 : 0.01;
    if (e.key === "ArrowLeft") { nudge(-st, 0); e.preventDefault(); }
    else if (e.key === "ArrowRight") { nudge(st, 0); e.preventDefault(); }
    else if (e.key === "ArrowUp") { nudge(0, -st); e.preventDefault(); }
    else if (e.key === "ArrowDown") { nudge(0, st); e.preventDefault(); }
    else if (e.key === "Tab" && !e.shiftKey && selectedBar === null) { /* fall through */ }
    else if (e.key === "Enter" && selectedBar === null) { selectBar(1); }
    else if (e.key === "r" || e.key === "R") { if (selectedBar) setRot(selectedBar, (show.rot || {})[String(selectedBar)] === 90 ? 0 : 90); }
    else if (/^[0-9]$/.test(e.key) && e.key !== "0") { var n = parseInt(e.key, 10); if (n <= show.bars) selectBar(n); }
  });

  // bars table: the screen-reader-accessible twin of the canvas
  function paintBarsTable(t) {
    var tb = $("lx-bars-tbody"); if (!tb) return;
    var looks = E.lightingAt(show, t), html = "";
    for (var i = 1; i <= show.bars; i++) {
      var p = barPos(i, show.bars), lk = looks[i - 1], rot = (show.rot || {})[String(i)] === 90;
      html += '<tr class="' + (selectedBar === i ? "is-sel" : "") + '"><th scope="row">Bar ' + i + '</th><td>' + Math.round(p[0] * 100) + '% across</td><td>' +
        (p[1] < 0.5 ? "truss" : "floor") + ' · ' + Math.round(p[1] * 100) + '%</td><td>' + (rot ? "side stick" : "hung") + '</td><td><span class="lx-sw" style="background:rgb(' +
        lk.rgb.join(",") + ')"></span> ' + Math.round(lk.inten * 100) + '%</td><td>' + (E.mirrorOf(i, show.bars) || "—") + '</td></tr>';
    }
    tb.innerHTML = html;
  }

  // ---------- DMX (ENTTEC USB Pro over Web Serial) ----------
  function paintDmx(state, text) {
    var chip = $("lx-dmx-chip");
    chip.className = "lx-chip" + (state === "on" ? " is-on" : (state === "err" ? " is-err" : ""));
    $("lx-dmx-text").textContent = text;
  }
  $("lx-dmx").addEventListener("click", function () {
    if (!("serial" in navigator)) { paintDmx("err", "No Web Serial in this browser — use Chrome or Edge on desktop"); return; }
    if (port) {
      try { writer && writer.releaseLock(); } catch (e) {}
      writer = null; port.close().catch(function () {}); port = null;
      paintDmx("", "Preview only · no hardware"); $("lx-dmx").textContent = "Connect DMX (ENTTEC)";
      return;
    }
    navigator.serial.requestPort().then(function (p) { port = p; return port.open({baudRate: 57600}); })
      .then(function () {
        writer = port.writable.getWriter(); dmxWrites = 0; dmxFps = 0;
        paintDmx("on", "Connected · universe 1 · — fps"); $("lx-dmx").textContent = "Disconnect DMX";
      }).catch(function () { port = null; paintDmx("", "Preview only · no hardware"); });
  });

  // ---------- cue list ----------
  var cuesWrap = $("lx-cues");
  function sortedCues() { return show.cues.slice().sort(function (a, b) { return a.t - b.t; }); }
  function selectCue(c, scroll) {
    selectedCue = c;
    if (c && !playing) scrubT = c.t;
    renderCues(false);
    paintGroups();
    if (c && scroll) { var el = cuesWrap.querySelector('[data-id="' + c._id + '"]'); if (el && el.scrollIntoView) el.scrollIntoView({block: "nearest"}); }
  }
  var cueSeq = 0;
  function ensureIds() { show.cues.forEach(function (c) { if (!c._id) c._id = "c" + (++cueSeq); }); }
  function glyphHtml(group) {
    var mem = E.membersOf(group, show.bars), h = '<span class="lx-glyph" aria-hidden="true">';
    for (var i = 1; i <= show.bars; i++) h += '<i class="' + (mem.indexOf(i) >= 0 ? "on" : "") + '"></i>';
    return h + "</span>";
  }
  function renderCues(full) {
    ensureIds();
    $("lx-cues-count").textContent = show.cues.length ? show.cues.length + (show.cues.length === 1 ? " cue" : " cues") : "";
    var sorted = sortedCues();
    if (!sorted.length) {
      cuesWrap.innerHTML = '<div class="lx-empty">No cues yet. Play the song and press <span class="lx-kbd">C</span> — or “+ Cue at playhead” — where the music turns: intro dim, chorus full, drop blackout. ' +
        'Pick a look chip to land a ready-made colour, then drag its flag on the waveform to retime it.</div>';
      return;
    }
    if (full === false && cuesWrap.children.length === sorted.length) {
      // light repaint: order, selection, timecodes, swatches
      sorted.forEach(function (c, idx) {
        var row = cuesWrap.querySelector('[data-id="' + c._id + '"]');
        if (!row) return;
        if (cuesWrap.children[idx] !== row) cuesWrap.insertBefore(row, cuesWrap.children[idx]);
        row.classList.toggle("is-sel", c === selectedCue); row.classList.toggle("is-black", E.isBlackout(c));
        var tc = row.querySelector(".lx-cue-tc input"); if (tc && document.activeElement !== tc) tc.value = c.t.toFixed(2);
        var sw = row.querySelector(".lx-swatch"); if (sw) { sw.style.background = c.color; sw.classList.toggle("is-black", E.isBlackout(c)); }
      });
      return;
    }
    cuesWrap.innerHTML = "";
    sorted.forEach(function (c) {
      var row = document.createElement("div");
      row.className = "lx-cue" + (c === selectedCue ? " is-sel" : "") + (E.isBlackout(c) ? " is-black" : "");
      row.setAttribute("data-id", c._id); row.setAttribute("role", "button"); row.tabIndex = 0;
      row.setAttribute("aria-label", "Cue at " + E.fmtTimecode(c.t) + ", " + E.groupLabel(c.group, show.bars) + (c.note ? ", " + c.note : ""));
      // timecode
      var tc = document.createElement("div"); tc.className = "lx-cue-tc";
      var tin = document.createElement("input"); tin.type = "number"; tin.step = "0.01"; tin.min = "0"; tin.value = c.t.toFixed(2); tin.setAttribute("aria-label", "Cue time in seconds");
      tin.addEventListener("input", function () { c.t = Math.max(0, parseFloat(tin.value) || 0); markDirty(); });
      tin.addEventListener("change", function () { renderCues(false); });
      tc.appendChild(tin); row.appendChild(tc);
      // swatch
      var sw = document.createElement("label"); sw.className = "lx-swatch" + (E.isBlackout(c) ? " is-black" : ""); sw.style.background = c.color; sw.title = "Colour";
      var cin = document.createElement("input"); cin.type = "color"; cin.value = /^#[0-9a-f]{6}$/i.test(c.color) ? c.color : "#000000"; cin.setAttribute("aria-label", "Cue colour");
      cin.addEventListener("input", function () { c.color = cin.value; sw.style.background = c.color; sw.classList.toggle("is-black", E.isBlackout(c)); markDirty(); });
      sw.appendChild(cin); row.appendChild(sw);
      // glyph
      var gl = document.createElement("span"); gl.innerHTML = glyphHtml(c.group); gl.title = E.groupLabel(c.group, show.bars); row.appendChild(gl.firstChild);
      // middle controls
      var mid = document.createElement("div"); mid.className = "lx-cue-mid";
      var sel = document.createElement("select"); sel.className = "lx-select"; sel.setAttribute("aria-label", "Group");
      E.groupOptions(show.bars).forEach(function (o) { var op = document.createElement("option"); op.value = o[0]; op.textContent = o[1]; op.selected = c.group === o[0]; sel.appendChild(op); });
      sel.addEventListener("change", function () { c.group = sel.value; markDirty(); renderCues(); paintGroups(); });
      mid.appendChild(sel);
      var inten = document.createElement("input"); inten.type = "range"; inten.min = 0; inten.max = 100; inten.value = c.intensity; inten.setAttribute("aria-label", "Intensity");
      inten.title = "Intensity";
      inten.addEventListener("input", function () { c.intensity = parseInt(inten.value, 10); sw.classList.toggle("is-black", E.isBlackout(c)); markDirty(); });
      mid.appendChild(inten);
      var fw = document.createElement("label"); fw.textContent = "fade "; fw.title = "Seconds from the previous look into this one";
      var fin = document.createElement("input"); fin.type = "number"; fin.step = "0.1"; fin.min = "0"; fin.value = c.fade; fin.className = "lx-input"; fin.style.width = "64px"; fin.setAttribute("aria-label", "Fade seconds");
      fin.addEventListener("input", function () { c.fade = Math.max(0, parseFloat(fin.value) || 0); markDirty(); });
      fw.appendChild(fin); fw.appendChild(document.createTextNode(" s")); mid.appendChild(fw);
      var note = document.createElement("input"); note.type = "text"; note.className = "lx-input lx-cue-note"; note.placeholder = "note — chorus, drop, verse 2…"; note.value = c.note || ""; note.maxLength = 80; note.setAttribute("aria-label", "Cue note");
      note.addEventListener("input", function () { c.note = note.value; markDirty(); });
      mid.appendChild(note);
      row.appendChild(mid);
      // delete
      var del = document.createElement("button"); del.type = "button"; del.className = "lx-cue-x"; del.textContent = "×"; del.setAttribute("aria-label", "Delete cue");
      del.addEventListener("click", function (e) { e.stopPropagation(); show.cues.splice(show.cues.indexOf(c), 1); if (selectedCue === c) selectedCue = null; markDirty(); renderCues(); });
      row.appendChild(del);
      // row click = preview at that time + select
      row.addEventListener("click", function (e) { if (isTyping(e.target) || e.target === del) return; selectCue(c); });
      row.addEventListener("keydown", function (e) { if ((e.key === "Enter" || e.key === " ") && e.target === row) { e.preventDefault(); selectCue(c); } });
      cuesWrap.appendChild(row);
    });
  }
  function addCue(look) {
    var t = Math.round(now() * 100) / 100;
    if (show.snap && show.bpm) t = E.snapToBeat(t, show.bpm, show.beatOffset);
    var c = {t: t, group: defaultGroup, color: "#d8b25a", intensity: 80, fade: 0.5, note: ""};
    if (look) { c.color = look.color; c.intensity = look.intensity; c.fade = look.fade; c.note = look.name; }
    show.cues.push(c); markDirty(); ensureIds(); renderCues(); selectCue(c, true);
  }
  $("lx-add").addEventListener("click", function () { addCue(); });
  $("lx-blackout").addEventListener("click", function () { addCue(E.LOOKS[5]); });

  // ---------- group picker ----------
  function miniStage(group) {
    var bars = show.bars, mem = E.membersOf(group, bars), s = '<svg viewBox="0 0 100 34" aria-hidden="true">';
    s += '<rect x="4" y="26" width="92" height="6" rx="1.5" fill="#1a1712" stroke="#3a3224"/>';
    for (var i = 1; i <= bars; i++) {
      var p = barPos(i, bars), x = 6 + p[0] * 88, y = 4 + p[1] * 22, on = mem.indexOf(i) >= 0;
      var rot = (show.rot || {})[String(i)] === 90;
      s += '<rect x="' + (x - (rot ? 1.5 : 5)) + '" y="' + (y - (rot ? 5 : 1.5)) + '" width="' + (rot ? 3 : 10) + '" height="' + (rot ? 10 : 3) + '" rx="0.8" fill="' + (on ? "#e8c667" : "#2b271f") + '"' + (on ? ' style="filter:drop-shadow(0 0 2px #e8c667)"' : "") + '/>';
    }
    return s + "</svg>";
  }
  function paintGroups() {
    var box = $("lx-groups"), cur = selectedCue ? selectedCue.group : defaultGroup;
    box.innerHTML = "";
    E.groupOptions(show.bars).forEach(function (o) {
      var b = document.createElement("button"); b.type = "button"; b.className = "lx-group";
      b.setAttribute("aria-pressed", cur === o[0] ? "true" : "false"); b.setAttribute("data-group", o[0]);
      b.innerHTML = miniStage(o[0]) + "<b>" + o[1] + "</b><small>" + o[2] + "</small>";
      b.addEventListener("mouseenter", function () { hoverGroup = o[0]; });
      b.addEventListener("mouseleave", function () { hoverGroup = null; });
      b.addEventListener("focus", function () { hoverGroup = o[0]; });
      b.addEventListener("blur", function () { hoverGroup = null; });
      b.addEventListener("click", function () {
        if (selectedCue) { selectedCue.group = o[0]; markDirty(); renderCues(); }
        else defaultGroup = o[0];
        paintGroups();
      });
      box.appendChild(b);
    });
    $("lx-groups-for").textContent = selectedCue ? "Sets the group of the selected cue (" + E.fmtTimecode(selectedCue.t) + ")." : "No cue selected — sets the group new cues start with.";
  }

  // ---------- looks ----------
  function paintLooks() {
    var box = $("lx-looks"); box.innerHTML = "";
    E.LOOKS.forEach(function (l, i) {
      var b = document.createElement("button"); b.type = "button"; b.className = "lx-look";
      b.innerHTML = '<i style="background:' + l.color + '"></i>' + l.name + ' <span class="lx-kbd">' + (i + 1) + '</span>';
      b.title = (selectedCue ? "Apply to the selected cue" : "Add a cue at the playhead with this look") + " — key " + (i + 1);
      b.addEventListener("click", function () { applyLook(l); });
      box.appendChild(b);
    });
  }
  function applyLook(l) {
    if (selectedCue) { selectedCue.color = l.color; selectedCue.intensity = l.intensity; selectedCue.fade = l.fade; if (!selectedCue.note) selectedCue.note = l.name; markDirty(); renderCues(); }
    else if (buffer || runStart !== null) addCue(l);
  }

  // ---------- rig ----------
  var barsSel = $("lx-bars");
  for (var b = 2; b <= 10; b++) { var o = document.createElement("option"); o.value = b; o.textContent = b + " bars"; o.selected = b === show.bars; barsSel.appendChild(o); }
  barsSel.addEventListener("change", function () { show.bars = parseInt(barsSel.value, 10); if (selectedBar > show.bars) selectBar(null); markDirty(); renderCues(); paintGroups(); });
  var chansSel = $("lx-chans"); chansSel.value = String(show.chans || 4);
  chansSel.addEventListener("change", function () { show.chans = parseInt(chansSel.value, 10); markDirty(); });

  // ---------- library & autosave ----------
  var savedEl = $("lx-saved");
  function paintSaved(state, text) { savedEl.className = "lx-saved" + (state ? " is-" + state : ""); savedEl.textContent = text; }
  function payload() {
    var out = {}; Object.keys(show).forEach(function (k) { out[k] = show[k]; });
    out.cues = show.cues.map(function (c) { var d = {}; Object.keys(c).forEach(function (k) { if (k !== "_id") d[k] = c[k]; }); return d; });
    return out;
  }
  function markDirty() {
    dirty = true; paintSaved("dirty", "Unsaved changes…");
    clearTimeout(saveTimer); saveTimer = setTimeout(autosave, 1500);
  }
  function post(url, body) {
    return fetch(url, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)}).then(function (r) { return r.json(); });
  }
  function autosave() {
    if (!dirty) return;
    paintSaved("", "Saving…");
    var data = payload();
    var jobs = [post("/lights/save", data)];
    if (show.libraryId) jobs.push(post("/lights/library/save", {id: show.libraryId, name: show.name, data: data, track_id: show.trackId || "", tour_show_id: show.tourShowId || "", autosave: true}));
    Promise.all(jobs).then(function (rs) {
      if (rs.every(function (d) { return d && d.ok; })) { dirty = false; paintSaved("ok", "Saved ✓ " + new Date().toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"})); }
      else paintSaved("dirty", "Save failed — will retry");
    }).catch(function () { paintSaved("dirty", "Offline — will retry"); });
  }
  function paintLibrary() {
    var sel = $("lx-lib-select"); sel.innerHTML = '<option value="">— working copy —</option>';
    lib.shows.forEach(function (s) { var op = document.createElement("option"); op.value = s.id; op.textContent = s.name + " · " + s.cue_count + " cues"; op.selected = s.id === show.libraryId; sel.appendChild(op); });
    $("lx-show-name").value = show.name || "";
    $("lx-track").value = show.trackId || ""; $("lx-tourshow").value = show.tourShowId || "";
    $("lx-lib-delete").disabled = !show.libraryId;
    loadVersions();
  }
  $("lx-show-name").addEventListener("input", function () { show.name = $("lx-show-name").value.slice(0, 120); markDirty(); });
  $("lx-track").addEventListener("change", function () { show.trackId = $("lx-track").value; markDirty(); });
  $("lx-tourshow").addEventListener("change", function () { show.tourShowId = $("lx-tourshow").value; markDirty(); });
  $("lx-lib-save").addEventListener("click", function () {
    paintSaved("", "Saving…");
    var data = payload();
    post("/lights/library/save", {id: show.libraryId || "", name: show.name || "Untitled show", data: data, track_id: show.trackId || "", tour_show_id: show.tourShowId || "", note: $("lx-version-note").value || ""})
      .then(function (d) {
        if (!d.ok) { paintSaved("dirty", "Save failed"); return; }
        show.libraryId = d.id; dirty = false;
        lib.shows = d.shows || lib.shows; $("lx-version-note").value = "";
        paintSaved("ok", "Saved to library ✓ v" + d.versions);
        paintLibrary();
        return post("/lights/save", payload());
      });
  });
  $("lx-lib-select").addEventListener("change", function () {
    var id = $("lx-lib-select").value;
    if (!id) { show.libraryId = null; paintLibrary(); markDirty(); return; }
    fetch("/lights/library/" + id).then(function (r) { return r.json(); }).then(function (d) {
      if (!d.ok) return;
      loadShowData(d.show.data, d.show); markDirty();
    });
  });
  function loadShowData(data, meta) {
    var keep = {bars: data.bars, chans: data.chans};
    show = data && data.cues ? data : {name: meta ? meta.name : "", bars: 6, chans: 4, cues: []};
    show.bars = Math.max(2, Math.min(10, show.bars || keep.bars || 6)); show.chans = show.chans === 3 ? 3 : 4;
    show.cues.forEach(function (c) { if (typeof c.note !== "string") c.note = ""; });
    if (meta) { show.libraryId = meta.id; show.name = meta.name; show.trackId = meta.track_id || ""; show.tourShowId = meta.tour_show_id || ""; }
    selectedCue = null; selectedBar = null;
    barsSel.value = String(show.bars); chansSel.value = String(show.chans);
    renderCues(); paintGroups(); paintLibrary(); paintBeats(); paintBarCtl();
  }
  $("lx-lib-new").addEventListener("click", function () {
    loadShowData({name: "", bars: show.bars, chans: show.chans, cues: []}, null);
    show.libraryId = null; show.name = ""; paintLibrary(); markDirty();
  });
  $("lx-lib-delete").addEventListener("click", function () {
    if (!show.libraryId || !window.confirm("Delete this show from the library? Versions go with it.")) return;
    post("/lights/library/" + show.libraryId + "/delete", {}).then(function (d) {
      if (d.ok) { lib.shows = d.shows || []; show.libraryId = null; paintLibrary(); paintSaved("", "Deleted from library"); }
    });
  });
  function loadVersions() {
    var box = $("lx-versions");
    if (!box) return;
    if (!show.libraryId) { box.innerHTML = '<span class="lx-hint">Save to the library to start a version history.</span>'; return; }
    fetch("/lights/library/" + show.libraryId + "/versions").then(function (r) { return r.json(); }).then(function (d) {
      if (!d.ok) return;
      if (!d.versions.length) { box.innerHTML = '<span class="lx-hint">No versions yet.</span>'; return; }
      box.innerHTML = "";
      d.versions.forEach(function (v) {
        var line = document.createElement("div");
        line.textContent = v.saved_at.slice(0, 16).replace("T", " ") + " UTC · " + v.cue_count + " cues" + (v.note ? " · " + v.note : "");
        var btn = document.createElement("button"); btn.type = "button"; btn.className = "lx-btn lx-btn--ghost lx-btn--small"; btn.textContent = "Restore";
        btn.addEventListener("click", function () {
          post("/lights/library/" + show.libraryId + "/restore", {version_id: v.id}).then(function (r) {
            if (r.ok) { loadShowData(r.data, {id: show.libraryId, name: show.name, track_id: show.trackId, tour_show_id: show.tourShowId}); markDirty(); }
          });
        });
        line.appendChild(btn); box.appendChild(line);
      });
    });
  }

  // ---------- focus mode ----------
  var FOCUS = "lxFocus", RAIL = "lxRail";
  function setFocus(on, persist) {
    document.body.classList.toggle("lx-focus", on);
    if (window.innerWidth >= 1024) {
      var railOn = on && (safeGet(RAIL) !== "0");
      document.body.classList.toggle("sb-rail", railOn);
      if (!on) { document.body.classList.toggle("sb-rail", safeGet("sbRail") === "1"); }
    }
    if (persist) safeSet(FOCUS, on ? "1" : "0");
    var btn = $("lx-focus"); btn.setAttribute("aria-pressed", on ? "true" : "false"); btn.textContent = on ? "Exit focus" : "Focus mode";
    var rt = $("sb-rail-tgl"); if (rt) rt.setAttribute("aria-pressed", document.body.classList.contains("sb-rail") ? "true" : "false");
  }
  function safeGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function safeSet(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  $("lx-focus").addEventListener("click", function () { setFocus(!document.body.classList.contains("lx-focus"), true); });
  var railTgl = $("sb-rail-tgl");
  if (railTgl) railTgl.addEventListener("click", function () { setTimeout(function () { safeSet(RAIL, document.body.classList.contains("sb-rail") ? "1" : "0"); }, 0); });
  setFocus(safeGet(FOCUS) !== "0", false);

  // ---------- keyboard ----------
  document.addEventListener("keydown", function (e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (isTyping(e.target)) return;
    if (e.key === " " || e.code === "Space") { e.preventDefault(); togglePlay(); }
    else if (e.key === "c" || e.key === "C") { if (!$("lx-add").disabled) addCue(); }
    else if (e.key === "b" || e.key === "B") { if (!$("lx-blackout").disabled) addCue(E.LOOKS[5]); }
    else if (/^[1-6]$/.test(e.key) && e.target !== stage) { applyLook(E.LOOKS[parseInt(e.key, 10) - 1]); }
    else if (e.key === "Escape") { selectCue(null); selectBar(null); }
    else if (e.key === "ArrowLeft" && e.target !== stage && buffer) { seek(now() - (e.shiftKey ? 5 : 1)); }
    else if (e.key === "ArrowRight" && e.target !== stage && buffer) { seek(now() + (e.shiftKey ? 5 : 1)); }
  });

  // ---------- resize ----------
  if (window.ResizeObserver) {
    new ResizeObserver(function () { invalidatePeaks(); stageSize(); }).observe(stageWrap);
  } else window.addEventListener("resize", function () { invalidatePeaks(); });

  // ---------- main loop ----------
  var lastTable = 0, dockClock = $("lx-dock-clock");
  function loop() {
    requestAnimationFrame(loop);
    var t = now();
    clockEl.textContent = E.fmtTimecode(t);
    if (dockClock) dockClock.textContent = clockEl.textContent;
    drawStage(t);
    drawWave(t);
    var ts = performance.now();
    if (ts - lastTable > 500) { lastTable = ts; paintBarsTable(t); }
    if (writer && (playing || runStart !== null)) {
      if (ts - lastDmx > 33) {
        lastDmx = ts; dmxWrites++;
        writer.write(E.dmxFrame(show, E.lightingAt(show, t))).catch(function () {});
      }
    }
    if (writer && ts - dmxSec > 1000) {
      dmxSec = ts; dmxFps = dmxWrites; dmxWrites = 0;
      paintDmx("on", "Connected · universe 1 · " + (playing || runStart !== null ? dmxFps + " fps" : "idle"));
    }
  }

  window.__lightsTest = {
    show: function () { return show; }, lightingAt: function (t) { return E.lightingAt(show, t); },
    membersOf: E.membersOf, dmxFrame: function (looks) { return E.dmxFrame(show, looks); }, drawStage: drawStage,
    seek: seek, now: now, addCue: addCue, selectCue: selectCue, selectBar: selectBar, view: function () { return view; },
    zoomTo: zoomTo, setFocus: setFocus, stageSize: function () { return stageCss; }, barRects: function () { return barRects; },
    loadShowData: loadShowData, loadBuffer: loadBuffer, ensureCtx: ensureCtx, detectBeats: detectBeats,
    drawWave: drawWave, tick: function () { var t = now(); clockEl.textContent = E.fmtTimecode(t); if (dockClock) dockClock.textContent = clockEl.textContent; drawStage(t); drawWave(t); paintBarsTable(t); return t; },
    setHover: function (b, grp) { hoverBar = b; hoverGroup = grp; }, state: function () { return {playing: playing, buffer: !!buffer, selectedBar: selectedBar, selectedCue: selectedCue, dirty: dirty}; }
  };
  ensureIds(); renderCues(); paintGroups(); paintLooks(); paintLibrary(); paintBeats(); paintTransport(); paintBarCtl(); paintDmx("", "Preview only · no hardware");
  loop();
})();
