"""Pantallas de configuración para RRHH y superadmin."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.administracion.formularios import (
    FormularioFestivo,
    FormularioHorasNocturnas,
    FormularioParametrosLaborales,
)
from app.administracion.servicios import activar_configuracion_nocturna, establecer_config
from app.constantes import RolUsuario
from app.extensiones import db
from app.modelos import ConfiguracionHorasNocturnas, Empresa, Festivo
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
    RolUsuario.ADMINISTRADOR_EMPRESA,
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
