"""Lógica de planificación semanal y plantillas."""

from datetime import date

from app.extensiones import db
from app.modelos import (
    ItemPlanificacionSemanal,
    ItemPlantillaPlanificacion,
    PlanificacionSemanal,
    PlantillaPlanificacion,
)


def crear_planificacion_vacia(inicio_semana: date, usuario_id: int | None, notas: str | None):
    """Crea cabecera en estado borrador."""
    p = PlanificacionSemanal(
        inicio_semana=inicio_semana,
        estado="borrador",
        creado_por_usuario_id=usuario_id,
        notas=notas,
    )
    db.session.add(p)
    db.session.commit()
    return p


def upsert_celda(
    planificacion_id: int,
    empleado_id: int,
    dia_semana: int,
    hora_inicio,
    hora_fin,
):
    """Crea o actualiza la celda para empleado/día."""
    q = ItemPlanificacionSemanal.query.filter_by(
        planificacion_semanal_id=planificacion_id,
        empleado_id=empleado_id,
        dia_semana=dia_semana,
    ).first()
    if q:
        q.hora_inicio = hora_inicio
        q.hora_fin = hora_fin
    else:
        q = ItemPlanificacionSemanal(
            planificacion_semanal_id=planificacion_id,
            empleado_id=empleado_id,
            dia_semana=dia_semana,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
        )
        db.session.add(q)
    db.session.commit()
    return q


def duplicar_semana(plan_origen_id: int, nuevo_lunes: date) -> PlanificacionSemanal:
    """Copia todos los items a una nueva semana."""
    origen = PlanificacionSemanal.query.get(plan_origen_id)
    if not origen:
        raise ValueError("Planificación origen no encontrada.")
    nueva = PlanificacionSemanal(
        inicio_semana=nuevo_lunes,
        estado="borrador",
        creado_por_usuario_id=origen.creado_por_usuario_id,
        notas=f"Duplicado de #{origen.id}",
    )
    db.session.add(nueva)
    db.session.flush()
    for it in origen.items:
        db.session.add(
            ItemPlanificacionSemanal(
                planificacion_semanal_id=nueva.id,
                empleado_id=it.empleado_id,
                dia_semana=it.dia_semana,
                hora_inicio=it.hora_inicio,
                hora_fin=it.hora_fin,
                notas=it.notas,
            )
        )
    db.session.commit()
    return nueva


def crear_plantilla_desde_plan(plan_id: int, nombre: str, descripcion: str | None):
    """Genera plantilla reutilizable desde una planificación existente."""
    plan = PlanificacionSemanal.query.get(plan_id)
    if not plan:
        raise ValueError("Plan no encontrado.")
    pl = PlantillaPlanificacion(nombre=nombre, descripcion=descripcion, activo=True)
    db.session.add(pl)
    db.session.flush()
    for it in plan.items:
        db.session.add(
            ItemPlantillaPlanificacion(
                plantilla_id=pl.id,
                empleado_id=it.empleado_id,
                dia_semana=it.dia_semana,
                hora_inicio=it.hora_inicio,
                hora_fin=it.hora_fin,
            )
        )
    db.session.commit()
    return pl


def aplicar_plantilla_a_plan(plantilla_id: int, plan_id: int) -> None:
    """Sustituye o añade celdas según la plantilla."""
    pl = PlantillaPlanificacion.query.get(plantilla_id)
    if not pl:
        raise ValueError("Plantilla no encontrada.")
    for it in pl.items:
        eid = it.empleado_id
        if not eid:
            continue
        upsert_celda(plan_id, eid, it.dia_semana, it.hora_inicio, it.hora_fin)
