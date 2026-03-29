"""Formularios de fichajes y correcciones."""

from flask_wtf import FlaskForm
from wtforms import (
    DateTimeField,
    DecimalField,
    HiddenField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Optional

from app.utilidades.fechas import FORMATO_FECHA_HORA_SEG
from app.utilidades.widgets_formulario import EntradaFechaHoraEspanola


class FormularioFicharMovil(FlaskForm):
    """Campos ocultos enviados desde el cliente al fichar."""

    latitud = DecimalField("Latitud", validators=[Optional()], places=7)
    longitud = DecimalField("Longitud", validators=[Optional()], places=7)
    precision_metros = DecimalField("Precisión (m)", validators=[Optional()])
    marca_cliente_iso = HiddenField(validators=[Optional()])
    enviar_entrada = SubmitField("Fichar entrada")
    enviar_salida = SubmitField("Fichar salida")
    enviar_pausa_inicio = SubmitField("Inicio pausa")
    enviar_pausa_fin = SubmitField("Fin pausa")


class FormularioCorreccionAdmin(FlaskForm):
    """Corrección de marca por RRHH."""

    fecha_hora_servidor = DateTimeField(
        "Fecha y hora (hora local España)",
        validators=[DataRequired()],
        format=FORMATO_FECHA_HORA_SEG,
        widget=EntradaFechaHoraEspanola(),
    )
    tipo_registro = SelectField(
        "Tipo",
        choices=[
            ("entrada", "Entrada"),
            ("salida", "Salida"),
            ("pausa_inicio", "Inicio pausa"),
            ("pausa_fin", "Fin pausa"),
            ("incidencia", "Incidencia"),
        ],
        validators=[DataRequired()],
    )
    notas = TextAreaField("Notas", validators=[Optional()])
    motivo = TextAreaField("Motivo del cambio", validators=[DataRequired()])
    enviar = SubmitField("Guardar corrección")


class FormularioSolicitudCorreccionEmpleado(FlaskForm):
    """Solicitud de revisión por el trabajador."""

    registro_jornada_id = HiddenField(validators=[Optional()])
    motivo = TextAreaField("Motivo", validators=[DataRequired()])
    detalle_solicitado = TextAreaField(
        "Qué desea corregir",
        validators=[DataRequired()],
    )
    enviar = SubmitField("Enviar solicitud")


class FormularioResolverSolicitud(FlaskForm):
    """Aprobar o rechazar solicitud."""

    notas = TextAreaField("Notas internas", validators=[Optional()])
    aprobar = SubmitField("Aprobar")
    rechazar = SubmitField("Rechazar")
