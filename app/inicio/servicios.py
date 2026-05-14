"""Agregados para widgets del panel de inicio."""

from datetime import date, datetime, timedelta

from sqlalchemy import or_

from app.constantes import (
    EstadoRegistroJornada,
    EstadoSolicitudVacaciones,
    TipoRegistroJornada,
)
from app.extensiones import db
from app.modelos import Empleado, RegistroJornada, SolicitudCorreccion, SolicitudVacaciones
from app.utilidades.fechas import (
    ZONA_MADRID,
    hoy_calendario_en_zona,
    intervalo_utc_dia_en_zona,
)


def inicio_dia_local() -> date:
    """Fecha calendario en Europa/Madrid (referencia para panel y rangos globales)."""
    return hoy_calendario_en_zona(ZONA_MADRID)


def contar_empleados_activos() -> int:
    return Empleado.query.filter_by(activo=True).count()


def contar_fichajes_hoy() -> int:
    hoy = inicio_dia_local()
    inicio, fin = intervalo_utc_dia_en_zona(hoy, ZONA_MADRID)
    return (
        RegistroJornada.query.filter(
            RegistroJornada.fecha_hora_servidor >= inicio,
            RegistroJornada.fecha_hora_servidor < fin,
            RegistroJornada.estado != EstadoRegistroJornada.ANULADO,
        ).count()
    )


def jornadas_incompletas_hoy_ids() -> list[int]:
    """Empleados activos con entrada hoy pero sin salida (heurística simple)."""
    from app.fichajes.zona_trabajo import fecha_calendario_hoy_para_empleado, zona_trabajo_para_empleado

    empleados = Empleado.query.filter_by(activo=True).all()
    incompletos = []
    for emp in empleados:
        hoy_e = fecha_calendario_hoy_para_empleado(emp.id)
        zona = zona_trabajo_para_empleado(emp.id)
        inicio, fin = intervalo_utc_dia_en_zona(hoy_e, zona)
        regs = (
            RegistroJornada.query.filter(
                RegistroJornada.empleado_id == emp.id,
                RegistroJornada.fecha_hora_servidor >= inicio,
                RegistroJornada.fecha_hora_servidor < fin,
                RegistroJornada.estado != EstadoRegistroJornada.ANULADO,
            )
            .order_by(RegistroJornada.fecha_hora_servidor)
            .all()
        )
        tipos = [r.tipo_registro for r in regs]
        if "entrada" in tipos and "salida" not in tipos:
            incompletos.append(emp.id)
    return incompletos


def solicitudes_correccion_pendientes() -> int:
    return SolicitudCorreccion.query.filter_by(estado="pendiente").count()


def vacaciones_pendientes_aprobar() -> int:
    return SolicitudVacaciones.query.filter_by(
        estado=EstadoSolicitudVacaciones.PENDIENTE
    ).count()


def resumen_panel_administrador() -> dict:
    """Datos para tarjetas del dashboard RRHH/admin."""
    return {
        "empleados_activos": contar_empleados_activos(),
        "fichajes_hoy": contar_fichajes_hoy(),
        "jornadas_incompletas": len(jornadas_incompletas_hoy_ids()),
        "incidencias_pendientes": solicitudes_correccion_pendientes(),
        "vacaciones_pendientes": vacaciones_pendientes_aprobar(),
    }


def _mapa_primera_entrada_ultima_salida_hoy(
    empleado_ids: list[int],
) -> dict[int, tuple[str, str]]:
    """
    Primera entrada y última salida del día de trabajo efectivo (incluye cierre de
    turnos nocturnos como en clasificar_dia), en hora local de la zona del empleado.
    """
    from app.fichajes.calculos import obtener_registros_dia_para_clasificacion
    from app.fichajes.zona_trabajo import fecha_calendario_hoy_para_empleado
    from app.utilidades.fechas import formatear_hora_corta

    if not empleado_ids:
        return {}
    salida: dict[int, tuple[str, str]] = {}
    for eid in empleado_ids:
        hoy_e = fecha_calendario_hoy_para_empleado(eid)
        lista = obtener_registros_dia_para_clasificacion(eid, hoy_e)
        primera_entrada: datetime | None = None
        ultima_salida: datetime | None = None
        for r in lista:
            if r.tipo_registro == TipoRegistroJornada.ENTRADA:
                if primera_entrada is None:
                    primera_entrada = r.fecha_hora_servidor
            elif r.tipo_registro == TipoRegistroJornada.SALIDA:
                ultima_salida = r.fecha_hora_servidor
        salida[eid] = (
            formatear_hora_corta(primera_entrada),
            formatear_hora_corta(ultima_salida),
        )
    return salida


def _rango_resumen_equipo(vista: str) -> tuple[date, date]:
    """Inicio y fin (inclusive) para horas del resumen de equipo."""
    hoy = inicio_dia_local()
    if vista == "semana":
        inicio = hoy - timedelta(days=hoy.weekday())
        fin = inicio + timedelta(days=6)
    elif vista == "mes":
        inicio = hoy.replace(day=1)
        if inicio.month == 12:
            siguiente = inicio.replace(year=inicio.year + 1, month=1, day=1)
        else:
            siguiente = inicio.replace(month=inicio.month + 1, day=1)
        fin = siguiente - timedelta(days=1)
    else:
        inicio = hoy
        fin = hoy
    return inicio, fin


def resumen_equipo_para_empleados(
    empleados: list[Empleado], vista: str = "dia"
) -> list[dict]:
    """
    Lista de empleados con estado actual y horas en el periodo (hoy / semana / mes).
    """
    from app.empleados.calendario_servicios import resolver_estado_dia_laboral
    from app.fichajes.calculos import calcular_resumen_periodo
    from app.fichajes.zona_trabajo import fecha_calendario_hoy_para_empleado

    inicio, fin = _rango_resumen_equipo(vista)
    resultado = []
    ids = [e.id for e in empleados]
    entradas_salidas = (
        _mapa_primera_entrada_ultima_salida_hoy(ids) if vista == "dia" else {}
    )
    for emp in empleados:
        if vista == "dia":
            h_e = fecha_calendario_hoy_para_empleado(emp.id)
            res = calcular_resumen_periodo(emp.id, h_e, h_e)
        else:
            res = calcular_resumen_periodo(emp.id, inicio, fin)
        estado_dia = None
        if vista == "dia":
            estado_dia = resolver_estado_dia_laboral(
                emp.id, fecha_calendario_hoy_para_empleado(emp.id)
            ).get("estado")
        hent, hsal = ("—", "—")
        if vista == "dia":
            hent, hsal = entradas_salidas.get(emp.id, ("—", "—"))
        resultado.append(
            {
                "id": emp.id,
                "nombre": emp.nombre_completo,
                "empresa": getattr(emp.empresa, "nombre", None),
                "dentro": empleado_dentro_jornada(emp.id),
                "horas": res.get("horas_trabajadas", 0),
                "estado_dia": estado_dia,
                "hora_entrada": hent,
                "hora_salida": hsal,
            }
        )
    return resultado


def resumen_equipo_admin(vista: str = "dia") -> list[dict]:
    """
    Lista de empleados activos (todos) con estado actual y horas.
    vista: 'dia', 'semana' o 'mes'
    """
    empleados = (
        Empleado.query.filter_by(activo=True)
        .order_by(Empleado.apellidos, Empleado.nombre)
        .all()
    )
    return resumen_equipo_para_empleados(empleados, vista)


def ultimo_fichaje_empleado(empleado_id: int) -> RegistroJornada | None:
    return (
        RegistroJornada.query.filter(
            RegistroJornada.empleado_id == empleado_id,
            RegistroJornada.estado != EstadoRegistroJornada.ANULADO,
        )
        .order_by(RegistroJornada.fecha_hora_servidor.desc())
        .first()
    )


def empleado_dentro_jornada(empleado_id: int) -> bool:
    """True si el estado de hoy indica jornada abierta."""
    from app.fichajes.zona_trabajo import fecha_calendario_hoy_para_empleado, zona_trabajo_para_empleado

    hoy_e = fecha_calendario_hoy_para_empleado(empleado_id)
    zona = zona_trabajo_para_empleado(empleado_id)
    inicio, fin = intervalo_utc_dia_en_zona(hoy_e, zona)
    ult_hoy = (
        RegistroJornada.query.filter(
            RegistroJornada.empleado_id == empleado_id,
            RegistroJornada.fecha_hora_servidor >= inicio,
            RegistroJornada.fecha_hora_servidor < fin,
            RegistroJornada.estado != EstadoRegistroJornada.ANULADO,
        )
        .order_by(RegistroJornada.fecha_hora_servidor.desc())
        .first()
    )
    if not ult_hoy:
        return False
    if ult_hoy.tipo_registro in ("entrada", "pausa_fin"):
        return True
    if ult_hoy.tipo_registro in ("salida", "pausa_inicio"):
        return False
    return False


def resumen_panel_empleado(empleado_id: int) -> dict:
    """Widgets del portal empleado."""
    from app.fichajes.calculos import calcular_resumen_periodo
    from app.fichajes.zona_trabajo import fecha_calendario_hoy_para_empleado

    hoy = fecha_calendario_hoy_para_empleado(empleado_id)
    inicio_sem = hoy - timedelta(days=hoy.weekday())
    fin_sem = inicio_sem + timedelta(days=6)
    res_hoy = calcular_resumen_periodo(empleado_id, hoy, hoy)
    res_sem = calcular_resumen_periodo(empleado_id, inicio_sem, fin_sem)

    prox_vac = (
        SolicitudVacaciones.query.filter(
            SolicitudVacaciones.empleado_id == empleado_id,
            or_(
                SolicitudVacaciones.estado == EstadoSolicitudVacaciones.APROBADO,
                SolicitudVacaciones.estado == EstadoSolicitudVacaciones.PENDIENTE,
            ),
            SolicitudVacaciones.fecha_inicio >= hoy,
        )
        .order_by(SolicitudVacaciones.fecha_inicio)
        .first()
    )

    pend_corr = SolicitudCorreccion.query.filter_by(
        empleado_id=empleado_id,
        estado="pendiente",
    ).count()

    return {
        "dentro": empleado_dentro_jornada(empleado_id),
        "ultimo_fichaje": ultimo_fichaje_empleado(empleado_id),
        "horas_hoy": res_hoy.get("horas_trabajadas", 0),
        "horas_semana": res_sem.get("horas_trabajadas", 0),
        "proximas_vacaciones": prox_vac,
        "solicitudes_pendientes": pend_corr,
    }
