"""Clasificación manual de días laborales (manager)."""

from app.extensiones import db
from app.modelos.usuario import ahora_utc


class ClasificacionDiaLaboral(db.Model):
    """Marca de un día con tipo (vacaciones, libre, ausencia justificada / no justificada) y motivo."""

    __tablename__ = "clasificaciones_dia_laboral"
    __table_args__ = (
        db.UniqueConstraint(
            "empleado_id",
            "fecha",
            name="uq_clasificacion_dia_empleado_fecha",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    empleado_id = db.Column(
        db.Integer,
        db.ForeignKey("empleados.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fecha = db.Column(db.Date, nullable=False, index=True)
    tipo = db.Column(db.String(32), nullable=False)
    motivo = db.Column(db.Text, nullable=True)
    creado_por_usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
    )
    creado_en = db.Column(
        db.DateTime(timezone=True), nullable=False, default=ahora_utc
    )

    empleado = db.relationship("Empleado", backref="clasificaciones_dia_laboral")
    creado_por = db.relationship(
        "Usuario", foreign_keys=[creado_por_usuario_id]
    )
