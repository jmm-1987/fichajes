"""Consultas y agregados para informes."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterator, List, Optional

from app.constantes import EstadoRegistroJornada
from app.extensiones import db
from app.fichajes.calculos import clasificar_dia, calcular_resumen_periodo
from app.modelos import Empleado, RegistroJornada


@dataclass
class FiltrosInforme:
    """Criterios de filtrado de un informe."""

    fecha_inicio: date
    fecha_fin: date
    empleado_id: Optional[int] = None
    centro_trabajo: Optional[str] = None
    equipo_responsable_id: Optional[int] = None
    incluir_extras: bool = True
    incluir_nocturnas: bool = True
    incluir_festivas: bool = True
    solo_incidencias: bool = False
    solo_incompletos: bool = False


def empleados_filtrados(f: FiltrosInforme) -> List[Empleado]:
    """Lista de empleados según filtros de informe."""
    q = Empleado.query.filter_by(activo=True)
    if f.empleado_id:
        q = q.filter(Empleado.id == f.empleado_id)
    if f.centro_trabajo:
        q = q.filter(Empleado.centro_trabajo == f.centro_trabajo)
    if f.equipo_responsable_id:
        q = q.filter(Empleado.responsable_id == f.equipo_responsable_id)
    return q.order_by(Empleado.apellidos).all()


def iterar_filas_detalle(
    empleado_id: int,
    fecha_inicio: date,
    fecha_fin: date,
) -> Iterator[dict]:
    """Una fila por día con cálculo y banderas."""
    d = fecha_inicio
    while d <= fecha_fin:
        det = clasificar_dia(empleado_id, d)
        regs = (
            RegistroJornada.query.filter(
                RegistroJornada.empleado_id == empleado_id,
                RegistroJornada.fecha_hora_servidor
                >= datetime.combine(d, time.min, tzinfo=timezone.utc),
                RegistroJornada.fecha_hora_servidor
                < datetime.combine(d + timedelta(days=1), time.min, tzinfo=timezone.utc),
                RegistroJornada.estado != EstadoRegistroJornada.ANULADO,
            )
            .order_by(RegistroJornada.fecha_hora_servidor)
            .all()
        )
        det["fichajes"] = regs
        yield det
        d += timedelta(days=1)


def construir_informe_empleado(f: FiltrosInforme) -> List[dict]:
    """Filas por empleado con resumen y detalle opcional."""
    filas = []
    for emp in empleados_filtrados(f):
        resumen = calcular_resumen_periodo(emp.id, f.fecha_inicio, f.fecha_fin)
        if f.solo_incompletos and resumen.get("dias_incompletos", 0) == 0:
            continue
        if f.solo_incidencias and resumen.get("dias_con_incidencia", 0) == 0:
            continue

        if not f.incluir_extras:
            resumen["horas_extras"] = 0
        if not f.incluir_nocturnas:
            resumen["horas_nocturnas"] = 0
            resumen["horas_nocturnas_festivas"] = 0
        if not f.incluir_festivas:
            resumen["horas_festivas"] = 0

        detalle = list(
            iterar_filas_detalle(emp.id, f.fecha_inicio, f.fecha_fin)
        )
        if f.solo_incompletos:
            detalle = [x for x in detalle if x.get("jornada_incompleta")]
        if f.solo_incidencias:
            detalle = [x for x in detalle if x.get("posible_incidencia")]

        filas.append(
            {
                "empleado": emp,
                "resumen": resumen,
                "detalle": detalle,
            }
        )
    return filas


def centros_distintos() -> List[str]:
    """Valores de centro de trabajo usados."""
    q = (
        db.session.query(Empleado.centro_trabajo)
        .filter(Empleado.centro_trabajo.isnot(None), Empleado.centro_trabajo != "")
        .distinct()
    )
    return [r[0] for r in q.all()]
