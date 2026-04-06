"""Vistas de gestión de empleados."""

from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from app.constantes import RolUsuario
from app.empleados.calendario_servicios import (
    aplicar_clasificacion_dia,
    construir_calendario_mes,
)
from app.empleados.formularios import (
    FormularioClasificacionDia,
    FormularioEmpleado,
    FormularioEmpleadoSuperadmin,
)
from app.empleados.servicios import (
    actualizar_empleado,
    crear_empleado_con_usuario,
    opciones_select_tipo_empleado,
    resumen_mes_actual,
    vacaciones_resumen,
)
from app.modelos import Empleado, Empresa, RegistroJornada, SolicitudCorreccion, Usuario
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


def _empresa_id_para_tipos_empleado(formulario, es_super: bool) -> int | None:
    """Empresa cuyos tipos aplican al desplegable (alta / edición)."""
    if es_super and hasattr(formulario, "empresa_id"):
        if request.method == "POST":
            raw = (request.form.get("empresa_id") or "").strip()
            if raw.isdigit():
                return int(raw)
        pref = request.args.get("empresa_id", type=int)
        if pref:
            return pref
        if formulario.empresa_id.data:
            return formulario.empresa_id.data
        return None
    emp_actual = getattr(current_user, "empleado", None)
    if emp_actual is not None:
        return emp_actual.empresa_id
    return getattr(current_user, "empresa_id", None)


def _choices_responsables():
    """Responsables: usuarios managers (rol responsable) por empresa."""
    q = Usuario.query.filter_by(rol=RolUsuario.RESPONSABLE, activo=True)
    if not es_superadministrador():
        empresa_id = getattr(current_user, "empresa_id", None)
        emp_actual = getattr(current_user, "empleado", None)
        if empresa_id is None and emp_actual is not None:
            empresa_id = emp_actual.empresa_id
        if empresa_id is not None:
            q = q.filter(Usuario.empresa_id == empresa_id)
    opciones = [(0, "— Sin asignar —")]
    for u in q.order_by(Usuario.correo_electronico).all():
        opciones.append((u.id, u.correo_electronico))
    return opciones


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
        cond = [Empleado.responsable_usuario_id == current_user.id]
        emp_id = obtener_id_empleado_actual()
        if emp_id:
            cond.append(Empleado.responsable_id == emp_id)
        lista = (
            Empleado.query.filter(or_(*cond))
            .order_by(Empleado.apellidos, Empleado.nombre)
            .all()
        )
    return render_template("listado.html", empleados=lista)


@empleados_bp.route("/nuevo", methods=["GET", "POST"])
@login_required
@roles_permitidos(
    RolUsuario.SUPERADMINISTRADOR,
    RolUsuario.ADMINISTRADOR_EMPRESA,
    RolUsuario.RESPONSABLE,
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

    eid_tipos = _empresa_id_para_tipos_empleado(
        formulario, es_superadministrador()
    )
    formulario.tipo_empleado.choices = opciones_select_tipo_empleado(eid_tipos, None)

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
                "tipo_empleado": formulario.tipo_empleado.data,
                "responsable_usuario_id": formulario.responsable_id.data
                if formulario.responsable_id.data
                else None,
                "activo": formulario.activo.data,
                "observaciones": formulario.observaciones.data,
                "rol": formulario.rol.data,
            }
            if formulario.responsable_id.data == 0:
                datos["responsable_usuario_id"] = None
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
    hoy = date.today()
    mes = request.args.get("mes", type=int) or hoy.month
    anio = request.args.get("anio", type=int) or hoy.year
    puede_editar_calendario = (
        current_user.rol != RolUsuario.EMPLEADO
        and puede_gestionar_empleado(empleado_id)
    )
    calendario_mes = construir_calendario_mes(
        emp.id,
        mes,
        anio,
        puede_editar=puede_editar_calendario,
    )
    form_clasificacion = FormularioClasificacionDia()
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
        calendario_mes=calendario_mes,
        form_clasificacion=form_clasificacion,
        puede_editar_calendario=puede_editar_calendario,
        incidencias=incidencias,
        ultimos_fichajes=ultimos_fichajes,
    )


@empleados_bp.route("/<int:empleado_id>/clasificar-dia", methods=["POST"])
@login_required
@roles_permitidos(
    RolUsuario.SUPERADMINISTRADOR,
    RolUsuario.ADMINISTRADOR_EMPRESA,
    RolUsuario.RESPONSABLE,
)
def clasificar_dia_guardar(empleado_id: int):
    if not puede_gestionar_empleado(empleado_id):
        flash("Sin acceso.", "peligro")
        return redirect(url_for("inicio_bp.panel"))

    form = FormularioClasificacionDia()
    if form.validate_on_submit():
        try:
            f = date.fromisoformat(form.fecha_iso.data.strip())
        except ValueError:
            flash("Fecha no válida.", "peligro")
            return redirect(
                url_for("empleados_bp.detalle", empleado_id=empleado_id)
            )
        ok, msg = aplicar_clasificacion_dia(
            empleado_id,
            f,
            form.tipo.data,
            form.motivo.data,
            current_user.id,
        )
        flash(msg, "exito" if ok else "peligro")
        return redirect(
            url_for(
                "empleados_bp.detalle",
                empleado_id=empleado_id,
                mes=f.month,
                anio=f.year,
            )
        )

    if form.errors:
        flash(
            "Revise el formulario: "
            + "; ".join(f"{k}: {v}" for k, v in form.errors.items()),
            "peligro",
        )
    else:
        flash("Revise el formulario.", "peligro")
    return redirect(url_for("empleados_bp.detalle", empleado_id=empleado_id))


@empleados_bp.route("/<int:empleado_id>/editar", methods=["GET", "POST"])
@login_required
@roles_permitidos(
    RolUsuario.SUPERADMINISTRADOR,
    RolUsuario.ADMINISTRADOR_EMPRESA,
    RolUsuario.RESPONSABLE,
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
    formulario.responsable_id.choices = _choices_responsables()
    if es_superadministrador() and hasattr(formulario, "empresa_id"):
        formulario.empresa_id.choices = [
            (e.id, e.nombre) for e in Empresa.query.order_by(Empresa.nombre).all()
        ]
    formulario.tipo_empleado.choices = opciones_select_tipo_empleado(
        emp.empresa_id, emp.tipo_empleado
    )

    if request.method == "GET":
        formulario.saldo_vacaciones.data = emp.saldo_vacaciones
        formulario.responsable_id.data = emp.responsable_usuario_id or 0
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
            "tipo_empleado": formulario.tipo_empleado.data,
            "responsable_usuario_id": formulario.responsable_id.data
            if formulario.responsable_id.data
            else None,
            "activo": formulario.activo.data,
            "observaciones": formulario.observaciones.data,
            "rol": formulario.rol.data,
        }
        if formulario.responsable_id.data == 0:
            datos["responsable_usuario_id"] = None
        if es_superadministrador() and hasattr(formulario, "empresa_id"):
            datos["empresa_id"] = formulario.empresa_id.data
        pwd = (formulario.contrasena.data or "").strip() or None
        try:
            actualizar_empleado(emp, datos, pwd)
        except ValueError as e:
            flash(str(e), "peligro")
        else:
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
