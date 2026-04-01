"""Formularios de empleados."""

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    DecimalField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from app.utilidades.fechas import FORMATO_FECHA
from app.utilidades.widgets_formulario import EntradaFechaEspanola


class FormularioEmpleado(FlaskForm):
    """Alta y edición de empleado."""

    correo_electronico = StringField(
        "Usuario (acceso al sistema)",
        validators=[DataRequired(), Length(min=2, max=255)],
    )
    contrasena = StringField(
        "Contraseña (solo en alta o si desea cambiarla)",
        validators=[Optional(), Length(min=8)],
    )
    codigo_empleado = StringField(
        "Código interno",
        validators=[DataRequired(), Length(max=64)],
    )
    nombre = StringField("Nombre", validators=[DataRequired(), Length(max=120)])
    apellidos = StringField(
        "Apellidos", validators=[DataRequired(), Length(max=200)]
    )
    telefono = StringField("Teléfono", validators=[Optional(), Length(max=40)])
    documento_identidad = StringField("DNI/NIF", validators=[Optional(), Length(max=32)])
    fecha_alta = DateField(
        "Fecha de alta",
        validators=[DataRequired()],
        format=FORMATO_FECHA,
        widget=EntradaFechaEspanola(),
    )
    horas_semanales = DecimalField(
        "Horas semanales teóricas",
        validators=[DataRequired(), NumberRange(min=0, max=60)],
        places=2,
    )
    vacaciones_anuales = DecimalField(
        "Días vacaciones anuales",
        validators=[DataRequired(), NumberRange(min=0, max=60)],
        places=2,
    )
    saldo_vacaciones = DecimalField(
        "Saldo vacaciones",
        validators=[Optional(), NumberRange(min=0, max=100)],
        places=2,
    )
    tipo_contrato = StringField("Tipo de contrato", validators=[Optional()])
    centro_trabajo = StringField("Centro de trabajo", validators=[Optional()])
    responsable_id = SelectField("Responsable", coerce=int, validators=[Optional()])
    activo = BooleanField("Activo", default=True)
    observaciones = TextAreaField("Observaciones internas", validators=[Optional()])
    rol = SelectField(
        "Rol de acceso",
        choices=[
            ("empleado", "Empleado"),
            ("responsable", "Responsable / mánager"),
        ],
        validators=[DataRequired()],
    )
    enviar = SubmitField("Guardar")


class FormularioEmpleadoSuperadmin(FormularioEmpleado):
    """Permite asignar superadministrador (solo superadmin)."""

    empresa_id = SelectField(
        "Empresa",
        coerce=int,
        validators=[DataRequired()],
    )
    rol = SelectField(
        "Rol de acceso",
        choices=[
            ("empleado", "Empleado"),
            ("responsable", "Responsable / mánager"),
            ("superadministrador", "Superadministrador"),
        ],
        validators=[DataRequired()],
    )
