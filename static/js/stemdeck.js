/* Street Banker · Stem deck — a waveform and a transport on every output file.
 *
 * The Audio Studio listed each returned file as a row with a browser's own
 * <audio> element on it. That plays, and nothing else: no picture of the
 * file, no way to jump, no way to nudge back four bars and hear the edit
 * again. Comparing four separated stems meant scrubbing four unlabelled
 * grey bars.
 *
 * HOW IT PLAYS, AND WHY
 *
 * The <audio> element stays the engine. It streams, it needs no user gesture
 * to be scheduled correctly, and it cannot get stuck behind a suspended
 * AudioContext - which is the bug that made every transport in Studio and
 * the Rack need two clicks. An AudioContext is opened once, to decode the
 * file for the drawing, and closed again: Chrome caps live contexts per tab
 * and a page of eight stems would otherwise run out.
 *
 * WHAT THE PICTURE IS
 *
 * Peaks, not a spectrum: for each pixel column, the largest absolute sample
 * in the slice behind it, mirrored about the centre line. That is the shape
 * an engineer reads for arrangement and for silence, and it is honest at any
 * width because it never averages a transient away.
 *
 * A file that will not decode still gets a working transport - the element
 * can usually play formats the decoder here will not accept - and says the
 * picture is unavailable rather than drawing a flat line, which would read
 * as silence.
 */
(function (root, doc) {
  "use strict";

  var NUDGE = 10;             // seconds a skip button moves
  var HEIGHT = 44;

  function mmss(t) {
    if (!isFinite(t) || t < 0) { t = 0; }
    var m = Math.floor(t / 60), s = Math.floor(t % 60);
    return m + ":" + (s < 10 ? "0" : "") + s;
  }

  /* One value per pixel column: the loudest sample behind it. */
  function peaks(buf, columns) {
    var out = new Float32Array(columns);
    var chans = [], i;
    for (i = 0; i < buf.numberOfChannels; i++) { chans.push(buf.getChannelData(i)); }
    var per = Math.max(1, Math.floor(buf.length / columns));
    for (var c = 0; c < columns; c++) {
      var start = c * per, end = Math.min(buf.length, start + per), top = 0;
      for (i = 0; i < chans.length; i++) {
        var data = chans[i];
        for (var n = start; n < end; n++) {
          var v = data[n] < 0 ? -data[n] : data[n];
          if (v > top) { top = v; }
        }
      }
      out[c] = top;
    }
    return out;
  }

  function draw(canvas, data, progress) {
    var ratio = root.devicePixelRatio || 1;
    var width = canvas.clientWidth || 320;
    canvas.width = Math.floor(width * ratio);
    canvas.height = Math.floor(HEIGHT * ratio);
    var g = canvas.getContext("2d");
    g.setTransform(ratio, 0, 0, ratio, 0, 0);
    g.clearRect(0, 0, width, HEIGHT);
    if (!data) { return; }
    var mid = HEIGHT / 2;
    var played = Math.floor(width * (progress || 0));
    /* Read from the stylesheet so the deck follows the theme rather than
       carrying its own colours, which the design lock forbids anyway. */
    var cs = getComputedStyle(canvas);
    var playedColor = cs.getPropertyValue("--sd-played").trim();
    var waveColor = cs.getPropertyValue("--sd-wave").trim();
    var headColor = cs.getPropertyValue("--sd-head").trim() || playedColor;
    for (var x = 0; x < width; x++) {
      var v = data[Math.floor(x / width * data.length)] || 0;
      var h = Math.max(1, v * (HEIGHT - 4) / 2);
      g.fillStyle = x <= played ? playedColor : waveColor;
      g.fillRect(x, mid - h, 1, h * 2);
    }
    /* The playhead: a line the eye can find after a skip, which the
       colour change alone did not give (owner, 2026-09-15). */
    if (progress > 0) {
      g.fillStyle = headColor;
      g.fillRect(Math.max(0, played - 1), 0, 2, HEIGHT);
    }
  }

  function decode(url) {
    var Ctx = root.AudioContext || root.webkitAudioContext;
    if (!Ctx) { return Promise.reject(new Error("no decoder")); }
    var ctx = new Ctx();
    return fetch(url, {credentials: "same-origin"})
      .then(function (r) {
        if (!r.ok) { throw new Error("could not read the file"); }
        return r.arrayBuffer();
      })
      .then(function (ab) { return ctx.decodeAudioData(ab); })
      .then(function (buf) {
        try { ctx.close(); } catch (e) { /* already gone */ }
        return buf;
      }, function (err) {
        try { ctx.close(); } catch (e) { /* already gone */ }
        throw err;
      });
  }

  /* Every deck on the page, so the group bar can drive them together. */
  var decks = [];

  function mount(deck) {
    var audio = deck.querySelector("audio");
    var canvas = deck.querySelector("[data-sd-wave]");
    var playBtn = deck.querySelector("[data-sd-play]");
    var backBtn = deck.querySelector("[data-sd-back]");
    var fwdBtn = deck.querySelector("[data-sd-fwd]");
    var clock = deck.querySelector("[data-sd-time]");
    var note = deck.querySelector("[data-sd-note]");
    if (!audio || !canvas) { return; }
    var data = null;
    decks.push({el: deck, audio: audio, tick: function () { tick(); }});

    function tick() {
      var dur = audio.duration;
      clock.textContent = mmss(audio.currentTime)
        + (isFinite(dur) ? " / " + mmss(dur) : "");
      draw(canvas, data, isFinite(dur) && dur > 0 ? audio.currentTime / dur : 0);
    }

    playBtn.addEventListener("click", function () {
      if (audio.paused) { audio.play(); } else { audio.pause(); }
    });
    function setLabel() {
      var playing = !audio.paused;
      playBtn.textContent = playing ? "⏸" : "▶";
      playBtn.setAttribute("aria-label", playing ? "Pause" : "Play");
    }
    audio.addEventListener("play", setLabel);
    audio.addEventListener("pause", setLabel);
    audio.addEventListener("timeupdate", tick);
    audio.addEventListener("loadedmetadata", tick);
    audio.addEventListener("ended", setLabel);

    backBtn.addEventListener("click", function () {
      audio.currentTime = Math.max(0, audio.currentTime - NUDGE);
    });
    fwdBtn.addEventListener("click", function () {
      var dur = isFinite(audio.duration) ? audio.duration : audio.currentTime;
      audio.currentTime = Math.min(dur, audio.currentTime + NUDGE);
    });
    canvas.addEventListener("click", function (e) {
      var dur = audio.duration;
      if (!isFinite(dur) || !dur) { return; }
      var box = canvas.getBoundingClientRect();
      audio.currentTime = Math.max(0, Math.min(dur,
        (e.clientX - box.left) / box.width * dur));
    });
    root.addEventListener("resize", tick);

    decode(deck.dataset.sdSrc)
      .then(function (buf) {
        data = peaks(buf, 1200);
        note.textContent = "";
        tick();
      })
      .catch(function () {
        /* The element can often play what the decoder here refuses. Say the
           picture is missing; do not draw a flat line, which reads as
           silence, and do not take the transport away. */
        note.textContent = "No waveform for this format — it still plays.";
      });

    setLabel();
    tick();
  }

  /* Stems are meant to be heard together. With more than one deck on the
     page a group bar plays them all from the same point, and each deck gets
     a Mute so a stem can be taken out of the mix and put back (owner,
     2026-09-15: "a group all button that plays all stems at once then you
     can mute as you like"). */
  function mountGroup() {
    if (decks.length < 2) { return; }
    var first = decks[0].el;
    var host = first.closest("table") || first.closest("section") || first.parentNode;
    var bar = doc.createElement("div");
    bar.className = "sd-group";
    bar.setAttribute("role", "group");
    bar.setAttribute("aria-label", "All stems together");
    var label = doc.createElement("span");
    label.className = "sd-group-label";
    label.textContent = "All stems together";
    var playAll = doc.createElement("button");
    playAll.type = "button"; playAll.className = "sd-btn"; playAll.textContent = "\u25B6 Play all";
    var backAll = doc.createElement("button");
    backAll.type = "button"; backAll.className = "sd-btn"; backAll.textContent = "\u23EA";
    backAll.setAttribute("aria-label", "All back ten seconds");
    var fwdAll = doc.createElement("button");
    fwdAll.type = "button"; fwdAll.className = "sd-btn"; fwdAll.textContent = "\u23E9";
    fwdAll.setAttribute("aria-label", "All forward ten seconds");
    var top = doc.createElement("button");
    top.type = "button"; top.className = "sd-btn"; top.textContent = "\u23EE";
    top.setAttribute("aria-label", "All to the start");
    var hint = doc.createElement("span");
    hint.className = "sd-group-label";
    hint.textContent = "Mute a stem on its own row to take it out of the mix.";
    bar.appendChild(label); bar.appendChild(top); bar.appendChild(backAll);
    bar.appendChild(playAll); bar.appendChild(fwdAll); bar.appendChild(hint);
    host.parentNode.insertBefore(bar, host);

    function each(fn) { decks.forEach(function (d) { fn(d.audio, d); }); }
    function anyPlaying() {
      return decks.some(function (d) { return !d.audio.paused; });
    }
    function setAllLabel() {
      var playing = anyPlaying();
      playAll.textContent = playing ? "\u23F8 Pause all" : "\u25B6 Play all";
    }
    function seekAll(t) {
      each(function (a) {
        var dur = isFinite(a.duration) ? a.duration : t;
        a.currentTime = Math.max(0, Math.min(dur, t));
      });
    }
    playAll.addEventListener("click", function () {
      if (anyPlaying()) { each(function (a) { a.pause(); }); return; }
      /* everyone starts from the first deck's clock, so the stems line up */
      var t = decks[0].audio.currentTime || 0;
      seekAll(t);
      each(function (a) { a.play(); });
    });
    backAll.addEventListener("click", function () {
      seekAll((decks[0].audio.currentTime || 0) - NUDGE);
    });
    fwdAll.addEventListener("click", function () {
      seekAll((decks[0].audio.currentTime || 0) + NUDGE);
    });
    top.addEventListener("click", function () { seekAll(0); });
    each(function (a) {
      a.addEventListener("play", setAllLabel);
      a.addEventListener("pause", setAllLabel);
      a.addEventListener("ended", setAllLabel);
    });

    decks.forEach(function (d) {
      var mute = doc.createElement("button");
      mute.type = "button"; mute.className = "sd-btn"; mute.textContent = "Mute";
      mute.setAttribute("aria-pressed", "false");
      var name = d.el.dataset.sdName || "this stem";
      mute.setAttribute("aria-label", "Mute " + name);
      mute.addEventListener("click", function () {
        d.audio.muted = !d.audio.muted;
        mute.setAttribute("aria-pressed", d.audio.muted ? "true" : "false");
        mute.textContent = d.audio.muted ? "Muted" : "Mute";
        d.el.classList.toggle("is-muted", d.audio.muted);
      });
      var fwd = d.el.querySelector("[data-sd-fwd]");
      if (fwd && fwd.parentNode) { fwd.parentNode.insertBefore(mute, fwd.nextSibling); }
    });
    setAllLabel();
  }

  function start() {
    Array.prototype.forEach.call(doc.querySelectorAll("[data-sd-src]"), mount);
    mountGroup();
  }

  if (doc.readyState === "loading") {
    doc.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})(typeof self !== "undefined" ? self : this, document);
