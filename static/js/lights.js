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

  // ---------- stage preview ----------
  var stage = document.getElementById("lx-stage");
  var g = stage.getContext("2d");
  function drawStage(t) {
    var w = stage.clientWidth;
    if (stage.width !== w) stage.width = w;
    var h = stage.height;
    g.clearRect(0, 0, w, h);
    g.fillStyle = "#0a0a0b"; g.fillRect(0, 0, w, h);
    var looks = lightingAt(t);
    var bars = show.bars;
    var top = Math.ceil(bars / 2), bottom = bars - top;
    function row(count, startIdx, y) {
      var bw = Math.min(120, (w - 80) / count - 20);
      var total = count * (bw + 20) - 20;
      var x0 = (w - total) / 2;
      for (var i = 0; i < count; i++) {
        var look = looks[startIdx + i - 1];
        var x = x0 + i * (bw + 20);
        var col = "rgb(" + look.rgb.join(",") + ")";
        g.save();
        g.shadowColor = col; g.shadowBlur = 60 * look.inten;
        g.globalAlpha = 0.15 + 0.85 * look.inten;
        g.fillStyle = col;
        g.fillRect(x, y, bw, 14);
        g.restore();
        g.strokeStyle = "#3a3424"; g.strokeRect(x, y, bw, 14);
        g.fillStyle = "#6b6459"; g.font = "9px Arial";
        g.fillText(String(startIdx + i), x + 2, y + 26);
      }
    }
    row(top, 1, 40);
    if (bottom) row(bottom, top + 1, h - 60);
    g.fillStyle = "#efe6cd"; g.font = "bold 18px 'Arial Narrow', Arial";
    g.textAlign = "center";
    g.fillText((show.name || "YOUR SET").toUpperCase(), w / 2, h / 2 + 6);
    g.textAlign = "left";
  }

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
                         dmxFrame: dmxFrame};
  renderCues();
  loop();
})();
