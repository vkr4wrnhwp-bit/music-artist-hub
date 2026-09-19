/* One system, eight tools: the lights.

   Three behaviours and nothing else.

   The power-on runs once, when the section is first reached, and then the
   rack is lit and still. The homepage must never change around the person
   reading it, so there is no loop and no idle animation. The only second
   run is one the visitor asks for with "Play the power-on again", which is
   in the owner's artifact and had been left out of the live page.

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
  /* Phones carry the names in a row under each half, in plate order. */
  var names = Array.prototype.slice.call(rack.querySelectorAll(".sbet-names li"));
  var replay = document.getElementById("sbet-replay");
  var timers = [];

  var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var idle = readout.getAttribute("data-idle") || "";

  /* --- the power-on, once ------------------------------------------- */
  function later(fn, at) { timers.push(window.setTimeout(fn, at)); }

  function powerOn() {
    /* A replay pressed mid-sequence starts clean rather than doubling up. */
    timers.forEach(window.clearTimeout);
    timers = [];
    rack.classList.add("is-arming");
    units.forEach(function (u) { u.classList.remove("is-on", "is-flash"); });
    units.forEach(function (unit, i) {
      var at = 320 + i * 230;
      later(function () { unit.classList.add("is-on", "is-flash"); }, at);
      later(function () { unit.classList.remove("is-flash"); }, at + 420);
    });
    later(function () {
      rack.classList.remove("is-arming");
      units.forEach(function (u) { u.classList.remove("is-on"); });
    }, 320 + units.length * 230 + 520);
  }

  /* Without the script there is no sequence to replay, so the button is
     only offered once this has run. */
  if (replay && !still) {
    replay.hidden = false;
    replay.addEventListener("click", powerOn);
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
    /* A quarter in view: stacked on a phone the rack is two rows tall,
       and waiting for 40% of it would light it late. */
    }, { threshold: 0.25 });
    watcher.observe(rack);
  }

  /* --- pointing at one ---------------------------------------------- */
  function say(unit) {
    rack.classList.add("is-focused");
    units.forEach(function (u, i) {
      u.classList.toggle("is-picked", u === unit);
      if (names[i]) { names[i].classList.toggle("is-picked", u === unit); }
    });

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
    names.forEach(function (n) { n.classList.remove("is-picked"); });
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
