/* The membership rack: touch, and the leave.

   The screens are links whose glass is dark until they are pointed at
   (CSS :hover / :focus-visible), when the tier cuts in. Two things CSS
   cannot do alone:

   TOUCH. A finger cannot point, so the FIRST tap on a screen renders the
   tier and the SECOND tap opens it - the same door as a click. No media
   query decides who gets the reveal, because a touchscreen laptop
   without a mouse reports no hover at all (the owner's own machine did,
   2026-09-23), and the reveal is the point of the band.

   THE LEAVE. When the pointer (or the focus, or the touch) leaves a
   screen, the number glitches OUT rather than vanishing: .is-out runs the
   sheet's leave animation for its length, then comes off. Only a screen
   that SHOWED something glitches out: a pointer that only crossed it,
   inside the cut-in's first step (the reading is still at opacity 0 for
   the first tenth of sbrk-assemble's 1.5s), leaves the glass dark - the
   leave animation starts at full opacity and used to flash the whole tier
   on every screen a sweeping pointer crossed (audit, 2026-09-23).

   Without this script a tap still opens Billing, which is a door and not
   a dead end, and a leave is a plain cut. */
(function () {
  "use strict";
  var doors = document.querySelectorAll(".sbrk-door");
  if (!doors.length) { return; }

  /* The first step of sbrk-assemble (split-home.css): 10% of 1.5s at
     opacity 0. A visit shorter than this has shown nothing. */
  var LIT_AFTER_MS = 150;
  function now() { return (window.performance && performance.now) ? performance.now() : Date.now(); }

  function leave(door) {
    var lit = door.classList.contains("is-on") ||
              (door._since !== undefined && now() - door._since >= LIT_AFTER_MS);
    door._since = undefined;
    if (lit) { out(door); return; }
    door.classList.remove("is-on", "is-out");   /* nothing showed: stay dark */
  }

  function arrive(ev) {
    var door = ev.currentTarget;
    door.classList.remove("is-out");
    if (door._since === undefined) { door._since = now(); }
  }

  function out(door) {
    door.classList.remove("is-on");
    door.classList.add("is-out");
    clearTimeout(door._out);
    door._out = setTimeout(function () { door.classList.remove("is-out"); }, 760);
  }

  function clear(except) {
    for (var i = 0; i < doors.length; i++) {
      if (doors[i] !== except && doors[i].classList.contains("is-on")) { out(doors[i]); }
    }
  }

  for (var i = 0; i < doors.length; i++) {
    doors[i].addEventListener("mouseenter", arrive);
    doors[i].addEventListener("focus", arrive);
    doors[i].addEventListener("mouseleave", function (ev) { leave(ev.currentTarget); });
    doors[i].addEventListener("blur", function (ev) { leave(ev.currentTarget); });
    doors[i].addEventListener("touchend", function (ev) {
      var door = ev.currentTarget;
      if (door.classList.contains("is-on")) { return; }   /* second tap: the door opens */
      /* a phone's screens are already rendered (the sheet shows the
         reading under 960px), so there is nothing to reveal: the tap opens */
      var read = door.querySelector(".sbrk-read");
      if (!read || getComputedStyle(read).opacity === "1") { return; }
      ev.preventDefault();                                 /* first tap: the screen renders */
      clear(door);
      door.classList.add("is-on");
    }, { passive: false });
  }

  /* a tap anywhere else puts the static back */
  document.addEventListener("touchend", function (ev) {
    if (!ev.target.closest || !ev.target.closest(".sbrk-door")) { clear(null); }
  }, { passive: true });
})();
