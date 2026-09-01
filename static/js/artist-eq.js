/* Artist EQ — six channels, one plan.
 *
 * The scoring, lane, module and action rules are the same ones in
 * artist_eq_config.py, deliberately kept simple enough to hold in two
 * places without drifting: a weighted mean, a lane by summed keys, and
 * two ordered passes over the channel ranking. /plan recomputes all of
 * it server-side from the link this file builds, so if the two ever
 * disagreed the visitor would watch their plan change on click.
 *
 * Nothing here predicts anything. It reports what the visitor set.
 */
(function () {
  "use strict";

  var root = document.getElementById("artist-eq");
  if (!root) { return; }

  var CFG = window.SB_ARTIST_EQ || null;
  if (!CFG) {
    try { CFG = JSON.parse(document.getElementById("sbeq-config").textContent); }
    catch (e) { return; }
  }

  var KEYS = CFG.channels.map(function (c) { return c.key; });
  var state = {
    preset: CFG.default_preset,
    values: Object.assign({}, CFG.default_values),
  };

  /* --- analytics: event names and preset ids only, never a person ------- */
  function track(name, detail) {
    try {
      if (typeof window.gtag === "function") {
        window.gtag("event", name, detail || {});
      } else if (window.dataLayer && typeof window.dataLayer.push === "function") {
        window.dataLayer.push(Object.assign({event: name}, detail || {}));
      } else if (typeof window.sbTrack === "function") {
        window.sbTrack(name, detail || {});
      }
    } catch (e) { /* analytics must never break the page */ }
  }

  function presetById(id) {
    for (var i = 0; i < CFG.presets.length; i++) {
      if (CFG.presets[i].id === id) { return CFG.presets[i]; }
    }
    return null;
  }

  function clamp(v) { return Math.max(0, Math.min(10, v)); }

  /* --- the plan (mirror of artist_eq_config.py) -------------------------- */
  function readiness(values, presetId) {
    var preset = presetById(presetId) || {};
    var weights = preset.weights || {};
    var weighted = 0, total = 0;
    KEYS.forEach(function (k) {
      var w = typeof weights[k] === "number" ? weights[k] : 1;
      weighted += clamp(values[k]) * w;
      total += w;
    });
    var score = total ? (weighted / total) * 10 : 0;
    return Math.max(0, Math.min(100, Math.round(score)));
  }

  function band(score) {
    for (var i = 0; i < CFG.readiness_bands.length; i++) {
      if (score < CFG.readiness_bands[i][0]) { return CFG.readiness_bands[i][1]; }
    }
    return CFG.readiness_bands[CFG.readiness_bands.length - 1][1];
  }

  function lane(values) {
    var best = CFG.lanes[0], bestScore = -1;
    CFG.lanes.forEach(function (l) {
      var s = l.keys.reduce(function (sum, k) { return sum + clamp(values[k]); }, 0);
      if (s > bestScore) { best = l; bestScore = s; }
    });
    return best;
  }

  function rankedKeys(values) {
    return KEYS.slice().sort(function (a, b) {
      var d = clamp(values[b]) - clamp(values[a]);
      return d !== 0 ? d : KEYS.indexOf(a) - KEYS.indexOf(b);
    });
  }

  function pickTwoPass(values, table, limit, depthMax, toItem, keyOf) {
    var picked = [], seen = {};
    var ranked = rankedKeys(values);
    for (var depth = 0; depth < depthMax; depth++) {
      for (var i = 0; i < ranked.length; i++) {
        var options = table[ranked[i]] || [];
        if (depth >= options.length) { continue; }
        var item = toItem(options[depth], ranked[i]);
        var id = keyOf(item);
        if (seen[id]) { continue; }
        seen[id] = true;
        picked.push(item);
        if (picked.length >= limit) { return picked; }
      }
    }
    return picked;
  }

  function modulesFor(values) {
    return pickTwoPass(values, CFG.modules, CFG.max_modules, 3,
      function (opt, channel) {
        return {name: opt[0], slug: opt[1], channel: channel,
                note: CFG.module_notes[opt[1]] || ""};
      },
      function (m) { return m.slug; });
  }

  function actionsFor(values) {
    return pickTwoPass(values, CFG.actions, CFG.action_count, 2,
      function (opt, channel) {
        return {label: opt[0], slug: opt[1], channel: channel};
      },
      function (a) { return a.label; });
  }

  function setupTime(values) {
    var heavy = clamp(values.rights) + clamp(values.revenue);
    if (heavy >= 16) { return CFG.setup_times[2]; }
    if (heavy >= 10 || clamp(values.release) >= 8) { return CFG.setup_times[1]; }
    return CFG.setup_times[0];
  }

  /* --- system output: the analyzer strip --------------------------------
   *
   * The ENVELOPE — the gold curve and the ghost ladder under it — is the
   * six channel values and nothing else, interpolated exactly the way
   * the old trace line was. The bars are signal-life beneath the curve
   * the visitor set: decoration, never data. The strip holds still for
   * prefers-reduced-motion, stops while the section is off screen, and
   * on any browser without canvas the SVG fallback keeps the old
   * behaviour untouched.
   */
  var traceLine = document.getElementById("sbeq-trace-line");
  var traceDots = document.getElementById("sbeq-trace-dots");

  function catmull(pts, x) {
    var i = Math.max(0, Math.min(pts.length - 2, Math.floor(x)));
    var t = x - i;
    var p0 = pts[i === 0 ? 0 : i - 1], p1 = pts[i], p2 = pts[i + 1];
    var p3 = pts[i + 2 < pts.length ? i + 2 : pts.length - 1];
    var t2 = t * t, t3 = t2 * t;
    return 0.5 * ((2 * p1) + (-p0 + p2) * t +
      (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
      (-p0 + 3 * p1 - 3 * p2 + p3) * t3);
  }

  function makeAnalyzer(cv) {
    if (!cv || typeof cv.getContext !== "function") { return null; }
    var ctx = null;
    try { ctx = cv.getContext("2d"); } catch (e) { return null; }
    if (!ctx) { return null; }

    var BARS = 48;
    var env = [], caps = [];
    for (var i = 0; i < BARS; i++) { env[i] = 0; caps[i] = 0; }
    var visible = true, rafId = null, lastTs = 0;

    var reduced = { matches: false };
    try {
      if (window.matchMedia) {
        reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
        var onPref = function () { if (reduced.matches) { stop(); drawFrame(0, true); } else { kick(); } };
        if (reduced.addEventListener) { reduced.addEventListener("change", onPref); }
        else if (reduced.addListener) { reduced.addListener(onPref); }
      }
    } catch (e) { /* no matchMedia: animate; the CSS guard still stands */ }

    function fit() {
      var w = cv.clientWidth || 600, h = cv.clientHeight || 150;
      var dpr = window.devicePixelRatio || 1;
      var W = Math.max(1, Math.round(w * dpr)), H = Math.max(1, Math.round(h * dpr));
      if (cv.width !== W || cv.height !== H) { cv.width = W; cv.height = H; }
      return { w: w, h: h, dpr: dpr };
    }

    /* One organic motion model, deterministic on purpose: low bands sway
       slowly like bass, high bands flicker faster, neighbours move
       together because program material is correlated. Never above the
       envelope — the bars live under the curve the visitor set. */
    function life(i, t) {
      var f = i / BARS;
      var slow = Math.sin(t * (0.7 + f * 0.5) + i * 0.55);
      var mid = Math.sin(t * (1.9 + f * 1.6) + i * 1.7);
      var fast = Math.sin(t * (3.8 + f * 2.4) + i * 3.1);
      var v = 0.63 + 0.21 * slow + 0.11 * mid + 0.05 * fast;
      return Math.max(0.06, Math.min(1, v));
    }

    function drawFrame(t, still) {
      var m = fit(), w = m.w, h = m.h;
      ctx.setTransform(m.dpr, 0, 0, m.dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      var padX = 6, top = 8, base = h - 6;
      var span = w - padX * 2;
      var slot = span / BARS, gap = Math.max(1.5, slot * 0.22), bw = slot - gap;
      var segP = 6, segH = 4;                      /* the LED ladder pitch */

      /* faint grid so the strip reads as an instrument, not a chart */
      ctx.strokeStyle = "rgba(242,238,230,0.06)";
      ctx.lineWidth = 1;
      for (var g = 1; g <= 3; g++) {
        var gy = top + ((base - top) * g) / 4;
        ctx.beginPath(); ctx.moveTo(padX, gy); ctx.lineTo(w - padX, gy); ctx.stroke();
      }

      for (var i = 0; i < BARS; i++) {
        var x = padX + i * slot + gap / 2;
        var envPx = env[i] * (base - top);
        var level = still ? env[i] : env[i] * life(i, t);
        var levelPx = level * (base - top);

        /* ghost ladder to the envelope: the region the visitor set */
        ctx.fillStyle = "rgba(242,238,230,0.045)";
        var nGhost = Math.floor(envPx / segP);
        for (var s = 0; s < nGhost; s++) {
          ctx.fillRect(x, base - (s + 1) * segP, bw, segH);
        }
        /* lit segments to the moving level */
        var nLit = Math.floor(levelPx / segP);
        for (var s2 = 0; s2 < nLit; s2++) {
          ctx.fillStyle = s2 >= nLit - 2 ? "rgba(224,196,140,0.95)" : "rgba(201,168,106,0.66)";
          ctx.fillRect(x, base - (s2 + 1) * segP, bw, segH);
        }
        /* peak-hold cap: rises instantly, falls slowly */
        if (still) { caps[i] = env[i]; }
        else if (level > caps[i]) { caps[i] = level; }
        var capPx = caps[i] * (base - top);
        if (capPx > 2) {
          ctx.fillStyle = "rgba(224,196,140,0.9)";
          ctx.fillRect(x, base - capPx - 2, bw, 2);
        }
      }

      /* the envelope line — literally the curve the six faders set */
      ctx.strokeStyle = "#C9A24A";
      ctx.lineWidth = 1.6;
      ctx.lineJoin = "round";
      ctx.beginPath();
      for (var b = 0; b < BARS; b++) {
        var lx = padX + b * slot + slot / 2;
        var ly = base - env[b] * (base - top);
        if (b === 0) { ctx.moveTo(lx, ly); } else { ctx.lineTo(lx, ly); }
      }
      ctx.stroke();
      /* dots at the six anchors, on the same track the line runs */
      ctx.fillStyle = "#C9A24A";
      for (var k = 0; k < KEYS.length; k++) {
        var ax = padX + slot / 2 + (k / (KEYS.length - 1)) * (span - slot);
        var ay = base - Math.max(0, Math.min(1, sixNow[k])) * (base - top);
        ctx.beginPath(); ctx.arc(ax, ay, 2.6, 0, Math.PI * 2); ctx.fill();
      }
    }

    var sixNow = [0, 0, 0, 0, 0, 0];

    function frame(ts) {
      rafId = null;
      var t = ts / 1000;
      var dt = lastTs ? Math.min(0.1, t - lastTs) : 0.016;
      lastTs = t;
      for (var i = 0; i < BARS; i++) {           /* caps fall between frames */
        caps[i] = Math.max(0, caps[i] - 0.22 * dt);
      }
      drawFrame(t, false);
      if (visible && !reduced.matches) {
        rafId = window.requestAnimationFrame(frame);
      }
    }

    function kick() {
      if (rafId === null && visible && !reduced.matches) {
        rafId = window.requestAnimationFrame(frame);
      }
    }
    function stop() {
      if (rafId !== null && window.cancelAnimationFrame) {
        window.cancelAnimationFrame(rafId);
      }
      rafId = null;
    }

    if ("IntersectionObserver" in window) {
      var vObs = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          visible = e.isIntersecting;
          if (visible) { kick(); } else { stop(); }
        });
      }, { threshold: 0.05 });
      vObs.observe(cv);
    }
    if (typeof ResizeObserver === "function") {
      new ResizeObserver(function () { drawFrame(lastTs, reduced.matches); }).observe(cv);
    }

    return {
      setValues: function (values) {
        sixNow = KEYS.map(function (k) { return clamp(values[k]) / 10; });
        for (var i = 0; i < BARS; i++) {
          var v = catmull(sixNow, (i / (BARS - 1)) * (KEYS.length - 1));
          env[i] = Math.max(0, Math.min(1, v));
        }
        if (reduced.matches || !visible) { drawFrame(lastTs, true); }
        else { kick(); }
      },
    };
  }

  var analyzer = makeAnalyzer(document.getElementById("sbeq-analyzer"));
  if (analyzer) {
    var traceWrap = root.querySelector(".sbeq-trace");
    if (traceWrap && traceWrap.classList) { traceWrap.classList.add("is-live"); }
  }

  /* The SVG fallback: the old trace, redrawn the old way, for any
     browser the canvas path declined. */
  function drawTrace(values) {
    if (!traceLine) { return; }
    var W = 600, H = 90, pad = 24;
    var step = (W - pad * 2) / (KEYS.length - 1);
    var pts = KEYS.map(function (k, i) {
      return [pad + i * step, H - 10 - (clamp(values[k]) / 10) * (H - 26)];
    });
    // Catmull-Rom-ish smoothing: sample between the six real points so the
    // line reads as a curve without inventing values between channels.
    var smooth = [];
    for (var i = 0; i < pts.length - 1; i++) {
      var p0 = pts[i === 0 ? 0 : i - 1], p1 = pts[i], p2 = pts[i + 1];
      var p3 = pts[i + 2 < pts.length ? i + 2 : pts.length - 1];
      for (var t = 0; t < 1; t += 0.1) {
        var t2 = t * t, t3 = t2 * t;
        smooth.push([
          0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t +
            (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
            (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3),
          0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t +
            (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
            (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3),
        ]);
      }
    }
    smooth.push(pts[pts.length - 1]);
    traceLine.setAttribute("points", smooth.map(function (p) {
      return p[0].toFixed(1) + "," + p[1].toFixed(1);
    }).join(" "));

    if (traceDots) {
      traceDots.innerHTML = "";
      pts.forEach(function (p) {
        var c = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        c.setAttribute("cx", p[0].toFixed(1));
        c.setAttribute("cy", p[1].toFixed(1));
        c.setAttribute("r", "2.6");
        c.setAttribute("fill", "#C9A24A");
        traceDots.appendChild(c);
      });
    }
  }

  /* --- rendering --------------------------------------------------------- */
  var el = {
    score: document.getElementById("sbeq-score"),
    band: document.getElementById("sbeq-band"),
    dial: document.getElementById("sbeq-dial-arc"),
    lane: document.getElementById("sbeq-lane"),
    laneName: document.getElementById("sbeq-lane-name"),
    laneWhy: document.getElementById("sbeq-lane-why"),
    modules: document.getElementById("sbeq-modules"),
    actions: document.getElementById("sbeq-actions"),
    setup: document.getElementById("sbeq-setup"),
    cta: document.getElementById("sbeq-cta"),
  };

  function planHref(base) {
    var params = KEYS.map(function (k) {
      return k + "=" + encodeURIComponent(state.values[k]);
    });
    params.push("preset=" + encodeURIComponent(state.preset));
    return base + "?" + params.join("&");
  }

  function render() {
    var v = state.values;
    var score = readiness(v, state.preset);
    var chosenLane = lane(v);
    var mods = modulesFor(v);
    var acts = actionsFor(v);

    KEYS.forEach(function (k) {
      var out = document.getElementById("sbeq-out-" + k);
      if (out) { out.textContent = Number(v[k]).toFixed(1); }
      var channel = root.querySelector('[data-channel="' + k + '"]');
      if (channel) { channel.style.setProperty("--lit", clamp(v[k]) / 10); }
    });

    if (el.score) { el.score.textContent = String(score); }
    if (el.band) { el.band.textContent = band(score); }
    if (el.dial) {
      var circumference = 2 * Math.PI * 27;
      el.dial.setAttribute("stroke-dasharray", circumference.toFixed(1));
      el.dial.setAttribute("stroke-dashoffset",
        (circumference * (1 - score / 100)).toFixed(1));
    }
    if (el.laneName) { el.laneName.textContent = chosenLane.name; }
    if (el.laneWhy) { el.laneWhy.textContent = chosenLane.why; }
    if (el.lane) { el.lane.setAttribute("href", chosenLane.href); }

    /* Rows, not links: the panel used to place eight outbound exits in
       the page's second screen, all variants of the same /plan
       destination. The one CTA below carries the click. */
    if (el.modules) {
      el.modules.innerHTML = "";
      mods.forEach(function (m) {
        var li = document.createElement("li");
        var row = document.createElement("span");
        row.className = "sbeq-module";
        row.innerHTML = '<span class="sbeq-module-name"></span><span class="sbeq-module-note"></span>';
        row.querySelector(".sbeq-module-name").textContent = m.name;
        row.querySelector(".sbeq-module-note").textContent = m.note;
        li.appendChild(row);
        el.modules.appendChild(li);
      });
    }

    if (el.actions) {
      el.actions.innerHTML = "";
      acts.forEach(function (a) {
        var li = document.createElement("li");
        var row = document.createElement("span");
        row.className = "sbeq-action";
        row.textContent = a.label;
        li.appendChild(row);
        el.actions.appendChild(li);
      });
    }

    if (el.setup) { el.setup.textContent = setupTime(v); }
    if (el.cta) { el.cta.setAttribute("href", planHref("/plan")); }

    if (analyzer) { analyzer.setValues(v); } else { drawTrace(v); }
    save();
    if (interacted) { saveProfile(chosenLane, mods, acts); }
  }

  /* --- state ------------------------------------------------------------- */
  function save() {
    try {
      localStorage.setItem(CFG.storage_key, JSON.stringify({
        preset: state.preset, values: state.values,
      }));
    } catch (e) { /* private mode: the page still works, it just forgets */ }
  }

  /* The account-facing copy of the same mix.
   *
   * The Command Center card, the Artist Twin context line and the
   * onboarding program panel all read one shape, written below. It is
   * recorded only once the visitor has actually moved something — an
   * untouched section is not a choice, and writing the defaults would
   * overwrite a mix they set on another day. The push is debounced so
   * dragging a fader is one request, and a signed-out visitor's 401 is
   * the correct answer to it, so it is ignored. */
  var interacted = false, syncTimer = null, lastSent = "", createdAt = "";

  function buildProfile(chosenLane, mods, acts) {
    var priorities = {}, labels = {};
    KEYS.forEach(function (k) { priorities[k] = Math.round(clamp(state.values[k])); });
    CFG.channels.forEach(function (c) { labels[c.key] = c.label; });
    var top = KEYS.slice().sort(function (a, b) {
      return state.values[b] - state.values[a] || KEYS.indexOf(a) - KEYS.indexOf(b);
    }).slice(0, 3);
    var now = new Date().toISOString();
    if (!createdAt) { createdAt = now; }
    return {
      version: 1,
      createdAt: createdAt,
      updatedAt: now,
      preset: (presetById(state.preset) || {}).name || "Custom",
      priorities: priorities,
      topPriorities: top.map(function (k) { return labels[k]; }),
      recommendedLane: chosenLane.name,
      recommendedModules: mods.map(function (m) { return m.name; }),
      firstActions: acts.map(function (a) { return a.label; }),
      source: "homepage_artist_eq"
    };
  }

  function saveProfile(chosenLane, mods, acts) {
    var profile = buildProfile(chosenLane, mods, acts);
    try {
      localStorage.setItem("streetBankerArtistSignalProfile",
                           JSON.stringify(profile));
    } catch (e) { /* private mode */ }
    var fingerprint = JSON.stringify([profile.priorities, profile.preset,
                                      profile.recommendedLane]);
    if (fingerprint === lastSent || typeof window.fetch !== "function") { return; }
    lastSent = fingerprint;
    if (syncTimer) { window.clearTimeout(syncTimer); }
    syncTimer = window.setTimeout(function () {
      window.fetch("/api/artist-signal-profile", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        credentials: "same-origin",
        body: JSON.stringify(profile)
      }).catch(function () { /* signed out, offline: the local copy stands */ });
    }, 1200);
  }

  function restore() {
    try {
      var raw = JSON.parse(localStorage.getItem(CFG.storage_key) || "null");
      if (!raw || typeof raw !== "object") { return; }
      if (raw.values) {
        KEYS.forEach(function (k) {
          var n = Number(raw.values[k]);
          if (isFinite(n)) { state.values[k] = clamp(Math.round(n * 2) / 2); }
        });
      }
      if (typeof raw.preset === "string" && presetById(raw.preset)) {
        state.preset = raw.preset;
      }
    } catch (e) { /* ignore anything that is not ours */ }
  }

  function syncInputs() {
    KEYS.forEach(function (k) {
      var input = document.getElementById("sbeq-" + k);
      if (input) { input.value = state.values[k]; }
    });
  }

  function markPreset(id) {
    state.preset = id;
    root.querySelectorAll(".sbeq-preset").forEach(function (b) {
      b.setAttribute("aria-pressed", b.dataset.preset === id ? "true" : "false");
    });
  }

  function applyPreset(id, quiet) {
    var preset = presetById(id);
    if (!preset) { return; }
    if (preset.values) {
      KEYS.forEach(function (k) { state.values[k] = preset.values[k]; });
      syncInputs();
    }
    markPreset(id);
    render();
    if (!quiet) { track("artist_eq_preset_selected", {preset: id}); }
  }

  /* --- wiring ------------------------------------------------------------ */
  root.querySelectorAll(".sbeq-range").forEach(function (input) {
    input.addEventListener("input", function () {
      interacted = true;
      state.values[input.dataset.key] = clamp(Number(input.value));
      // Any manual move is a Custom mix - a preset button that stays lit
      // while the faders no longer match it is a lie about the state.
      if (state.preset !== "custom") { markPreset("custom"); }
      render();
    });
    input.addEventListener("change", function () {
      track("artist_eq_channel_adjusted",
            {channel: input.dataset.key, preset: state.preset});
    });
  });

  root.querySelectorAll(".sbeq-preset").forEach(function (btn) {
    btn.addEventListener("click", function () {
      interacted = true;
      applyPreset(btn.dataset.preset);
    });
  });

  var reset = document.getElementById("sbeq-reset");
  if (reset) {
    reset.addEventListener("click", function () {
      interacted = true;
      applyPreset(CFG.default_preset, true);
      track("artist_eq_reset_clicked", {});
    });
  }

  if (el.cta) {
    el.cta.addEventListener("click", function () {
      track("artist_eq_plan_cta_clicked", {preset: state.preset});
    });
  }

  /* Section viewed, once. */
  if ("IntersectionObserver" in window) {
    var seen = false;
    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting && !seen) {
          seen = true;
          track("artist_eq_section_viewed", {});
          obs.disconnect();
        }
      });
    }, {threshold: 0.35});
    obs.observe(root);
  }

  restore();
  syncInputs();
  markPreset(state.preset);
  render();
})();
