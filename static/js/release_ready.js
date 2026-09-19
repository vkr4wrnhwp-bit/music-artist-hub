/* Release-Ready (/creative-studio/release-ready): the page's small helpers.

   - The upload form: shows the fields for the kind of upload picked, sends
     the files with a progress bar, and shows the server's own refusal word
     for word (too long, wrong format, boxes not ticked...).
   - While RoEx is working, the page asks its own JSON every 5 seconds (every
     15 after two minutes) and stops when nothing is in flight. A status that
     moved reloads the page, unless a preview is playing: then it offers a
     "Show it" button instead of cutting the music off.
   - The previews form keeps to two loudness settings (one when one free
     preview is left), and the vocal level shows its value.
   - A form marked data-rr-confirm asks before it deletes anything.

   Nothing here decides anything: the server checks every step again. */
(function () {
  "use strict";

  var FAST = 5000, SLOW = 15000, SLOW_AFTER = 120000;

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $all(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function badge(text, tone) {
    var b = document.createElement("span");
    b.className = "sb-badge sb-badge-" + (tone || "idle");
    b.textContent = text;
    return b;
  }

  /* ---- confirm before deleting ------------------------------------------- */
  $all("form[data-rr-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (!window.confirm(form.getAttribute("data-rr-confirm"))) { e.preventDefault(); }
    });
  });

  /* ---- the upload form ----------------------------------------------------- */
  var upload = $("form[data-rr-upload]");
  if (upload) {
    var groups = $all("[data-rr-mode]", upload);
    var picks = $all("input[data-rr-mode-pick]", upload);
    var sendNote = $("[data-rr-send-note]", upload);
    var noteText = sendNote ? sendNote.textContent : "";
    var closed = upload.querySelector("fieldset[disabled]") !== null;

    var showMode = function () {
      var mode = "mix";
      picks.forEach(function (p) { if (p.checked) { mode = p.value; } });
      groups.forEach(function (g) {
        var on = g.getAttribute("data-rr-mode") === mode;
        g.hidden = !on;
        /* A hidden file field must not be sent (it could be 150 MB) nor
           demanded: only the fields for the picked kind are live. */
        $all("input, select", g).forEach(function (el) {
          el.disabled = !on || closed;
          if (el.type === "file") { el.required = on && !closed; }
        });
      });
      if (sendNote) { sendNote.textContent = mode === "mix" ? noteText : ""; }
    };
    picks.forEach(function (p) { p.addEventListener("change", showMode); });
    showMode();

    var bar = $("[data-rr-progress]", upload);
    var fill = bar ? bar.querySelector("i") : null;
    var error = $("[data-rr-error]", upload);
    var button = $("#rr-send");

    var fail = function (text) {
      if (bar) { bar.hidden = true; }
      if (button) { button.disabled = false; button.textContent = "Send"; }
      if (error) { error.textContent = text; error.hidden = false; }
    };

    upload.addEventListener("submit", function (e) {
      if (closed || !window.FormData || !window.XMLHttpRequest) { return; }
      e.preventDefault();
      if (error) { error.hidden = true; }
      var xhr = new XMLHttpRequest();
      xhr.open("POST", upload.action);
      xhr.setRequestHeader("Accept", "application/json");
      if (bar && fill) { bar.hidden = false; fill.style.width = "0%"; }
      if (button) { button.disabled = true; button.textContent = "Sending"; }
      xhr.upload.onprogress = function (ev) {
        if (fill && ev.lengthComputable) {
          fill.style.width = Math.round(100 * ev.loaded / ev.total) + "%";
        }
      };
      xhr.onload = function () {
        var data = null;
        try { data = JSON.parse(xhr.responseText); } catch (err) { data = null; }
        if (xhr.status >= 200 && xhr.status < 300 && data && data.url) {
          window.location.href = data.url;
          return;
        }
        if (xhr.status === 413) {
          fail("That's more than can be sent at once. Export at 44.1 kHz, 16-bit and try again.");
          return;
        }
        fail((data && (data.message || data.error)) || "The file couldn't be sent. Try again in a minute.");
      };
      xhr.onerror = function () { fail("The upload stopped. Check your connection and try again."); };
      xhr.send(new FormData(upload));
    });
  }

  /* ---- the previews form --------------------------------------------------- */
  var make = $("form[data-rr-make]");
  if (make) {
    var left = parseInt(make.getAttribute("data-left") || "2", 10);
    var most = Math.max(1, Math.min(2, left));
    var boxes = $all('input[name="loudness"]', make);
    var makeBtn = $("#rr-make-btn");
    var keep = function () {
      var ticked = boxes.filter(function (b) { return b.checked; }).length;
      boxes.forEach(function (b) { b.disabled = !b.checked && ticked >= most; });
      if (makeBtn) {
        makeBtn.textContent = ticked === 2 ? "Make two free previews"
          : (ticked === 1 ? "Make one free preview" : "Pick a loudness setting");
        makeBtn.disabled = ticked === 0;
      }
    };
    boxes.forEach(function (b) { b.addEventListener("change", keep); });
    keep();

    var gain = $("input[data-rr-gain]", make);
    var gainOut = $("[data-rr-gain-out]", make);
    if (gain && gainOut) {
      var show = function () {
        var v = parseFloat(gain.value || "0");
        gainOut.textContent = (v > 0 ? "+" : "") + v.toFixed(1) + " dB";
      };
      gain.addEventListener("input", show);
      show();
    }
  }

  /* ---- keeping the page current while RoEx works ---------------------------- */
  var started = Date.now();
  var timer = null;

  function later(fn) {
    var wait = (Date.now() - started) > SLOW_AFTER ? SLOW : FAST;
    timer = window.setTimeout(fn, wait);
  }

  function getJSON(url, done) {
    var xhr = new XMLHttpRequest();
    xhr.open("GET", url);
    xhr.setRequestHeader("Accept", "application/json");
    xhr.onload = function () {
      var data = null;
      try { data = JSON.parse(xhr.responseText); } catch (err) { data = null; }
      done(xhr.status === 200 ? data : null);
    };
    xhr.onerror = function () { done(null); };
    xhr.send();
  }

  function playing() {
    return $all("audio").some(function (a) { return !a.paused && !a.ended; });
  }

  var fresh = $("[data-rr-fresh]");
  var reloadBtn = $("[data-rr-reload]");
  if (reloadBtn) { reloadBtn.addEventListener("click", function () { window.location.reload(); }); }

  /* One upload's page: any job whose status moved, or a new job, means the
     page has something new to draw. */
  var sourcePage = $('[data-rr-page="source"]');
  if (sourcePage && sourcePage.getAttribute("data-in-flight") === "1") {
    var url = sourcePage.getAttribute("data-rr-source-url");
    var seen = {};
    $all("[data-rr-job]").forEach(function (el) {
      seen[el.getAttribute("data-rr-job")] = el.getAttribute("data-status");
    });
    var tick = function () {
      if (document.hidden) { later(tick); return; }
      getJSON(url, function (data) {
        if (!data || !data.source) { later(tick); return; }
        var src = data.source, jobs = (src.previews || []).slice();
        if (src.report) { jobs.push(src.report); }
        /* A job that came to rest (a preview to play, a report to read, a
           master stored, a failure to explain) or a job this page has never
           drawn needs the page redrawn. A step between two working states
           only changes its chip. */
        var redraw = jobs.some(function (j) {
          return !(j.id in seen) || (seen[j.id] !== j.status && !j.in_flight);
        });
        if (redraw && !playing()) {
          window.location.reload();
          return;
        }
        jobs.forEach(function (j) {
          if (seen[j.id] === j.status) { return; }
          $all('[data-rr-job="' + j.id + '"] [data-rr-chip]').forEach(function (c) {
            c.textContent = "";
            c.appendChild(badge(j.chip, j.tone));
          });
          if (j.in_flight) { seen[j.id] = j.status; }
        });
        if (redraw && fresh) { fresh.hidden = false; }
        if (src.in_flight) { later(tick); }
      });
    };
    later(tick);
  }

  /* The uploads list: the chips change in place. */
  var listPage = $('[data-rr-page="list"]');
  if (listPage && $all('[data-rr-source][data-in-flight="1"]').length) {
    var stateUrl = listPage.getAttribute("data-rr-state-url");
    var listTick = function () {
      if (document.hidden) { later(listTick); return; }
      getJSON(stateUrl, function (data) {
        if (!data || !data.sources) { later(listTick); return; }
        var busy = false;
        data.sources.forEach(function (s) {
          var row = $('[data-rr-source="' + s.id + '"]');
          if (!row) { return; }
          row.setAttribute("data-in-flight", s.in_flight ? "1" : "0");
          if (s.in_flight) { busy = true; }
          var chip = row.querySelector("[data-rr-chip]");
          if (chip && s.chip) {
            chip.textContent = "";
            chip.appendChild(badge(s.chip, s.chip_tone));
          }
        });
        if (busy) { later(listTick); }
      });
    };
    later(listTick);
  }
})();
