"""Planificación semanal y plantillas reutilizables."""

from app.extensiones import db
from app.modelos.usuario import ahora_utc


class PlanificacionSemanal(db.Model):
    """Cabecera de una semana planificada."""

    __tablename__ = "planificaciones_semanales"

    id = db.Column(db.Integer, primary_key=True)
    inicio_semana = db.Column(db.Date, nullable=False, index=True)
    estado = db.Column(db.String(32), nullable=False, default="borrador")
    creado_por_usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
    )
    notas = db.Column(db.Text, nullable=True)
    creado_en = db.Column(
        db.DateTime(timezone=True), nullable=False, default=ahora_utc
    )

    creado_por = db.relationship("Usuario", foreign_keys=[creado_por_usuario_id])
    items = db.relationship(
        "ItemPlanificacionSemanal",
        back_populates="planificacion",
        cascade="all, delete-orphan",
    )


class ItemPlanificacionSemanal(db.Model):
    """Celda: empleado en un día concreto con horario."""

    __tablename__ = "items_planificacion_semanal"

    id = db.Column(db.Integer, primary_key=True)
    planificacion_semanal_id = db.Column(
        db.Integer,
        db.ForeignKey("planificaciones_semanales.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    empleado_id = db.Column(
        db.Integer,
        db.ForeignKey("empleados.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dia_semana = db.Column(db.Integer, nullable=False)  # 0=lunes … 6=domingo
    hora_inicio = db.Column(db.Time, nullable=True)
    hora_fin = db.Column(db.Time, nullable=True)
    nombre_plantilla = db.Column(db.String(120), nullable=True)
    notas = db.Column(db.String(500), nullable=True)

    planificacion = db.relationship(
        "PlanificacionSemanal", back_populates="items"
    )
    empleado = db.relationship("Empleado", backref="items_planificacion")


class PlantillaPlanificacion(db.Model):
    """Plantilla de horarios reutilizable."""

    __tablename__ = "plantillas_planificacion"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    creado_en = db.Column(
        db.DateTime(timezone=True), nullable=False, default=ahora_utc
    )

    items = db.relationship(
        "ItemPlantillaPlanificacion",
        back_populates="plantilla",
        cascade="all, delete-orphan",
    )


class ItemPlantillaPlanificacion(db.Model):
    """Definición de celda dentro de una plantilla."""

    __tablename__ = "items_plantilla_planificacion"

    id = db.Column(db.Integer, primary_key=True)
    plantilla_id = db.Column(
        db.Integer,
        db.ForeignKey("plantillas_planificacion.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    empleado_id = db.Column(
        db.Integer,
        db.ForeignKey("empleados.id", ondelete="SET NULL"),
        nullable=True,
    )
    etiqueta_rol = db.Column(db.String(80), nullable=True)
    dia_semana = db.Column(db.Integer, nullable=False)
    hora_inicio = db.Column(db.Time, nullable=True)
    hora_fin = db.Column(db.Time, nullable=True)

    plantilla = db.relationship("PlantillaPlanificacion", back_populates="items")
    empleado = db.relationship("Empleado", backref="items_plantilla")
