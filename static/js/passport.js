/* Section 11 — Metadata Passport + Rights.
 *
 * The section reads with this file absent: all seven descriptions are
 * printed, the first detail panel is open, the completeness figure is
 * rendered server-side and the CTA is a link. What is here is the part
 * that connects the two sets of controls - the transparent areas on the
 * blueprint and the row of names beneath it are the same seven
 * categories - plus the connected-data disclosure and measurement.
 *
 * No credit, share, identifier, agreement or file name exists in this
 * section to send anywhere. The events carry category slugs only.
 */
(function () {
  "use strict";

  var root = document.getElementById("metadata-passport");
  if (!root) { return; }

  /* The blueprint carries no controls. The row of seven named buttons is
     the only control set, which is what a keyboard always had anyway. */
  var cats = [].slice.call(root.querySelectorAll(".sbmp-cat"));
  var panels = [].slice.call(root.querySelectorAll(".sbmp-panel"));
  if (!cats.length) { return; }

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

  /* One category at a time, in both control sets and in the detail. */
  function select(slug) {
    cats.forEach(function (c) {
      var on = c.dataset.category === slug;
      c.classList.toggle("is-active", on);
      c.setAttribute("aria-pressed", on ? "true" : "false");
    });
    panels.forEach(function (p) {
      if (p.dataset.panel === slug) { p.removeAttribute("hidden"); }
      else { p.setAttribute("hidden", ""); }
    });
  }

  var seen = {};
  function note(slug, how) {
    var key = slug + how;
    if (seen[key]) { return; }
    seen[key] = true;
    track(how === "hover" ? "passport_category_hovered"
          : how === "focus" ? "passport_category_focused"
          : "passport_category_selected", {category: slug});
  }

  cats.forEach(function (control) {
    var slug = control.dataset.category;
    control.addEventListener("mouseenter", function () {
      select(slug);
      note(slug, "hover");
    });
    control.addEventListener("focus", function () {
      select(slug);
      note(slug, "focus");
    });
    control.addEventListener("click", function () {
      select(slug);
      note(slug, "click");
    });
  });

  /* The first category is the one the server rendered open. */
  select(cats[0].dataset.category);

  var connectBtn = document.getElementById("sbmp-connect-btn");
  var connect = document.getElementById("sbmp-connect");
  if (connectBtn && connect) {
    connectBtn.addEventListener("click", function () {
      var opening = connect.hasAttribute("hidden");
      if (opening) { connect.removeAttribute("hidden"); }
      else { connect.setAttribute("hidden", ""); }
      connectBtn.setAttribute("aria-expanded", opening ? "true" : "false");
      if (opening) {
        connect.scrollIntoView({block: "nearest",
          behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
            ? "auto" : "smooth"});
        track("passport_connected_example_viewed", {});
      }
    });
  }

  var cta = root.querySelector(".sbmp-cta");
  if (cta) {
    cta.addEventListener("click", function () {
      track("passport_open_clicked", {href: cta.getAttribute("href")});
    });
  }

  var trust = root.querySelector(".sbmp-trust-link");
  if (trust) {
    trust.addEventListener("click", function () {
      track("passport_trust_link_clicked", {});
    });
  }

  /* Section viewed, once. */
  if ("IntersectionObserver" in window) {
    var viewed = false;
    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting && !viewed) {
          viewed = true;
          track("passport_section_viewed", {});
          obs.disconnect();
        }
      });
    }, {threshold: 0.2});
    obs.observe(root);
  }
})();
