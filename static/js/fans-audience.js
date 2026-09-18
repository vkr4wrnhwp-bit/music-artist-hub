/* The Audience screen's three behaviours.

   1. "Import a list" opens the existing list import on this screen.
   2. Region checkboxes really select; Select all and Clear work; the
      selection bar and the first-send step count what is ticked. The
      checkboxes are ordinary form inputs and "Use this selection" is
      rendered enabled, so it submits them to /fans?export=csv even with
      this file absent (an empty selection redirects back to /fans). This
      file only disables it while nothing is ticked.
   3. "How these are measured" shows what each health score is made of.

   Nothing here sends anything, or talks to anything but this page. */
(function () {
  "use strict";

  // 1 - the import panel
  var panel = document.getElementById("au-import");
  function openImport(e) {
    if (!panel) return;             // the Fan CRM tab keeps its import in the page
    if (e) e.preventDefault();
    panel.classList.add("open");
    var target = document.getElementById("import") || panel;
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    var first = panel.querySelector("input, textarea");
    if (first) setTimeout(function () { first.focus({ preventScroll: true }); }, 300);
  }
  document.querySelectorAll("[data-au-import]").forEach(function (a) {
    a.addEventListener("click", openImport);
  });
  if (panel && location.hash === "#import") panel.classList.add("open");

  // 2 - the selection
  var form = document.getElementById("au-sel");
  if (form) {
    var boxes = Array.prototype.slice.call(form.querySelectorAll('input[name="region"]'));
    var nOut = form.querySelector("[data-au-n]");
    var tagOut = form.querySelector("[data-au-tags]");
    var use = form.querySelector("[data-au-use]");
    var step = document.querySelector("[data-au-step1]");
    var n2 = document.querySelector("[data-au-n2]");
    var ready = document.querySelector("[data-au-ready]");
    var fmt = new Intl.NumberFormat("en-US");

    var update = function () {
      var total = 0, names = [];
      boxes.forEach(function (b) {
        if (b.checked) { total += parseInt(b.getAttribute("data-count"), 10) || 0; names.push(b.getAttribute("data-name")); }
      });
      if (nOut) nOut.textContent = fmt.format(total);
      if (n2) n2.textContent = fmt.format(total);
      if (tagOut) {
        tagOut.hidden = names.length === 0;
        tagOut.textContent = names.length > 3
          ? names.slice(0, 3).join(" · ") + " +" + (names.length - 3) + " more"
          : names.join(" · ");
      }
      if (use) use.disabled = names.length === 0;
      if (step) step.classList.toggle("ready", total > 0);
      if (ready) {
        ready.textContent = total > 0 ? "Ready" : "Pick places";
        ready.classList.toggle("ok", total > 0);
      }
    };
    boxes.forEach(function (b) { b.addEventListener("change", update); });
    var all = form.querySelector("[data-au-all]");
    if (all) all.addEventListener("click", function () {
      boxes.forEach(function (b) { b.checked = true; }); update();
    });
    var clear = form.querySelector("[data-au-clear]");
    if (clear) clear.addEventListener("click", function () {
      boxes.forEach(function (b) { b.checked = false; }); update();
    });
    update();
  }

  // 3 - how the scores are made
  var how = document.querySelector("[data-au-how]");
  var howBody = document.getElementById("au-how");
  if (how && howBody) how.addEventListener("click", function () {
    howBody.hidden = !howBody.hidden;
    how.setAttribute("aria-expanded", howBody.hidden ? "false" : "true");
  });
})();
