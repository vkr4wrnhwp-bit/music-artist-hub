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
  var looksBox = document.getElementById("sg-looks");
  if (!stage || (!rows.length && !looksBox)) return;

  var out = {
    name: document.getElementById("sg-sel-name"),
    group: document.getElementById("sg-sel-group"),
    intensity: document.getElementById("sg-sel-int"),
    fade: document.getElementById("sg-sel-fade"),
    swatch: document.getElementById("sg-sel-swatch")
  };

  function show(row) {
    paint({
      colour: row.getAttribute("data-colour") || "#d8b25a",
      intensity: parseInt(row.getAttribute("data-intensity"), 10),
      name: row.getAttribute("data-name") || "",
      group: row.getAttribute("data-group") || "",
      fade: row.getAttribute("data-fade") || "0"
    });
    for (var i = 0; i < rows.length; i++) rows[i].classList.remove("is-on");
    row.classList.add("is-on");
  }

  function paint(look) {
    var colour = look.colour || "#d8b25a";
    var level = look.intensity;
    if (isNaN(level) || level === null || level === undefined) level = 100;

    /* One colour on the svg: every fixture inherits it, and the beam
       gradient is currentColor, so bar and beam move together. Intensity
       dims rather than re-tints - a 30% look is the same gel, lower. */
    stage.style.color = colour;
    stage.style.setProperty("--sg-dim", String(level / 100));

    if (out.name) out.name.textContent = look.name || "";
    if (out.group) out.group.textContent = look.group || "";
    if (out.intensity) out.intensity.textContent = level + "%";
    if (out.fade) out.fade.textContent = (look.fade || "0") + "s";
    if (out.swatch) out.swatch.style.background = colour;
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

  /* The Plot / Rig / Both toggle. One stage, two layers - the rig's bars
     where they were dragged, the plot's items where the designer put them.
     Both is the default because the whole point of one drawing is seeing
     them together. */
  var layers = document.querySelectorAll("[data-sg-layer]");
  var groups = document.querySelectorAll("[data-sg-layer-g]");
  function layer(which) {
    for (var i = 0; i < groups.length; i++) {
      var key = groups[i].getAttribute("data-sg-layer-g");
      groups[i].style.display = (which === "both" || which === key) ? "" : "none";
    }
    for (var j = 0; j < layers.length; j++) {
      var on = layers[j].getAttribute("data-sg-layer") === which;
      layers[j].classList.toggle("is-on", on);
      layers[j].setAttribute("aria-pressed", on ? "true" : "false");
    }
  }
  for (var k = 0; k < layers.length; k++) {
    (function (btn) {
      btn.setAttribute("aria-pressed", btn.classList.contains("is-on") ? "true" : "false");
      btn.addEventListener("click", function () {
        layer(btn.getAttribute("data-sg-layer"));
      });
    })(layers[k]);
  }

  /* With nothing programmed there is nothing to click, and a rig you cannot
     touch is the black box the owner kept finding. These are the Light
     Studio's OWN looks, read from the engine that defines them
     (lights-engine.js LOOKS) rather than copied here, so the room can never
     drift from the studio's palette. They are labelled as the studio's, not
     as the artist's cues. */
  if (looksBox && !rows.length && window.LightsEngine && window.LightsEngine.LOOKS) {
    window.LightsEngine.LOOKS.forEach(function (look) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "sg-look";
      b.setAttribute("aria-label", "Show " + look.name + " on the rig above");
      var sw = document.createElement("i");
      sw.style.background = look.color;
      b.appendChild(sw);
      b.appendChild(document.createTextNode(look.name));
      b.addEventListener("click", function () {
        paint({colour: look.color, intensity: look.intensity,
               name: look.name, group: "all", fade: String(look.fade)});
        var all = looksBox.querySelectorAll(".sg-look");
        for (var i = 0; i < all.length; i++) all[i].classList.remove("is-on");
        b.classList.add("is-on");
      });
      looksBox.appendChild(b);
    });
  }
})();
