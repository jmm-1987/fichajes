/* Interacciones globales ligeras */
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll('[data-bs-dismiss="alert"]').forEach(function (btn) {
    btn.addEventListener("click", function () {
      var a = btn.closest(".alert");
      if (a) a.remove();
    });
  });

  // Dropdown de ayuda tipo "¿Necesitas ayuda?"
  var logoAyuda = document.getElementById("logo-ayuda-toggle");
  var dropdownAyuda = document.getElementById("ayuda-dropdown");
  if (logoAyuda && dropdownAyuda) {
    function toggleAyuda() {
      dropdownAyuda.classList.toggle("hidden");
    }
    logoAyuda.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      toggleAyuda();
    });
    document.addEventListener("click", function (e) {
      if (!dropdownAyuda.classList.contains("hidden")) {
        var dentro = dropdownAyuda.contains(e.target) || logoAyuda.contains(e.target);
        if (!dentro) {
          dropdownAyuda.classList.add("hidden");
        }
      }
    });
  }
});
