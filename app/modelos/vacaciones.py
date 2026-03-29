"""Solicitudes y períodos de vacaciones."""

from app.extensiones import db
from app.modelos.usuario import ahora_utc


class SolicitudVacaciones(db.Model):
    """Solicitud o registro de vacaciones de un empleado."""

    __tablename__ = "solicitudes_vacaciones"

    id = db.Column(db.Integer, primary_key=True)
    empleado_id = db.Column(
        db.Integer,
        db.ForeignKey("empleados.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    fecha_inicio = db.Column(db.Date, nullable=False, index=True)
    fecha_fin = db.Column(db.Date, nullable=False, index=True)
    numero_dias = db.Column(db.Numeric(6, 2), nullable=False)
    estado = db.Column(db.String(32), nullable=False, default="pendiente", index=True)
    solicitado_en = db.Column(
        db.DateTime(timezone=True), nullable=False, default=ahora_utc
    )
    aprobado_por_usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
    )
    aprobado_en = db.Column(db.DateTime(timezone=True), nullable=True)
    notas = db.Column(db.Text, nullable=True)

    empleado = db.relationship("Empleado", backref="solicitudes_vacaciones")
    aprobado_por = db.relationship(
        "Usuario", foreign_keys=[aprobado_por_usuario_id]
    )
