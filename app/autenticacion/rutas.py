"""Rutas de inicio de sesión, cierre y recuperación de contraseña."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.autenticacion.formularios import (
    FormularioInicioSesion,
    FormularioRestablecerContrasena,
    FormularioSolicitudRecuperacion,
)
from app.autenticacion.servicios import (
    autenticar_usuario,
    buscar_usuario_por_token_recuperacion,
    crear_token_recuperacion,
    restablecer_contrasena_con_token,
)
from app.modelos import Usuario

autenticacion_bp = Blueprint(
    "autenticacion_bp",
    __name__,
    url_prefix="/autenticacion",
    template_folder="../plantillas/autenticacion",
)


@autenticacion_bp.route("/iniciar-sesion", methods=["GET", "POST"])
def iniciar_sesion():
    """Formulario de acceso."""
    if current_user.is_authenticated:
        return redirect(url_for("inicio_bp.panel"))

    formulario = FormularioInicioSesion()
    if formulario.validate_on_submit():
        usuario = autenticar_usuario(
            formulario.nombre_usuario.data,
            formulario.contrasena.data,
        )
        if usuario:
            login_user(usuario, remember=formulario.recordarme.data)
            siguiente = request.args.get("next")
            if siguiente and siguiente.startswith("/"):
                return redirect(siguiente)
            return redirect(url_for("inicio_bp.panel"))
        flash(
            "Credenciales incorrectas o cuenta bloqueada temporalmente.",
            "peligro",
        )

    return render_template("iniciar_sesion.html", formulario=formulario)


@autenticacion_bp.route("/cerrar-sesion")
@login_required
def cerrar_sesion():
    """Cierra la sesión actual."""
    logout_user()
    flash("Ha cerrado sesión correctamente.", "exito")
    return redirect(url_for("autenticacion_bp.iniciar_sesion"))


@autenticacion_bp.route("/recuperar-contrasena", methods=["GET", "POST"])
def solicitar_recuperacion_contrasena():
    """Solicitud de restablecimiento (en demo se muestra el enlace en pantalla)."""
    if current_user.is_authenticated:
        return redirect(url_for("inicio_bp.panel"))

    formulario = FormularioSolicitudRecuperacion()
    if formulario.validate_on_submit():
        ident = (formulario.nombre_usuario.data or "").strip().lower()
        usuario = Usuario.query.filter_by(correo_electronico=ident).first()
        if usuario and usuario.activo:
            token = crear_token_recuperacion(usuario)
            enlace = url_for(
                "autenticacion_bp.restablecer_contrasena",
                token=token,
                _external=True,
            )
            flash(
                "Si el usuario existe, puede usar el enlace de recuperación. "
                f"(Demo: {enlace})",
                "aviso",
            )
        else:
            flash(
                "Si el usuario existe en el sistema, recibirá instrucciones.",
                "info",
            )
        return redirect(url_for("autenticacion_bp.iniciar_sesion"))

    return render_template("recuperar_contrasena.html", formulario=formulario)


@autenticacion_bp.route("/restablecer/<token>", methods=["GET", "POST"])
def restablecer_contrasena(token: str):
    """Establece nueva contraseña con token válido."""
    usuario = buscar_usuario_por_token_recuperacion(token)
    if not usuario:
        flash("El enlace no es válido o ha caducado.", "peligro")
        return redirect(url_for("autenticacion_bp.iniciar_sesion"))

    formulario = FormularioRestablecerContrasena()
    if formulario.validate_on_submit():
        restablecer_contrasena_con_token(usuario, formulario.contrasena.data)
        flash("Contraseña actualizada. Ya puede iniciar sesión.", "exito")
        return redirect(url_for("autenticacion_bp.iniciar_sesion"))

    return render_template("restablecer_contrasena.html", formulario=formulario)
