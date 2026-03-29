/* Interacciones globales ligeras */
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll('[data-bs-dismiss="alert"]').forEach(function (btn) {
    btn.addEventListener("click", function () {
      var a = btn.closest(".alert");
      if (a) a.remove();
    });
  });
});
