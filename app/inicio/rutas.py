"""Panel principal tras autenticación."""

from flask import Blueprint, render_template
from flask_login import current_user, login_required

from app.constantes import RolUsuario
from app.inicio.servicios import (
    resumen_equipo_admin,
    resumen_panel_administrador,
    resumen_panel_empleado,
)
from app.utilidades.predicados import modulo_planificacion_habilitado, roles_dashboard_admin

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
    from flask import request

    rol = current_user.rol
    es_admin = rol in roles_dashboard_admin()
    datos_admin = None
    datos_empleado = None
    vista_equipo = "dia"
    resumen_equipo = []

    if es_admin and rol != RolUsuario.EMPLEADO:
        vista_equipo = request.args.get("vista", "dia")
        if vista_equipo not in ("dia", "semana", "mes"):
            vista_equipo = "dia"
        datos_admin = resumen_panel_administrador()
        resumen_equipo = resumen_equipo_admin(vista_equipo)

    emp = getattr(current_user, "empleado", None)
    if emp:
        datos_empleado = resumen_panel_empleado(emp.id)

    return render_template(
        "panel.html",
        datos_admin=datos_admin,
        datos_empleado=datos_empleado,
        es_admin_vista=es_admin,
        vista_equipo=vista_equipo,
        resumen_equipo=resumen_equipo,
        planificacion_habilitada=modulo_planificacion_habilitado(),
    )
