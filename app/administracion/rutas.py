"""Pantallas de configuración para RRHH y superadmin."""

import secrets
import string

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.administracion.formularios import (
    FormularioEditarResponsable,
    FormularioFestivo,
    FormularioHorasNocturnas,
    FormularioManagerEmpresa,
    FormularioParametrosLaborales,
    FormularioTiposEmpleado,
)
from app.administracion.servicios import (
    activar_configuracion_nocturna,
    establecer_config,
    establecer_config_empresa,
    obtener_config_empresa,
    obtener_o_crear_config,
)
from app.constantes import RolUsuario
from app.extensiones import db
from app.modelos import ConfiguracionHorasNocturnas, Empleado, Empresa, Festivo, Usuario
from app.fichajes.calculos import leer_sabado_domingo_festivo_empresa, leer_sabado_domingo_festivo_global
from app.utilidades.predicados import roles_permitidos

administracion_bp = Blueprint(
    "administracion_bp",
    __name__,
    url_prefix="/administracion",
    template_folder="../plantillas/administracion",
)


@administracion_bp.route("/laboral", methods=["GET", "POST"])
@login_required
@roles_permitidos(
    RolUsuario.SUPERADMINISTRADOR,
)
def configuracion_laboral():
    form_noche = FormularioHorasNocturnas(prefix="noche")
    form_festivo = FormularioFestivo(prefix="fest")
    form_params = FormularioParametrosLaborales(prefix="par")

    if request.method == "GET":
        activa = ConfiguracionHorasNocturnas.query.filter_by(activo=True).first()
        if activa:
            form_noche.hora_inicio.data = activa.hora_inicio
            form_noche.hora_fin.data = activa.hora_fin
        cfg_tol = obtener_o_crear_config("tolerancia_fichaje_minutos", "5")
        cfg_jornada = obtener_o_crear_config("jornada_teorica_horas_dia", "8.0")
        form_params.tolerancia_minutos.data = cfg_tol.valor
        form_params.jornada_teorica_dia.data = cfg_jornada.valor
        sab, dom = leer_sabado_domingo_festivo_global()
        form_params.sabado_festivo.data = sab
        form_params.domingo_festivo.data = dom

    if request.method == "POST":
        if "noche-enviar_nocturnas" in request.form and form_noche.validate():
            activar_configuracion_nocturna(
                form_noche.hora_inicio.data,
                form_noche.hora_fin.data,
            )
            flash("Franja nocturna actualizada.", "exito")
            return redirect(url_for("administracion_bp.configuracion_laboral"))
        if "fest-enviar_festivo" in request.form and form_festivo.validate():
            f = Festivo(
                fecha=form_festivo.fecha.data,
                nombre=form_festivo.nombre.data,
                ambito=form_festivo.ambito.data,
                ciudad=form_festivo.ciudad.data or None,
                region=form_festivo.region.data or None,
                activo=True,
            )
            db.session.add(f)
            db.session.commit()
            flash("Festivo añadido.", "exito")
            return redirect(url_for("administracion_bp.configuracion_laboral"))
        if "par-enviar_parametros" in request.form and form_params.validate():
            establecer_config(
                "sabado_festivo",
                "1" if form_params.sabado_festivo.data else "0",
            )
            establecer_config(
                "domingo_festivo",
                "1" if form_params.domingo_festivo.data else "0",
            )
            if form_params.tolerancia_minutos.data:
                establecer_config(
                    "tolerancia_fichaje_minutos",
                    form_params.tolerancia_minutos.data.strip(),
                )
            if form_params.jornada_teorica_dia.data:
                establecer_config(
                    "jornada_teorica_horas_dia",
                    form_params.jornada_teorica_dia.data.strip(),
                )
            flash(
                "Parámetros guardados en base de datos. "
                "Algunos valores siguen leyendo también del archivo .env.",
                "aviso",
            )
            return redirect(url_for("administracion_bp.configuracion_laboral"))

    festivos = (
        Festivo.query.filter_by(activo=True)
        .order_by(Festivo.fecha.desc())
        .limit(50)
        .all()
    )

    return render_template(
        "laboral.html",
        form_noche=form_noche,
        form_festivo=form_festivo,
        form_params=form_params,
        festivos=festivos,
    )


@administracion_bp.route("/laboral/mi-empresa", methods=["GET", "POST"])
@login_required
@roles_permitidos(
    RolUsuario.SUPERADMINISTRADOR,
    RolUsuario.ADMINISTRADOR_EMPRESA,
    RolUsuario.RESPONSABLE,
)
def configuracion_laboral_empresa():
    """
    Configuración laboral específica por empresa.
    - Administrador de empresa: siempre su propia empresa.
    - Superadmin: debe venir empresa_id en querystring.
    """
    empresa_id = None
    if current_user.rol in (RolUsuario.ADMINISTRADOR_EMPRESA, RolUsuario.RESPONSABLE):
        emp_actual = getattr(current_user, "empleado", None)
        empresa_id = getattr(current_user, "empresa_id", None)
        if empresa_id is None and emp_actual is not None:
            empresa_id = emp_actual.empresa_id
        if not empresa_id:
            flash("No hay empresa asociada al usuario actual.", "peligro")
            return redirect(url_for("inicio_bp.panel"))
    else:
        empresa_id = request.args.get("empresa_id", type=int)
        if not empresa_id:
            flash("Seleccione una empresa desde el listado para configurar.", "aviso")
            return redirect(url_for("administracion_bp.listado_empresas"))

    empresa = Empresa.query.get_or_404(empresa_id)
    form_params = FormularioParametrosLaborales(prefix="par")
    form_noche = FormularioHorasNocturnas(prefix="noche")
    form_festivo = FormularioFestivo(prefix="fest")
    form_tipos = FormularioTiposEmpleado(prefix="tipos")

    from app.modelos import ConfiguracionHorasNocturnas, Festivo

    if request.method == "GET":
        cfg_tol = obtener_config_empresa(empresa_id, "tolerancia_fichaje_minutos", "5")
        cfg_jornada = obtener_config_empresa(
            empresa_id, "jornada_teorica_horas_dia", "8.0"
        )
        form_params.tolerancia_minutos.data = cfg_tol.valor
        form_params.jornada_teorica_dia.data = cfg_jornada.valor
        sab, dom = leer_sabado_domingo_festivo_empresa(empresa_id)
        form_params.sabado_festivo.data = sab
        form_params.domingo_festivo.data = dom

        noct_activa = ConfiguracionHorasNocturnas.query.filter_by(
            empresa_id=empresa_id, activo=True
        ).first()
        if noct_activa:
            form_noche.hora_inicio.data = noct_activa.hora_inicio
            form_noche.hora_fin.data = noct_activa.hora_fin

        cfg_tipos = obtener_config_empresa(empresa_id, "tipos_empleado", "")
        form_tipos.tipos_lineas.data = cfg_tipos.valor or ""

    if request.method == "POST":
        if "tipos-enviar_tipos" in request.form and form_tipos.validate():
            establecer_config_empresa(
                empresa_id,
                "tipos_empleado",
                (form_tipos.tipos_lineas.data or "").strip(),
            )
            flash(
                f"Tipos de empleado guardados para {empresa.nombre}.",
                "exito",
            )
            if current_user.rol == RolUsuario.SUPERADMINISTRADOR:
                return redirect(
                    url_for(
                        "administracion_bp.configuracion_laboral_empresa",
                        empresa_id=empresa_id,
                    )
                )
            return redirect(url_for("administracion_bp.configuracion_laboral_empresa"))

        if "noche-enviar_nocturnas" in request.form and form_noche.validate():
            # Desactivar anteriores y activar una nueva para la empresa
            for fila in ConfiguracionHorasNocturnas.query.filter_by(
                empresa_id=empresa_id
            ).all():
                fila.activo = False
            nueva = ConfiguracionHorasNocturnas(
                hora_inicio=form_noche.hora_inicio.data,
                hora_fin=form_noche.hora_fin.data,
                activo=True,
                empresa_id=empresa_id,
            )
            db.session.add(nueva)
            db.session.commit()
            flash("Franja nocturna actualizada para la empresa.", "exito")
            return redirect(url_for("administracion_bp.configuracion_laboral_empresa"))

        if "fest-enviar_festivo" in request.form and form_festivo.validate():
            f = Festivo(
                fecha=form_festivo.fecha.data,
                nombre=form_festivo.nombre.data,
                ambito=form_festivo.ambito.data,
                ciudad=form_festivo.ciudad.data or None,
                region=form_festivo.region.data or None,
                activo=True,
                empresa_id=empresa_id,
            )
            db.session.add(f)
            db.session.commit()
            flash("Festivo añadido para la empresa.", "exito")
            return redirect(url_for("administracion_bp.configuracion_laboral_empresa"))

        if "par-enviar_parametros" in request.form and form_params.validate():
            establecer_config_empresa(
                empresa_id,
                "sabado_festivo",
                "1" if form_params.sabado_festivo.data else "0",
            )
            establecer_config_empresa(
                empresa_id,
                "domingo_festivo",
                "1" if form_params.domingo_festivo.data else "0",
            )
            if form_params.tolerancia_minutos.data:
                establecer_config_empresa(
                    empresa_id,
                    "tolerancia_fichaje_minutos",
                    form_params.tolerancia_minutos.data.strip(),
                )
            if form_params.jornada_teorica_dia.data:
                establecer_config_empresa(
                    empresa_id,
                    "jornada_teorica_horas_dia",
                    form_params.jornada_teorica_dia.data.strip(),
                )
            flash(
                f"Configuración laboral guardada para {empresa.nombre}.",
                "exito",
            )
            return redirect(url_for("administracion_bp.configuracion_laboral_empresa"))

    festivos = (
        Festivo.query.filter_by(empresa_id=empresa_id, activo=True)
        .order_by(Festivo.fecha.desc())
        .limit(50)
        .all()
    )
    nocturna = (
        ConfiguracionHorasNocturnas.query.filter_by(
            empresa_id=empresa_id, activo=True
        )
        .order_by(ConfiguracionHorasNocturnas.id.desc())
        .first()
    )

    return render_template(
        "laboral_empresa.html",
        form_params=form_params,
        form_noche=form_noche,
        form_festivo=form_festivo,
        form_tipos=form_tipos,
        empresa=empresa,
        festivos=festivos,
        nocturna=nocturna,
    )


@administracion_bp.route("/empresas")
@login_required
@roles_permitidos(RolUsuario.SUPERADMINISTRADOR)
def listado_empresas():
    empresas = Empresa.query.order_by(Empresa.nombre).all()
    return render_template("empresas_listado.html", empresas=empresas)


@administracion_bp.route("/empresas/nueva", methods=["POST"])
@login_required
@roles_permitidos(RolUsuario.SUPERADMINISTRADOR)
def crear_empresa_rapida():
    nombre = (request.form.get("nombre") or "").strip()
    if not nombre:
        flash("El nombre de empresa es obligatorio.", "peligro")
        return redirect(url_for("administracion_bp.listado_empresas"))
    existe = Empresa.query.filter_by(nombre=nombre).first()
    if existe:
        flash("Ya existe una empresa con ese nombre.", "peligro")
        return redirect(url_for("administracion_bp.listado_empresas"))
    emp = Empresa(nombre=nombre, activa=True)
    db.session.add(emp)
    db.session.commit()
    flash("Empresa creada.", "exito")
    return redirect(url_for("administracion_bp.listado_empresas"))


@administracion_bp.route("/empresas/<int:empresa_id>/toggle", methods=["POST"])
@login_required
@roles_permitidos(RolUsuario.SUPERADMINISTRADOR)
def toggle_activa_empresa(empresa_id: int):
    emp = Empresa.query.get_or_404(empresa_id)
    emp.activa = not emp.activa
    db.session.commit()
    flash("Estado de la empresa actualizado.", "exito")
    return redirect(url_for("administracion_bp.listado_empresas"))


@administracion_bp.route("/empresas/<int:empresa_id>/manager", methods=["GET", "POST"])
@login_required
@roles_permitidos(RolUsuario.SUPERADMINISTRADOR)
def crear_manager_empresa(empresa_id: int):
    """Crea un usuario manager (rol responsable) ligado a una empresa, sin ficha de empleado."""
    empresa = Empresa.query.get_or_404(empresa_id)
    form = FormularioManagerEmpresa()

    if form.validate_on_submit():
        correo = (form.correo_electronico.data or "").strip().lower()
        existe = Usuario.query.filter_by(correo_electronico=correo).first()
        if existe:
            flash("Ya existe un usuario con ese identificador.", "peligro")
        else:
            u = Usuario(
                correo_electronico=correo,
                rol=RolUsuario.RESPONSABLE,
                activo=True,
                empresa_id=empresa.id,
            )
            u.establecer_contrasena(form.contrasena.data)
            db.session.add(u)
            db.session.commit()
            flash(f"Manager creado para {empresa.nombre}.", "exito")
            return redirect(url_for("administracion_bp.listado_empresas"))

    return render_template(
        "manager_empresa_form.html",
        formulario=form,
        empresa=empresa,
    )


@administracion_bp.route("/responsables")
@login_required
@roles_permitidos(RolUsuario.SUPERADMINISTRADOR)
def listado_responsables():
    """Listado de managers (usuarios con rol responsable) por empresa."""
    q = (
        Usuario.query.filter_by(rol=RolUsuario.RESPONSABLE)
        .order_by(Usuario.empresa_id.nullsfirst(), Usuario.correo_electronico)
        .all()
    )
    return render_template("responsables_listado.html", responsables=q, Empleado=Empleado)


@administracion_bp.route("/responsables/<int:usuario_id>/editar", methods=["GET", "POST"])
@login_required
@roles_permitidos(RolUsuario.SUPERADMINISTRADOR)
def editar_responsable(usuario_id: int):
    """Permite a superadmin editar un usuario responsable."""
    u = Usuario.query.filter_by(id=usuario_id, rol=RolUsuario.RESPONSABLE).first_or_404()
    form = FormularioEditarResponsable(obj=u)

    if request.method == "GET":
        form.correo_electronico.data = u.correo_electronico
        form.activo.data = bool(u.activo)

    if form.validate_on_submit():
        nuevo_ident = (form.correo_electronico.data or "").strip().lower()
        existe = Usuario.query.filter(
            Usuario.correo_electronico == nuevo_ident,
            Usuario.id != u.id,
        ).first()
        if existe:
            flash("Ya existe otro usuario con ese identificador.", "peligro")
        else:
            u.correo_electronico = nuevo_ident
            u.activo = bool(form.activo.data)
            nueva_pwd = (form.contrasena.data or "").strip()
            if nueva_pwd:
                u.establecer_contrasena(nueva_pwd)
            db.session.commit()
            flash("Responsable actualizado.", "exito")
            return redirect(url_for("administracion_bp.listado_responsables"))

    return render_template("responsable_form.html", formulario=form, responsable=u)


@administracion_bp.route("/responsables/<int:usuario_id>/eliminar", methods=["POST"])
@login_required
@roles_permitidos(RolUsuario.SUPERADMINISTRADOR)
def eliminar_responsable(usuario_id: int):
    """Elimina responsable; si hay dependencias, lo desactiva."""
    u = Usuario.query.filter_by(id=usuario_id, rol=RolUsuario.RESPONSABLE).first_or_404()
    try:
        emp = Empleado.query.filter_by(usuario_id=u.id).first()
        if emp is not None:
            db.session.delete(emp)
        db.session.delete(u)
        db.session.commit()
        flash("Responsable eliminado.", "exito")
    except IntegrityError:
        db.session.rollback()
        u.activo = False
        emp = Empleado.query.filter_by(usuario_id=u.id).first()
        if emp is not None:
            emp.activo = False
        db.session.commit()
        flash(
            "No se pudo borrar por dependencias históricas. Se ha desactivado el responsable.",
            "aviso",
        )
    return redirect(url_for("administracion_bp.listado_responsables"))


def _generar_contrasena_temporal(longitud: int = 12) -> str:
    """Contraseña temporal legible y suficientemente robusta."""
    if longitud < 10:
        longitud = 10
    alfabeto = string.ascii_letters + string.digits
    while True:
        pwd = "".join(secrets.choice(alfabeto) for _ in range(longitud))
        if (
            any(c.islower() for c in pwd)
            and any(c.isupper() for c in pwd)
            and any(c.isdigit() for c in pwd)
        ):
            return pwd


@administracion_bp.route("/responsables/<int:usuario_id>/reset-password", methods=["POST"])
@login_required
@roles_permitidos(RolUsuario.SUPERADMINISTRADOR)
def reset_password_responsable(usuario_id: int):
    """Resetea contraseña de responsable y la muestra una sola vez."""
    u = Usuario.query.filter_by(id=usuario_id, rol=RolUsuario.RESPONSABLE).first_or_404()
    temporal = _generar_contrasena_temporal()
    u.establecer_contrasena(temporal)
    u.intentos_fallidos_login = 0
    u.bloqueado_hasta = None
    db.session.commit()
    flash(
        f"Contraseña temporal para {u.correo_electronico}: {temporal}",
        "aviso",
    )
    return redirect(url_for("administracion_bp.listado_responsables"))
