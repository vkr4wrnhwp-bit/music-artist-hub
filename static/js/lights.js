/* Light Studio — cue timeline locked to the song, canvas stage preview
   (simulation), and real DMX output to an ENTTEC USB Pro over Web Serial.
   Audio and cues stay in the browser; saving stores the cue list only. */
(function () {
  "use strict";
  var saved = window.__savedShow || null;
  var show = (saved && saved.cues) ? saved
    : {name: "", bars: 6, chans: 4, cues: []};
  show.bars = Math.max(2, Math.min(10, show.bars || 6));

  var ctx = null, buffer = null, playing = false, startAt = 0, runStart = null;
  var port = null, writer = null, lastDmx = 0;

  function ensureCtx() {
    if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
    return ctx;
  }

  // ---------- groups ----------
  function membersOf(group, bars) {
    var out = [], i;
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
    var opts = [["all", "All bars"], ["odd", "Odd side"], ["even", "Even side"]];
    for (var k = 1; k <= Math.ceil(bars / 2); k++) {
      opts.push(["pair" + k, "Pair " + k + " (" + k + " & " + (bars + 1 - k) + ")"]);
    }
    for (var n = 1; n <= bars; n++) opts.push(["b" + n, "Bar " + n]);
    return opts;
  }

  function hexRgb(hex) {
    var m = /^#?([0-9a-f]{6})$/i.exec(hex || "#000000");
    var v = parseInt(m ? m[1] : "000000", 16);
    return [v >> 16 & 255, v >> 8 & 255, v & 255];
  }

  // ---------- lighting engine ----------
  function lightingAt(t) {
    // Per fixture: latest cue at or before t, faded in from the look before it.
    var bars = show.bars, out = [];
    var sorted = show.cues.slice().sort(function (a, b) { return a.t - b.t; });
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

  // ---------- stage preview: audience view, draggable bars ----------
  var stage = document.getElementById("lx-stage");
  var g = stage.getContext("2d");
  var barRects = [];   // hit boxes rebuilt every frame for dragging
  var bgImg = new Image();
  bgImg.src = "/static/img/stage-bg.jpg";   // generated backdrop; drawn scene is the fallback

  function hz(n) {
    // Cheap deterministic hash for haze specks — stable per bar/particle.
    var x = Math.sin(n * 12.9898) * 43758.5453;
    return x - Math.floor(x);
  }

  function barPos(i, bars, w, h) {
    // Normalized positions persist in the show; defaults: truss + floor rows.
    var key = String(i);
    if (show.pos && show.pos[key]) return show.pos[key];
    var top = Math.ceil(bars / 2);
    if (i <= top) return [0.15 + 0.7 * ((i - 0.5) / top), 0.12];
    var n = i - top, count = bars - top;
    return [0.17 + 0.66 * ((n - 0.5) / count), 0.78];
  }

  function drawStage(t) {
    var w = stage.clientWidth;
    if (stage.width !== w) stage.width = w;
    var h = stage.height;
    var bgReady = bgImg.complete && bgImg.naturalWidth > 0;
    if (bgReady) {
      var scale = Math.max(w / bgImg.naturalWidth, h / bgImg.naturalHeight);
      var iw = bgImg.naturalWidth * scale, ih = bgImg.naturalHeight * scale;
      g.drawImage(bgImg, (w - iw) / 2, (h - ih) / 2, iw, ih);
      var vg = g.createLinearGradient(0, 0, 0, h);
      vg.addColorStop(0, "rgba(5,5,6,0.35)"); vg.addColorStop(0.4, "rgba(5,5,6,0)");
      vg.addColorStop(1, "rgba(5,5,6,0.25)");
      g.fillStyle = vg; g.fillRect(0, 0, w, h);
    } else {
      var bgg = g.createLinearGradient(0, 0, 0, h);
      bgg.addColorStop(0, "#08080a"); bgg.addColorStop(1, "#111014");
      g.fillStyle = bgg; g.fillRect(0, 0, w, h);
      g.fillStyle = "#0d0c10"; g.fillRect(w * 0.1, h * 0.08, w * 0.8, h * 0.5);
      g.strokeStyle = "#1d1a22";
      for (var cx = w * 0.12; cx < w * 0.88; cx += 26) {
        g.beginPath(); g.moveTo(cx, h * 0.08); g.lineTo(cx, h * 0.58); g.stroke();
      }
      g.fillStyle = "#17150f";
      g.beginPath();
      g.moveTo(w * 0.13, h * 0.58); g.lineTo(w * 0.87, h * 0.58);
      g.lineTo(w * 0.97, h * 0.9); g.lineTo(w * 0.03, h * 0.9);
      g.closePath(); g.fill();
      g.strokeStyle = "#2c2820"; g.stroke();
    }
    g.fillStyle = "rgba(239,230,205,0.55)";
    g.font = "bold " + Math.round(h * 0.06) + "px 'Arial Narrow', Arial";
    g.textAlign = "center";
    g.fillText((show.name || "YOUR SET").toUpperCase(), w / 2, h * 0.1);
    g.textAlign = "left";

    var looks = lightingAt(t);
    var bars = show.bars;
    barRects = [];

    // Light adds like real light: additive compositing over the photo.
    g.save();
    g.globalCompositeOperation = "lighter";
    var WIDTHS = [1, 0.62, 0.3], ALPHAS = [0.16, 0.24, 0.4];
    for (var i = 1; i <= bars; i++) {
      var p = barPos(i, bars, w, h);
      var bx = p[0] * w, by = p[1] * h;
      var look = looks[i - 1];
      var col = look.rgb, a = look.inten;
      if (a > 0.02) {
        var vert = (show.rot || {})[String(i)] === 90;
        var c3;
        if (vert) {
          var ex = bx < w / 2 ? bx + w * 0.42 : bx - w * 0.42;
          for (c3 = 0; c3 < 3; c3++) {
            var hw = 60 * WIDTHS[c3];
            var hgrad = g.createLinearGradient(bx, by, ex, by);
            hgrad.addColorStop(0, "rgba(" + col.join(",") + "," + (ALPHAS[c3] * a).toFixed(3) + ")");
            hgrad.addColorStop(1, "rgba(" + col.join(",") + ",0)");
            g.fillStyle = hgrad;
            g.beginPath();
            g.moveTo(bx, by - 16 * WIDTHS[c3]); g.lineTo(bx, by + 16 * WIDTHS[c3]);
            g.lineTo(ex, by + hw); g.lineTo(ex, by - hw);
            g.closePath(); g.fill();
          }
          for (var k = 0; k < 7; k++) {
            var pr = (hz(i * 97 + k) + t * 0.02 * (0.5 + hz(i + k))) % 1;
            var px = bx + (ex - bx) * pr;
            var py = by + (hz(i * 31 + k) - 0.5) * 2 * (16 + 44 * pr);
            g.fillStyle = "rgba(" + col.join(",") + "," + (0.35 * a * (1 - pr)).toFixed(3) + ")";
            g.beginPath(); g.arc(px, py, 1.6, 0, 7); g.fill();
          }
        } else {
          var down = p[1] < 0.5;
          var ly = down ? h * 0.86 : h * 0.1;
          for (c3 = 0; c3 < 3; c3++) {
            var lw = 70 * WIDTHS[c3];
            var grad = g.createLinearGradient(bx, by, bx, ly);
            grad.addColorStop(0, "rgba(" + col.join(",") + "," + (ALPHAS[c3] * a).toFixed(3) + ")");
            grad.addColorStop(1, "rgba(" + col.join(",") + ",0)");
            g.fillStyle = grad;
            g.beginPath();
            g.moveTo(bx - 16 * WIDTHS[c3], by); g.lineTo(bx + 16 * WIDTHS[c3], by);
            g.lineTo(bx + lw, ly); g.lineTo(bx - lw, ly);
            g.closePath(); g.fill();
          }
          for (var k2 = 0; k2 < 7; k2++) {
            var pr2 = (hz(i * 53 + k2) + t * 0.02 * (0.5 + hz(i * 7 + k2))) % 1;
            var py2 = by + (ly - by) * pr2;
            var px2 = bx + (hz(i * 17 + k2) - 0.5) * 2 * (16 + 54 * pr2);
            g.fillStyle = "rgba(" + col.join(",") + "," + (0.35 * a * (1 - pr2)).toFixed(3) + ")";
            g.beginPath(); g.arc(px2, py2, 1.6, 0, 7); g.fill();
          }
          if (down) {
            var pool = g.createRadialGradient(bx, h * 0.8, 4, bx, h * 0.8, 90);
            pool.addColorStop(0, "rgba(" + col.join(",") + "," + (0.4 * a).toFixed(3) + ")");
            pool.addColorStop(1, "rgba(" + col.join(",") + ",0)");
            g.fillStyle = pool;
            g.beginPath(); g.ellipse(bx, h * 0.8, 95, 28, 0, 0, 7); g.fill();
            // Glossy-deck reflection streak under the pool
            var refl = g.createLinearGradient(bx, h * 0.8, bx, h * 0.98);
            refl.addColorStop(0, "rgba(" + col.join(",") + "," + (0.12 * a).toFixed(3) + ")");
            refl.addColorStop(1, "rgba(" + col.join(",") + ",0)");
            g.fillStyle = refl;
            g.fillRect(bx - 24, h * 0.8, 48, h * 0.18);
          }
        }
      }
    }
    g.restore();

    // Backline silhouettes (audience view) — drawn fallback only
    if (!bgReady) {
    g.fillStyle = "#0b0a08"; g.strokeStyle = "#332d20";
    g.fillRect(w * 0.42, h * 0.5, w * 0.16, h * 0.09);
    g.strokeRect(w * 0.42, h * 0.5, w * 0.16, h * 0.09);
    g.beginPath(); g.arc(w * 0.5, h * 0.51, h * 0.045, 0, 7); g.fill(); g.stroke();
    g.beginPath(); g.arc(w * 0.46, h * 0.53, h * 0.028, 0, 7); g.fill();
    g.beginPath(); g.arc(w * 0.54, h * 0.53, h * 0.028, 0, 7); g.fill();
    g.fillRect(w * 0.2, h * 0.52, w * 0.07, h * 0.11);
    g.strokeRect(w * 0.2, h * 0.52, w * 0.07, h * 0.11);
    g.fillRect(w * 0.73, h * 0.52, w * 0.07, h * 0.11);
    g.strokeRect(w * 0.73, h * 0.52, w * 0.07, h * 0.11);
    g.fillRect(w * 0.62, h * 0.6, w * 0.1, h * 0.025);
    g.fillRect(w * 0.66, h * 0.62, w * 0.015, h * 0.09);
    g.fillRect(w * 0.497, h * 0.56, w * 0.006, h * 0.16);
    g.beginPath(); g.arc(w * 0.5, h * 0.555, h * 0.012, 0, 7); g.fill();
    g.beginPath();
    g.moveTo(w * 0.36, h * 0.72); g.lineTo(w * 0.41, h * 0.72);
    g.lineTo(w * 0.4, h * 0.76); g.lineTo(w * 0.37, h * 0.76);
    g.closePath(); g.fill(); g.stroke();
    g.beginPath();
    g.moveTo(w * 0.59, h * 0.72); g.lineTo(w * 0.64, h * 0.72);
    g.lineTo(w * 0.63, h * 0.76); g.lineTo(w * 0.6, h * 0.76);
    g.closePath(); g.fill(); g.stroke();
    }

    // Fixtures on top
    for (var j = 1; j <= bars; j++) {
      var p2 = barPos(j, bars, w, h);
      var x2 = p2[0] * w, y2 = p2[1] * h;
      var lk = looks[j - 1];
      var vert2 = (show.rot || {})[String(j)] === 90;
      var bw = vert2 ? 10 : 54, bh = vert2 ? 54 : 10;
      g.save();
      g.shadowColor = "rgb(" + lk.rgb.join(",") + ")";
      g.shadowBlur = 26 * lk.inten;
      g.fillStyle = "#1a1712";
      g.fillRect(x2 - bw / 2, y2 - bh / 2, bw, bh);
      g.restore();
      // Double outline: dark halo + gold line reads on any backdrop.
      g.lineWidth = 4; g.strokeStyle = "rgba(0,0,0,0.85)";
      g.strokeRect(x2 - bw / 2, y2 - bh / 2, bw, bh);
      g.lineWidth = 1.5; g.strokeStyle = "#d8b25a";
      g.strokeRect(x2 - bw / 2, y2 - bh / 2, bw, bh);
      g.lineWidth = 1;
      for (var s2 = 0; s2 < 6; s2++) {
        g.fillStyle = lk.inten > 0.02
          ? "rgba(" + lk.rgb.join(",") + "," + (0.25 + 0.75 * lk.inten).toFixed(2) + ")"
          : "#26221a";
        g.beginPath();
        if (vert2) g.arc(x2, y2 - bh / 2 + 6 + s2 * 8.4, 2.6, 0, 7);
        else g.arc(x2 - bw / 2 + 6 + s2 * 8.4, y2, 2.6, 0, 7);
        g.fill();
      }
      if (lk.inten > 0.02) {
        g.save();
        g.globalCompositeOperation = "lighter";
        var bloom = g.createRadialGradient(x2, y2, 1, x2, y2, 30 + 26 * lk.inten);
        bloom.addColorStop(0, "rgba(" + lk.rgb.join(",") + "," + (0.5 * lk.inten).toFixed(3) + ")");
        bloom.addColorStop(1, "rgba(" + lk.rgb.join(",") + ",0)");
        g.fillStyle = bloom;
        g.beginPath(); g.arc(x2, y2, 30 + 26 * lk.inten, 0, 7); g.fill();
        g.restore();
      }
      g.fillStyle = "rgba(0,0,0,0.75)";
      g.fillRect(x2 - bw / 2 - 4, y2 - bh / 2 - 16, 14, 12);
      g.fillStyle = "#e8c667"; g.font = "bold 9px Arial";
      g.fillText(String(j), x2 - bw / 2 - 1, y2 - bh / 2 - 7);
      barRects.push({i: j, x: x2 - bw / 2 - 8, y: y2 - bh / 2 - 8,
                     w: bw + 16, h: bh + 16});
    }

    // Audience heads: the POV anchor — drawn fallback only
    if (!bgReady) {
    g.fillStyle = "#050505";
    for (var a2 = 0; a2 < 9; a2++) {
      var hx = w * (0.06 + 0.11 * a2), hr = h * (0.075 + (a2 % 3) * 0.012);
      g.beginPath(); g.arc(hx, h + hr * 0.35, hr, Math.PI, 2 * Math.PI); g.fill();
    }
    }
  }

  // Drag bars anywhere: truss, floor, side sticks — position persists.
  var dragBar = null;
  stage.style.touchAction = "none";
  stage.style.cursor = "grab";
  stage.addEventListener("pointerdown", function (e) {
    var r = stage.getBoundingClientRect();
    var mx = e.clientX - r.left, my = e.clientY - r.top;
    for (var k = barRects.length - 1; k >= 0; k--) {
      var b = barRects[k];
      if (mx >= b.x && mx <= b.x + b.w && my >= b.y && my <= b.y + b.h) {
        dragBar = b.i;
        stage.setPointerCapture(e.pointerId);
        e.preventDefault();
        return;
      }
    }
  });
  stage.addEventListener("pointermove", function (e) {
    if (dragBar === null) return;
    var r = stage.getBoundingClientRect();
    show.pos = show.pos || {};
    show.pos[String(dragBar)] = [
      Math.max(0.03, Math.min(0.97, (e.clientX - r.left) / r.width)),
      Math.max(0.04, Math.min(0.92, (e.clientY - r.top) / stage.height))];
  });
  stage.addEventListener("pointerup", function () { dragBar = null; });
  stage.addEventListener("pointercancel", function () { dragBar = null; });
  stage.addEventListener("dblclick", function (e) {
    var r = stage.getBoundingClientRect();
    var mx = e.clientX - r.left, my = e.clientY - r.top;
    for (var k = barRects.length - 1; k >= 0; k--) {
      var b = barRects[k];
      if (mx >= b.x && mx <= b.x + b.w && my >= b.y && my <= b.y + b.h) {
        show.rot = show.rot || {};
        show.rot[String(b.i)] = show.rot[String(b.i)] === 90 ? 0 : 90;
        return;
      }
    }
  });

  // ---------- DMX (ENTTEC USB Pro over Web Serial) ----------

  function dmxFrame(looks) {
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
  document.getElementById("lx-dmx").addEventListener("click", function () {
    var stateEl = document.getElementById("lx-dmx-state");
    if (!("serial" in navigator)) {
      stateEl.textContent = "Hardware: this browser has no Web Serial — use Chrome or Edge on desktop.";
      return;
    }
    navigator.serial.requestPort().then(function (p) {
      port = p;
      return port.open({baudRate: 57600});
    }).then(function () {
      writer = port.writable.getWriter();
      stateEl.textContent = "Hardware: connected — cues are driving real DMX.";
    }).catch(function () {
      stateEl.textContent = "Hardware: not connected — preview only";
    });
  });

  // ---------- transport ----------
  var playBtn = document.getElementById("lx-play");
  var src = null;
  function now() {
    if (buffer && playing) return ctx.currentTime - startAt;
    if (runStart !== null) return (performance.now() - runStart) / 1000;
    return 0;
  }
  function stopAll() {
    if (src) { try { src.stop(); } catch (e) {} src = null; }
    playing = false; runStart = null;
    playBtn.textContent = "Play";
  }
  playBtn.addEventListener("click", function () {
    if (playing || runStart !== null) { stopAll(); return; }
    ensureCtx().resume();
    src = ctx.createBufferSource();
    src.buffer = buffer;
    src.connect(ctx.destination);
    src.onended = function () { stopAll(); };
    src.start();
    startAt = ctx.currentTime; playing = true;
    playBtn.textContent = "Stop";
  });
  document.getElementById("lx-run").addEventListener("click", function () {
    if (runStart !== null || playing) { stopAll(); return; }
    runStart = performance.now();
    playBtn.textContent = "Play";
  });
  document.getElementById("lx-file").addEventListener("change", function (e) {
    var f = e.target.files[0];
    if (!f) return;
    ensureCtx().resume();
    f.arrayBuffer().then(function (ab) { return ctx.decodeAudioData(ab); })
      .then(function (buf) {
        buffer = buf;
        show.name = show.name || f.name.replace(/\.[^.]+$/, "");
        document.getElementById("lx-fileinfo").textContent =
          f.name + " — " + buf.duration.toFixed(1) + "s (stays on this machine)";
        playBtn.disabled = false;
      });
  });

  // ---------- cue list UI ----------
  var cuesWrap = document.getElementById("lx-cues");
  function renderCues() {
    cuesWrap.innerHTML = "";
    var sorted = show.cues.slice().sort(function (a, b) { return a.t - b.t; });
    if (!sorted.length) {
      cuesWrap.innerHTML = '<p class="text-[11px] text-gray-600">No cues yet. ' +
        'Play the song and hit “+ Cue at playhead” where the music turns — ' +
        'intro dim, chorus full, drop blackout.</p>';
      return;
    }
    sorted.forEach(function (c) {
      var row = document.createElement("div");
      row.className = "flex flex-wrap items-center gap-2 rounded-lg border border-white/10 bg-black/30 px-3 py-2";
      function inp(type, value, cls, onchange, attrs) {
        var el = document.createElement("input");
        el.type = type; el.value = value; el.className = cls;
        Object.keys(attrs || {}).forEach(function (k) { el.setAttribute(k, attrs[k]); });
        el.addEventListener("input", onchange);
        return el;
      }
      row.appendChild(inp("number", c.t, "w-20 rounded border border-white/15 bg-black/50 px-2 py-1 font-mono text-xs text-[#e8c667]",
        function (e) { c.t = parseFloat(e.target.value) || 0; }, {step: "0.1", min: "0", title: "seconds"}));
      var sel = document.createElement("select");
      sel.className = "rounded border border-white/15 bg-black/50 px-2 py-1 text-xs text-white";
      groupOptions(show.bars).forEach(function (o) {
        var op = document.createElement("option");
        op.value = o[0]; op.textContent = o[1]; op.selected = c.group === o[0];
        sel.appendChild(op);
      });
      sel.addEventListener("change", function () { c.group = sel.value; });
      row.appendChild(sel);
      row.appendChild(inp("color", c.color, "h-7 w-10 cursor-pointer rounded border border-white/15 bg-transparent",
        function (e) { c.color = e.target.value; }));
      var inten = inp("range", c.intensity, "w-28 accent-[#c9a24a]",
        function (e) { c.intensity = parseInt(e.target.value, 10); }, {min: 0, max: 100});
      row.appendChild(inten);
      var fadeWrap = document.createElement("label");
      fadeWrap.className = "flex items-center gap-1 text-[10px] text-gray-500";
      fadeWrap.textContent = "fade";
      fadeWrap.appendChild(inp("number", c.fade, "w-16 rounded border border-white/15 bg-black/50 px-2 py-1 font-mono text-xs text-gray-300",
        function (e) { c.fade = parseFloat(e.target.value) || 0; }, {step: "0.1", min: "0"}));
      row.appendChild(fadeWrap);
      var del = document.createElement("button");
      del.textContent = "×";
      del.className = "ml-auto h-7 w-7 rounded border border-white/15 text-sm text-gray-500 hover:border-red-500/40 hover:text-red-400";
      del.addEventListener("click", function () {
        show.cues.splice(show.cues.indexOf(c), 1); renderCues();
      });
      row.appendChild(del);
      cuesWrap.appendChild(row);
    });
  }
  document.getElementById("lx-add").addEventListener("click", function () {
    show.cues.push({t: Math.round(now() * 10) / 10, group: "all",
                    color: "#d8b25a", intensity: 80, fade: 0.5});
    renderCues();
  });
  document.getElementById("lx-blackout").addEventListener("click", function () {
    show.cues.push({t: Math.round(now() * 10) / 10, group: "all",
                    color: "#000000", intensity: 0, fade: 0.1});
    renderCues();
  });
  document.getElementById("lx-save").addEventListener("click", function () {
    fetch("/lights/save", {method: "POST", headers: {"Content-Type": "application/json"},
                           body: JSON.stringify(show)})
      .then(function (r) { return r.json(); })
      .then(function (d) {
        document.getElementById("lx-status").textContent =
          d.ok ? "Show saved." : "Save failed.";
      });
  });

  // ---------- rig config ----------
  var barsSel = document.getElementById("lx-bars");
  for (var b = 2; b <= 10; b++) {
    var o = document.createElement("option");
    o.value = b; o.textContent = b + " bars"; o.selected = b === show.bars;
    barsSel.appendChild(o);
  }
  barsSel.addEventListener("change", function () {
    show.bars = parseInt(barsSel.value, 10); renderCues();
  });
  var chansSel = document.getElementById("lx-chans");
  chansSel.value = String(show.chans || 4);
  chansSel.addEventListener("change", function () {
    show.chans = parseInt(chansSel.value, 10);
  });

  // ---------- main loop ----------
  function fmtClock(t) {
    var m = Math.floor(t / 60), s = (t - m * 60);
    return m + ":" + (s < 10 ? "0" : "") + s.toFixed(1);
  }
  function loop() {
    requestAnimationFrame(loop);
    var t = now();
    document.getElementById("lx-clock").textContent = fmtClock(t);
    drawStage(t);
    if (writer && (playing || runStart !== null)) {
      var ts = performance.now();
      if (ts - lastDmx > 33) {
        lastDmx = ts;
        writer.write(dmxFrame(lightingAt(t))).catch(function () {});
      }
    }
  }

  window.__lightsTest = {show: function () { return show; },
                         lightingAt: lightingAt, membersOf: membersOf,
                         dmxFrame: dmxFrame, drawStage: drawStage};
  renderCues();
  loop();
})();
