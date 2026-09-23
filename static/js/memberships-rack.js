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
   screen, the number statics OUT rather than vanishing: .is-out runs the
   sheet's leave animation for its length, then comes off.

   Without this script a tap still opens Billing, which is a door and not
   a dead end, and a leave is a plain cut. */
(function () {
  "use strict";
  var doors = document.querySelectorAll(".sbrk-door");
  if (!doors.length) { return; }

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
    doors[i].addEventListener("mouseenter", function (ev) { ev.currentTarget.classList.remove("is-out"); });
    doors[i].addEventListener("mouseleave", function (ev) { out(ev.currentTarget); });
    doors[i].addEventListener("blur", function (ev) { out(ev.currentTarget); });
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
