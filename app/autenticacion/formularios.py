"""Formularios WTForms del módulo de autenticación."""

from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, Optional


class FormularioInicioSesion(FlaskForm):
    """Credenciales de acceso (identificador de usuario, sin formato correo)."""

    nombre_usuario = StringField(
        "Usuario",
        validators=[DataRequired(message="Obligatorio."), Length(max=255)],
    )
    contrasena = PasswordField(
        "Contraseña",
        validators=[DataRequired(message="Obligatorio.")],
    )
    recordarme = BooleanField("Recordarme en este equipo")
    enviar = SubmitField("Entrar")


class FormularioSolicitudRecuperacion(FlaskForm):
    """Solicitud de enlace para restablecer contraseña."""

    nombre_usuario = StringField(
        "Usuario",
        validators=[DataRequired(), Length(max=255)],
    )
    enviar = SubmitField("Enviar instrucciones")


class FormularioRestablecerContrasena(FlaskForm):
    """Nueva contraseña tras token válido."""

    contrasena = PasswordField(
        "Nueva contraseña",
        validators=[DataRequired(), Length(min=8, message="Mínimo 8 caracteres.")],
    )
    contrasena_confirmacion = PasswordField(
        "Repetir contraseña",
        validators=[
            DataRequired(),
            EqualTo("contrasena", message="Las contraseñas no coinciden."),
        ],
    )
    enviar = SubmitField("Guardar contraseña")


class FormularioCambiarContrasena(FlaskForm):
    """Cambio de contraseña estando logueado."""

    contrasena_actual = PasswordField(
        "Contraseña actual",
        validators=[DataRequired()],
    )
    contrasena_nueva = PasswordField(
        "Nueva contraseña",
        validators=[DataRequired(), Length(min=8)],
    )
    contrasena_nueva_confirmacion = PasswordField(
        "Confirmar nueva contraseña",
        validators=[
            DataRequired(),
            EqualTo("contrasena_nueva", message="No coinciden."),
        ],
    )
    enviar = SubmitField("Actualizar")
