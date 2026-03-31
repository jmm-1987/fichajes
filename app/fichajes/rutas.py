"""Vistas de fichajes (empleado móvil y administración)."""

from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.constantes import (
    EstadoRegistroJornada,
    OrigenRegistroJornada,
    RolUsuario,
    TipoRegistroJornada,
)
from app.fichajes.calculos import clasificar_dia
from app.fichajes.formularios import (
    FormularioCorreccionAdmin,
    FormularioFicharMovil,
    FormularioResolverSolicitud,
    FormularioSolicitudCorreccionEmpleado,
)
from app.fichajes.servicios import (
    corregir_registro_admin,
    crear_solicitud_correccion_empleado,
    datos_contador_portal_fichaje,
    obtener_registros_dia_ordenados,
    registrar_marca,
    resolver_solicitud_correccion,
)
from app.modelos import Empleado, RegistroJornada, SolicitudCorreccion
from app.utilidades.fechas import ZONA_MADRID
from app.utilidades.predicados import (
    es_administrador_o_superior,
    obtener_id_empleado_actual,
    puede_gestionar_empleado,
    roles_permitidos,
)

fichajes_bp = Blueprint(
    "fichajes_bp",
    __name__,
    url_prefix="/fichajes",
    template_folder="../plantillas/fichajes",
)


def _parse_cliente_iso(cadena: str | None) -> datetime | None:
    if not cadena:
        return None
    try:
        if cadena.endswith("Z"):
            cadena = cadena.replace("Z", "+00:00")
        return datetime.fromisoformat(cadena)
    except ValueError:
        return None


@fichajes_bp.route("/empleado", methods=["GET", "POST"])
@login_required
def portal_empleado():
    """Pantalla principal de fichaje para móvil."""
    emp_id = obtener_id_empleado_actual()
    if not emp_id:
        flash("Su usuario no tiene empleado asociado.", "peligro")
        return redirect(url_for("inicio_bp.panel"))

    formulario = FormularioFicharMovil()
    if formulario.validate_on_submit():
        tipo = None
        if formulario.enviar_entrada.data:
            tipo = TipoRegistroJornada.ENTRADA
        elif formulario.enviar_salida.data:
            tipo = TipoRegistroJornada.SALIDA
        elif formulario.enviar_pausa_inicio.data:
            tipo = TipoRegistroJornada.PAUSA_INICIO
        elif formulario.enviar_pausa_fin.data:
            tipo = TipoRegistroJornada.PAUSA_FIN
        # Tras geolocalización se usa form.submit(): el botón no viaja; se envía un hidden con el mismo name.
        if tipo is None:
            if request.form.get("enviar_entrada"):
                tipo = TipoRegistroJornada.ENTRADA
            elif request.form.get("enviar_salida"):
                tipo = TipoRegistroJornada.SALIDA
            elif request.form.get("enviar_pausa_inicio"):
                tipo = TipoRegistroJornada.PAUSA_INICIO
            elif request.form.get("enviar_pausa_fin"):
                tipo = TipoRegistroJornada.PAUSA_FIN

        if tipo:
            lat = (
                float(formulario.latitud.data)
                if formulario.latitud.data is not None
                else None
            )
            lon = (
                float(formulario.longitud.data)
                if formulario.longitud.data is not None
                else None
            )
            prec = (
                float(formulario.precision_metros.data)
                if formulario.precision_metros.data is not None
                else None
            )
            cliente_dt = _parse_cliente_iso(formulario.marca_cliente_iso.data)
            reg, err = registrar_marca(
                empleado_id=emp_id,
                tipo_registro=tipo,
                usuario_id=current_user.id,
                origen=OrigenRegistroJornada.WEB_EMPLEADO,
                latitud=lat,
                longitud=lon,
                precision_metros=prec,
                fecha_hora_cliente=cliente_dt,
            )
            if err:
                flash(err, "peligro")
            else:
                flash(
                    f"Registrado: {tipo.replace('_', ' ')}. {reg.texto_ubicacion or ''}",
                    "exito",
                )
            return redirect(url_for("fichajes_bp.portal_empleado"))

        flash(
            "No se reconoció la acción de fichaje. Pulse de nuevo el botón deseado.",
            "peligro",
        )

    hoy = datetime.now(timezone.utc).date()
    registros = obtener_registros_dia_ordenados(emp_id, hoy)
    resumen = clasificar_dia(emp_id, hoy)
    contador = datos_contador_portal_fichaje(registros)
    return render_template(
        "portal_empleado.html",
        formulario=formulario,
        registros=registros,
        resumen=resumen,
        contador=contador,
    )


@fichajes_bp.route("/empleado/historial")
@login_required
def historial_empleado():
    """Historial reciente del empleado."""
    emp_id = obtener_id_empleado_actual()
    if not emp_id:
        abort_redirect()
    lista = (
        RegistroJornada.query.filter(
            RegistroJornada.empleado_id == emp_id,
            RegistroJornada.estado != EstadoRegistroJornada.ANULADO,
        )
        .order_by(RegistroJornada.fecha_hora_servidor.desc())
        .limit(60)
        .all()
    )
    return render_template(
        "historial_empleado.html",
        registros=lista,
    )


def abort_redirect():
    from flask import abort

    abort(403)


@fichajes_bp.route("/empleado/solicitar-correccion", methods=["GET", "POST"])
@login_required
def solicitar_correccion():
    emp_id = obtener_id_empleado_actual()
    if not emp_id:
        abort_redirect()

    formulario = FormularioSolicitudCorreccionEmpleado()
    rid = request.args.get("registro_id", type=int)
    if rid:
        formulario.registro_jornada_id.data = str(rid)

    if formulario.validate_on_submit():
        reg_id = formulario.registro_jornada_id.data
        reg_int = int(reg_id) if reg_id else None
        crear_solicitud_correccion_empleado(
            empleado_id=emp_id,
            registro_jornada_id=reg_int,
            motivo=formulario.motivo.data,
            valor_solicitado=formulario.detalle_solicitado.data,
        )
        flash("Solicitud enviada. RRHH la revisará.", "exito")
        return redirect(url_for("fichajes_bp.portal_empleado"))

    return render_template(
        "solicitar_correccion.html",
        formulario=formulario,
    )


@fichajes_bp.route("/admin/listado")
@login_required
@roles_permitidos(
    RolUsuario.SUPERADMINISTRADOR,
    RolUsuario.ADMINISTRADOR_EMPRESA,
    RolUsuario.RESPONSABLE,
)
def listado_admin():
    """Listado filtrable de fichajes (vista administrativa)."""
    emp_filtro = request.args.get("empleado_id", type=int)
    consulta = RegistroJornada.query.filter(
        RegistroJornada.estado != EstadoRegistroJornada.ANULADO,
    )

    # Filtrar por empresa del usuario actual (salvo superadmin)
    if current_user.rol != RolUsuario.SUPERADMINISTRADOR:
        emp_actual = getattr(current_user, "empleado", None)
        if emp_actual:
            consulta = consulta.join(Empleado).filter(
                Empleado.empresa_id == emp_actual.empresa_id
            )
    if emp_filtro and puede_gestionar_empleado(emp_filtro):
        consulta = consulta.filter(RegistroJornada.empleado_id == emp_filtro)
    elif not es_administrador_o_superior():
        emp_actual = obtener_id_empleado_actual()
        subordinados = _ids_equipo(emp_actual)
        if not subordinados:
            consulta = consulta.filter(RegistroJornada.id == -1)
        else:
            consulta = consulta.filter(
                RegistroJornada.empleado_id.in_(subordinados)
            )
    registros = consulta.order_by(
        RegistroJornada.fecha_hora_servidor.desc()
    ).limit(200).all()

    solicitudes = []
    if es_administrador_o_superior():
        solicitudes = (
            SolicitudCorreccion.query.filter_by(estado="pendiente")
            .order_by(SolicitudCorreccion.creado_en.desc())
            .limit(50)
            .all()
        )

    return render_template(
        "listado_admin.html",
        registros=registros,
        solicitudes=solicitudes,
    )


def _ids_equipo(responsable_id: int | None) -> list[int]:
    from app.modelos import Empleado

    if not responsable_id:
        return []
    subs = Empleado.query.filter_by(responsable_id=responsable_id).all()
    return [s.id for s in subs]


@fichajes_bp.route("/admin/registro/<int:registro_id>/corregir", methods=["GET", "POST"])
@login_required
@roles_permitidos(
    RolUsuario.SUPERADMINISTRADOR,
    RolUsuario.ADMINISTRADOR_EMPRESA,
)
def corregir_registro(registro_id: int):
    reg = RegistroJornada.query.get_or_404(registro_id)
    if not puede_gestionar_empleado(reg.empleado_id):
        flash("Sin permiso para este empleado.", "peligro")
        return redirect(url_for("fichajes_bp.listado_admin"))

    formulario = FormularioCorreccionAdmin(obj=reg)

    if formulario.validate_on_submit():
        nueva = formulario.fecha_hora_servidor.data
        if nueva.tzinfo is None:
            nueva = nueva.replace(tzinfo=ZONA_MADRID).astimezone(timezone.utc)
        else:
            nueva = nueva.astimezone(timezone.utc)
        ok, msg = corregir_registro_admin(
            registro_id,
            current_user.id,
            current_user.rol,
            {
                "fecha_hora_servidor": nueva,
                "tipo_registro": formulario.tipo_registro.data,
                "notas": formulario.notas.data,
            },
            formulario.motivo.data,
        )
        if ok:
            flash("Corrección guardada con auditoría.", "exito")
            return redirect(url_for("fichajes_bp.listado_admin"))
        flash(msg or "Error", "peligro")

    return render_template(
        "corregir_registro.html",
        formulario=formulario,
        registro=reg,
    )


@fichajes_bp.route(
    "/admin/solicitud/<int:solicitud_id>/resolver",
    methods=["GET", "POST"],
)
@login_required
@roles_permitidos(
    RolUsuario.SUPERADMINISTRADOR,
    RolUsuario.ADMINISTRADOR_EMPRESA,
)
def resolver_solicitud(solicitud_id: int):
    sol = SolicitudCorreccion.query.get_or_404(solicitud_id)
    if not puede_gestionar_empleado(sol.empleado_id):
        flash("Sin permiso.", "peligro")
        return redirect(url_for("fichajes_bp.listado_admin"))

    formulario = FormularioResolverSolicitud()
    if formulario.validate_on_submit():
        aprobar = "aprobar" in request.form
        rechazar = "rechazar" in request.form
        if aprobar:
            resolver_solicitud_correccion(
                solicitud_id, True, current_user.id, formulario.notas.data
            )
            flash("Solicitud aprobada.", "exito")
        elif rechazar:
            resolver_solicitud_correccion(
                solicitud_id, False, current_user.id, formulario.notas.data
            )
            flash("Solicitud rechazada.", "aviso")
        return redirect(url_for("fichajes_bp.listado_admin"))

    return render_template(
        "resolver_solicitud.html",
        formulario=formulario,
        solicitud=sol,
    )


@fichajes_bp.route("/admin/registro/<int:registro_id>/auditoria")
@login_required
@roles_permitidos(
    RolUsuario.SUPERADMINISTRADOR,
    RolUsuario.ADMINISTRADOR_EMPRESA,
    RolUsuario.RESPONSABLE,
)
def historial_auditoria_registro(registro_id: int):
    from app.modelos import RegistroAuditoria

    reg = RegistroJornada.query.get_or_404(registro_id)
    if not puede_gestionar_empleado(reg.empleado_id):
        flash("Sin permiso.", "peligro")
        return redirect(url_for("fichajes_bp.listado_admin"))

    entradas = (
        RegistroAuditoria.query.filter_by(
            tipo_entidad="registro_jornada",
            id_entidad=registro_id,
        )
        .order_by(RegistroAuditoria.creado_en.desc())
        .all()
    )
    return render_template(
        "auditoria_registro.html",
        registro=reg,
        entradas=entradas,
    )
