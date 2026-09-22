/* The Release-Ready preview unit.

   The faceplate is a photograph; this drives the parts of it that light or
   move, and every one of them is driven by something real:

     the display window  the preview's own waveform, drawn from the decoded
                         audio, with a playhead and the elapsed time
     the meter lenses    the live signal through a WebAudio analyser, so the
                         meters are showing this track and not an animation
     the jewel           the job's state: breathing while RoEx is working,
                         steady when the preview is here, red when it failed
     the knob            output level, which is a real range input underneath

   The <audio> element keeps its id and its ARIA label and stays the thing
   that actually plays, so the page works with this script absent, and below
   900px the plain controls are what is shown.

   Nothing here invents a figure. With no audio yet the window says so
   rather than drawing a waveform that is not of anything. */
(function () {
  "use strict";

  function ready(fn) {
    if (document.readyState !== "loading") { fn(); }
    else { document.addEventListener("DOMContentLoaded", fn); }
  }

  function clock(s) {
    s = Math.max(0, Math.floor(s || 0));
    return Math.floor(s / 60) + ":" + ("0" + (s % 60)).slice(-2);
  }

  function Unit(root) {
    this.root = root;
    this.audio = document.getElementById(root.getAttribute("data-rr-audio") || "");
    this.canvas = root.querySelector("canvas");
    this.screen = root.querySelector(".rr-unit-screen");
    this.strips = [root.querySelector(".rr-unit-meter--l"),
                   root.querySelector(".rr-unit-meter--r")];
    this.knob = root.querySelector(".rr-unit-knob input");
    this.readout = root.parentNode.querySelector("[data-rr-unit-time]");
    this.peak = [0, 0];
    this.wave = null;
    this.ctx = this.canvas ? this.canvas.getContext("2d") : null;
    this.dpr = Math.min(window.devicePixelRatio || 1, 2);
    if (this.canvas) { this.fit(); }
    this.bind();
    this.paint();
  }

  Unit.prototype.state = function () {
    return this.root.getAttribute("data-state") || "working";
  };

  Unit.prototype.fit = function () {
    var box = this.canvas.getBoundingClientRect();
    if (!box.width) { return; }
    this.canvas.width = Math.round(box.width * this.dpr);
    this.canvas.height = Math.round(box.height * this.dpr);
  };

  Unit.prototype.bind = function () {
    var self = this;

    if (this.screen) {
      this.screen.addEventListener("click", function (e) {
        if (self.state() !== "ready" || !self.audio) { return; }
        var box = self.screen.getBoundingClientRect();
        var x = e.clientX - box.left;
        // The left tenth is play/pause; the rest of the window is a scrub
        // strip, which is what a display of this shape reads as.
        if (x > box.width * 0.1 && self.audio.duration) {
          self.audio.currentTime = Math.max(0, Math.min(
            self.audio.duration, (x / box.width) * self.audio.duration));
          if (self.audio.paused) { self.play(); }
        } else if (self.audio.paused) {
          self.play();
        } else {
          self.audio.pause();
        }
      });
      this.screen.addEventListener("keydown", function (e) {
        if (e.key === " " || e.key === "Enter") { e.preventDefault(); self.screen.click(); }
      });
    }

    if (this.audio) {
      ["play", "pause", "ended", "seeked", "timeupdate", "loadedmetadata"]
        .forEach(function (name) {
          self.audio.addEventListener(name, function () { self.paint(); });
        });
      this.audio.addEventListener("play", function () { self.run(); });
    }

    if (this.knob) {
      this.knob.addEventListener("input", function () { self.level(); });
      var wrap = this.knob.parentNode;
      var dragging = false, startY = 0, startV = 0;
      wrap.addEventListener("pointerdown", function (e) {
        dragging = true;
        startY = e.clientY;
        startV = Number(self.knob.value);
        wrap.setPointerCapture(e.pointerId);
      });
      wrap.addEventListener("pointermove", function (e) {
        if (!dragging) { return; }
        // Up is louder, and 140px of travel covers the whole range.
        var next = startV + ((startY - e.clientY) / 140) * 100;
        self.knob.value = String(Math.max(0, Math.min(100, Math.round(next))));
        self.level();
      });
      ["pointerup", "pointercancel"].forEach(function (n) {
        wrap.addEventListener(n, function () { dragging = false; });
      });
      this.level();
    }

    window.addEventListener("resize", function () {
      if (self.canvas) { self.fit(); self.paint(); }
    });
  };

  Unit.prototype.level = function () {
    var v = Number(this.knob.value) / 100;
    if (this.audio) { this.audio.volume = Math.max(0, Math.min(1, v)); }
    // A pointerless knob reads its position through the knurling and the
    // brushed spin, so the sweep has to be wide enough to see: -150 to +150.
    var img = this.root.querySelector(".rr-unit-knob img");
    if (img) { img.style.transform = "rotate(" + (-150 + v * 300) + "deg)"; }
    this.knob.setAttribute("aria-valuetext", Math.round(v * 100) + "% output");
  };

  /* ---- the meters, from the real signal -------------------------------- */

  Unit.prototype.listen = function () {
    if (this.analyser || this.noAudioApi || !this.audio) { return; }
    var AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) { this.noAudioApi = true; return; }
    try {
      this.ac = new AC();
      var src = this.ac.createMediaElementSource(this.audio);
      var split = this.ac.createChannelSplitter(2);
      this.analyser = [this.ac.createAnalyser(), this.ac.createAnalyser()];
      src.connect(split);
      for (var i = 0; i < 2; i++) {
        this.analyser[i].fftSize = 1024;
        split.connect(this.analyser[i], i);
      }
      src.connect(this.ac.destination);
      this.buf = new Float32Array(this.analyser[0].fftSize);
    } catch (err) {
      // A file the page may not read sample-by-sample, or a second source
      // node on the same element. The player still plays; the meters stay
      // dark rather than showing numbers that are not measurements.
      this.analyser = null;
      this.noAudioApi = true;
    }
  };

  Unit.prototype.play = function () {
    this.listen();
    if (this.ac && this.ac.state === "suspended") { this.ac.resume(); }
    var going = this.audio.play();
    if (going && going.catch) { going.catch(function () {}); }
  };

  Unit.prototype.run = function () {
    var self = this;
    if (this.raf) { return; }
    var tick = function () {
      self.meters(false);
      if (self.audio && !self.audio.paused) {
        self.raf = requestAnimationFrame(tick);
      } else {
        self.raf = 0;
        self.meters(true);
      }
    };
    this.raf = requestAnimationFrame(tick);
  };

  Unit.prototype.meters = function (fade) {
    for (var ch = 0; ch < 2; ch++) {
      var rms = 0;
      if (!fade && this.analyser && this.analyser[ch]) {
        this.analyser[ch].getFloatTimeDomainData(this.buf);
        var sum = 0;
        for (var i = 0; i < this.buf.length; i++) {
          sum += this.buf[i] * this.buf[i];
        }
        rms = Math.sqrt(sum / this.buf.length);
      }
      // dBFS across eleven lenses: the first at -48 dB, the last at 0.
      var db = rms > 0 ? 20 * Math.log10(rms) : -100;
      var lit = Math.max(0, Math.min(11, Math.round((db + 48) / 48 * 11)));
      this.peak[ch] = fade ? 0 : Math.max(lit, this.peak[ch] - 0.35);
      var strip = this.strips[ch];
      if (!strip) { continue; }
      var cells = strip.children, want = Math.round(this.peak[ch]);
      for (var c = 0; c < cells.length; c++) {
        cells[c].classList.toggle("on", c < want);
      }
    }
  };

  /* ---- the display window ---------------------------------------------- */

  Unit.prototype.shape = function () {
    // The waveform of this preview, decoded once. Until it is here the
    // window draws no waveform at all, rather than a decorative one.
    var self = this;
    if (this.wave || this.shaping || !this.audio || !this.audio.currentSrc) { return; }
    var AC = window.AudioContext || window.webkitAudioContext;
    if (!AC || !window.fetch) { return; }
    this.shaping = true;
    fetch(this.audio.currentSrc).then(function (r) {
      if (!r.ok) { throw new Error("not ours to read"); }
      return r.arrayBuffer();
    }).then(function (buf) {
      var ac = new AC();
      return ac.decodeAudioData(buf).then(function (audio) {
        ac.close();
        return audio;
      });
    }).then(function (audio) {
      var data = audio.getChannelData(0);
      var n = 220, step = Math.floor(data.length / n) || 1, out = [];
      for (var i = 0; i < n; i++) {
        var top = 0;
        for (var j = 0; j < step; j += 8) {
          var v = Math.abs(data[i * step + j] || 0);
          if (v > top) { top = v; }
        }
        out.push(top);
      }
      self.wave = out;
      self.paint();
    }).catch(function () { self.wave = null; });
  };

  Unit.prototype.paint = function () {
    if (!this.ctx) { return; }
    var g = this.ctx, W = this.canvas.width, H = this.canvas.height;
    if (!W || !H) { return; }
    // Read off the screen element, where rr-unit.css declares them from the
    // tokens. Hard-coding the brand values here would be a second source of
    // truth for them, and it is what the design system refuses.
    var css = getComputedStyle(this.screen || this.root);
    var gold = css.getPropertyValue("--wave").trim() || "rgba(255,255,255,.85)";
    var dim = css.getPropertyValue("--wave-rest").trim() || "rgba(255,255,255,.45)";
    g.clearRect(0, 0, W, H);

    var st = this.state();
    if (st === "ready") { this.shape(); }

    var pad = H * 0.16, mid = H / 2, i;

    if (st === "ready" && this.wave) {
      var n = this.wave.length, bw = W / n;
      var at = (this.audio && this.audio.duration)
        ? this.audio.currentTime / this.audio.duration : 0;
      for (i = 0; i < n; i++) {
        var h = Math.max(1, this.wave[i] * (H / 2 - pad) * 2);
        var past = (i / n) <= at;
        g.fillStyle = past ? gold : dim;
        g.globalAlpha = past ? 0.95 : 0.34;
        g.fillRect(i * bw, mid - h / 2, Math.max(1, bw - this.dpr), h);
      }
      g.globalAlpha = 1;
      g.fillStyle = gold;
      g.fillRect(Math.min(W - this.dpr * 2, at * W), pad * 0.5, this.dpr * 2, H - pad);
    } else {
      // Nothing to display yet. One quiet line, and while RoEx is working a
      // sweep travelling along it, so the unit reads as alive without
      // pretending to show a signal it does not have.
      g.globalAlpha = 0.28;
      g.fillStyle = dim;
      g.fillRect(0, mid - this.dpr / 2, W, this.dpr);
      if (st === "working" && !this.stillMotion()) {
        var t = (Date.now() % 2600) / 2600, x = t * W;
        var grad = g.createLinearGradient(x - W * 0.14, 0, x + W * 0.14, 0);
        grad.addColorStop(0, "rgba(0,0,0,0)");
        grad.addColorStop(0.5, gold);
        grad.addColorStop(1, "rgba(0,0,0,0)");
        g.globalAlpha = 0.55;
        g.fillStyle = grad;
        g.fillRect(x - W * 0.14, mid - this.dpr * 1.5, W * 0.28, this.dpr * 3);
        this.sweep();
      }
      g.globalAlpha = 1;
    }

    if (this.readout) {
      var a = this.audio;
      this.readout.textContent = (a && a.duration && isFinite(a.duration))
        ? clock(a.currentTime) + " / " + clock(a.duration) : "";
    }
  };

  Unit.prototype.stillMotion = function () {
    return window.matchMedia
      && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  };

  Unit.prototype.sweep = function () {
    if (this.sweeping) { return; }
    this.sweeping = true;
    var self = this;
    var again = function () {
      if (self.state() !== "working" || self.stillMotion()) {
        self.sweeping = false;
        return;
      }
      self.paint();
      requestAnimationFrame(again);
    };
    requestAnimationFrame(again);
  };

  ready(function () {
    var all = document.querySelectorAll("[data-rr-unit]");
    for (var i = 0; i < all.length; i++) { new Unit(all[i]); }
  });
}());
