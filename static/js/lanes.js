/* Section 6 — three lanes, one system.
 *
 * The section reads and links with this file absent: the summaries are
 * anchors, the comparison is in the document, and hover on a summary is
 * CSS. What is here is the live half - engaging one lane, driving the
 * three controls that mean something, carrying the Artist EQ
 * recommendation down the page, and measurement.
 *
 * Only three controls move: the VU (engagement), the fader (depth of
 * support - Core, Guided, High-touch, never volume) and the lamp
 * (engaged). Every other knob on the unit belongs to the photograph. A
 * decorative knob that responds to dragging teaches people the controls
 * are fake.
 */
(function () {
  "use strict";

  var root = document.getElementById("lanes");
  if (!root) { return; }

  var unit = root.querySelector(".sblane-unit");
  var summaries = [].slice.call(root.querySelectorAll(".sblane-summary"));
  if (!summaries.length) { return; }

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

  function select(lane) {
    summaries.forEach(function (s) {
      s.classList.toggle("is-active", !!lane && s.dataset.lane === lane);
    });
    if (!unit) { return; }
    if (lane) { unit.dataset.active = lane; } else { delete unit.dataset.active; }
  }

  /* Whatever still holds focus keeps the channel lit, so moving the
     mouse away does not darken the lane a keyboard reader is on. */
  function release() {
    var held = null;
    summaries.forEach(function (s) {
      if (s.contains(document.activeElement)) { held = s.dataset.lane; }
    });
    select(held);
  }

  var hovered = {};
  summaries.forEach(function (summary) {
    var lane = summary.dataset.lane;
    var link = summary.querySelector(".sblane-link");

    summary.addEventListener("mouseenter", function () {
      select(lane);
      if (hovered[lane]) { return; }
      hovered[lane] = true;
      track("lane_hovered", {lane: lane});
    });
    summary.addEventListener("mouseleave", release);

    if (link) {
      link.addEventListener("focus", function () {
        select(lane);
        track("lane_focused", {lane: lane});
      });
      link.addEventListener("blur", function () { window.setTimeout(release, 0); });
      link.addEventListener("click", function () {
        track("lane_clicked", {lane: lane, href: link.getAttribute("href")});
      });
    }
  });

  var compare = document.getElementById("sblane-compare");
  var comparison = document.getElementById("sblane-comparison");
  if (compare && comparison) {
    compare.addEventListener("click", function () {
      var open = comparison.hasAttribute("hidden");
      if (open) { comparison.removeAttribute("hidden"); }
      else { comparison.setAttribute("hidden", ""); }
      compare.setAttribute("aria-expanded", open ? "true" : "false");
      if (open) {
        comparison.scrollIntoView({block: "nearest",
          behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
            ? "auto" : "smooth"});
        track("lane_comparison_opened", {});
      }
    });
  }

  var primary = root.querySelector(".sblane-primary");
  if (primary) {
    primary.addEventListener("click", function () {
      track("find_my_lane_clicked", {href: primary.getAttribute("href")});
    });
  }

  /* Section viewed, once. */
  if ("IntersectionObserver" in window) {
    var seen = false;
    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting && !seen) {
          seen = true;
          track("lanes_section_viewed", {});
          obs.disconnect();
        }
      });
    }, {threshold: 0.25});
    obs.observe(root);
  }

  /* --- engaging a lane ---------------------------------------------------
     Hover lights a channel; a click engages it. One at a time, and the
     engaged lane survives the pointer leaving. */
  var channels = {};
  [].slice.call(root.querySelectorAll(".sblane-channel")).forEach(function (c) {
    channels[c.dataset.channel] = c;
  });

  var supportRow = document.getElementById("sblane-support");
  var supportNote = document.getElementById("sblane-support-note");
  var supportBtns = [].slice.call(root.querySelectorAll(".sblane-support-btn"));
  var LEVELS = supportBtns.map(function (b) { return b.textContent.trim(); });

  var engaged = null;
  var engagedRest = 0;

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* Needle travel across the arc, in degrees. Resting is hard left. */
  function needle(channel, level, animate) {
    var vu = channel.querySelector(".sblane-vu");
    if (!vu) { return; }
    var deg = -38 + (level + 1) * 24;          /* three usable detents */
    var line = vu.querySelector(".sblane-vu-needle");
    if (!line) { return; }
    if (animate && !reduced) {
      vu.classList.add("is-live");
      /* Fast rise past the mark, then settle back onto it. The overshoot
         is what makes a meter read as mechanical rather than as a bar
         chart growing. */
      line.style.transform = "rotate(" + (deg + 7) + "deg)";
      window.setTimeout(function () {
        line.style.transform = "rotate(" + deg + "deg)";
      }, 190);
    } else {
      vu.classList.remove("is-live");
      line.style.transform = "rotate(" + deg + "deg)";
    }
  }

  function setSupport(level, animate) {
    if (!engaged || !channels[engaged]) { return; }
    var channel = channels[engaged];
    channel.dataset.support = String(level);
    needle(channel, level, animate);
    supportBtns.forEach(function (b) {
      b.setAttribute("aria-pressed", Number(b.dataset.support) === level ? "true" : "false");
    });
    if (supportNote) {
      /* Partnership is reviewed case by case at every depth. Saying so
         at the top detent is the difference between a setting and a
         promise. */
      supportNote.textContent = engaged === "partnership"
        ? LEVELS[level] + " support. Partnership is reviewed case by case at every level."
        : LEVELS[level] + " support on the " + engaged + " lane.";
    }
  }

  function engage(lane, animate) {
    engaged = lane;
    Object.keys(channels).forEach(function (k) {
      channels[k].classList.toggle("is-engaged", k === lane);
    });
    if (unit) {
      if (lane) { unit.dataset.active = lane; } else { delete unit.dataset.active; }
    }
    summaries.forEach(function (s) {
      s.classList.toggle("is-engaged", s.dataset.lane === lane);
    });
    if (!lane) {
      if (supportRow) { supportRow.hidden = true; }
      return;
    }
    var link = root.querySelector('[data-lane-link="' + lane + '"]');
    engagedRest = link ? Number(link.dataset.rest || 0) : 0;
    if (supportRow) { supportRow.hidden = false; }
    setSupport(engagedRest, animate !== false);
    track("lane_engaged", {lane: lane});
  }

  supportBtns.forEach(function (btn) {
    btn.addEventListener("click", function () {
      setSupport(Number(btn.dataset.support), true);
      track("lane_support_selected",
            {lane: engaged, level: LEVELS[Number(btn.dataset.support)]});
    });
  });

  /* Clicking the summary engages the lane; the link still navigates, so
     a click on the CTA itself is not swallowed. */
  summaries.forEach(function (summary) {
    summary.addEventListener("click", function (e) {
      if (e.target.closest(".sblane-cta")) { return; }
      if (engaged !== summary.dataset.lane) {
        e.preventDefault();
        engage(summary.dataset.lane);
      }
    });
  });

  /* --- the Artist EQ hand-off --------------------------------------------
     If the visitor moved the console at the top of the page, the lane it
     recommended is engaged here and named. With no EQ interaction there
     is no recommendation, and the line stays hidden rather than
     defaulting to one nobody asked for. */
  var fromEq = document.getElementById("sblane-fromeq");
  var fromEqLane = document.getElementById("sblane-fromeq-lane");
  try {
    var raw = window.localStorage.getItem("streetBankerArtistEq");
    var saved = raw ? JSON.parse(raw) : null;
    var laneId = saved && saved.plan && saved.plan.lane && saved.plan.lane.id;
    if (laneId && channels[laneId]) {
      if (fromEq && fromEqLane) {
        var link = root.querySelector('[data-lane-link="' + laneId + '"]');
        var name = link ? link.querySelector(".sblane-name") : null;
        fromEqLane.textContent = name ? name.textContent.trim() : laneId;
        fromEq.hidden = false;
      }
      engage(laneId, false);
      track("lane_recommended_from_eq", {lane: laneId});
    }
  } catch (e) { /* private mode: no recommendation, no line */ }

})();
