"""Panel principal tras autenticación."""

from datetime import date, timedelta

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from app.constantes import RolUsuario
from app.empleados.calendario_servicios import aplicar_clasificacion_dia
from app.inicio.calendario_equipo_servicios import (
    construir_calendario_equipo_mes,
    construir_calendario_equipo_semana,
    detalle_dia_equipo_json,
    empleados_alcance_panel,
    lunes_semana_conteniendo,
)
from app.inicio.servicios import (
    inicio_dia_local,
    resumen_equipo_para_empleados,
    resumen_panel_administrador,
    resumen_panel_empleado,
)
from app.utilidades.predicados import (
    modulo_planificacion_habilitado,
    puede_gestionar_empleado,
    roles_dashboard_admin,
)

inicio_bp = Blueprint(
    "inicio_bp",
    __name__,
    template_folder="../plantillas/inicio",
)


@inicio_bp.route("/")
def raiz():
    """Redirige al panel o al login."""
    from flask import redirect, url_for

    if current_user.is_authenticated:
        return redirect(url_for("inicio_bp.panel"))
    return redirect(url_for("autenticacion_bp.iniciar_sesion"))


@inicio_bp.route("/panel")
@login_required
def panel():
    """Dashboard según rol."""
    rol = current_user.rol
    es_admin = rol in roles_dashboard_admin()
    datos_admin = None
    datos_empleado = None
    calendario_equipo = None
    cal_vista = "semana"
    hoy = inicio_dia_local()
    mes_incluye_hoy = False
    semana_incluye_hoy = False
    resumen_equipo: list[dict] = []
    vista_equipo = "dia"
    equipo_vista_cal = "calendario"
    solo_hoy = request.args.get("solo_hoy", "0") == "1"

    if es_admin and rol != RolUsuario.EMPLEADO:
        datos_admin = resumen_panel_administrador()
        empleados_cal = empleados_alcance_panel()
        vista_equipo = request.args.get("vista_equipo", "dia")
        if vista_equipo not in ("dia", "semana", "mes"):
            vista_equipo = "dia"
        resumen_equipo = resumen_equipo_para_empleados(empleados_cal, vista_equipo)
        equipo_vista_cal = request.args.get("equipo_vista_cal", "calendario")
        if equipo_vista_cal not in ("calendario", "lista"):
            equipo_vista_cal = "calendario"
        cal_vista = request.args.get("cal_vista", "semana")
        if cal_vista not in ("mes", "semana"):
            cal_vista = "semana"
        if solo_hoy:
            # Modo control diario: centra siempre en la semana de hoy.
            cal_vista = "semana"
        if cal_vista == "mes":
            mes = request.args.get("mes", type=int) or hoy.month
            anio = request.args.get("anio", type=int) or hoy.year
            calendario_equipo = construir_calendario_equipo_mes(
                anio, mes, empleados_cal
            )
        else:
            sem_raw = request.args.get("semana")
            if sem_raw:
                try:
                    ref = date.fromisoformat(sem_raw[:10])
                except ValueError:
                    ref = hoy
            else:
                ref = hoy
            lunes = lunes_semana_conteniendo(ref)
            calendario_equipo = construir_calendario_equipo_semana(
                lunes, empleados_cal
            )

        if calendario_equipo:
            if cal_vista == "mes":
                mes_incluye_hoy = (
                    calendario_equipo["anio"] == hoy.year
                    and calendario_equipo["mes"] == hoy.month
                )
            else:
                lu = calendario_equipo["lunes"]
                semana_incluye_hoy = lu <= hoy <= lu + timedelta(days=6)

    emp = getattr(current_user, "empleado", None)
    if emp:
        datos_empleado = resumen_panel_empleado(emp.id)

    return render_template(
        "panel.html",
        datos_admin=datos_admin,
        datos_empleado=datos_empleado,
        es_admin_vista=es_admin,
        cal_vista=cal_vista,
        calendario_equipo=calendario_equipo,
        resumen_equipo=resumen_equipo,
        vista_equipo=vista_equipo,
        equipo_vista_cal=equipo_vista_cal,
        solo_hoy=solo_hoy,
        hoy_iso=hoy.isoformat(),
        weekday_hoy=hoy.weekday(),
        mes_incluye_hoy=mes_incluye_hoy,
        semana_incluye_hoy=semana_incluye_hoy,
        planificacion_habilitada=modulo_planificacion_habilitado(),
    )


@inicio_bp.route("/panel/api/dia-equipo/<fecha_iso>")
@login_required
def api_dia_equipo(fecha_iso: str):
    """Detalle JSON de un día para el modal del calendario de equipo."""
    if current_user.rol not in roles_dashboard_admin():
        return jsonify({"error": "Sin permiso."}), 403
    try:
        f = date.fromisoformat(fecha_iso[:10])
    except ValueError:
        return jsonify({"error": "Fecha no válida."}), 400
    empleados = empleados_alcance_panel()
    return jsonify(detalle_dia_equipo_json(f, empleados))


@inicio_bp.route("/panel/marcar-hoy/<int:empleado_id>", methods=["POST"])
@login_required
def marcar_hoy_rapido(empleado_id: int):
    """Acción rápida en panel: clasificar hoy para empleados sin fichaje."""
    if current_user.rol not in roles_dashboard_admin():
        return jsonify({"error": "Sin permiso."}), 403
    if not puede_gestionar_empleado(empleado_id):
        return jsonify({"error": "Sin permiso sobre ese empleado."}), 403

    tipo = (request.form.get("tipo") or "").strip()
    if tipo not in {
        "vacaciones",
        "libre",
        "ausencia_justificada",
        "ausencia_no_justificada",
    }:
        return jsonify({"error": "Tipo no permitido."}), 400

    hoy = inicio_dia_local()
    motivo = (request.form.get("motivo") or "").strip()
    if tipo in {"libre", "ausencia_justificada", "ausencia_no_justificada"} and not motivo:
        from flask import flash, redirect, url_for

        flash("Debe indicar un motivo para esa clasificación.", "peligro")
        destino = request.form.get("next")
        if destino and destino.startswith("/"):
            return redirect(destino)
        return redirect(url_for("inicio_bp.panel", vista_equipo="dia"))

    ok, msg = aplicar_clasificacion_dia(
        empleado_id,
        hoy,
        tipo,
        motivo if tipo in {"libre", "ausencia_justificada", "ausencia_no_justificada"} else None,
        current_user.id,
    )

    from flask import flash, redirect, url_for

    flash(msg, "exito" if ok else "peligro")
    destino = request.form.get("next")
    if destino and destino.startswith("/"):
        return redirect(destino)
    return redirect(url_for("inicio_bp.panel", vista_equipo="dia"))
