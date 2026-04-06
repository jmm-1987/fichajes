"""Calendario agregado del equipo en el panel (mensual / semanal)."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from typing import Any

from flask_login import current_user
from sqlalchemy import or_

from app.constantes import RolUsuario, TipoClasificacionDiaLaboral
from app.empleados.calendario_servicios import (
    mapa_clasificaciones_manual_rango,
    resolver_estado_dia_laboral,
)
from app.fichajes.calculos import tipo_apariencia_calendario_no_laborable
from app.inicio.servicios import empleado_dentro_jornada, inicio_dia_local
from app.modelos import Empleado
from app.utilidades.predicados import obtener_id_empleado_actual


def empleados_alcance_panel() -> list[Empleado]:
    """Empleados activos visibles según rol (empresa / equipo)."""
    q = Empleado.query.filter_by(activo=True)
    if current_user.rol == RolUsuario.SUPERADMINISTRADOR:
        return q.order_by(Empleado.apellidos, Empleado.nombre).all()
    empresa_id = getattr(current_user, "empresa_id", None)
    emp_actual = getattr(current_user, "empleado", None)
    if not empresa_id and emp_actual:
        empresa_id = emp_actual.empresa_id
    if empresa_id:
        q = q.filter(Empleado.empresa_id == empresa_id)
    if current_user.rol == RolUsuario.RESPONSABLE:
        cond_r = [Empleado.responsable_usuario_id == current_user.id]
        eid = obtener_id_empleado_actual()
        if eid:
            cond_r.append(Empleado.responsable_id == eid)
        q = q.filter(or_(*cond_r))
    return q.order_by(Empleado.apellidos, Empleado.nombre).all()


def lunes_semana_conteniendo(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _vinieron_a_trabajar_hoy_o_dia(
    r: dict[str, Any],
    empleado_id: int,
    d: date,
    hoy: date,
) -> bool:
    """
    Cuenta como «han trabajado / están en jornada»:
    jornada cerrada (trabajado), horas registradas en el día (p. ej. dentro sin salida),
    o hoy mismo si siguen dentro de jornada.
    """
    estado = r["estado"]
    if estado in (
        "vacaciones",
        "libre",
        TipoClasificacionDiaLaboral.AUSENCIA_JUSTIFICADA,
        TipoClasificacionDiaLaboral.AUSENCIA_NO_JUSTIFICADA,
    ):
        return False
    if estado == "trabajado":
        return True
    if float(r.get("horas_trabajadas") or 0) > 0:
        return True
    if d == hoy and empleado_dentro_jornada(empleado_id):
        return True
    return False


def _agregar_celda_dia(
    d: date,
    empleados: list[Empleado],
    manual_map: dict[tuple[int, date], Any],
    *,
    hoy: date,
    empresa_id_cal: int | None,
) -> dict[str, Any]:
    vinieron = 0
    no_vinieron = 0
    laborables = 0
    for emp in empleados:
        cls = manual_map.get((emp.id, d))
        r = resolver_estado_dia_laboral(emp.id, d, manual=cls)
        if not r["laborable"]:
            continue
        laborables += 1
        if _vinieron_a_trabajar_hoy_o_dia(r, emp.id, d, hoy):
            vinieron += 1
        else:
            no_vinieron += 1
    estilo_nl = None
    if laborables == 0 and empresa_id_cal is not None:
        estilo_nl = tipo_apariencia_calendario_no_laborable(d, empresa_id_cal)

    return {
        "fecha": d,
        "fecha_iso": d.isoformat(),
        "dia": d.day,
        "weekday": d.weekday(),
        "vinieron": vinieron,
        "no_vinieron": no_vinieron,
        "laborables": laborables,
        "estilo_no_laborable": estilo_nl,
    }


def construir_calendario_equipo_mes(anio: int, mes: int, empleados: list[Empleado]) -> dict[str, Any]:
    ult = monthrange(anio, mes)[1]
    desde = date(anio, mes, 1)
    hasta = date(anio, mes, ult)
    ids = [e.id for e in empleados]
    manual_map = mapa_clasificaciones_manual_rango(ids, desde, hasta)
    hoy = inicio_dia_local()
    empresa_id_cal = empleados[0].empresa_id if empleados else None
    celdas: list[dict[str, Any]] = []
    d = desde
    while d <= hasta:
        celdas.append(
            _agregar_celda_dia(
                d, empleados, manual_map, hoy=hoy, empresa_id_cal=empresa_id_cal
            )
        )
        d += timedelta(days=1)
    pad_ini = date(anio, mes, 1).weekday()
    pad_fin = (7 - (pad_ini + ult) % 7) % 7
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
    return {
        "mes": mes,
        "anio": anio,
        "titulo": f"{nombres_meses[mes - 1]} {anio}",
        "celdas": celdas,
        "padding_inicio": pad_ini,
        "padding_fin": pad_fin,
        "prev": {"mes": prev_mes, "anio": prev_anio},
        "sig": {"mes": sig_mes, "anio": sig_anio},
    }


def construir_calendario_equipo_semana(lunes: date, empleados: list[Empleado]) -> dict[str, Any]:
    hasta = lunes + timedelta(days=6)
    ids = [e.id for e in empleados]
    manual_map = mapa_clasificaciones_manual_rango(ids, lunes, hasta)
    hoy = inicio_dia_local()
    empresa_id_cal = empleados[0].empresa_id if empleados else None
    celdas: list[dict[str, Any]] = []
    d = lunes
    while d <= hasta:
        celdas.append(
            _agregar_celda_dia(
                d, empleados, manual_map, hoy=hoy, empresa_id_cal=empresa_id_cal
            )
        )
        d += timedelta(days=1)
    prev_lunes = lunes - timedelta(days=7)
    sig_lunes = lunes + timedelta(days=7)
    return {
        "lunes": lunes,
        "titulo": f"Semana {lunes.strftime('%d/%m')} — {hasta.strftime('%d/%m/%Y')}",
        "celdas": celdas,
        "padding_inicio": 0,
        "padding_fin": 0,
        "prev": {"semana": prev_lunes.isoformat()},
        "sig": {"semana": sig_lunes.isoformat()},
    }


def detalle_dia_equipo_json(fecha: date, empleados: list[Empleado]) -> dict[str, Any]:
    """Datos para el modal del día (listas por categoría)."""
    ids = [e.id for e in empleados]
    manual_map = mapa_clasificaciones_manual_rango(ids, fecha, fecha)
    hoy = inicio_dia_local()
    es_hoy = fecha == hoy

    trabajaron: list[dict[str, Any]] = []
    vacaciones: list[dict[str, Any]] = []
    libre: list[dict[str, Any]] = []
    ausencias: list[dict[str, Any]] = []
    pendientes: list[dict[str, Any]] = []
    dentro_ahora: list[dict[str, Any]] = []
    fuera_ahora: list[dict[str, Any]] = []

    for emp in empleados:
        cls = manual_map.get((emp.id, fecha))
        r = resolver_estado_dia_laboral(emp.id, fecha, manual=cls)
        estado = r["estado"]
        laborable = r["laborable"]
        horas = round(r["horas_trabajadas"], 2)
        nombre = emp.nombre_completo
        eid = emp.id

        if estado == "trabajado":
            trabajaron.append({"id": eid, "nombre": nombre, "horas": horas})

        if estado == "vacaciones":
            vacaciones.append({"id": eid, "nombre": nombre})
        elif estado == "libre":
            libre.append({"id": eid, "nombre": nombre, "motivo": r["motivo"] or ""})
        elif estado in (
            TipoClasificacionDiaLaboral.AUSENCIA_JUSTIFICADA,
            TipoClasificacionDiaLaboral.AUSENCIA_NO_JUSTIFICADA,
        ):
            ausencias.append(
                {
                    "id": eid,
                    "nombre": nombre,
                    "tipo": "ausencia justificada"
                    if estado == TipoClasificacionDiaLaboral.AUSENCIA_JUSTIFICADA
                    else "ausencia no justificada",
                    "motivo": r["motivo"] or "",
                }
            )
        elif laborable and estado == "pendiente":
            pendientes.append({"id": eid, "nombre": nombre})

        if es_hoy and laborable:
            if estado in (
                "vacaciones",
                "libre",
                TipoClasificacionDiaLaboral.AUSENCIA_JUSTIFICADA,
                TipoClasificacionDiaLaboral.AUSENCIA_NO_JUSTIFICADA,
            ):
                pass
            elif empleado_dentro_jornada(eid):
                dentro_ahora.append({"id": eid, "nombre": nombre, "horas": horas})
            else:
                fuera_ahora.append({"id": eid, "nombre": nombre, "horas": horas})

    return {
        "fecha": fecha.isoformat(),
        "fecha_texto": fecha.strftime("%d/%m/%Y"),
        "es_hoy": es_hoy,
        "trabajaron": trabajaron,
        "vacaciones": vacaciones,
        "libre": libre,
        "ausencias": ausencias,
        "pendientes": pendientes,
        "dentro_ahora": dentro_ahora,
        "fuera_ahora": fuera_ahora,
    }
