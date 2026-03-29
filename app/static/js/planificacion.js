/**
 * Drag & drop visual: resalta celdas al arrastrar empleados (UX).
 */
(function () {
  var lista = document.getElementById("lista-empleados-plan");
  if (!lista) return;

  lista.querySelectorAll(".empleado-chip").forEach(function (chip) {
    chip.addEventListener("dragstart", function () {
      chip.classList.add("opacity-50");
    });
    chip.addEventListener("dragend", function () {
      chip.classList.remove("opacity-50");
    });
  });

  document.querySelectorAll(".celda-plan").forEach(function (celda) {
    celda.addEventListener("dragover", function (e) {
      e.preventDefault();
      celda.classList.add("bg-light");
    });
    celda.addEventListener("dragleave", function () {
      celda.classList.remove("bg-light");
    });
    celda.addEventListener("drop", function (e) {
      e.preventDefault();
      celda.classList.remove("bg-light");
    });
  });
})();
