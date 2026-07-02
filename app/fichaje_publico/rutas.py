"""Blueprints de fichaje público (terminal / código)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)

from app.constantes import OrigenRegistroJornada, TipoRegistroJornada
from app.fichaje_publico.servicios import (
    NOTA_HORA_MANUAL_KIOSK,
    buscar_empleado_por_codigo,
    estado_kiosk_empleado,
    hora_local_empleado_iso,
    puede_fichar_salida_kiosk,
    resolver_hora_fichaje_kiosk,
)
from app.fichajes.servicios import (
    datos_contador_portal_fichaje,
    obtener_registros_dia_ordenados,
    registrar_marca,
)
from app.fichajes.zona_trabajo import fecha_calendario_hoy_para_empleado
from app.utilidades.fechas import formatear_hora_corta

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ConfigKiosk:
    nombre_bp: str
    url_prefix: str
    logo_archivo: str
    logo_alt: str


def _kiosk_habilitado() -> bool:
    return bool(current_app.config.get("HABILITAR_FICHAJE_PUBLICO", True))


def _abort_si_deshabilitado() -> None:
    if not _kiosk_habilitado():
        abort(404)


def crear_blueprint_kiosk(config: ConfigKiosk) -> Blueprint:
    """Crea un blueprint de terminal público con logo y prefijo propios."""
    bp = Blueprint(
        config.nombre_bp,
        __name__,
        url_prefix=config.url_prefix,
        template_folder="../plantillas/fichaje_publico",
    )
    session_key = f"kiosk_emp_{config.nombre_bp}"

    @bp.context_processor
    def _ctx_kiosk():
        return {"kiosk_logo_alt": config.logo_alt}

    def _empleado_sesion_kiosk():
        from app.modelos import Empleado

        eid = session.get(session_key)
        if not eid:
            return None
        emp = Empleado.query.get(eid)
        if not emp or not emp.activo:
            session.pop(session_key, None)
            return None
        return emp

    def _registrar_marca_kiosk(emp, tipo_registro: str):
        usar_manual = request.form.get("usar_hora_manual") == "1"
        hora_txt = request.form.get("hora_manual") or ""
        ts_manual, err_hora = resolver_hora_fichaje_kiosk(
            emp.id, usar_manual, hora_txt, tipo_registro
        )
        if err_hora:
            return None, err_hora

        notas = NOTA_HORA_MANUAL_KIOSK if usar_manual and ts_manual else None
        return registrar_marca(
            empleado_id=emp.id,
            tipo_registro=tipo_registro,
            usuario_id=None,
            origen=OrigenRegistroJornada.PANEL_PUBLICO,
            fecha_hora_servidor=ts_manual,
            notas=notas,
            validar_secuencia=True,
        )

    @bp.route("/logo.png")
    @bp.route("/logo-alditraex.png")
    def logo():
        """Logo del terminal (compat. ruta antigua logo-alditraex.png)."""
        ruta_logo = RAIZ_PROYECTO / config.logo_archivo
        if not ruta_logo.is_file():
            abort(404, description=f"Logo no encontrado: {config.logo_archivo}")
        return send_from_directory(RAIZ_PROYECTO, config.logo_archivo)

    @bp.route("/manifest.webmanifest")
    def manifest():
        _abort_si_deshabilitado()
        contenido = {
            "name": "Control horario - Fichaje",
            "short_name": "Fichaje",
            "description": "Fichaje público rápido desde móvil.",
            "lang": "es-ES",
            "start_url": url_for(f"{config.nombre_bp}.inicio"),
            "scope": url_for(f"{config.nombre_bp}.inicio"),
            "display": "standalone",
            "background_color": "#f8f9fa",
            "theme_color": "#1b3a5c",
            "icons": [
                {
                    "src": url_for("static", filename="img/logo-jm.png"),
                    "sizes": "192x192",
                    "type": "image/png",
                },
                {
                    "src": url_for("static", filename="img/logo-jm-completo.png"),
                    "sizes": "512x512",
                    "type": "image/png",
                },
            ],
        }
        resp = make_response(contenido)
        resp.headers["Content-Type"] = "application/manifest+json"
        return resp

    @bp.route("/sw.js")
    def service_worker():
        _abort_si_deshabilitado()
        return send_from_directory(
            current_app.static_folder,
            "js/sw-fichaje-publico.js",
            mimetype="application/javascript",
        )

    @bp.route("/", methods=["GET", "POST"])
    def inicio():
        _abort_si_deshabilitado()
        if request.method == "POST":
            codigo = (request.form.get("codigo") or "").strip()
            emp = buscar_empleado_por_codigo(codigo)
            if not emp:
                flash("Código no reconocido o empleado inactivo.", "peligro")
                return redirect(url_for(".inicio"))

            est = estado_kiosk_empleado(emp.id)
            if est == "pausa":
                flash(
                    "Tiene una pausa abierta. Cierre la pausa desde el móvil o espere a RRHH "
                    "antes de fichar salida en este terminal.",
                    "aviso",
                )
                return redirect(url_for(".inicio"))

            if est == "fuera":
                session[session_key] = emp.id
                session.permanent = False
                return redirect(url_for(".confirmar_entrada"))

            session[session_key] = emp.id
            session.permanent = False
            return redirect(url_for(".sesion_activa"))

        session.pop(session_key, None)
        return render_template("inicio.html")

    @bp.route("/entrada", methods=["GET", "POST"])
    def confirmar_entrada():
        _abort_si_deshabilitado()
        emp = _empleado_sesion_kiosk()
        if not emp:
            flash("Introduzca su código en la pantalla inicial.", "aviso")
            return redirect(url_for(".inicio"))

        est = estado_kiosk_empleado(emp.id)
        if est != "fuera":
            if est == "dentro":
                return redirect(url_for(".sesion_activa"))
            flash("No puede fichar entrada en este momento.", "peligro")
            return redirect(url_for(".inicio"))

        if request.method == "POST":
            reg, err = _registrar_marca_kiosk(emp, TipoRegistroJornada.ENTRADA)
            if err or not reg:
                flash(err or "No se pudo registrar la entrada.", "peligro")
                return render_template(
                    "confirmar_entrada.html",
                    empleado=emp,
                    hora_actual=hora_local_empleado_iso(emp.id),
                    hora_default=request.form.get("hora_manual")
                    or hora_local_empleado_iso(emp.id),
                    usar_hora_manual_checked=request.form.get("usar_hora_manual")
                    == "1",
                )

            session.pop(session_key, None)
            hoy = fecha_calendario_hoy_para_empleado(emp.id)
            regs = obtener_registros_dia_ordenados(emp.id, hoy)
            cont = datos_contador_portal_fichaje(regs)
            return render_template(
                "entrada_ok.html",
                empleado=emp,
                contador=cont,
                hora_registrada=formatear_hora_corta(reg.fecha_hora_servidor),
                hora_manual=bool(reg.notas and NOTA_HORA_MANUAL_KIOSK in reg.notas),
            )

        return render_template(
            "confirmar_entrada.html",
            empleado=emp,
            hora_actual=hora_local_empleado_iso(emp.id),
            hora_default=hora_local_empleado_iso(emp.id),
            usar_hora_manual_checked=False,
        )

    @bp.route("/sesion", methods=["GET"])
    def sesion_activa():
        _abort_si_deshabilitado()
        emp = _empleado_sesion_kiosk()
        if not emp:
            flash("Introduzca su código en la pantalla inicial.", "aviso")
            return redirect(url_for(".inicio"))

        est = estado_kiosk_empleado(emp.id)
        if est != "dentro" or not puede_fichar_salida_kiosk(emp.id):
            session.pop(session_key, None)
            if est == "pausa":
                flash(
                    "Pausa abierta: use el móvil para fin de pausa o salga desde allí.",
                    "aviso",
                )
            else:
                flash(
                    "La jornada ya está cerrada. Introduzca el código de nuevo.",
                    "aviso",
                )
            return redirect(url_for(".inicio"))

        hoy = fecha_calendario_hoy_para_empleado(emp.id)
        regs = obtener_registros_dia_ordenados(emp.id, hoy)
        cont = datos_contador_portal_fichaje(regs)

        return render_template(
            "sesion_activa.html",
            empleado=emp,
            contador=cont,
            hora_actual=hora_local_empleado_iso(emp.id),
            hora_default=hora_local_empleado_iso(emp.id),
            usar_hora_manual_checked=False,
        )

    @bp.route("/salida", methods=["POST"])
    def fichar_salida():
        _abort_si_deshabilitado()
        emp = _empleado_sesion_kiosk()
        if not emp:
            flash("Sesión caducada. Introduzca el código otra vez.", "peligro")
            return redirect(url_for(".inicio"))

        if not puede_fichar_salida_kiosk(emp.id):
            session.pop(session_key, None)
            flash("No se puede fichar salida en este momento.", "peligro")
            return redirect(url_for(".inicio"))

        reg, err = _registrar_marca_kiosk(emp, TipoRegistroJornada.SALIDA)

        if err or not reg:
            flash(err or "No se pudo registrar la salida.", "peligro")
            return redirect(url_for(".sesion_activa"))

        session.pop(session_key, None)

        return render_template(
            "salida_ok.html",
            empleado=emp,
            hora_registrada=formatear_hora_corta(reg.fecha_hora_servidor),
            hora_manual=bool(reg.notas and NOTA_HORA_MANUAL_KIOSK in reg.notas),
        )

    return bp


fichaje_publico_bp = crear_blueprint_kiosk(
    ConfigKiosk(
        nombre_bp="fichaje_publico_bp",
        url_prefix="/fichaje-publico",
        logo_archivo="logoalditraex.png",
        logo_alt="Alditraex",
    )
)

fichaje_publico_sfm234r_bp = crear_blueprint_kiosk(
    ConfigKiosk(
        nombre_bp="fichaje_publico_sfm234r_bp",
        url_prefix="/fichaje_publico_sfm234r",
        logo_archivo="logosfm.png",
        logo_alt="SFM",
    )
)
