"""Consultas y agregados para informes."""

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterator, List, Optional

from app.constantes import EstadoRegistroJornada, TipoClasificacionDiaLaboral
from app.extensiones import db
from app.fichajes.calculos import clasificar_dia, calcular_resumen_periodo
from app.modelos import Empleado, RegistroJornada


def etiqueta_estado_dia_laboral(estado: str) -> str:
    """Una sola etiqueta legible (misma lógica que el calendario)."""
    m = {
        "trabajado": "Trabajando",
        "vacaciones": "Vacaciones",
        TipoClasificacionDiaLaboral.LIBRE: "Libre",
        TipoClasificacionDiaLaboral.AUSENCIA_JUSTIFICADA: "Ausencia justif.",
        TipoClasificacionDiaLaboral.AUSENCIA_NO_JUSTIFICADA: "Ausencia no justif.",
        "pendiente": "Pendiente",
        "no_laborable": "No laborable",
    }
    return m.get(estado, estado)


def resumen_tipos_dia_periodo(
    empleado_id: int, fecha_inicio: date, fecha_fin: date
) -> str:
    """
    Texto breve para la columna «Tipo día»:

    - **Un solo día** en el informe: una etiqueta (p. ej. «Trabajando», «Libre»).
    - **Varios días**: conteo por tipo en todo el periodo (incluye marcas manuales
      como libre en un día concreto); como mucho tres categorías y «…» si hay más.

    No se usa solo «hoy» en rangos largos: si no, se ocultarían días marcados
    como libre u otros en el mismo periodo.
    """
    from app.empleados.calendario_servicios import (
        mapa_clasificaciones_manual_rango,
        resolver_estado_dia_laboral,
    )

    manual_map = mapa_clasificaciones_manual_rango(
        [empleado_id], fecha_inicio, fecha_fin
    )

    if fecha_inicio == fecha_fin:
        cls = manual_map.get((empleado_id, fecha_inicio))
        r = resolver_estado_dia_laboral(empleado_id, fecha_inicio, manual=cls)
        return etiqueta_estado_dia_laboral(r["estado"])

    conteo: Counter[str] = Counter()
    d = fecha_inicio
    while d <= fecha_fin:
        cls = manual_map.get((empleado_id, d))
        r = resolver_estado_dia_laboral(empleado_id, d, manual=cls)
        conteo[r["estado"]] += 1
        d += timedelta(days=1)

    orden = [
        ("trabajado", "Trabajo"),
        ("vacaciones", "Vacaciones"),
        (TipoClasificacionDiaLaboral.LIBRE, "Libre"),
        (TipoClasificacionDiaLaboral.AUSENCIA_JUSTIFICADA, "Ausencia justif."),
        (TipoClasificacionDiaLaboral.AUSENCIA_NO_JUSTIFICADA, "Ausencia no justif."),
        ("pendiente", "Pendiente"),
        ("no_laborable", "No laborable"),
    ]
    partes: List[str] = []
    for clave, etiqueta in orden:
        n = conteo.get(clave, 0)
        if n:
            partes.append(f"{etiqueta} {n}")
    if len(partes) > 3:
        return " · ".join(partes[:3]) + " · …"
    return " · ".join(partes) if partes else "—"


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
    # Alcance (no superadmin): empresa y/o equipo del responsable
    empresa_id_alcance: Optional[int] = None
    responsable_usuario_id_equipo: Optional[int] = None
    responsable_empleado_id_legacy: Optional[int] = None


def empleados_filtrados(f: FiltrosInforme) -> List[Empleado]:
    """Lista de empleados según filtros de informe."""
    from sqlalchemy import or_

    q = Empleado.query.filter_by(activo=True)
    if f.empresa_id_alcance is not None:
        q = q.filter(Empleado.empresa_id == f.empresa_id_alcance)
    if f.responsable_usuario_id_equipo is not None:
        cond_eq = [Empleado.responsable_usuario_id == f.responsable_usuario_id_equipo]
        if f.responsable_empleado_id_legacy is not None:
            cond_eq.append(
                Empleado.responsable_id == f.responsable_empleado_id_legacy
            )
        q = q.filter(or_(*cond_eq))
    if f.empleado_id is not None:
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
        det["fecha_dia"] = d
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
                "resumen_tipos_dia": resumen_tipos_dia_periodo(
                    emp.id, f.fecha_inicio, f.fecha_fin
                ),
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
