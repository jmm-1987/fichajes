"""Pantallas de configuración para RRHH y superadmin."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.administracion.formularios import (
    FormularioFestivo,
    FormularioHorasNocturnas,
    FormularioManagerEmpresa,
    FormularioParametrosLaborales,
)
from app.administracion.servicios import (
    activar_configuracion_nocturna,
    establecer_config,
    establecer_config_empresa,
    obtener_config_empresa,
)
from app.constantes import RolUsuario
from app.extensiones import db
from app.modelos import ConfiguracionHorasNocturnas, Empresa, Festivo, Usuario
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
                "fines_semana_festivo",
                "1" if form_params.fines_de_semana_festivo.data else "0",
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
        if not emp_actual or not emp_actual.empresa_id:
            flash("No hay empresa asociada al usuario actual.", "peligro")
            return redirect(url_for("inicio_bp.panel"))
        empresa_id = emp_actual.empresa_id
    else:
        empresa_id = request.args.get("empresa_id", type=int)
        if not empresa_id:
            flash("Seleccione una empresa desde el listado para configurar.", "aviso")
            return redirect(url_for("administracion_bp.listado_empresas"))

    empresa = Empresa.query.get_or_404(empresa_id)
    form_params = FormularioParametrosLaborales(prefix="par")

    if request.method == "GET":
        cfg_fs = obtener_config_empresa(empresa_id, "fines_semana_festivo", "0")
        cfg_tol = obtener_config_empresa(empresa_id, "tolerancia_fichaje_minutos", "5")
        cfg_jornada = obtener_config_empresa(
            empresa_id, "jornada_teorica_horas_dia", "8.0"
        )
        form_params.fines_de_semana_festivo.data = cfg_fs.valor == "1"
        form_params.tolerancia_minutos.data = cfg_tol.valor
        form_params.jornada_teorica_dia.data = cfg_jornada.valor

    if request.method == "POST" and form_params.validate_on_submit():
        establecer_config_empresa(
            empresa_id,
            "fines_semana_festivo",
            "1" if form_params.fines_de_semana_festivo.data else "0",
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

    return render_template(
        "laboral_empresa.html",
        form_params=form_params,
        empresa=empresa,
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
