"""Modelo de empresa (multiempresa sobre una sola base de datos)."""

from app.extensiones import db


class Empresa(db.Model):
    """Empresa cliente que usa el sistema de fichajes."""

    __tablename__ = "empresas"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False, unique=True, index=True)
    cif = db.Column(db.String(32), nullable=True, unique=True, index=True)
    activa = db.Column(db.Boolean, nullable=False, default=True)
    # Marcas temporales: se usa hora UTC en base de datos,
    # igual que en el resto de modelos, y se presenta en hora de Madrid en las vistas.
    creado_en = db.Column(db.DateTime(timezone=True), nullable=True)
    actualizado_en = db.Column(db.DateTime(timezone=True), nullable=True)

