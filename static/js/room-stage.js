/* The Stage room's cue list, wired to the stage above it.

   Owner, 2026-09-22: the instruments "don't do anything". This is the
   small answer and deliberately so: clicking a cue lights the rig in that
   look. No animation loop, no transport, no invented data - every value
   comes off the row the server already rendered from the saved show.

   The Light Studio itself still owns programming, the song, DMX and the
   phone remote. This is a player for what is on file, not a second editor.

   It degrades honestly: with no script the page is exactly what the server
   drew, lit by the first cue, and the rows are still readable. */
(function () {
  "use strict";

  var stage = document.getElementById("sg-stage");
  var rows = document.querySelectorAll("[data-sg-cue]");
  if (!stage || !rows.length) return;

  var out = {
    name: document.getElementById("sg-sel-name"),
    group: document.getElementById("sg-sel-group"),
    intensity: document.getElementById("sg-sel-int"),
    fade: document.getElementById("sg-sel-fade"),
    swatch: document.getElementById("sg-sel-swatch")
  };

  function show(row) {
    var colour = row.getAttribute("data-colour") || "#d8b25a";
    var level = parseInt(row.getAttribute("data-intensity"), 10);
    if (isNaN(level)) level = 100;

    /* One colour on the svg: every fixture inherits it, and the beam
       gradient is currentColor, so bar and beam move together. Intensity
       dims rather than re-tints - a 30% look is the same gel, lower. */
    stage.style.color = colour;
    stage.style.setProperty("--sg-dim", String(level / 100));

    if (out.name) out.name.textContent = row.getAttribute("data-name") || "";
    if (out.group) out.group.textContent = row.getAttribute("data-group") || "";
    if (out.intensity) out.intensity.textContent = level + "%";
    if (out.fade) out.fade.textContent = (row.getAttribute("data-fade") || "0") + "s";
    if (out.swatch) out.swatch.style.background = colour;

    for (var i = 0; i < rows.length; i++) rows[i].classList.remove("is-on");
    row.classList.add("is-on");
  }

  for (var i = 0; i < rows.length; i++) {
    (function (row) {
      row.addEventListener("click", function () { show(row); });
      /* A row is a button, so it answers the keys a button answers to. */
      row.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " " || e.key === "Spacebar") {
          e.preventDefault();
          show(row);
        }
      });
    })(rows[i]);
  }
})();
