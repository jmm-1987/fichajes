"""Registros de jornada y solicitudes de corrección."""

from app.extensiones import db
from app.modelos.usuario import ahora_utc


class RegistroJornada(db.Model):
    """Marca horaria de fichaje (inmutable salvo corrección con auditoría)."""

    __tablename__ = "registros_jornada"

    id = db.Column(db.Integer, primary_key=True)
    empleado_id = db.Column(
        db.Integer,
        db.ForeignKey("empleados.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    tipo_registro = db.Column(db.String(32), nullable=False, index=True)
    fecha_hora_servidor = db.Column(
        db.DateTime(timezone=True), nullable=False, index=True
    )
    fecha_hora_cliente = db.Column(db.DateTime(timezone=True), nullable=True)
    latitud = db.Column(db.Numeric(10, 7), nullable=True)
    longitud = db.Column(db.Numeric(10, 7), nullable=True)
    precision_metros = db.Column(db.Numeric(10, 2), nullable=True)
    texto_ubicacion = db.Column(db.String(500), nullable=True)
    direccion_ip = db.Column(db.String(64), nullable=True)
    agente_usuario = db.Column(db.String(512), nullable=True)
    origen = db.Column(db.String(32), nullable=False, default="web_empleado")
    estado = db.Column(db.String(32), nullable=False, default="valido", index=True)
    notas = db.Column(db.Text, nullable=True)
    creado_por_usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
    )
    actualizado_en = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=ahora_utc,
        onupdate=ahora_utc,
    )

    empleado = db.relationship("Empleado", back_populates="registros_jornada")
    creado_por = db.relationship("Usuario", foreign_keys=[creado_por_usuario_id])


class SolicitudCorreccion(db.Model):
    """Solicitud de corrección de jornada o registro."""

    __tablename__ = "solicitudes_correccion"

    id = db.Column(db.Integer, primary_key=True)
    empleado_id = db.Column(
        db.Integer,
        db.ForeignKey("empleados.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    registro_jornada_id = db.Column(
        db.Integer,
        db.ForeignKey("registros_jornada.id", ondelete="RESTRICT"),
        nullable=True,
    )
    tipo_solicitud = db.Column(db.String(64), nullable=False)
    valor_solicitado = db.Column(db.Text, nullable=True)
    valor_actual = db.Column(db.Text, nullable=True)
    motivo = db.Column(db.Text, nullable=False)
    estado = db.Column(db.String(32), nullable=False, default="pendiente", index=True)
    revisado_por_usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
    )
    revisado_en = db.Column(db.DateTime(timezone=True), nullable=True)
    notas_resolucion = db.Column(db.Text, nullable=True)
    creado_en = db.Column(
        db.DateTime(timezone=True), nullable=False, default=ahora_utc
    )

    empleado = db.relationship("Empleado", backref="solicitudes_correccion")
    registro_jornada = db.relationship("RegistroJornada", backref="solicitudes")
    revisado_por = db.relationship("Usuario", foreign_keys=[revisado_por_usuario_id])
