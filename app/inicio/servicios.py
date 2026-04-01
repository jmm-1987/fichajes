"""Agregados para widgets del panel de inicio."""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import or_

from app.constantes import EstadoRegistroJornada, EstadoSolicitudVacaciones
from app.extensiones import db
from app.modelos import Empleado, RegistroJornada, SolicitudCorreccion, SolicitudVacaciones


def inicio_dia_local() -> date:
    """Fecha local simple (servidor); en producción usar zona de empresa."""
    return datetime.now(timezone.utc).date()


def contar_empleados_activos() -> int:
    return Empleado.query.filter_by(activo=True).count()


def contar_fichajes_hoy() -> int:
    hoy = inicio_dia_local()
    inicio = datetime.combine(hoy, datetime.min.time()).replace(tzinfo=timezone.utc)
    fin = inicio + timedelta(days=1)
    return (
        RegistroJornada.query.filter(
            RegistroJornada.fecha_hora_servidor >= inicio,
            RegistroJornada.fecha_hora_servidor < fin,
            RegistroJornada.estado != EstadoRegistroJornada.ANULADO,
        ).count()
    )


def jornadas_incompletas_hoy_ids() -> list[int]:
    """Empleados activos con entrada hoy pero sin salida (heurística simple)."""
    hoy = inicio_dia_local()
    inicio = datetime.combine(hoy, datetime.min.time()).replace(tzinfo=timezone.utc)
    fin = inicio + timedelta(days=1)
    empleados = Empleado.query.filter_by(activo=True).all()
    incompletos = []
    for emp in empleados:
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


def resumen_equipo_admin(vista: str = "dia") -> list[dict]:
    """
    Lista de empleados con estado actual y horas.
    vista: 'dia', 'semana' o 'mes'
    """
    from app.fichajes.calculos import calcular_resumen_periodo

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

    empleados = Empleado.query.filter_by(activo=True).order_by(
        Empleado.apellidos, Empleado.nombre
    )

    resultado = []
    for emp in empleados:
        res = calcular_resumen_periodo(emp.id, inicio, fin)
        resultado.append(
            {
                "id": emp.id,
                "nombre": emp.nombre_completo,
                "empresa": getattr(emp.empresa, "nombre", None),
                "dentro": empleado_dentro_jornada(emp.id),
                "horas": res.get("horas_trabajadas", 0),
            }
        )
    return resultado


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
    """True si el último fichaje relevante sugiere que está en jornada."""
    ultimo = ultimo_fichaje_empleado(empleado_id)
    if not ultimo:
        return False
    if ultimo.tipo_registro in ("entrada", "pausa_fin"):
        return True
    if ultimo.tipo_registro in ("salida", "pausa_inicio"):
        return False
    return False


def resumen_panel_empleado(empleado_id: int) -> dict:
    """Widgets del portal empleado."""
    from app.fichajes.calculos import calcular_resumen_periodo

    hoy = inicio_dia_local()
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
