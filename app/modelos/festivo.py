"""Días festivos para cálculo de horas festivas."""

from app.extensiones import db
from app.modelos.usuario import ahora_utc


class Festivo(db.Model):
    """Festivo manual (nacional, autonómico o local)."""

    __tablename__ = "festivos"

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, nullable=False, index=True)
    nombre = db.Column(db.String(200), nullable=False)
    ambito = db.Column(db.String(32), nullable=False, default="nacional")
    ciudad = db.Column(db.String(120), nullable=True)
    region = db.Column(db.String(120), nullable=True)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    creado_en = db.Column(
        db.DateTime(timezone=True), nullable=False, default=ahora_utc
    )


class ConfiguracionHorasNocturnas(db.Model):
    """Rango horario considerado nocturno (una fila activa)."""

    __tablename__ = "configuracion_horas_nocturnas"

    id = db.Column(db.Integer, primary_key=True)
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fin = db.Column(db.Time, nullable=False)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    creado_en = db.Column(
        db.DateTime(timezone=True), nullable=False, default=ahora_utc
    )
