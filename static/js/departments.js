/* Section 4 — one system, six departments.
 *
 * The section works with this file absent: the picture, the six slices,
 * the tone progression, the rules, hover, focus and the scroller are all
 * CSS. Everything here is measurement — which department a reader looked
 * at, which one they opened, how far they scrolled the strip on a phone.
 * Event names and department slugs only, never a person.
 */
(function () {
  "use strict";

  var root = document.getElementById("departments");
  if (!root) { return; }

  var grid = root.querySelector(".sbdept-grid");
  var depts = [].slice.call(root.querySelectorAll(".sbdept-dept"));
  if (!depts.length) { return; }

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

  /* The selected state. CSS already carries hover and keyboard focus on
     its own; this mirrors it onto a class so the same state reaches a
     touch or assistive-technology focus, and so the other five dim in
     browsers without :has(). */
  /* The phone grid shares one description line, so choosing a department
     changes one thing rather than stacking six paragraphs. Written from
     the control's own markup, so it cannot drift from the label. */
  var sharedName = document.getElementById("sbdept-shared-name");
  var sharedDesc = document.getElementById("sbdept-shared-desc");

  function writeShared(a) {
    if (!a || !sharedName || !sharedDesc) { return; }
    var name = a.querySelector(".sbdept-name");
    var desc = a.querySelector(".sbdept-desc");
    if (name) { sharedName.textContent = name.textContent.trim(); }
    if (desc) { sharedDesc.textContent = desc.textContent.trim(); }
  }

  function select(a) {
    depts.forEach(function (d) { d.classList.toggle("is-active", d === a); });
    writeShared(a);
    if (grid) {
      if (a) { grid.dataset.active = a.dataset.index; }
      else { delete grid.dataset.active; }
    }
  }

  /* Letting go: whatever still holds focus keeps the state, so moving
     the mouse off one department does not darken the one a keyboard
     reader is sitting on. */
  function release() {
    var held = null;
    depts.forEach(function (d) { if (d === document.activeElement) { held = d; } });
    select(held);
  }

  /* A department counts as focused once: a reader sweeping the mouse
     across six slices is one gesture, not six events. */
  var focused = {};
  depts.forEach(function (a) {
    var slug = a.dataset.dept;
    function note() {
      select(a);
      if (focused[slug]) { return; }
      focused[slug] = true;
      track("department_focused", {department: slug, index: Number(a.dataset.index)});
    }
    a.addEventListener("mouseenter", note);
    a.addEventListener("focus", note);
    a.addEventListener("mouseleave", release);
    a.addEventListener("blur", function () { window.setTimeout(release, 0); });
    a.addEventListener("click", function (e) {
      /* Touch, and this department is not the one being described yet:
         describe it instead of navigating. A second tap follows the
         link. On a pointer device the description is already showing by
         the time a click happens, so nothing is intercepted. */
      var coarse = window.matchMedia("(hover: none)").matches;
      if (coarse && !a.classList.contains("is-active")) {
        e.preventDefault();
        select(a);
        track("department_focused", {department: slug, index: Number(a.dataset.index)});
        return;
      }
      track("department_clicked", {department: slug, index: Number(a.dataset.index),
                                   href: a.getAttribute("href")});
    });
  });

  /* Section viewed, once. */
  if ("IntersectionObserver" in window) {
    var seen = false;
    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting && !seen) {
          seen = true;
          track("departments_section_viewed", {});
          obs.disconnect();
        }
      });
    }, {threshold: 0.3});
    obs.observe(root);
  }

  /* How far the strip was swiped, reported once when the scrolling stops
     and only if it actually moved. */
  if (grid) {
    var timer = null, furthest = 0, reported = -1;
    grid.addEventListener("scroll", function () {
      var width = depts[0].getBoundingClientRect().width || 1;
      var index = Math.round(grid.scrollLeft / width);
      if (index > furthest) { furthest = index; }
      if (timer) { window.clearTimeout(timer); }
      timer = window.setTimeout(function () {
        if (furthest > 0 && furthest !== reported) {
          reported = furthest;
          track("departments_swiped", {
            furthest: furthest,
            department: (depts[Math.min(furthest, depts.length - 1)] || {}).dataset.dept
          });
        }
      }, 400);
    }, {passive: true});
  }
})();
