/* The membership rack: touch.

   The screens are links whose glass shows CRT static until they are
   pointed at (CSS :hover / :focus-visible). A finger cannot point, so
   here the FIRST tap on a screen clears its static and renders the tier,
   and the SECOND tap opens it - the same door as a click.

   Nothing else. No media query decides who gets the static, because a
   touchscreen laptop without a mouse plugged in reports no hover at all
   (the owner's own machine did, 2026-09-23), and the reveal is the point
   of the band. Without this script a tap still opens Billing, which is a
   door and not a dead end; the reveal is what it adds. */
(function () {
  "use strict";
  var doors = document.querySelectorAll(".sbrk-door");
  if (!doors.length) { return; }

  function clear(except) {
    for (var i = 0; i < doors.length; i++) {
      if (doors[i] !== except) { doors[i].classList.remove("is-on"); }
    }
  }

  for (var i = 0; i < doors.length; i++) {
    doors[i].addEventListener("touchend", function (ev) {
      var door = ev.currentTarget;
      if (door.classList.contains("is-on")) { return; }   /* second tap: the door opens */
      /* a phone's screens are already rendered (the sheet hides the
         static under 760px), so there is nothing to reveal: the tap opens */
      var snow = door.querySelector(".sbrk-static");
      if (!snow || getComputedStyle(snow).display === "none") { return; }
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
