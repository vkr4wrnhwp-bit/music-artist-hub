/* The Artist EQ.

   Reads its data from the JSON block the template renders, drives fifteen
   native range inputs, draws the response curve, and works out which lane
   the visitor's own settings point at.

   Everything shown is derived from the sliders in front of the user. No
   figure here is a forecast, an estimate, or a promise. */
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
  var curveLine = document.getElementById("sbeq-curve-line");
  var curveFill = document.getElementById("sbeq-curve-fill");
  var laneEl = document.getElementById("sbeq-lane");
  var laneBlurbEl = document.getElementById("sbeq-lane-blurb");
  var modulesEl = document.getElementById("sbeq-modules");
  var actionsEl = document.getElementById("sbeq-actions");
  var buildEl = document.getElementById("sbeq-build");
  var liveEl = document.getElementById("sbeq-live");

  var CUSTOM = "custom-mix";
  var current = { preset: CFG.default_preset, values: {} };
  var lastResult = null;

  /* --- analytics ------------------------------------------------------
     Fires into whatever the site already has. If nothing is installed
     this is a no-op - we do not add a provider for one component. */
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

  /* --- the curve ------------------------------------------------------
     Catmull-Rom through the fifteen points, converted to cubic beziers so
     the line is smooth without overshooting the slider positions. */
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
    var pts = pointsFor(values);
    var d = smoothPath(pts);
    if (curveLine) { curveLine.setAttribute("d", d); }
    /* Fill sits between the curve and the 0 dB line, so boosts read as
       lift above centre and cuts as dips below it. */
    if (curveFill) {
      curveFill.setAttribute("d", d + "L1200 120L0 120Z");
    }
  }

  /* --- recommendation -------------------------------------------------- */
  function sortedKeys(values) {
    return Object.keys(values).sort(function (a, b) {
      if (values[b] !== values[a]) { return values[b] - values[a]; }
      return a < b ? -1 : 1;            // stable, so results never flicker
    });
  }

  function recommendLane(values) {
    var order = sortedKeys(values);
    var topTwo = order.slice(0, 2);
    if (topTwo.indexOf("royaltyRecovery") !== -1 &&
        values.royaltyRecovery >= CFG.sweep_first_min) {
      return CFG.sweep_first;
    }
    var scored = CFG.lanes.map(function (lane) {
      var total = 0;
      lane.keys.forEach(function (k) { total += values[k]; });
      return {
        id: lane.id, name: lane.name, href: lane.href,
        blurb: lane.blurb, score: total / lane.keys.length
      };
    }).sort(function (a, b) { return b.score - a.score; });

    if (scored.length > 1 &&
        (scored[0].score - scored[1].score) < CFG.lane_tie_gap) {
      return CFG.integrated;
    }
    return scored[0];
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

  function render(values) {
    var lane = recommendLane(values);
    var modules = recommendModules(values);
    var actions = recommendActions(values);
    lastResult = { lane: lane, modules: modules, actions: actions };

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
          /* Real module, no page of its own yet. Printed as plain text
             rather than wrapped in a link that would go nowhere. */
          li.textContent = name;
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

  /* Announce the outcome, not every slider tick. */
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

  /* --- slider plumbing ------------------------------------------------- */
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

  function update(values, presetId) {
    current.values = values;
    current.preset = presetId;
    drawCurve(values);
    render(values);
    markPreset(presetId);
    announce();
  }

  /* Presets glide into place, but the glide is decoration only.

     The result is committed before the first frame is ever requested: a
     background tab, a throttled timer or a browser that never runs an
     animation frame must still end up with the right sliders and the
     right recommendation. */
  var animFrame = null;
  function animateTo(target, presetId) {
    if (animFrame) { cancelAnimationFrame(animFrame); animFrame = null; }
    var from = readInputs();

    writeInputs(target);
    update(target, presetId);

    if (reduceMotion || typeof window.requestAnimationFrame !== "function") {
      return;
    }

    var start = null;
    var DURATION = 420;
    function step(ts) {
      if (start === null) { start = ts; }
      var t = Math.min(1, (ts - start) / DURATION);
      var e = 1 - Math.pow(1 - t, 3);         // easeOutCubic
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

  /* --- events ---------------------------------------------------------- */
  var sliderTrackTimer = null;
  inputs.forEach(function (input) {
    input.addEventListener("input", function () {
      cancelAnimationFrame(animFrame);
      var values = readInputs();
      input.setAttribute("aria-valuetext", describe(parseInt(input.value, 10)));
      /* Touching a slider means the mix is now the visitor's own. */
      update(values, CUSTOM);
      clearTimeout(sliderTrackTimer);
      sliderTrackTimer = setTimeout(function () {
        track("artist_eq_slider_changed", {
          band: input.dataset.band, value: parseInt(input.value, 10)
        });
      }, 500);
    });
  });

  presetButtons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      var id = btn.dataset.preset;
      var preset = presetById(id);
      if (!preset) { return; }
      if (!preset.values) {
        /* Custom Mix keeps whatever the visitor last set. */
        markPreset(CUSTOM);
        current.preset = CUSTOM;
        announce();
      } else {
        animateTo(Object.assign({}, preset.values), id);
      }
      track("artist_eq_preset_selected", { preset: preset.name });
    });
  });

  if (buildEl) {
    buildEl.addEventListener("click", function (ev) {
      var preset = presetById(current.preset);
      var payload = {
        preset: preset ? preset.name : "Custom Mix",
        priorities: current.values,
        recommendedLane: lastResult ? lastResult.lane.name : null,
        recommendedModules: lastResult ? lastResult.modules : [],
        firstActions: lastResult ? lastResult.actions : [],
        source: "artist-eq",
        savedAt: new Date().toISOString()
      };
      try {
        window.localStorage.setItem(CFG.storage_key, JSON.stringify(payload));
      } catch (e) {
        /* Private mode or a full quota: still continue to signup rather
           than trapping the visitor on the homepage. */
      }
      track("artist_eq_program_built", {
        preset: payload.preset, lane: payload.recommendedLane
      });
      /* Let the link do the navigating - no preventDefault, so the CTA
         still works if anything above threw. */
      void ev;
    });
  }

  /* --- boot ------------------------------------------------------------ */
  function restore() {
    try {
      var raw = window.localStorage.getItem(CFG.storage_key);
      if (!raw) { return null; }
      var saved = JSON.parse(raw);
      if (!saved || !saved.priorities) { return null; }
      var values = {};
      var ok = true;
      CFG.bands.forEach(function (b) {
        var v = saved.priorities[b.key];
        if (typeof v !== "number" || v < 0 || v > 10) { ok = false; }
        values[b.key] = Math.min(10, Math.max(0, Math.round(v || 0)));
      });
      return ok ? { values: values, preset: saved.preset } : null;
    } catch (e) { return null; }
  }

  function presetIdByName(name) {
    for (var i = 0; i < CFG.presets.length; i++) {
      if (CFG.presets[i].name === name) { return CFG.presets[i].id; }
    }
    return CUSTOM;
  }

  var saved = restore();
  var startValues;
  var startPreset;
  if (saved) {
    startValues = saved.values;
    startPreset = presetIdByName(saved.preset);
  } else {
    var def = presetById(CFG.default_preset);
    startValues = Object.assign({}, def.values);
    startPreset = def.id;
  }
  writeInputs(startValues);
  update(startValues, startPreset);

  /* One view event, the first time the rack actually comes into sight. */
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
