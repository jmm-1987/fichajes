"""Calendario laboral mensual: trabajado automático, vacaciones (solicitudes + manual), libre, ausencias."""

from calendar import monthrange
from datetime import date, timedelta
from typing import Any

from app.constantes import EstadoSolicitudVacaciones, TipoClasificacionDiaLaboral
from app.extensiones import db
from app.fichajes.calculos import (
    clasificar_dia,
    es_festivo,
    tipo_apariencia_calendario_no_laborable,
)
from app.modelos import ClasificacionDiaLaboral, Empleado, SolicitudVacaciones


def _dia_en_vacaciones_solicitud(empleado_id: int, d: date) -> bool:
    q = SolicitudVacaciones.query.filter(
        SolicitudVacaciones.empleado_id == empleado_id,
        SolicitudVacaciones.estado.in_(
            (
                EstadoSolicitudVacaciones.APROBADO,
                EstadoSolicitudVacaciones.DISFRUTADO,
            )
        ),
        SolicitudVacaciones.fecha_inicio <= d,
        SolicitudVacaciones.fecha_fin >= d,
    )
    return q.first() is not None


def _mapa_clasificaciones_manual(empleado_id: int, desde: date, hasta: date) -> dict[date, ClasificacionDiaLaboral]:
    filas = (
        ClasificacionDiaLaboral.query.filter(
            ClasificacionDiaLaboral.empleado_id == empleado_id,
            ClasificacionDiaLaboral.fecha >= desde,
            ClasificacionDiaLaboral.fecha <= hasta,
        )
        .order_by(ClasificacionDiaLaboral.fecha)
        .all()
    )
    return {c.fecha: c for c in filas}


def _normalizar_tipo_clasificacion(tipo: str) -> str:
    """Compatibilidad: absentismo antiguo → ausencia no justificada."""
    if tipo == TipoClasificacionDiaLaboral.ABSENTISMO_LEGACY:
        return TipoClasificacionDiaLaboral.AUSENCIA_NO_JUSTIFICADA
    return tipo


def mapa_clasificaciones_manual_rango(
    empleado_ids: list[int], desde: date, hasta: date
) -> dict[tuple[int, date], ClasificacionDiaLaboral]:
    """Clasificaciones manuales para varios empleados en un rango de fechas."""
    if not empleado_ids:
        return {}
    filas = (
        ClasificacionDiaLaboral.query.filter(
            ClasificacionDiaLaboral.empleado_id.in_(empleado_ids),
            ClasificacionDiaLaboral.fecha >= desde,
            ClasificacionDiaLaboral.fecha <= hasta,
        )
        .order_by(ClasificacionDiaLaboral.fecha)
        .all()
    )
    return {(c.empleado_id, c.fecha): c for c in filas}


def resolver_estado_dia_laboral(
    empleado_id: int,
    fecha: date,
    *,
    manual: ClasificacionDiaLaboral | None = None,
) -> dict[str, Any]:
    """
    Estado laboral de un empleado en un día (misma lógica que el calendario de ficha).
    `manual`: fila ya cargada o None para consultar.
    """
    emp = Empleado.query.get(empleado_id)
    if not emp:
        raise ValueError("Empleado no encontrado")
    empresa_id = emp.empresa_id
    laborable = not es_festivo(fecha, empresa_id)
    part = clasificar_dia(empleado_id, fecha)
    trabajado_auto = laborable and (
        not part["jornada_incompleta"] and part["horas_trabajadas"] > 0
    )
    en_vac_sol = laborable and _dia_en_vacaciones_solicitud(empleado_id, fecha)
    cls = manual
    if cls is None:
        cls = (
            ClasificacionDiaLaboral.query.filter_by(
                empleado_id=empleado_id,
                fecha=fecha,
            ).first()
        )

    estado = "no_laborable"
    motivo: str | None = None
    fuente_vacaciones: str | None = None

    if not laborable:
        estado = "no_laborable"
    elif en_vac_sol:
        estado = "vacaciones"
        fuente_vacaciones = "solicitud"
    elif cls is not None:
        tnorm = _normalizar_tipo_clasificacion(cls.tipo)
        estado = tnorm
        motivo = cls.motivo
        if tnorm == TipoClasificacionDiaLaboral.VACACIONES:
            fuente_vacaciones = "manual"
    elif trabajado_auto:
        estado = "trabajado"
    else:
        estado = "pendiente"

    return {
        "estado": estado,
        "laborable": laborable,
        "horas_trabajadas": float(part["horas_trabajadas"]),
        "motivo": motivo,
        "fuente_vacaciones": fuente_vacaciones,
    }


def construir_calendario_mes(
    empleado_id: int,
    mes: int,
    anio: int,
    *,
    puede_editar: bool,
) -> dict[str, Any]:
    """Devuelve celdas del mes, contadores y metadatos de navegación."""
    emp = Empleado.query.get(empleado_id)
    if not emp:
        raise ValueError("Empleado no encontrado")

    ult = monthrange(anio, mes)[1]
    desde = date(anio, mes, 1)
    hasta = date(anio, mes, ult)
    empresa_id = emp.empresa_id

    manual = _mapa_clasificaciones_manual(empleado_id, desde, hasta)

    celdas: list[dict[str, Any]] = []
    contadores = {
        "trabajado": 0,
        "vacaciones": 0,
        "libre": 0,
        "ausencia_justificada": 0,
        "ausencia_no_justificada": 0,
    }

    d = desde
    while d <= hasta:
        cls = manual.get(d)
        r = resolver_estado_dia_laboral(empleado_id, d, manual=cls)
        estado = r["estado"]
        laborable = r["laborable"]
        motivo = r["motivo"]
        fuente_vacaciones = r["fuente_vacaciones"]

        if laborable:
            if estado == "vacaciones":
                contadores["vacaciones"] += 1
            elif estado == TipoClasificacionDiaLaboral.LIBRE:
                contadores["libre"] += 1
            elif estado == TipoClasificacionDiaLaboral.AUSENCIA_JUSTIFICADA:
                contadores["ausencia_justificada"] += 1
            elif estado == TipoClasificacionDiaLaboral.AUSENCIA_NO_JUSTIFICADA:
                contadores["ausencia_no_justificada"] += 1
            elif estado == "trabajado":
                contadores["trabajado"] += 1

        editable = bool(
            puede_editar
            and laborable
            and not (laborable and _dia_en_vacaciones_solicitud(empleado_id, d))
        )

        estilo_nl = (
            tipo_apariencia_calendario_no_laborable(d, empresa_id)
            if not laborable
            else None
        )
        celdas.append(
            {
                "fecha": d,
                "dia": d.day,
                "weekday": d.weekday(),
                "laborable": laborable,
                "estado": estado,
                "fuente_vacaciones": fuente_vacaciones,
                "motivo": motivo,
                "editable": editable,
                "clasificacion_id": cls.id if cls else None,
                "estilo_no_laborable": estilo_nl,
            }
        )
        d += timedelta(days=1)

    prev_mes = mes - 1
    prev_anio = anio
    if prev_mes < 1:
        prev_mes = 12
        prev_anio -= 1
    sig_mes = mes + 1
    sig_anio = anio
    if sig_mes > 12:
        sig_mes = 1
        sig_anio += 1

    nombres_meses = (
        "Enero",
        "Febrero",
        "Marzo",
        "Abril",
        "Mayo",
        "Junio",
        "Julio",
        "Agosto",
        "Septiembre",
        "Octubre",
        "Noviembre",
        "Diciembre",
    )

    pad_ini = date(anio, mes, 1).weekday()
    pad_fin = (7 - (pad_ini + ult) % 7) % 7

    return {
        "mes": mes,
        "anio": anio,
        "titulo_mes": f"{nombres_meses[mes - 1]} {anio}",
        "celdas": celdas,
        "contadores": contadores,
        "prev": {"mes": prev_mes, "anio": prev_anio},
        "sig": {"mes": sig_mes, "anio": sig_anio},
        "padding_inicio": pad_ini,
        "padding_fin": pad_fin,
    }


def aplicar_clasificacion_dia(
    empleado_id: int,
    fecha: date,
    tipo: str,
    motivo: str | None,
    usuario_id: int,
) -> tuple[bool, str]:
    """
    Guarda o elimina clasificación manual.
    tipo: vacaciones, libre, ausencia_justificada, ausencia_no_justificada o borrar.
    """
    emp = Empleado.query.get(empleado_id)
    if not emp:
        return False, "Empleado no encontrado."

    if tipo == "borrar":
        row = ClasificacionDiaLaboral.query.filter_by(
            empleado_id=empleado_id,
            fecha=fecha,
        ).first()
        if row:
            db.session.delete(row)
            db.session.commit()
        return True, "Clasificación eliminada."

    if tipo not in (
        TipoClasificacionDiaLaboral.VACACIONES,
        TipoClasificacionDiaLaboral.LIBRE,
        TipoClasificacionDiaLaboral.AUSENCIA_JUSTIFICADA,
        TipoClasificacionDiaLaboral.AUSENCIA_NO_JUSTIFICADA,
    ):
        return False, "Tipo no válido."

    m = (motivo or "").strip()
    if tipo in (
        TipoClasificacionDiaLaboral.LIBRE,
        TipoClasificacionDiaLaboral.AUSENCIA_JUSTIFICADA,
        TipoClasificacionDiaLaboral.AUSENCIA_NO_JUSTIFICADA,
    ):
        if not m:
            return False, "Indique el motivo para libre o ausencias."

    if _dia_en_vacaciones_solicitud(empleado_id, fecha) and tipo in (
        TipoClasificacionDiaLaboral.VACACIONES,
        TipoClasificacionDiaLaboral.LIBRE,
        TipoClasificacionDiaLaboral.AUSENCIA_JUSTIFICADA,
        TipoClasificacionDiaLaboral.AUSENCIA_NO_JUSTIFICADA,
    ):
        return False, "Este día ya está cubierto por vacaciones aprobadas en el sistema."

    row = ClasificacionDiaLaboral.query.filter_by(
        empleado_id=empleado_id,
        fecha=fecha,
    ).first()
    if row is None:
        row = ClasificacionDiaLaboral(
            empleado_id=empleado_id,
            fecha=fecha,
            tipo=tipo,
            motivo=m or None,
            creado_por_usuario_id=usuario_id,
        )
        db.session.add(row)
    else:
        row.tipo = tipo
        row.motivo = m or None
        row.creado_por_usuario_id = usuario_id
    db.session.commit()
    return True, "Clasificación guardada."
