"""Modelo de empleado / persona trabajadora."""

from app.extensiones import db
from app.modelos.usuario import ahora_utc


class Empleado(db.Model):
    """Datos laborales y personales del empleado."""

    __tablename__ = "empleados"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    codigo_empleado = db.Column(db.String(64), unique=True, nullable=False, index=True)
    nombre = db.Column(db.String(120), nullable=False)
    apellidos = db.Column(db.String(200), nullable=False)
    telefono = db.Column(db.String(40), nullable=True)
    documento_identidad = db.Column(db.String(32), nullable=True, index=True)
    fecha_alta = db.Column(db.Date, nullable=False)
    horas_semanales = db.Column(db.Numeric(5, 2), nullable=False, default=40)
    vacaciones_anuales = db.Column(db.Integer, nullable=False, default=22)
    saldo_vacaciones = db.Column(db.Numeric(6, 2), nullable=False, default=22)
    tipo_contrato = db.Column(db.String(80), nullable=True)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    centro_trabajo = db.Column(db.String(200), nullable=True)
    responsable_id = db.Column(
        db.Integer,
        db.ForeignKey("empleados.id", ondelete="SET NULL"),
        nullable=True,
    )
    observaciones = db.Column(db.Text, nullable=True)
    creado_en = db.Column(
        db.DateTime(timezone=True), nullable=False, default=ahora_utc
    )
    actualizado_en = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=ahora_utc,
        onupdate=ahora_utc,
    )

    usuario = db.relationship("Usuario", back_populates="empleado")
    responsable = db.relationship(
        "Empleado",
        remote_side=[id],
        backref=db.backref("equipo", lazy="dynamic"),
    )
    registros_jornada = db.relationship(
        "RegistroJornada",
        back_populates="empleado",
        lazy="dynamic",
        foreign_keys="RegistroJornada.empleado_id",
    )

    @property
    def nombre_completo(self) -> str:
        """Nombre y apellidos para mostrar."""
        return f"{self.nombre} {self.apellidos}".strip()
