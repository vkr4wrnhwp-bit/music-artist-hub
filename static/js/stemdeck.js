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
    for (var x = 0; x < width; x++) {
      var v = data[Math.floor(x / width * data.length)] || 0;
      var h = Math.max(1, v * (HEIGHT - 4) / 2);
      /* Read from the stylesheet so the deck follows the theme rather than
         carrying its own colours, which the design lock forbids anyway. */
      g.fillStyle = x <= played
        ? getComputedStyle(canvas).getPropertyValue("--sd-played").trim()
        : getComputedStyle(canvas).getPropertyValue("--sd-wave").trim();
      g.fillRect(x, mid - h, 1, h * 2);
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

  function start() {
    Array.prototype.forEach.call(doc.querySelectorAll("[data-sd-src]"), mount);
  }

  if (doc.readyState === "loading") {
    doc.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})(typeof self !== "undefined" ? self : this, document);
