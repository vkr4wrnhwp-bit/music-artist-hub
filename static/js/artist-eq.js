/* The Artist EQ — the Artist Signal Profile control surface.

   Reads its data from the JSON block the template renders, drives fifteen
   native range inputs, draws the response curve, works out which lane the
   visitor's own settings point at, and - after the mix settles - commits
   the whole page to one of five Adaptive Visual Modes: tint variables,
   hero and banner image crossfades, the signal line, and the one main
   program CTA, all in a single coordinated switch. The layout never moves.

   Everything shown is derived from the sliders in front of the user. No
   figure here is a forecast, an estimate, or a promise.

   Persistence: streetBankerArtistSignalProfile (v1), migrated once from
   the legacy streetBankerArtistEq key. All stored data is validated and
   clamped before use, and only ever rendered through textContent. */
(function () {
  "use strict";

  var root = document.getElementById("artist-eq");
  var dataEl = document.getElementById("sbeq-data");
  if (!root || !dataEl) { return; }

  var CFG;
  try { CFG = JSON.parse(dataEl.textContent); } catch (e) { return; }

  var reduceMotion = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var inputs = Array.prototype.slice.call(
    root.querySelectorAll(".sbeq-range"));
  var presetButtons = Array.prototype.slice.call(
    root.querySelectorAll(".sbeq-preset"));
  var bankButtons = Array.prototype.slice.call(
    root.querySelectorAll(".sbeq-bank"));
  var curveLine = document.getElementById("sbeq-curve-line");
  var curveFill = document.getElementById("sbeq-curve-fill");
  var laneEl = document.getElementById("sbeq-lane");
  var laneBlurbEl = document.getElementById("sbeq-lane-blurb");
  var modulesEl = document.getElementById("sbeq-modules");
  var actionsEl = document.getElementById("sbeq-actions");
  var buildEl = document.getElementById("sbeq-build");
  var liveEl = document.getElementById("sbeq-live");
  var resetEl = document.getElementById("sbeq-reset");

  /* The EQ touches nothing outside its own racks. The signal line lives
     inside the recommendation panel - the EQ reporting its result, not
     the page changing around the visitor. */
  var signalEl = document.getElementById("sbeq-signal");

  var CUSTOM = "custom-mix";
  var LABELS = {};
  CFG.bands.forEach(function (b) { LABELS[b.key] = b.label; });

  var current = { preset: CFG.default_preset, values: {} };
  var lastResult = null;
  var committedLaneId = null;      // what the homepage currently reflects
  var createdAt = null;            // preserved across saves

  /* --- analytics: general names, no priority values --------------------- */
  function track(name, detail) {
    try {
      if (typeof window.gtag === "function") {
        window.gtag("event", name, detail || {});
      } else if (window.dataLayer && typeof window.dataLayer.push === "function") {
        window.dataLayer.push(Object.assign({ event: name }, detail || {}));
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

  /* --- the curve --------------------------------------------------------- */
  function pointsFor(values) {
    var pts = [];
    for (var i = 0; i < CFG.bands.length; i++) {
      var v = values[CFG.bands[i].key];
      pts.push({
        x: (i * 1200) / (CFG.bands.length - 1),
        y: 120 - (v - 5) * 20
      });
    }
    return pts;
  }

  function smoothPath(pts) {
    if (!pts.length) { return ""; }
    var d = "M" + pts[0].x.toFixed(1) + " " + pts[0].y.toFixed(1);
    for (var i = 0; i < pts.length - 1; i++) {
      var p0 = pts[i - 1] || pts[i];
      var p1 = pts[i];
      var p2 = pts[i + 1];
      var p3 = pts[i + 2] || p2;
      var c1x = p1.x + (p2.x - p0.x) / 6;
      var c1y = p1.y + (p2.y - p0.y) / 6;
      var c2x = p2.x - (p3.x - p1.x) / 6;
      var c2y = p2.y - (p3.y - p1.y) / 6;
      d += "C" + c1x.toFixed(1) + " " + c1y.toFixed(1) +
           "," + c2x.toFixed(1) + " " + c2y.toFixed(1) +
           "," + p2.x.toFixed(1) + " " + p2.y.toFixed(1);
    }
    return d;
  }

  function drawCurve(values) {
    var d = smoothPath(pointsFor(values));
    if (curveLine) { curveLine.setAttribute("d", d); }
    if (curveFill) { curveFill.setAttribute("d", d + "L1200 120L0 120Z"); }
  }

  /* --- recommendation ----------------------------------------------------
     Scoring: each lane's score is the MEAN of its member priorities, so a
     six-band lane and a four-band lane compete on the same 0-10 scale.
     Royalty Sweep First is a rule, not a score: Royalty Recovery in the
     top two AND >= sweep_first_min. Integrated fires when the top two
     lanes sit inside lane_tie_gap of each other. */
  function sortedKeys(values) {
    return Object.keys(values).sort(function (a, b) {
      if (values[b] !== values[a]) { return values[b] - values[a]; }
      return a < b ? -1 : 1;            // stable, so results never flicker
    });
  }

  function scoreLanes(values) {
    return CFG.lanes.map(function (lane) {
      var total = 0;
      lane.keys.forEach(function (k) { total += values[k]; });
      return {
        id: lane.id, name: lane.name, href: lane.href,
        blurb: lane.blurb, score: total / lane.keys.length
      };
    }).sort(function (a, b) { return b.score - a.score; });
  }

  function recommendLane(values) {
    var order = sortedKeys(values);
    if (order.slice(0, 2).indexOf("royaltyRecovery") !== -1 &&
        values.royaltyRecovery >= CFG.sweep_first_min) {
      return Object.assign({ score: 10 }, CFG.sweep_first);
    }
    var scored = scoreLanes(values);
    if (scored.length > 1 &&
        (scored[0].score - scored[1].score) < CFG.lane_tie_gap) {
      return Object.assign({ score: scored[0].score }, CFG.integrated);
    }
    return scored[0];
  }

  /* Hysteresis: the homepage only re-commits to a new lane when the
     challenger clearly wins mid-drag (by lane_switch_margin beyond the
     incumbent), or when the sliders settle and the challenger still
     leads. The curve and the module/action lists stay live. */
  function laneScoreById(values, id) {
    if (id === CFG.sweep_first.id || id === CFG.integrated.id) { return null; }
    var scored = scoreLanes(values);
    for (var i = 0; i < scored.length; i++) {
      if (scored[i].id === id) { return scored[i].score; }
    }
    return null;
  }

  function chooseLane(values, settled) {
    var target = recommendLane(values);
    if (committedLaneId === null || settled ||
        target.id === committedLaneId) {
      return target;
    }
    /* Mid-drag: rule-based states switch immediately (they are yes/no,
       not a score race); scored lanes must clear the margin. */
    if (target.id === CFG.sweep_first.id || target.id === CFG.integrated.id ||
        committedLaneId === CFG.sweep_first.id ||
        committedLaneId === CFG.integrated.id) {
      return target;
    }
    var incumbent = laneScoreById(values, committedLaneId);
    if (incumbent !== null &&
        target.score - incumbent < CFG.lane_switch_margin) {
      /* keep the incumbent for now; the settle pass will decide */
      var scored = scoreLanes(values);
      for (var i = 0; i < scored.length; i++) {
        if (scored[i].id === committedLaneId) { return scored[i]; }
      }
    }
    return target;
  }

  function recommendModules(values) {
    var out = [];
    sortedKeys(values).forEach(function (key) {
      (CFG.priority_modules[key] || []).forEach(function (name) {
        if (out.length < CFG.max_modules && out.indexOf(name) === -1) {
          out.push(name);
        }
      });
    });
    return out;
  }

  function recommendActions(values) {
    var out = [];
    sortedKeys(values).forEach(function (key) {
      (CFG.priority_actions[key] || []).forEach(function (text) {
        if (out.length < CFG.action_count && out.indexOf(text) === -1) {
          out.push(text);
        }
      });
    });
    return out;
  }

  /* --- the recommendation panel ----------------------------------------- */
  function renderPanel(lane, modules, actions) {
    if (laneEl) {
      laneEl.textContent = "";
      if (lane.href) {
        var a = document.createElement("a");
        a.href = lane.href;
        a.textContent = lane.name;
        laneEl.appendChild(a);
      } else {
        laneEl.textContent = lane.name;
      }
    }
    if (laneBlurbEl) { laneBlurbEl.textContent = lane.blurb || ""; }

    if (modulesEl) {
      modulesEl.textContent = "";
      modules.forEach(function (name) {
        var li = document.createElement("li");
        var href = CFG.modules[name];
        if (href) {
          var link = document.createElement("a");
          link.href = href;
          link.textContent = name;
          li.appendChild(link);
        } else {
          li.textContent = name;   // real module, no page yet - no dead link
        }
        modulesEl.appendChild(li);
      });
    }

    if (actionsEl) {
      actionsEl.textContent = "";
      actions.forEach(function (text) {
        var li = document.createElement("li");
        li.appendChild(document.createTextNode(text));
        actionsEl.appendChild(li);
      });
    }
  }

  /* --- Adaptive Visual Modes ---------------------------------------------
     The homepage responds through ONE coordinated mode switch, never
     per-element tweaks. Scoring: mean of each mode's member priorities
     (normalized across group sizes). Recovery is rule-gated - Royalty
     Recovery in the top two AND >= sweep_first_min - it never wins on
     score alone. If the top two scored modes sit within mode_tie_gap,
     the signal is broad and Full-Stack wins. Deterministic: the same
     fifteen values always produce the same mode. */
  var MODES_BY_ID = {};
  CFG.modes.forEach(function (m) { MODES_BY_ID[m.id] = m; });
  var committedModeId = null;

  function scoreModes(values) {
    return CFG.modes.filter(function (m) {
      return m.keys.length && m.id !== "recovery";
    }).map(function (m) {
      var total = 0;
      m.keys.forEach(function (k) { total += values[k]; });
      return { mode: m, score: total / m.keys.length };
    }).sort(function (a, b) { return b.score - a.score; });
  }

  function computeMode(values) {
    var order = sortedKeys(values);
    if (order.slice(0, 2).indexOf("royaltyRecovery") !== -1 &&
        values.royaltyRecovery >= CFG.sweep_first_min) {
      return MODES_BY_ID.recovery;
    }
    var scored = scoreModes(values);
    if ((scored[0].score - scored[1].score) < CFG.mode_tie_gap) {
      return MODES_BY_ID["full-stack"];
    }
    /* Hysteresis: keep the incumbent unless the challenger clearly wins. */
    if (committedModeId && committedModeId !== scored[0].mode.id) {
      for (var i = 0; i < scored.length; i++) {
        if (scored[i].mode.id === committedModeId &&
            scored[0].score - scored[i].score < CFG.mode_switch_margin) {
          return scored[i].mode;
        }
      }
    }
    return scored[0].mode;
  }

  /* Commit = update the signal line inside the panel and save. The page
     itself never changes - no tints, no image swaps, no CTA rewording.
     The computed mode still rides the saved profile so the Command
     Center and Artist Twin can use it. */
  function commitMode(values) {
    var mode = computeMode(values);
    var changed = mode.id !== committedModeId;
    committedModeId = mode.id;
    if (signalEl) { signalEl.textContent = mode.signal; }
    if (changed) {
      track("artist_visual_mode_committed", {
        mode: mode.id,
        preset: (presetById(current.preset) || { name: "Custom Mix" }).name,
        source: CFG.profile_source
      });
      scheduleSave();
    }
    return mode;
  }

  /* --- announcements ------------------------------------------------------ */
  var announceTimer = null;
  function announce() {
    if (!liveEl || !lastResult) { return; }
    clearTimeout(announceTimer);
    announceTimer = setTimeout(function () {
      liveEl.textContent = "Recommended: " + lastResult.lane.name +
        ". Modules: " + lastResult.modules.join(", ") +
        ". First action: " + (lastResult.actions[0] || "");
    }, 700);
  }

  /* --- slider plumbing ---------------------------------------------------- */
  function readInputs() {
    var values = {};
    inputs.forEach(function (input) {
      values[input.dataset.band] = parseInt(input.value, 10);
    });
    return values;
  }

  function writeInputs(values) {
    inputs.forEach(function (input) {
      var v = values[input.dataset.band];
      if (typeof v === "number") {
        input.value = String(v);
        input.setAttribute("aria-valuetext", describe(v));
      }
    });
  }

  function describe(v) {
    var db = (v - 5) * 2.4;
    var word = v >= 8 ? "critical" : v >= 6 ? "high"
             : v >= 4 ? "moderate" : v >= 2 ? "low" : "not a priority";
    return v + " of 10, " + word + ", " +
      (db > 0 ? "+" : "") + Math.round(db) + " decibels";
  }

  function markPreset(id) {
    presetButtons.forEach(function (btn) {
      btn.setAttribute("aria-pressed",
        btn.dataset.preset === id ? "true" : "false");
    });
  }

  /* --- the Artist Signal Profile ------------------------------------------ */
  function clamp(v) {
    v = Math.round(Number(v));
    if (isNaN(v)) { return null; }
    return Math.min(10, Math.max(0, v));
  }

  function validValues(raw) {
    if (!raw || typeof raw !== "object") { return null; }
    var values = {};
    for (var i = 0; i < CFG.bands.length; i++) {
      var v = clamp(raw[CFG.bands[i].key]);
      if (v === null) { return null; }   // every priority must exist
      values[CFG.bands[i].key] = v;
    }
    return values;
  }

  function buildProfile() {
    var preset = presetById(current.preset);
    var top = sortedKeys(current.values).slice(0, 3).map(function (k) {
      return LABELS[k] || k;
    });
    var now = new Date().toISOString();
    if (!createdAt) { createdAt = now; }
    return {
      version: CFG.profile_version,
      createdAt: createdAt,
      updatedAt: now,
      preset: preset ? preset.name : "Custom Mix",
      priorities: current.values,
      topPriorities: top,
      recommendedLane: lastResult ? lastResult.lane.name : null,
      recommendedModules: lastResult ? lastResult.modules : [],
      firstActions: lastResult ? lastResult.actions : [],
      activeVisualMode: committedModeId,
      source: CFG.profile_source
    };
  }

  function saveProfile() {
    try {
      window.localStorage.setItem(CFG.storage_key,
        JSON.stringify(buildProfile()));
    } catch (e) { /* private mode or full quota: the EQ still works */ }
  }

  var saveTimer = null;
  function scheduleSave() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(saveProfile, CFG.save_debounce_ms);
  }

  function restoreProfile() {
    /* New key first; fall back to the legacy key once and migrate. Any
       malformed, unsupported, or incomplete data is ignored safely. */
    try {
      var raw = window.localStorage.getItem(CFG.storage_key);
      if (raw) {
        var p = JSON.parse(raw);
        /* v1 (no activeVisualMode) and v2 both restore; the mode is
           recomputed from priorities when absent or invalid. */
        if (p && (p.version === 1 || p.version === 2)) {
          var values = validValues(p.priorities);
          if (values) {
            createdAt = (typeof p.createdAt === "string") ? p.createdAt : null;
            var mode = (typeof p.activeVisualMode === "string" &&
                        MODES_BY_ID[p.activeVisualMode])
              ? p.activeVisualMode : null;
            return { values: values, presetName: String(p.preset || ""),
                     mode: mode };
          }
        }
      }
      var legacy = window.localStorage.getItem(CFG.legacy_storage_key);
      if (legacy) {
        var old = JSON.parse(legacy);
        var oldValues = validValues(old && old.priorities);
        if (oldValues) {
          createdAt = (old && typeof old.savedAt === "string")
            ? old.savedAt : null;
          return { values: oldValues,
                   presetName: String((old && old.preset) || "") };
        }
      }
    } catch (e) { /* storage unavailable or corrupt: use the default */ }
    return null;
  }

  function presetIdByName(name) {
    for (var i = 0; i < CFG.presets.length; i++) {
      if (CFG.presets[i].name === name) { return CFG.presets[i].id; }
    }
    return CUSTOM;
  }

  /* --- update pipeline ----------------------------------------------------
     live: curve + panel follow every input; the homepage (lane card and
     CTA text) waits for a clear win or the settle timer. */
  var settleTimer = null;
  function update(values, presetId, opts) {
    opts = opts || {};
    current.values = values;
    current.preset = presetId;
    drawCurve(values);

    var lane = chooseLane(values, !!opts.settled);
    var modules = recommendModules(values);
    var actions = recommendActions(values);
    lastResult = { lane: lane, modules: modules, actions: actions };

    renderPanel(lane, modules, actions);
    markPreset(presetId);
    announce();

    if (opts.settled || opts.commit) {
      committedLaneId = lane.id;
      commitMode(values);
    } else {
      /* Curve and panel stay live; the page-wide mode switch waits for
         the mix to settle - at most one mode change per drag. */
      clearTimeout(settleTimer);
      settleTimer = setTimeout(function () {
        var settledLane = recommendLane(current.values);
        lastResult.lane = settledLane;
        renderPanel(settledLane, lastResult.modules, lastResult.actions);
        committedLaneId = settledLane.id;
        commitMode(current.values);
        announce();
      }, CFG.settle_ms);
    }
    scheduleSave();
  }

  /* --- preset glide (decoration only; state commits first) ---------------- */
  var animFrame = null;
  function animateTo(target, presetId) {
    if (animFrame) { cancelAnimationFrame(animFrame); animFrame = null; }
    var from = readInputs();

    writeInputs(target);
    update(target, presetId, { commit: true });

    if (reduceMotion || typeof window.requestAnimationFrame !== "function") {
      return;
    }
    var start = null;
    var DURATION = 420;
    function step(ts) {
      if (start === null) { start = ts; }
      var t = Math.min(1, (ts - start) / DURATION);
      var e = 1 - Math.pow(1 - t, 3);
      var frame = {};
      Object.keys(target).forEach(function (k) {
        frame[k] = Math.round(from[k] + (target[k] - from[k]) * e);
      });
      writeInputs(frame);
      drawCurve(frame);
      if (t < 1) {
        animFrame = requestAnimationFrame(step);
      } else {
        animFrame = null;
        writeInputs(target);
        drawCurve(target);
      }
    }
    animFrame = requestAnimationFrame(step);
  }

  /* --- events -------------------------------------------------------------- */
  var sliderTrackTimer = null;
  inputs.forEach(function (input) {
    input.addEventListener("input", function () {
      if (animFrame) { cancelAnimationFrame(animFrame); animFrame = null; }
      var values = readInputs();
      input.setAttribute("aria-valuetext",
        describe(parseInt(input.value, 10)));
      update(values, CUSTOM);
      clearTimeout(sliderTrackTimer);
      sliderTrackTimer = setTimeout(function () {
        /* band name only - priority values stay on the user's machine */
        track("artist_eq_slider_changed", { band: input.dataset.band });
      }, 500);
    });
  });

  presetButtons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      var id = btn.dataset.preset;
      var preset = presetById(id);
      if (!preset) { return; }
      if (!preset.values) {
        markPreset(CUSTOM);
        current.preset = CUSTOM;
        announce();
        scheduleSave();
      } else {
        animateTo(Object.assign({}, preset.values), id);
      }
      track("artist_eq_preset_selected", { preset: preset.name });
    });
  });

  /* --- Reset Mix ------------------------------------------------------------
     Returns the board to the default preset. Resets the mix only: it
     never touches an account, a connection, or any release/royalty/fan
     data - there is nothing here that could. Confirmation only when a
     custom mix has drifted well away from every named preset. */
  function substantiallyCustom() {
    if (current.preset !== CUSTOM) { return false; }
    var best = Infinity;
    CFG.presets.forEach(function (p) {
      if (!p.values) { return; }
      var d = 0;
      Object.keys(p.values).forEach(function (k) {
        d += Math.abs((current.values[k] || 0) - p.values[k]);
      });
      best = Math.min(best, d);
    });
    return best > 8;
  }

  if (resetEl) {
    resetEl.addEventListener("click", function () {
      if (substantiallyCustom() &&
          !window.confirm("Reset your mix to the default preset? Your " +
                          "current custom settings will be replaced.")) {
        return;
      }
      var def = presetById(CFG.default_preset);
      animateTo(Object.assign({}, def.values), def.id);
      saveProfile();
      track("artist_signal_profile_reset", {});
    });
  }

  /* --- mobile banks ---------------------------------------------------------
     Buttons show one bank of five channels below 640px. Values in hidden
     banks persist; the curve and every recommendation always use all
     fifteen. Pure show/hide - no slider is ever rebuilt. */
  function applyBank(bankId) {
    bankButtons.forEach(function (btn) {
      btn.setAttribute("aria-pressed",
        btn.dataset.bank === bankId ? "true" : "false");
    });
    Array.prototype.forEach.call(
      root.querySelectorAll(".sbeq-channel"), function (ch) {
        if (ch.getAttribute("data-bank") === bankId) {
          ch.removeAttribute("data-hidden-bank");
        } else {
          ch.setAttribute("data-hidden-bank", "");
        }
      });
  }
  bankButtons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      applyBank(btn.dataset.bank);
    });
  });
  if (bankButtons.length) { applyBank(bankButtons[0].dataset.bank); }

  /* --- Build My Program ----------------------------------------------------- */
  if (buildEl) {
    buildEl.addEventListener("click", function () {
      /* Recalculate at the moment of commitment, then persist the full
         profile. Only the source indicator rides the URL. */
      var lane = recommendLane(current.values);
      lastResult = {
        lane: lane,
        modules: recommendModules(current.values),
        actions: recommendActions(current.values)
      };
      saveProfile();
      track("artist_eq_program_built", {
        preset: (presetById(current.preset) || { name: "Custom Mix" }).name,
        lane: lane.name
      });
      /* no preventDefault: the link navigates even if anything above threw */
    });
  }

  /* --- boot ------------------------------------------------------------------ */
  var saved = restoreProfile();
  var startValues, startPreset;
  if (saved) {
    startValues = saved.values;
    startPreset = presetIdByName(saved.presetName);
    /* Seeding the saved mode means a near-tied score keeps the mode the
       visitor last saw, instead of silently flipping on reload. */
    if (saved.mode) { committedModeId = saved.mode; }
    track("artist_signal_profile_loaded", { preset: saved.presetName });
  } else {
    var def = presetById(CFG.default_preset);
    startValues = Object.assign({}, def.values);
    startPreset = def.id;
  }
  writeInputs(startValues);
  update(startValues, startPreset, { commit: true });
  saveProfile();   /* migration writes the new key immediately */

  if ("IntersectionObserver" in window) {
    var seen = false;
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting && !seen) {
          seen = true;
          track("artist_eq_viewed", {});
          io.disconnect();
        }
      });
    }, { threshold: 0.35 });
    io.observe(root);
  } else {
    track("artist_eq_viewed", {});
  }
})();
