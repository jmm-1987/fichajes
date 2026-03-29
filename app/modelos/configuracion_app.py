"""Parámetros de configuración por clave/valor."""

from app.extensiones import db
from app.modelos.usuario import ahora_utc


class ConfiguracionAplicacion(db.Model):
    """Clave-valor tipado para reglas laborales y flags."""

    __tablename__ = "configuracion_aplicacion"

    id = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(120), unique=True, nullable=False, index=True)
    valor = db.Column(db.Text, nullable=False)
    tipo_valor = db.Column(db.String(32), nullable=False, default="texto")
    descripcion = db.Column(db.String(500), nullable=True)
    actualizado_en = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=ahora_utc,
        onupdate=ahora_utc,
    )
