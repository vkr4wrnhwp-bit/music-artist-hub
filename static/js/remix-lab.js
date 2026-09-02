/* Remix Lab — the brief builder.
 *
 * What this file does: gates the upload behind the two rights
 * confirmations, screens reference text for imitation requests, mirrors
 * the real form state onto the lit indicators (steps, status chips, the
 * rights safe zone), wires the segmented switches to the <select>s they
 * enhance, draws the amplitude of a chosen file on the hero canvas in
 * the browser, builds the remixLabSubmission object the backend will
 * receive, and reveals the worked example.
 *
 * What it deliberately does not do: transmit anything on its own. No
 * fetch, no beacon with content, no storage of the file. With the engine
 * off the chosen audio never leaves the browser, and the page says so.
 * With the engine on, the browser posts the form itself and the
 * banned-pattern screen runs again server-side
 * (remix_lab_config.check_reference_text); this copy is convenience,
 * not enforcement.
 *
 * Nothing drawn here is a measurement. The waveform is the file's own
 * amplitude, decoded locally and labelled as such; tempo, sections and
 * energy are measured only after upload, on the brief page.
 */
(function () {
  "use strict";

  var root = document.getElementById("sbrl-form");
  var cfgEl = document.getElementById("sbrl-config");
  if (!root || !cfgEl) { return; }

  var CFG;
  try { CFG = JSON.parse(cfgEl.textContent); } catch (e) { return; }

  var PATTERNS = (CFG.patterns || []).map(function (p) {
    try { return new RegExp(p, "i"); } catch (e) { return null; }
  }).filter(Boolean);

  function track(name, payload) {
    try {
      if (typeof window.gtag === "function") {
        window.gtag("event", name, payload || {});
      } else if (window.dataLayer && typeof window.dataLayer.push === "function") {
        window.dataLayer.push(Object.assign({event: name}, payload || {}));
      } else if (typeof window.sbTrack === "function") {
        window.sbTrack(name, payload || {});
      }
    } catch (e) { /* analytics must never break the page */ }
  }

  function all(selector, scope) {
    return [].slice.call((scope || document).querySelectorAll(selector));
  }

  /* --- the rights gate --------------------------------------------------- */
  var ownBox = document.getElementById("sbrl-rights-own");
  var likenessBox = document.getElementById("sbrl-rights-likeness");
  var drop = document.getElementById("sbrl-drop");
  var fileInput = document.getElementById("sbrl-file");
  var uploadBtn = document.getElementById("sbrl-upload-btn");
  var fileName = document.getElementById("sbrl-file-name");
  var chosenFile = null;

  function gateOpen() {
    return !!(ownBox && ownBox.checked && likenessBox && likenessBox.checked);
  }

  var gateNoted = false;
  function applyGate() {
    var open = gateOpen();
    if (fileInput) { fileInput.disabled = !open; }
    if (drop) { drop.classList.toggle("is-locked", !open); }
    if (uploadBtn) { uploadBtn.setAttribute("aria-disabled", open ? "false" : "true"); }
    if (open && !gateNoted) {
      gateNoted = true;
      track("remix_lab_rights_confirmed", {});
    }
    /* Unchecking after choosing a file revokes the choice: the file was
       only acceptable while the confirmations stood. */
    if (!open && fileInput && (fileInput.value || chosenFile)) {
      fileInput.value = "";
      chosenFile = null;
      if (fileName) { fileName.textContent = ""; }
      clearWave();
    }
    syncState();
  }
  if (ownBox) { ownBox.addEventListener("change", applyGate); }
  if (likenessBox) { likenessBox.addEventListener("change", applyGate); }

  /* --- the file ---------------------------------------------------------- */
  function extOf(name) {
    var i = (name || "").lastIndexOf(".");
    return i < 0 ? "" : name.slice(i).toLowerCase();
  }

  function acceptFile(file) {
    if (!file) { return; }
    var formats = CFG.formats || [];
    if (formats.indexOf(extOf(file.name)) === -1) {
      if (fileName) {
        fileName.textContent = "That file type is not supported — use " +
          formats.join(", ") + ".";
      }
      chosenFile = null;
      clearWave();
      syncState();
      return;
    }
    if (file.size > (CFG.max_mb || 250) * 1024 * 1024) {
      if (fileName) {
        fileName.textContent = "That file is over " + (CFG.max_mb || 250) +
          " MB — export a smaller master for the brief.";
      }
      chosenFile = null;
      clearWave();
      syncState();
      return;
    }
    chosenFile = file;
    if (fileName) {
      fileName.textContent = file.name + (CFG.engineLive
        ? " — ready."
        : " — ready. Nothing is uploaded in this preview.");
    }
    track("remix_lab_track_selected", {ext: extOf(file.name)});
    syncState();
    drawWave(file);
  }

  if (fileInput) {
    fileInput.addEventListener("change", function () {
      acceptFile(fileInput.files && fileInput.files[0]);
    });
  }

  if (drop) {
    ["dragenter", "dragover"].forEach(function (type) {
      drop.addEventListener(type, function (event) {
        event.preventDefault();
        if (gateOpen()) { drop.classList.add("is-drag"); }
      });
    });
    ["dragleave", "drop"].forEach(function (type) {
      drop.addEventListener(type, function (event) {
        event.preventDefault();
        drop.classList.remove("is-drag");
      });
    });
    drop.addEventListener("drop", function (event) {
      if (!gateOpen()) { return; }
      var file = event.dataTransfer && event.dataTransfer.files &&
                 event.dataTransfer.files[0];
      acceptFile(file);
    });
  }

  /* --- the hero waveform: amplitude, drawn locally, not a measurement ---- */
  var canvas = document.getElementById("sbrl-hero-canvas");
  var streak = document.getElementById("sbrl-hero-streak");
  var waveNote = document.getElementById("sbrl-wave-note");
  var WAVE_CAPS = {".wav": 40, ".aiff": 40, ".mp3": 12, ".flac": 12};

  function clearWave() {
    if (canvas) {
      var c2 = canvas.getContext && canvas.getContext("2d");
      if (c2) { c2.clearRect(0, 0, canvas.width, canvas.height); }
      canvas.hidden = true;
      canvas.setAttribute("aria-label", "");
    }
    if (streak) { streak.hidden = false; }
    if (waveNote) { waveNote.textContent = ""; }
  }

  function skipWave(reason) {
    if (streak) { streak.hidden = false; }
    if (canvas) { canvas.hidden = true; }
    if (waveNote) {
      waveNote.textContent = "Waveform preview skipped — " + reason +
        ". The brief does not depend on it.";
    }
  }

  function paintWave(buffer, name) {
    var dpr = window.devicePixelRatio || 1;
    var rect = canvas.getBoundingClientRect();
    var width = Math.max(1, Math.round((rect.width || 800) * dpr));
    var height = Math.max(1, Math.round((rect.height || 180) * dpr));
    canvas.width = width;
    canvas.height = height;
    var ctx = canvas.getContext("2d");
    if (!ctx) { throw new Error("no 2d context"); }
    var data = buffer.getChannelData(0);
    var per = Math.max(1, Math.floor(data.length / width));
    var mid = height / 2;
    var colour = getComputedStyle(canvas).color;
    var columns = [];
    for (var x = 0; x < width; x++) {
      var lo = 0, hi = 0;
      var start = x * per, end = Math.min(data.length, start + per);
      for (var i = start; i < end; i++) {
        var v = data[i];
        if (v < lo) { lo = v; }
        if (v > hi) { hi = v; }
      }
      columns.push([lo, hi]);
    }
    ctx.clearRect(0, 0, width, height);
    ctx.strokeStyle = colour;
    ctx.lineCap = "round";
    /* A light, not a meter: the envelope sits at about half the band and
       stays translucent so the headline in front of it still reads. */
    [[6 * dpr, 0.08], [1 * dpr, 0.45]].forEach(function (pass) {
      ctx.lineWidth = pass[0];
      ctx.globalAlpha = pass[1];
      ctx.beginPath();
      for (var x = 0; x < width; x++) {
        var top = mid - columns[x][1] * mid * 0.55;
        var bottom = mid - columns[x][0] * mid * 0.55;
        if (bottom - top < 1) { bottom = top + 1; }
        ctx.moveTo(x + 0.5, top);
        ctx.lineTo(x + 0.5, bottom);
      }
      ctx.stroke();
    });
    ctx.globalAlpha = 1;
    var note = CFG.engineLive
      ? "Amplitude of " + name + ", drawn in your browser. Tempo, sections and energy are measured after upload."
      : "Amplitude of " + name + ", drawn in your browser from the file you chose. Nothing is uploaded in this preview.";
    canvas.setAttribute("aria-label", note);
    if (waveNote) { waveNote.textContent = note; }
    if (streak) { streak.hidden = true; }
    canvas.hidden = false;
  }

  function drawWave(file) {
    if (!canvas || !file) { return; }
    var Offline = window.OfflineAudioContext || window.webkitOfflineAudioContext;
    if (!Offline || typeof file.arrayBuffer !== "function") {
      skipWave("this browser cannot decode audio locally");
      return;
    }
    var cap = WAVE_CAPS[extOf(file.name)] || 12;
    if (file.size > cap * 1024 * 1024) {
      skipWave("the file is over " + cap + " MB");
      return;
    }
    var mine = file;
    var ctx = null;
    file.arrayBuffer().then(function (buf) {
      if (chosenFile !== mine) { return null; }
      /* 8 kHz mono: enough to draw an envelope, small enough to hold. */
      ctx = new Offline(1, 8000, 8000);
      return ctx.decodeAudioData(buf);
    }).then(function (buffer) {
      if (!buffer || chosenFile !== mine) { return; }
      paintWave(buffer, mine.name);
    }).catch(function () {
      if (chosenFile === mine) { skipWave("the file could not be decoded"); }
    }).then(function () {
      try { if (ctx && ctx.close) { ctx.close(); } } catch (e) { /* offline contexts may not close */ }
    });
  }

  /* --- references, screened as you type ----------------------------------- */
  var refsWrap = document.getElementById("sbrl-refs");
  var addRef = document.getElementById("sbrl-add-ref");
  var warning = document.getElementById("sbrl-warning");

  function refInputs() {
    return all(".sbrl-ref", root);
  }

  function violation(text) {
    for (var i = 0; i < PATTERNS.length; i++) {
      var match = PATTERNS[i].exec(text || "");
      if (match) { return match[0]; }
    }
    return null;
  }

  var warned = false;
  function screenRefs() {
    var flagged = false;
    refInputs().forEach(function (input) {
      var hit = violation(input.value);
      input.classList.toggle("is-flagged", !!hit);
      if (hit) { flagged = true; }
    });
    if (warning) { warning.hidden = !flagged; }
    if (flagged && !warned) {
      warned = true;
      /* The event carries no text - only that the screen fired. */
      track("remix_lab_blocked_prompt", {});
    }
    syncState();
    return flagged;
  }

  root.addEventListener("input", function (event) {
    if (event.target && event.target.classList &&
        event.target.classList.contains("sbrl-ref")) {
      screenRefs();
    }
  });

  if (addRef && refsWrap) {
    addRef.addEventListener("click", function () {
      var count = refInputs().length;
      if (count >= (CFG.reference_max || 5)) { return; }
      var input = document.createElement("input");
      input.type = "text";
      input.maxLength = 300;
      input.className = "sbrl-input sbrl-ref";
      /* Named, so the server screen sees lines three to five as well. */
      input.name = "reference";
      input.placeholder = "Another direction (optional)";
      input.setAttribute("aria-label", "Reference direction " + (count + 1));
      refsWrap.appendChild(input);
      if (refInputs().length >= (CFG.reference_max || 5)) {
        addRef.hidden = true;
      }
      input.focus();
    });
  }

  /* --- the segmented switches ------------------------------------------- */
  /* The class that swaps the selects for the switches is added here, by the
     script that wires them, so a page whose script never ran keeps its
     working selects instead of clipped controls beside inert buttons. */
  document.documentElement.classList.add("sbrl-js");
  var isJs = true;

  all(".sbrl-seg", root).forEach(function (seg) {
    var key = seg.getAttribute("data-seg");
    var select = root.querySelector('select[name="' + key + '"]');
    if (!select) { return; }
    var buttons = all(".sbrl-seg-btn", seg);
    if (isJs) {
      select.tabIndex = -1;
      select.setAttribute("aria-hidden", "true");
      var label = select.closest && select.closest(".sbrl-vibe");
      if (label) {
        label.addEventListener("click", function (event) { event.preventDefault(); });
      }
    }

    function paint() {
      buttons.forEach(function (btn) {
        var on = btn.getAttribute("data-value") === select.value;
        btn.setAttribute("aria-checked", on ? "true" : "false");
        btn.tabIndex = on ? 0 : -1;
      });
    }

    function choose(btn, focus) {
      select.value = btn.getAttribute("data-value");
      select.dispatchEvent(new Event("change", {bubbles: true}));
      paint();
      if (focus) { btn.focus(); }
    }

    buttons.forEach(function (btn, index) {
      btn.addEventListener("click", function () { choose(btn, false); });
      btn.addEventListener("keydown", function (event) {
        var next = null;
        if (event.key === "ArrowRight" || event.key === "ArrowDown") {
          next = buttons[(index + 1) % buttons.length];
        } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
          next = buttons[(index - 1 + buttons.length) % buttons.length];
        } else if (event.key === "Home") {
          next = buttons[0];
        } else if (event.key === "End") {
          next = buttons[buttons.length - 1];
        } else if (event.key === " " || event.key === "Enter") {
          next = btn;
        }
        if (next) {
          event.preventDefault();
          choose(next, true);
        }
      });
    });

    select.addEventListener("change", paint);
    paint();
  });

  /* --- the lit indicators: state read from the form, nothing else --------- */
  var gate = document.getElementById("sbrl-rights-gate");
  var submitBar = document.getElementById("sbrl-submit-bar");
  var fileCard = document.getElementById("sbrl-file-card");
  var fileTitle = document.getElementById("sbrl-file-title");
  var fileMeta = document.getElementById("sbrl-file-meta");

  function checkedValue(name) {
    var el = root.querySelector('input[name="' + name + '"]:checked');
    return el ? el.value : "";
  }

  function setSr(el, text) {
    var sr = el && el.querySelector(".sbrl-sr");
    if (sr) { sr.textContent = text; }
  }

  function syncState() {
    var rights = gateOpen();
    var trackChosen = !!chosenFile;
    var lane = !!checkedValue("remixLane");
    var use = !!checkedValue("targetUse");
    var refs = refInputs();
    var refsTyped = refs.some(function (el) { return el.value.trim() !== ""; });
    var refsFlagged = refs.some(function (el) { return el.classList.contains("is-flagged"); });
    var armed = rights && trackChosen && lane && use;

    var chips = {rights: rights, track: trackChosen, lane: lane, use: use};
    all(".sbrl-chip-state[data-chip]").forEach(function (chip) {
      var on = !!chips[chip.getAttribute("data-chip")];
      chip.setAttribute("data-on", on ? "true" : "false");
      setSr(chip, on ? ": done" : ": not yet");
    });

    var steps = {rights: rights, track: trackChosen, lane: lane && use, vibe: armed};
    all(".sbrl-step[data-step]").forEach(function (step) {
      var on = !!steps[step.getAttribute("data-step")];
      step.classList.toggle("is-lit", on);
      setSr(step, on ? "done" : "not yet");
    });

    var safe = {
      own: !!(ownBox && ownBox.checked) ? "true" : "false",
      likeness: !!(likenessBox && likenessBox.checked) ? "true" : "false",
      refs: refsFlagged ? "warn" : (refsTyped ? "true" : "false")
    };
    all(".sbrl-safe-row[data-safe]").forEach(function (row) {
      var state = safe[row.getAttribute("data-safe")] || "false";
      row.setAttribute("data-on", state);
      setSr(row, state === "true" ? "on" : (state === "warn" ? "needs attention" : "off"));
    });

    if (gate) { gate.classList.toggle("is-open", rights); }
    if (submitBar) { submitBar.classList.toggle("is-armed", armed); }

    if (fileCard) {
      if (chosenFile) {
        if (fileTitle) { fileTitle.textContent = chosenFile.name; }
        if (fileMeta) {
          fileMeta.textContent = (chosenFile.size / 1048576).toFixed(1) + " MB · " +
            extOf(chosenFile.name).replace(".", "").toUpperCase();
        }
        fileCard.hidden = false;
      } else {
        fileCard.hidden = true;
      }
    }
  }

  root.addEventListener("change", syncState);
  applyGate();

  /* --- submit ------------------------------------------------------------- */
  var results = document.getElementById("sbrl-results");
  var note = document.getElementById("sbrl-submit-note");
  var submitBtn = document.getElementById("sbrl-submit");

  function say(message) {
    if (note) { note.textContent = message; }
  }

  root.addEventListener("submit", function (event) {
    /* Every check below blocks the submit either way, so each one cancels
       the event itself. preventDefault() used to sit at the top and cancel
       it unconditionally - which was fine while this page was a preview and
       became a real bug the moment the form got an action: the server never
       saw a submission from any browser with JavaScript on. */
    function stop(message) { event.preventDefault(); say(message); }

    if (!gateOpen()) {
      stop("Confirm both rights statements first — the upload stays off until you do.");
      return;
    }
    if (screenRefs()) {
      stop("Rewrite the flagged reference using musical descriptors, then try again.");
      return;
    }
    if (!chosenFile) {
      stop("Choose an audio file — WAV, MP3, AIFF or FLAC.");
      return;
    }
    var lane = checkedValue("remixLane");
    if (!lane) { stop("Pick a remix lane."); return; }
    var use = checkedValue("targetUse");
    if (!use) { stop("Pick a target use."); return; }

    /* Engine live: hand the form to the browser. The server screens every
       reference again and re-checks both rights confirmations - this screen
       is convenience, that one is enforcement. */
    if (CFG.engineLive) {
      say("Reading your track — this takes a moment.");
      if (submitBtn) { submitBtn.classList.add("is-busy"); }
      track("remix_lab_brief_submitted", {lane: lane, use: use});
      return;
    }
    event.preventDefault();

    /* The contract the backend will receive when generation is wired.
       Built and held in memory; nothing here transmits it. */
    var submission = {
      audioFile: {name: chosenFile.name, size: chosenFile.size,
                  type: chosenFile.type},
      optionalStems: all('input[name="stems"]:checked', root)
        .map(function (el) { return el.value; }),
      rightsConfirmed: true,
      noLikenessConfirmed: true,
      referenceDirections: refInputs().map(function (el) {
        return el.value.trim();
      }).filter(Boolean),
      remixLane: lane,
      targetUse: use,
      vibeControls: {
        energy: (root.querySelector('select[name="energy"]') || {}).value,
        tempoDirection: (root.querySelector('select[name="tempoDirection"]') || {}).value,
        vocalTreatment: (root.querySelector('select[name="vocalTreatment"]') || {}).value,
        instrumentation: (root.querySelector('select[name="instrumentation"]') || {}).value,
        riskLevel: (root.querySelector('select[name="riskLevel"]') || {}).value
      }
    };
    window.sbrlSubmission = submission;   /* inspectable, not transmitted */

    /* Preview path only - the live path returned above. */
    say("Example brief shown below — generation is not connected yet.");
    track("remix_lab_brief_started", {lane: lane, use: use});

    if (results) {
      results.hidden = false;
      results.scrollIntoView({
        block: "start",
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "auto" : "smooth"
      });
    }
  });

  /* --- the output cards open the worked example ---------------------------- */
  all(".sbrl-out").forEach(function (card) {
    card.addEventListener("click", function () {
      if (results) { results.hidden = false; }
      track("remix_lab_output_previewed", {target: card.getAttribute("href")});
    });
  });

  /* --- the producer handoff ----------------------------------------------- */
  var producer = document.querySelector(".sbrl-producer a");
  if (producer) {
    producer.addEventListener("click", function () {
      track("remix_lab_producer_review_clicked", {});
    });
  }

  /* --- section viewed, once ------------------------------------------------ */
  if ("IntersectionObserver" in window) {
    var seen = false;
    var target = document.querySelector(".sbrl-head");
    if (target) {
      var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting && !seen) {
            seen = true;
            track("remix_lab_viewed", {});
            observer.disconnect();
          }
        });
      }, {threshold: 0.3});
      observer.observe(target);
    }
  }
})();
