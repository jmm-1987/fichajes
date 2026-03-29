"""Vistas del módulo de planificación (activable por configuración)."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.constantes import RolUsuario
from app.modelos import Empleado, PlanificacionSemanal, PlantillaPlanificacion
from app.planificacion.formularios import (
    FormularioDuplicarSemana,
    FormularioNuevaSemana,
    FormularioPlantilla,
)
from app.planificacion.servicios import (
    aplicar_plantilla_a_plan,
    crear_planificacion_vacia,
    crear_plantilla_desde_plan,
    duplicar_semana,
    upsert_celda,
)
from app.utilidades.predicados import modulo_planificacion_habilitado, roles_permitidos

planificacion_bp = Blueprint(
    "planificacion_bp",
    __name__,
    url_prefix="/planificacion",
    template_folder="../plantillas/planificacion",
)


def _exigir_modulo():
    if not modulo_planificacion_habilitado():
        abort(404)


@planificacion_bp.before_request
def antes_de_peticion():
    _exigir_modulo()


@planificacion_bp.route("/")
@login_required
@roles_permitidos(
    RolUsuario.SUPERADMINISTRADOR,
    RolUsuario.ADMINISTRADOR_EMPRESA,
    RolUsuario.RESPONSABLE,
)
def indice():
    planes = (
        PlanificacionSemanal.query.order_by(
            PlanificacionSemanal.inicio_semana.desc()
        )
        .limit(20)
        .all()
    )
    plantillas = PlantillaPlanificacion.query.filter_by(activo=True).all()
    form_nueva = FormularioNuevaSemana()
    return render_template(
        "planificacion/indice.html",
        planes=planes,
        plantillas=plantillas,
        form_nueva=form_nueva,
    )


@planificacion_bp.route("/nueva", methods=["POST"])
@login_required
@roles_permitidos(
    RolUsuario.SUPERADMINISTRADOR,
    RolUsuario.ADMINISTRADOR_EMPRESA,
)
def nueva_semana():
    form = FormularioNuevaSemana()
    if form.validate_on_submit():
        crear_planificacion_vacia(
            form.inicio_semana.data,
            current_user.id,
            form.notas.data,
        )
        flash("Planificación creada.", "exito")
    return redirect(url_for("planificacion_bp.indice"))


@planificacion_bp.route("/<int:plan_id>/tablero", methods=["GET", "POST"])
@login_required
@roles_permitidos(
    RolUsuario.SUPERADMINISTRADOR,
    RolUsuario.ADMINISTRADOR_EMPRESA,
    RolUsuario.RESPONSABLE,
)
def tablero(plan_id: int):
    plan = PlanificacionSemanal.query.get_or_404(plan_id)
    empleados = Empleado.query.filter_by(activo=True).order_by(Empleado.apellidos).all()
    plantillas = PlantillaPlanificacion.query.filter_by(activo=True).all()
    mapa_celdas = {
        (it.empleado_id, it.dia_semana): it for it in plan.items
    }
    form_dup = FormularioDuplicarSemana()
    form_plant = FormularioPlantilla()

    if request.method == "POST":
        empleado_id = request.form.get("empleado_id", type=int)
        dia = request.form.get("dia_semana", type=int)
        if empleado_id is not None and dia is not None:
            from datetime import datetime

            hi = request.form.get("hora_inicio")
            hf = request.form.get("hora_fin")
            t_hi = datetime.strptime(hi, "%H:%M").time() if hi else None
            t_hf = datetime.strptime(hf, "%H:%M").time() if hf else None
            upsert_celda(plan_id, empleado_id, dia, t_hi, t_hf)
            flash("Celda actualizada.", "exito")
            return redirect(url_for("planificacion_bp.tablero", plan_id=plan_id))

    return render_template(
        "planificacion/tablero.html",
        plan=plan,
        empleados=empleados,
        plantillas=plantillas,
        mapa_celdas=mapa_celdas,
        form_dup=form_dup,
        form_plant=form_plant,
        dias=["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"],
    )


@planificacion_bp.route("/<int:plan_id>/duplicar", methods=["POST"])
@login_required
@roles_permitidos(
    RolUsuario.SUPERADMINISTRADOR,
    RolUsuario.ADMINISTRADOR_EMPRESA,
)
def duplicar(plan_id: int):
    form = FormularioDuplicarSemana()
    if form.validate_on_submit():
        try:
            duplicar_semana(plan_id, form.nuevo_inicio.data)
            flash("Semana duplicada.", "exito")
        except ValueError as err:
            flash(str(err), "peligro")
    return redirect(url_for("planificacion_bp.indice"))


@planificacion_bp.route("/<int:plan_id>/guardar-plantilla", methods=["POST"])
@login_required
@roles_permitidos(
    RolUsuario.SUPERADMINISTRADOR,
    RolUsuario.ADMINISTRADOR_EMPRESA,
)
def guardar_plantilla(plan_id: int):
    form = FormularioPlantilla()
    if form.validate_on_submit():
        crear_plantilla_desde_plan(
            plan_id,
            form.nombre.data,
            form.descripcion.data,
        )
        flash("Plantilla guardada.", "exito")
    return redirect(url_for("planificacion_bp.tablero", plan_id=plan_id))


@planificacion_bp.route("/<int:plan_id>/aplicar-plantilla/<int:plantilla_id>", methods=["POST"])
@login_required
@roles_permitidos(
    RolUsuario.SUPERADMINISTRADOR,
    RolUsuario.ADMINISTRADOR_EMPRESA,
)
def aplicar_plantilla(plan_id: int, plantilla_id: int):
    aplicar_plantilla_a_plan(plantilla_id, plan_id)
    flash("Plantilla aplicada.", "exito")
    return redirect(url_for("planificacion_bp.tablero", plan_id=plan_id))
