/* One system, eight tools: the lights.

   Two behaviours and nothing else.

   The power-on runs once, when the section is first reached, and then the
   rack is lit and still. The homepage must never change around the person
   reading it, so there is no loop, no idle animation and no second run.

   Pointing at a plate dims the other seven and writes a sentence below the
   rack. Every sentence is read from the markup, so the words live in the
   config beside the rest of the homepage copy rather than in here.

   Anyone who has asked for less motion gets the rack lit from the start:
   the sequence never starts, and the readout still works. */
(function () {
  "use strict";
  var rack = document.getElementById("sbet-rack");
  var readout = document.getElementById("sbet-readout");
  if (!rack || !readout) { return; }

  var units = Array.prototype.slice.call(rack.querySelectorAll(".sbet-unit"));
  if (!units.length) { return; }

  var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var idle = readout.getAttribute("data-idle") || "";

  /* --- the power-on, once ------------------------------------------- */
  function powerOn() {
    units.forEach(function (unit, i) {
      var at = 320 + i * 230;
      window.setTimeout(function () {
        unit.classList.add("is-on", "is-flash");
      }, at);
      window.setTimeout(function () {
        unit.classList.remove("is-flash");
      }, at + 420);
    });
    window.setTimeout(function () {
      rack.classList.remove("is-arming");
      units.forEach(function (u) { u.classList.remove("is-on"); });
    }, 320 + units.length * 230 + 520);
  }

  if (!still && "IntersectionObserver" in window) {
    rack.classList.add("is-arming");
    var watcher = new IntersectionObserver(function (entries) {
      for (var i = 0; i < entries.length; i++) {
        if (entries[i].isIntersecting) {
          watcher.disconnect();
          powerOn();
          return;
        }
      }
    }, { threshold: 0.4 });
    watcher.observe(rack);
  }

  /* --- pointing at one ---------------------------------------------- */
  function say(unit) {
    rack.classList.add("is-focused");
    units.forEach(function (u) { u.classList.toggle("is-picked", u === unit); });

    var opens = unit.getAttribute("data-opens") || "";
    var how = opens === "Credits" ? "Runs on credits"
            : opens === "Soon" ? "Coming soon"
            : "Opens with " + opens;

    var name = document.createElement("b");
    name.textContent = unit.getAttribute("data-name") || "";
    name.style.color = window.getComputedStyle(unit).getPropertyValue("color");
    var what = document.createElement("span");
    what.textContent = " " + (unit.getAttribute("data-desc") || "") + " ";
    var tag = document.createElement("i");
    tag.textContent = how;

    readout.textContent = "";
    readout.appendChild(name);
    readout.appendChild(what);
    readout.appendChild(tag);
  }

  function clear() {
    rack.classList.remove("is-focused");
    units.forEach(function (u) { u.classList.remove("is-picked"); });
    readout.textContent = idle;
  }

  units.forEach(function (unit) {
    unit.addEventListener("mouseenter", function () { say(unit); });
    unit.addEventListener("focus", function () { say(unit); });
    /* Nothing to open: a stranger asking what a tool is must not meet a
       password field, so a press just says what it is. */
    unit.addEventListener("click", function (e) { e.preventDefault(); say(unit); });
  });
  rack.addEventListener("mouseleave", clear);
  rack.addEventListener("focusout", function (e) {
    if (!rack.contains(e.relatedTarget)) { clear(); }
  });
})();
