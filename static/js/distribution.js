/* Section 10 — Global Distribution.
 *
 * The section reads with this file absent: the five capabilities are
 * printed, every workflow detail is in the document, the checklist is
 * plain markup and both CTAs are links. What is here is the workflow
 * reveal and measurement.
 *
 * No release metadata, contributor name, audio detail or ownership
 * information exists in this section to send anywhere, and the events
 * carry stage names from the config only.
 */
(function () {
  "use strict";

  var root = document.getElementById("global-distribution");
  if (!root) { return; }

  var stages = [].slice.call(root.querySelectorAll(".sbds-stage"));
  var detail = root.querySelector(".sbds-flow-text");
  var details = {};
  var terms = root.querySelectorAll(".sbds-flow-fallback dt");
  var defs = root.querySelectorAll(".sbds-flow-fallback dd");
  for (var i = 0; i < terms.length; i++) {
    if (defs[i]) { details[terms[i].textContent.toLowerCase()] = defs[i].textContent; }
  }

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

  var seenStage = {};
  stages.forEach(function (button, index) {
    var id = button.dataset.stage;
    function show() {
      stages.forEach(function (b) { b.classList.toggle("is-active", b === button); });
      if (detail && details[id]) { detail.textContent = details[id]; }
      if (seenStage[id]) { return; }
      seenStage[id] = true;
      track("distribution_stage_selected", {stage: id});
    }
    button.addEventListener("mouseenter", show);
    button.addEventListener("focus", show);
    button.addEventListener("click", show);
    if (index === 0) { button.classList.add("is-active"); }
  });

  var primary = root.querySelector(".sbds-cta");
  if (primary) {
    primary.addEventListener("click", function () {
      track("distribute_now_clicked", {href: primary.getAttribute("href")});
    });
  }

  var guide = root.querySelector(".sbds-guide");
  if (guide) {
    guide.addEventListener("click", function () {
      track("distribution_guide_clicked", {});
    });
  }

  var final = root.querySelector(".sbds-final-cta");
  if (final) {
    final.addEventListener("click", function () {
      track("start_a_release_clicked", {href: final.getAttribute("href")});
    });
  }

  /* The example checklist counted as seen once it has actually been on
     screen, so "viewed" means viewed. */
  var checklist = root.querySelector(".sbds-check");
  if (checklist && "IntersectionObserver" in window) {
    var listSeen = false;
    var listObs = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting && !listSeen) {
          listSeen = true;
          track("distribution_checklist_viewed", {});
          listObs.disconnect();
        }
      });
    }, {threshold: 0.4});
    listObs.observe(checklist);
  }

  /* Section viewed, once. */
  if ("IntersectionObserver" in window) {
    var seen = false;
    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting && !seen) {
          seen = true;
          track("distribution_section_viewed", {});
          obs.disconnect();
        }
      });
    }, {threshold: 0.2});
    obs.observe(root);
  }
})();
