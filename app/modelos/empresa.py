"""Modelo de empresa (multiempresa sobre una sola base de datos)."""

from app.extensiones import db
from app.modelos.usuario import ahora_utc


class Empresa(db.Model):
    """Empresa cliente que usa el sistema de fichajes."""

    __tablename__ = "empresas"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False, unique=True, index=True)
    cif = db.Column(db.String(32), nullable=True, unique=True, index=True)
    activa = db.Column(db.Boolean, nullable=False, default=True)
    creado_en = db.Column(
        db.DateTime(timezone=True), nullable=False, default=ahora_utc
    )
    actualizado_en = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=ahora_utc,
        onupdate=ahora_utc,
    )

