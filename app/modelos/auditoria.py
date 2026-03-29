"""Registro inmutable de auditoría."""

import json
from typing import Any, Optional

from app.extensiones import db
from app.modelos.usuario import ahora_utc


class RegistroAuditoria(db.Model):
    """
    Trazabilidad inmutable: no se debe borrar filas de esta tabla.
    """

    __tablename__ = "registros_auditoria"

    id = db.Column(db.Integer, primary_key=True)
    tipo_entidad = db.Column(db.String(80), nullable=False, index=True)
    id_entidad = db.Column(db.Integer, nullable=False, index=True)
    accion = db.Column(db.String(64), nullable=False)
    usuario_actor_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
    )
    rol_actor = db.Column(db.String(64), nullable=True)
    motivo = db.Column(db.Text, nullable=True)
    estado_anterior_json = db.Column(db.Text, nullable=True)
    estado_nuevo_json = db.Column(db.Text, nullable=True)
    direccion_ip = db.Column(db.String(64), nullable=True)
    agente_usuario = db.Column(db.String(512), nullable=True)
    origen_cambio = db.Column(db.String(64), nullable=True)
    creado_en = db.Column(
        db.DateTime(timezone=True), nullable=False, default=ahora_utc, index=True
    )

    usuario_actor = db.relationship("Usuario", foreign_keys=[usuario_actor_id])

    @staticmethod
    def serializar(objeto: Optional[Any]) -> Optional[str]:
        """Convierte dict u objeto serializable a JSON string."""
        if objeto is None:
            return None
        if isinstance(objeto, str):
            return objeto
        return json.dumps(objeto, ensure_ascii=False, default=str)
