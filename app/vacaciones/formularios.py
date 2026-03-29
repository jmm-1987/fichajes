"""Formularios de vacaciones."""

from flask_wtf import FlaskForm
from wtforms import DateField, SelectField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Optional

from app.utilidades.fechas import FORMATO_FECHA
from app.utilidades.widgets_formulario import EntradaFechaEspanola


class FormularioSolicitudVacaciones(FlaskForm):
    """Solicitud por empleado o alta manual RRHH."""

    fecha_inicio = DateField(
        "Fecha inicio",
        validators=[DataRequired()],
        format=FORMATO_FECHA,
        widget=EntradaFechaEspanola(),
    )
    fecha_fin = DateField(
        "Fecha fin",
        validators=[DataRequired()],
        format=FORMATO_FECHA,
        widget=EntradaFechaEspanola(),
    )
    notas = TextAreaField("Notas", validators=[Optional()])
    enviar = SubmitField("Enviar solicitud")


class FormularioVacacionesManual(FlaskForm):
    """RRHH crea período aprobado directamente."""

    empleado_id = SelectField("Empleado", coerce=int, validators=[DataRequired()])
    fecha_inicio = DateField(
        "Inicio",
        validators=[DataRequired()],
        format=FORMATO_FECHA,
        widget=EntradaFechaEspanola(),
    )
    fecha_fin = DateField(
        "Fin",
        validators=[DataRequired()],
        format=FORMATO_FECHA,
        widget=EntradaFechaEspanola(),
    )
    notas = TextAreaField("Notas", validators=[Optional()])
    enviar = SubmitField("Registrar y aprobar")


class FormularioResolverVacaciones(FlaskForm):
    notas = TextAreaField("Notas", validators=[Optional()])
    aprobar = SubmitField("Aprobar")
    rechazar = SubmitField("Rechazar")
