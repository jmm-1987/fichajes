"""Formularios del planificador semanal."""

from flask_wtf import FlaskForm
from wtforms import DateField, HiddenField, SelectField, StringField, SubmitField, TimeField
from wtforms.validators import DataRequired, Optional

from app.utilidades.fechas import FORMATO_FECHA
from app.utilidades.widgets_formulario import EntradaFechaEspanola


class FormularioNuevaSemana(FlaskForm):
    inicio_semana = DateField(
        "Lunes de la semana",
        validators=[DataRequired()],
        format=FORMATO_FECHA,
        widget=EntradaFechaEspanola(),
    )
    notas = StringField("Notas", validators=[Optional()])
    enviar = SubmitField("Crear planificación")


class FormularioItemCelda(FlaskForm):
    """Actualización AJAX/POST de una celda (empleado + día)."""

    planificacion_id = HiddenField(validators=[DataRequired()])
    empleado_id = SelectField("Empleado", coerce=int, validators=[DataRequired()])
    dia_semana = HiddenField(validators=[DataRequired()])
    hora_inicio = TimeField("Inicio", validators=[Optional()])
    hora_fin = TimeField("Fin", validators=[Optional()])
    enviar = SubmitField("Guardar celda")


class FormularioPlantilla(FlaskForm):
    nombre = StringField("Nombre plantilla", validators=[DataRequired()])
    descripcion = StringField("Descripción", validators=[Optional()])
    enviar = SubmitField("Crear plantilla vacía")


class FormularioDuplicarSemana(FlaskForm):
    nuevo_inicio = DateField(
        "Nuevo lunes",
        validators=[DataRequired()],
        format=FORMATO_FECHA,
        widget=EntradaFechaEspanola(),
    )
    enviar = SubmitField("Duplicar semana")
