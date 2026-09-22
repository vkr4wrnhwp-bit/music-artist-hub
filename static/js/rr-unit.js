/* The Release-Ready unit: one photographed rack unit, lit by code.

   One unit for the whole upload, not one per preview. Every part that
   lights or moves is driven by something real:

     the load slot     lights when a file is over it, and hands that file to
                       the page's own upload form. It does NOT upload by
                       itself: uploading needs the rights and licence boxes
                       ticked, and a slot that quietly skipped them would be
                       the one dishonest thing on this faceplate.
     the display       the selected take's own waveform, decoded from the
                       file, with a playhead and the elapsed time
     three take buttons  the previews RoEx has made. Dark when a take does
                       not exist, a low ember when it does, lit when it is
                       the one playing.
     the transport     play/pause
     the meter lenses  the live signal through a WebAudio analyser, so the
                       meters are showing this track and not an animation
     the jewel         the job's state
     the knob          output level, a real range input underneath

   The <audio> element keeps its id and its ARIA label and is what actually
   plays, so the page works with this script absent, and in a column too
   narrow for the faceplate the plain controls are what is shown.

   Nothing here invents a figure. With nothing to play the window draws no
   waveform at all rather than one that is not of anything. */
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
    this.slot = root.querySelector(".rr-unit-slot");
    this.takes = [].slice.call(root.querySelectorAll(".rr-unit-take"));
    this.go = root.querySelector(".rr-unit-go");
    this.strips = [root.querySelector(".rr-unit-meter--l"),
                   root.querySelector(".rr-unit-meter--r")];
    this.knob = root.querySelector(".rr-unit-knob input");
    this.readout = root.parentNode.querySelector("[data-rr-unit-time]");
    this.says = root.parentNode.querySelector("[data-rr-unit-says]");
    this.peak = [0, 0];
    this.waves = {};
    this.ctx = this.canvas ? this.canvas.getContext("2d") : null;
    this.dpr = Math.min(window.devicePixelRatio || 1, 2);
    if (this.canvas) { this.fit(); }
    this.bind();
    var first = this.takes.filter(function (b) {
      return b.getAttribute("data-has") === "1";
    })[0];
    if (first) { this.pick(first, true); } else { this.paint(); }
  }

  Unit.prototype.state = function () {
    return this.root.getAttribute("data-state") || "idle";
  };

  Unit.prototype.fit = function () {
    var box = this.canvas.getBoundingClientRect();
    if (!box.width) { return; }
    this.canvas.width = Math.round(box.width * this.dpr);
    this.canvas.height = Math.round(box.height * this.dpr);
  };

  Unit.prototype.tell = function (words) {
    if (this.says) { this.says.textContent = words || ""; }
  };

  /* ---- the load slot --------------------------------------------------- */

  Unit.prototype.formInput = function () {
    // The page's own upload form. Its file input is the only way in: the
    // consent boxes beside it are not ours to skip.
    var url = this.root.getAttribute("data-rr-upload");
    var form = url ? document.querySelector('form[action="' + url + '"]') : null;
    if (!form) { form = document.querySelector('form[action*="/upload"]'); }
    return form ? { form: form, input: form.querySelector('input[type="file"]') } : null;
  };

  Unit.prototype.hand = function (file) {
    var got = this.formInput();
    if (!got || !got.input) { return false; }
    try {
      var box = new DataTransfer();
      box.items.add(file);
      got.input.files = box.files;
      got.input.dispatchEvent(new Event("change", { bubbles: true }));
    } catch (err) {
      return false;                   // an older browser: the picker still works
    }
    this.tell(file.name + " is on the form below. Tick the boxes to send it.");
    got.form.scrollIntoView({ behavior: "smooth", block: "center" });
    var first = got.form.querySelector('input[type="checkbox"]');
    if (first) { first.focus({ preventScroll: true }); }
    return true;
  };

  /* ---- wiring ---------------------------------------------------------- */

  Unit.prototype.bind = function () {
    var self = this;

    if (this.slot && this.root.getAttribute("data-can-load") === "1") {
      this.slot.addEventListener("click", function () {
        var got = self.formInput();
        if (got && got.input) { got.input.click(); }
      });
      ["dragenter", "dragover"].forEach(function (n) {
        self.slot.addEventListener(n, function (e) {
          e.preventDefault();
          self.root.setAttribute("data-over", "1");
        });
      });
      ["dragleave", "drop"].forEach(function (n) {
        self.slot.addEventListener(n, function () {
          self.root.setAttribute("data-over", "0");
        });
      });
      this.slot.addEventListener("drop", function (e) {
        e.preventDefault();
        var f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
        if (f && !self.hand(f)) {
          self.tell("Use the upload form below for this one.");
        }
      });
    }

    this.takes.forEach(function (b) {
      b.addEventListener("click", function () {
        if (b.getAttribute("data-has") !== "1") { return; }
        self.pick(b, false);
      });
    });

    if (this.go) {
      this.go.addEventListener("click", function () { self.toggle(); });
    }

    if (this.screen) {
      this.screen.addEventListener("click", function (e) {
        if (!self.audio || !self.audio.duration) { self.toggle(); return; }
        var box = self.screen.getBoundingClientRect();
        self.audio.currentTime = Math.max(0, Math.min(
          self.audio.duration,
          ((e.clientX - box.left) / box.width) * self.audio.duration));
        if (self.audio.paused) { self.play(); }
      });
    }

    if (this.audio) {
      ["play", "pause", "ended", "seeked", "timeupdate", "loadedmetadata"]
        .forEach(function (n) {
          self.audio.addEventListener(n, function () { self.paint(); self.lamp(); });
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
        var next = startV + ((startY - e.clientY) / 140) * 100;   // up is louder
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

  Unit.prototype.lamp = function () {
    if (this.go) {
      this.go.setAttribute("data-playing",
        (this.audio && !this.audio.paused) ? "1" : "0");
    }
  };

  Unit.prototype.pick = function (button, quiet) {
    var src = button.getAttribute("data-src");
    if (!src || !this.audio) { return; }
    this.takes.forEach(function (b) {
      b.setAttribute("aria-pressed", b === button ? "true" : "false");
    });
    if (this.audio.getAttribute("src") !== src) {
      var wasPlaying = !this.audio.paused;
      this.audio.setAttribute("src", src);
      this.audio.load();
      if (wasPlaying && !quiet) { this.play(); }
    }
    this.tell(button.getAttribute("aria-label") || "");
    this.paint();
  };

  Unit.prototype.toggle = function () {
    if (!this.audio || !this.audio.getAttribute("src")) { return; }
    if (this.audio.paused) { this.play(); } else { this.audio.pause(); }
  };

  Unit.prototype.level = function () {
    var v = Number(this.knob.value) / 100;
    if (this.audio) { this.audio.volume = Math.max(0, Math.min(1, v)); }
    // A pointerless knob reads its position through the knurling and the
    // brushed spin, so the sweep has to be wide enough to see.
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
      // A file the page may not read sample by sample. It still plays; the
      // meters stay dark rather than showing a number that is not measured.
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
      // dBFS across thirteen lenses: the first at -48 dB, the last at 0.
      var db = rms > 0 ? 20 * Math.log10(rms) : -100;
      var lit = Math.max(0, Math.min(13, Math.round((db + 48) / 48 * 13)));
      this.peak[ch] = fade ? 0 : Math.max(lit, this.peak[ch] - 0.4);
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
    var self = this;
    var src = this.audio && this.audio.currentSrc;
    if (!src || this.waves[src] || this.shaping === src) { return; }
    var AC = window.AudioContext || window.webkitAudioContext;
    if (!AC || !window.fetch) { return; }
    this.shaping = src;
    fetch(src).then(function (r) {
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
      var n = 260, step = Math.floor(data.length / n) || 1, out = [];
      for (var i = 0; i < n; i++) {
        var top = 0;
        for (var j = 0; j < step; j += 8) {
          var v = Math.abs(data[i * step + j] || 0);
          if (v > top) { top = v; }
        }
        out.push(top);
      }
      self.waves[src] = out;
      self.shaping = null;
      self.paint();
    }).catch(function () { self.shaping = null; });
  };

  Unit.prototype.stillMotion = function () {
    return window.matchMedia
      && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  };

  Unit.prototype.paint = function () {
    if (!this.ctx) { return; }
    var g = this.ctx, W = this.canvas.width, H = this.canvas.height;
    if (!W || !H) { return; }
    var css = getComputedStyle(this.screen || this.root);
    var gold = css.getPropertyValue("--wave").trim() || "rgba(255,255,255,.85)";
    var dim = css.getPropertyValue("--wave-rest").trim() || "rgba(255,255,255,.45)";
    g.clearRect(0, 0, W, H);

    var src = this.audio && this.audio.currentSrc;
    if (src) { this.shape(); }
    var wave = src ? this.waves[src] : null;
    var pad = H * 0.16, mid = H / 2, i;

    if (wave) {
      var n = wave.length, bw = W / n;
      var at = (this.audio && this.audio.duration)
        ? this.audio.currentTime / this.audio.duration : 0;
      for (i = 0; i < n; i++) {
        var h = Math.max(1, wave[i] * (H / 2 - pad) * 2);
        var past = (i / n) <= at;
        g.fillStyle = past ? gold : dim;
        g.globalAlpha = past ? 1 : 0.55;
        g.fillRect(i * bw, mid - h / 2, Math.max(1, bw - this.dpr), h);
      }
      g.globalAlpha = 1;
      g.fillStyle = gold;
      g.fillRect(Math.min(W - this.dpr * 2, at * W), pad * 0.5, this.dpr * 2, H - pad);
    } else {
      // Nothing to display. One quiet line, and while RoEx is working a
      // sweep travelling along it, so the unit reads as alive without
      // pretending to show a signal it does not have.
      g.globalAlpha = 0.28;
      g.fillStyle = dim;
      g.fillRect(0, mid - this.dpr / 2, W, this.dpr);
      if (this.state() === "working" && !this.stillMotion()) {
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
