/* Collab Marketplace: the filter pills submit on change, so the Filter
   button (the no-JavaScript fallback) is hidden. */
(function () {
  var forms = document.querySelectorAll("form[data-cm-autosubmit]");
  Array.prototype.forEach.call(forms, function (form) {
    var go = form.querySelector(".cm-fgo");
    if (go) go.hidden = true;
    Array.prototype.forEach.call(form.querySelectorAll("select"), function (sel) {
      sel.addEventListener("change", function () { form.submit(); });
    });
  });
})();
