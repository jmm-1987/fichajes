"""Formularios de administración / configuración laboral."""

from flask_wtf import FlaskForm
from wtforms import BooleanField, DateField, PasswordField, SelectField, StringField, SubmitField, TimeField
from wtforms.validators import DataRequired, Email, Length, Optional

from app.utilidades.fechas import FORMATO_FECHA
from app.utilidades.widgets_formulario import EntradaFechaEspanola


class FormularioFestivo(FlaskForm):
    fecha = DateField(
        "Fecha",
        validators=[DataRequired()],
        format=FORMATO_FECHA,
        widget=EntradaFechaEspanola(),
    )
    nombre = StringField("Nombre", validators=[DataRequired()])
    ambito = SelectField(
        "Ámbito",
        choices=[
            ("nacional", "Nacional"),
            ("autonomico", "Autonómico"),
            ("local", "Local"),
        ],
        validators=[DataRequired()],
    )
    ciudad = StringField("Ciudad", validators=[Optional()])
    region = StringField("Comunidad / provincia", validators=[Optional()])
    enviar_festivo = SubmitField("Guardar festivo")


class FormularioHorasNocturnas(FlaskForm):
    hora_inicio = TimeField("Inicio franja nocturna", validators=[DataRequired()])
    hora_fin = TimeField("Fin franja nocturna", validators=[DataRequired()])
    enviar_nocturnas = SubmitField("Guardar franja nocturna")


class FormularioParametrosLaborales(FlaskForm):
    fines_de_semana_festivo = BooleanField("Tratar sábado y domingo como festivo")
    tolerancia_minutos = StringField("Tolerancia fichaje (minutos)", validators=[Optional()])
    jornada_teorica_dia = StringField("Jornada teórica diaria (horas)", validators=[Optional()])
    enviar_parametros = SubmitField("Guardar parámetros")


class FormularioManagerEmpresa(FlaskForm):
    """Alta rápida de usuario manager (solo acceso, sin ficha de empleado)."""

    correo_electronico = StringField(
        "Usuario (correo o identificador)",
        validators=[DataRequired(), Length(min=2, max=255)],
    )
    contrasena = PasswordField(
        "Contraseña",
        validators=[DataRequired(), Length(min=8)],
    )
    enviar = SubmitField("Crear manager")
