"""Vistas de vacaciones."""

from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.constantes import RolUsuario, EstadoSolicitudVacaciones
from app.modelos import Empleado, SolicitudVacaciones
from app.utilidades.predicados import (
    es_administrador_o_superior,
    obtener_id_empleado_actual,
    puede_gestionar_empleado,
    roles_permitidos,
)
from app.vacaciones.formularios import (
    FormularioResolverVacaciones,
    FormularioSolicitudVacaciones,
    FormularioVacacionesManual,
)
from app.vacaciones.servicios import (
    aprobar_solicitud,
    crear_solicitud,
    marcar_disfrutadas_pasadas,
    rechazar_solicitud,
)

vacaciones_bp = Blueprint(
    "vacaciones_bp",
    __name__,
    url_prefix="/vacaciones",
    template_folder="../plantillas/vacaciones",
)


@vacaciones_bp.route("/mis-vacaciones", methods=["GET", "POST"])
@login_required
def mis_vacaciones():
    emp_id = obtener_id_empleado_actual()
    if not emp_id:
        flash("Sin empleado asociado.", "peligro")
        return redirect(url_for("inicio_bp.panel"))

    lista = (
        SolicitudVacaciones.query.filter_by(empleado_id=emp_id)
        .order_by(SolicitudVacaciones.fecha_inicio.desc())
        .all()
    )
    formulario = FormularioSolicitudVacaciones()
    if formulario.validate_on_submit():
        sol = crear_solicitud(
            emp_id,
            formulario.fecha_inicio.data,
            formulario.fecha_fin.data,
            formulario.notas.data,
        )
        if sol:
            flash("Solicitud registrada.", "exito")
        else:
            flash("Hay solape con otras vacaciones o fechas inválidas.", "peligro")
        return redirect(url_for("vacaciones_bp.mis_vacaciones"))

    return render_template(
        "mis_vacaciones.html",
        solicitudes=lista,
        formulario=formulario,
    )


@vacaciones_bp.route("/calendario")
@login_required
def calendario_simple():
    """Vista mensual muy simple (lista por semanas)."""
    emp_id = obtener_id_empleado_actual()
    if not emp_id and not es_administrador_o_superior():
        flash("Sin acceso.", "peligro")
        return redirect(url_for("inicio_bp.panel"))

    if emp_id:
        consulta = SolicitudVacaciones.query.filter_by(empleado_id=emp_id)
    else:
        consulta = SolicitudVacaciones.query

    from calendar import monthrange

    mes = request.args.get("mes", type=int) or date.today().month
    anio = request.args.get("anio", type=int) or date.today().year
    desde = date(anio, mes, 1)
    ult = monthrange(anio, mes)[1]
    hasta = date(anio, mes, ult)

    lista = (
        consulta.filter(
            SolicitudVacaciones.fecha_inicio <= hasta,
            SolicitudVacaciones.fecha_fin >= desde,
        )
        .order_by(SolicitudVacaciones.fecha_inicio)
        .all()
    )
    return render_template(
        "calendario.html",
        solicitudes=lista,
        mes=mes,
        anio=anio,
    )


@vacaciones_bp.route("/admin")
@login_required
@roles_permitidos(
    RolUsuario.SUPERADMINISTRADOR,
    RolUsuario.ADMINISTRADOR_EMPRESA,
)
def listado_admin():
    marcar_disfrutadas_pasadas()
    pendientes = (
        SolicitudVacaciones.query.filter_by(
            estado=EstadoSolicitudVacaciones.PENDIENTE
        )
        .order_by(SolicitudVacaciones.solicitado_en.desc())
        .all()
    )
    form_manual = FormularioVacacionesManual()
    form_manual.empleado_id.choices = [
        (e.id, e.nombre_completo) for e in Empleado.query.filter_by(activo=True).all()
    ]
    if form_manual.validate_on_submit():
        sol = crear_solicitud(
            form_manual.empleado_id.data,
            form_manual.fecha_inicio.data,
            form_manual.fecha_fin.data,
            form_manual.notas.data,
            estado_inicial=EstadoSolicitudVacaciones.APROBADO,
        )
        if sol:
            from app.modelos import Empleado as EmpModel

            emp = EmpModel.query.get(form_manual.empleado_id.data)
            if emp:
                from decimal import Decimal

                dias = float(sol.numero_dias)
                emp.saldo_vacaciones = Decimal(
                    str(float(emp.saldo_vacaciones) - dias)
                )
            sol.aprobado_por_usuario_id = current_user.id
            from app.fichajes.validadores import ahora_servidor

            sol.aprobado_en = ahora_servidor()
            from app.extensiones import db

            db.session.commit()
            flash("Vacaciones registradas y aprobadas.", "exito")
        else:
            flash("No se pudo crear (solape o error).", "peligro")
        return redirect(url_for("vacaciones_bp.listado_admin"))

    return render_template(
        "admin.html",
        pendientes=pendientes,
        form_manual=form_manual,
    )


@vacaciones_bp.route("/admin/<int:solicitud_id>/resolver", methods=["GET", "POST"])
@login_required
@roles_permitidos(
    RolUsuario.SUPERADMINISTRADOR,
    RolUsuario.ADMINISTRADOR_EMPRESA,
)
def resolver(solicitud_id: int):
    sol = SolicitudVacaciones.query.get_or_404(solicitud_id)
    if not puede_gestionar_empleado(sol.empleado_id):
        flash("Sin permiso.", "peligro")
        return redirect(url_for("vacaciones_bp.listado_admin"))

    formulario = FormularioResolverVacaciones()
    if formulario.validate_on_submit():
        if "aprobar" in request.form:
            ok, msg = aprobar_solicitud(solicitud_id, formulario.notas.data)
            flash(msg, "exito" if ok else "peligro")
        elif "rechazar" in request.form:
            ok, msg = rechazar_solicitud(solicitud_id, formulario.notas.data)
            flash(msg, "exito" if ok else "peligro")
        return redirect(url_for("vacaciones_bp.listado_admin"))

    return render_template(
        "resolver.html",
        solicitud=sol,
        formulario=formulario,
    )
