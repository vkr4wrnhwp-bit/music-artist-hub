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
      // sb-keep: the fallback GEL colour for a cue with none saved - data
      // the light designer chose, not chrome (the design-system sweep
      // exempts a marked line).
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
    // sb-keep: same fallback gel, same reason
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

  /* Drag a light. The whole point of the room's stage (owner, 2026-09-22:
     "people could just drag around ... that would just entice them to open
     the light studio").

     It moves the bar and its beam together and it saves NOTHING. A room
     that quietly rewrote the rig would be a second editor with no undo, and
     the foot line says plainly that the Studio is where a show is kept.
     Keyboard works too, because a thing you can drag with a mouse and not
     with the arrow keys is a thing some people simply cannot move. */
  var bars = stage.querySelectorAll("[data-sg-bar]");
  var box = stage.viewBox && stage.viewBox.baseVal;

  function moveBar(bar, dxUser, dyUser) {
    var beam = bar.previousElementSibling;   /* the polygon in the same <g> */
    var x = parseFloat(bar.getAttribute("x")) + dxUser;
    var y = parseFloat(bar.getAttribute("y")) + dyUser;
    /* Kept on the stage: a light dragged into the caption is just lost. */
    x = Math.max(6, Math.min((box ? box.width : 600) - 32, x));
    y = Math.max(6, Math.min((box ? box.height : 300) - 16, y));
    bar.setAttribute("x", x);
    bar.setAttribute("y", y);
    if (beam && beam.tagName.toLowerCase() === "polygon") {
      var pts = beam.getAttribute("points").trim().split(/\s+/).map(function (p) {
        return p.split(",").map(Number);
      });
      if (pts.length === 3) {
        var cx = x + 13, cy = y + 5, down = pts[1][1] > pts[0][1];
        var reach = down ? 190 : -150;
        beam.setAttribute("points",
          cx + "," + cy + " " + (cx - 34) + "," + (cy + reach) + " " +
          (cx + 34) + "," + (cy + reach));
      }
    }
  }

  for (var b = 0; b < bars.length; b++) {
    (function (bar) {
      var dragging = false, lastX = 0, lastY = 0, scale = 1;

      bar.addEventListener("pointerdown", function (e) {
        dragging = true;
        bar.setPointerCapture(e.pointerId);
        var r = stage.getBoundingClientRect();
        scale = (box ? box.width : 600) / (r.width || 1);
        lastX = e.clientX; lastY = e.clientY;
        bar.classList.add("is-held");
        e.preventDefault();
      });
      bar.addEventListener("pointermove", function (e) {
        if (!dragging) return;
        moveBar(bar, (e.clientX - lastX) * scale, (e.clientY - lastY) * scale);
        lastX = e.clientX; lastY = e.clientY;
      });
      function drop(e) {
        if (!dragging) return;
        dragging = false;
        bar.classList.remove("is-held");
        try { bar.releasePointerCapture(e.pointerId); } catch (err) {}
      }
      bar.addEventListener("pointerup", drop);
      bar.addEventListener("pointercancel", drop);

      bar.addEventListener("keydown", function (e) {
        var step = e.shiftKey ? 20 : 6, dx = 0, dy = 0;
        if (e.key === "ArrowLeft") dx = -step;
        else if (e.key === "ArrowRight") dx = step;
        else if (e.key === "ArrowUp") dy = -step;
        else if (e.key === "ArrowDown") dy = step;
        else return;
        e.preventDefault();
        moveBar(bar, dx, dy);
      });
    })(bars[b]);
  }
})();
