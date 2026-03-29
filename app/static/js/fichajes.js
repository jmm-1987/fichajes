/**
 * Contador en vivo: tiempo transcurrido desde la última entrada (UTC en data-inicio-utc).
 */
(function () {
  var bloque = document.getElementById("bloque-contador-jornada");
  var elTexto = document.getElementById("texto-contador-jornada");
  if (!bloque || !elTexto) return;

  var inicioAttr = bloque.getAttribute("data-inicio-utc");
  if (!inicioAttr) return;

  var inicio = Date.parse(inicioAttr);
  if (Number.isNaN(inicio)) return;

  function dos(n) {
    return n < 10 ? "0" + n : String(n);
  }

  function tick() {
    var ahora = Date.now();
    var diff = Math.max(0, ahora - inicio);
    var totalSeg = Math.floor(diff / 1000);
    var h = Math.floor(totalSeg / 3600);
    var m = Math.floor((totalSeg % 3600) / 60);
    var s = totalSeg % 60;
    elTexto.textContent = dos(h) + ":" + dos(m) + ":" + dos(s);
  }

  tick();
  setInterval(tick, 1000);
})();

/**
 * Geolocalización solo en el momento del envío del formulario de fichaje.
 *
 * Importante: HTMLFormElement.submit() no incluye el botón pulsado. Sin un campo
 * oculto con el mismo name que el botón, Flask-WTF no sabe si era entrada/salida/pausa.
 */
(function () {
  var form = document.getElementById("form-fichar");
  if (!form) return;

  var ultimoBotonSubmit = null;
  form.querySelectorAll('button[type="submit"]').forEach(function (btn) {
    btn.addEventListener("click", function () {
      ultimoBotonSubmit = btn;
    });
  });

  function adjuntarNombreBotonYEnviar(submitter) {
    var btn = submitter || ultimoBotonSubmit;
    if (btn && btn.name) {
      var ya = form.querySelector('input[type="hidden"][data-fichaje-boton="1"]');
      if (ya) ya.remove();
      var h = document.createElement("input");
      h.type = "hidden";
      h.setAttribute("data-fichaje-boton", "1");
      h.name = btn.name;
      h.value = btn.value || "y";
      form.appendChild(h);
    }
    form.submit();
  }

  form.addEventListener("submit", function (ev) {
    var lat = form.querySelector('[name="latitud"]');
    var lon = form.querySelector('[name="longitud"]');
    var prec = form.querySelector('[name="precision_metros"]');
    var marca = form.querySelector('[name="marca_cliente_iso"]');
    if (!lat || !lon || !prec || !marca) return;

    var submitter = ev.submitter || ultimoBotonSubmit;

    if (!navigator.geolocation) {
      marca.value = new Date().toISOString();
      return;
    }

    ev.preventDefault();
    navigator.geolocation.getCurrentPosition(
      function (pos) {
        lat.value = pos.coords.latitude;
        lon.value = pos.coords.longitude;
        prec.value = pos.coords.accuracy != null ? pos.coords.accuracy : "";
        marca.value = new Date().toISOString();
        adjuntarNombreBotonYEnviar(submitter);
      },
      function () {
        marca.value = new Date().toISOString();
        adjuntarNombreBotonYEnviar(submitter);
      },
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 0 }
    );
  });
})();
