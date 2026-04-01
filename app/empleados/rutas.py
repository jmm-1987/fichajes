"""Vistas de gestión de empleados."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.constantes import RolUsuario
from app.empleados.formularios import FormularioEmpleado, FormularioEmpleadoSuperadmin
from app.empleados.servicios import (
    actualizar_empleado,
    crear_empleado_con_usuario,
    resumen_mes_actual,
    vacaciones_resumen,
)
from app.modelos import Empleado, Empresa, RegistroJornada, SolicitudCorreccion
from app.utilidades.predicados import (
    es_superadministrador,
    obtener_id_empleado_actual,
    puede_gestionar_empleado,
    roles_permitidos,
)

empleados_bp = Blueprint(
    "empleados_bp",
    __name__,
    url_prefix="/empleados",
    template_folder="../plantillas/empleados",
)


def _choices_responsables(excluir_id: int | None = None):
    q = Empleado.query.filter_by(activo=True)
    # Filtrar por empresa del usuario actual (salvo superadmin que puede ver todas)
    if not es_superadministrador():
        emp_actual = getattr(current_user, "empleado", None)
        if emp_actual:
            q = q.filter(Empleado.empresa_id == emp_actual.empresa_id)
    if excluir_id:
        q = q.filter(Empleado.id != excluir_id)
    return [(0, "— Sin asignar —")] + [(e.id, e.nombre_completo) for e in q.all()]


@empleados_bp.route("/")
@login_required
@roles_permitidos(
    RolUsuario.SUPERADMINISTRADOR,
    RolUsuario.ADMINISTRADOR_EMPRESA,
    RolUsuario.RESPONSABLE,
)
def listado():
    if es_superadministrador():
        lista = Empleado.query.order_by(Empleado.apellidos, Empleado.nombre).all()
    elif current_user.rol == RolUsuario.ADMINISTRADOR_EMPRESA:
        emp_actual = getattr(current_user, "empleado", None)
        q = Empleado.query
        if emp_actual:
            q = q.filter(Empleado.empresa_id == emp_actual.empresa_id)
        lista = q.order_by(Empleado.apellidos, Empleado.nombre).all()
    else:
        emp_id = obtener_id_empleado_actual()
        lista = Empleado.query.filter_by(responsable_id=emp_id).all()
    return render_template("listado.html", empleados=lista)


@empleados_bp.route("/nuevo", methods=["GET", "POST"])
@login_required
@roles_permitidos(
    RolUsuario.SUPERADMINISTRADOR,
    RolUsuario.ADMINISTRADOR_EMPRESA,
)
def nuevo():
    ClaseForm = (
        FormularioEmpleadoSuperadmin
        if es_superadministrador()
        else FormularioEmpleado
    )
    formulario = ClaseForm()
    formulario.responsable_id.choices = _choices_responsables()
    if es_superadministrador() and hasattr(formulario, "empresa_id"):
        formulario.empresa_id.choices = [
            (e.id, e.nombre) for e in Empresa.query.order_by(Empresa.nombre).all()
        ]
        empresa_pref = request.args.get("empresa_id", type=int)
        if empresa_pref:
            formulario.empresa_id.data = empresa_pref

    rol_pref = request.args.get("rol")
    if rol_pref in [
        RolUsuario.EMPLEADO,
        RolUsuario.RESPONSABLE,
        RolUsuario.ADMINISTRADOR_EMPRESA,
        RolUsuario.SUPERADMINISTRADOR,
    ]:
        formulario.rol.data = rol_pref

    if formulario.validate_on_submit():
        try:
            datos = {
                "correo_electronico": formulario.correo_electronico.data,
                "codigo_empleado": formulario.codigo_empleado.data,
                "nombre": formulario.nombre.data,
                "apellidos": formulario.apellidos.data,
                "telefono": formulario.telefono.data,
                "documento_identidad": formulario.documento_identidad.data,
                "fecha_alta": formulario.fecha_alta.data,
                "horas_semanales": formulario.horas_semanales.data,
                "vacaciones_anuales": formulario.vacaciones_anuales.data,
                "saldo_vacaciones": formulario.saldo_vacaciones.data,
                "tipo_contrato": formulario.tipo_contrato.data,
                "centro_trabajo": formulario.centro_trabajo.data,
                "responsable_id": formulario.responsable_id.data
                if formulario.responsable_id.data
                else None,
                "activo": formulario.activo.data,
                "observaciones": formulario.observaciones.data,
                "rol": formulario.rol.data,
            }
            if formulario.responsable_id.data == 0:
                datos["responsable_id"] = None
            if es_superadministrador() and hasattr(formulario, "empresa_id"):
                datos["empresa_id"] = formulario.empresa_id.data
            crear_empleado_con_usuario(
                datos,
                formulario.contrasena.data,
                formulario.rol.data,
            )
            flash("Empleado creado.", "exito")
            return redirect(url_for("empleados_bp.listado"))
        except ValueError as e:
            flash(str(e), "peligro")

    return render_template("formulario.html", formulario=formulario, titulo="Nuevo empleado")


@empleados_bp.route("/<int:empleado_id>")
@login_required
def detalle(empleado_id: int):
    if not puede_gestionar_empleado(empleado_id):
        flash("Sin acceso.", "peligro")
        return redirect(url_for("inicio_bp.panel"))

    emp = Empleado.query.get_or_404(empleado_id)
    resumen = resumen_mes_actual(emp.id)
    vac = vacaciones_resumen(emp)
    incidencias = (
        SolicitudCorreccion.query.filter_by(empleado_id=emp.id)
        .order_by(SolicitudCorreccion.creado_en.desc())
        .limit(10)
        .all()
    )
    ultimos_fichajes = (
        RegistroJornada.query.filter_by(empleado_id=emp.id)
        .order_by(RegistroJornada.fecha_hora_servidor.desc())
        .limit(15)
        .all()
    )
    return render_template(
        "detalle.html",
        empleado=emp,
        resumen_mes=resumen,
        vacaciones=vac,
        incidencias=incidencias,
        ultimos_fichajes=ultimos_fichajes,
    )


@empleados_bp.route("/<int:empleado_id>/editar", methods=["GET", "POST"])
@login_required
@roles_permitidos(
    RolUsuario.SUPERADMINISTRADOR,
    RolUsuario.ADMINISTRADOR_EMPRESA,
)
def editar(empleado_id: int):
    emp = Empleado.query.get_or_404(empleado_id)
    if not puede_gestionar_empleado(empleado_id):
        flash("Sin acceso.", "peligro")
        return redirect(url_for("empleados_bp.listado"))

    ClaseForm = (
        FormularioEmpleadoSuperadmin
        if es_superadministrador()
        else FormularioEmpleado
    )
    formulario = ClaseForm(obj=emp)
    formulario.correo_electronico.data = emp.usuario.correo_electronico
    formulario.rol.data = emp.usuario.rol
    formulario.responsable_id.choices = _choices_responsables(excluir_id=emp.id)
    if es_superadministrador() and hasattr(formulario, "empresa_id"):
        formulario.empresa_id.choices = [
            (e.id, e.nombre) for e in Empresa.query.order_by(Empresa.nombre).all()
        ]

    if request.method == "GET":
        formulario.saldo_vacaciones.data = emp.saldo_vacaciones
        formulario.responsable_id.data = emp.responsable_id or 0
        if es_superadministrador() and hasattr(formulario, "empresa_id"):
            formulario.empresa_id.data = emp.empresa_id

    if formulario.validate_on_submit():
        datos = {
            "correo_electronico": formulario.correo_electronico.data,
            "codigo_empleado": formulario.codigo_empleado.data,
            "nombre": formulario.nombre.data,
            "apellidos": formulario.apellidos.data,
            "telefono": formulario.telefono.data,
            "documento_identidad": formulario.documento_identidad.data,
            "fecha_alta": formulario.fecha_alta.data,
            "horas_semanales": formulario.horas_semanales.data,
            "vacaciones_anuales": formulario.vacaciones_anuales.data,
            "saldo_vacaciones": formulario.saldo_vacaciones.data,
            "tipo_contrato": formulario.tipo_contrato.data,
            "centro_trabajo": formulario.centro_trabajo.data,
            "responsable_id": formulario.responsable_id.data
            if formulario.responsable_id.data
            else None,
            "activo": formulario.activo.data,
            "observaciones": formulario.observaciones.data,
            "rol": formulario.rol.data,
        }
        if formulario.responsable_id.data == 0:
            datos["responsable_id"] = None
        if es_superadministrador() and hasattr(formulario, "empresa_id"):
            datos["empresa_id"] = formulario.empresa_id.data
        pwd = (formulario.contrasena.data or "").strip() or None
        actualizar_empleado(emp, datos, pwd)
        flash("Cambios guardados.", "exito")
        return redirect(url_for("empleados_bp.detalle", empleado_id=emp.id))

    return render_template(
        "formulario.html",
        formulario=formulario,
        titulo=f"Editar {emp.nombre_completo}",
    )


@empleados_bp.route("/mi-ficha")
@login_required
def mi_ficha():
    """El empleado ve solo su resumen (privacidad)."""
    eid = obtener_id_empleado_actual()
    if not eid:
        flash("Sin empleado asociado.", "peligro")
        return redirect(url_for("inicio_bp.panel"))
    return redirect(url_for("empleados_bp.detalle", empleado_id=eid))
