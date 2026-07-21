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


def contar_empleados_activos(empleado_ids: list[int] | None = None) -> int:
    q = Empleado.query.filter_by(activo=True)
    if empleado_ids is not None:
        if not empleado_ids:
            return 0
        q = q.filter(Empleado.id.in_(empleado_ids))
    return q.count()


def contar_fichajes_hoy(empleado_ids: list[int] | None = None) -> int:
    hoy = inicio_dia_local()
    inicio, fin = intervalo_utc_dia_en_zona(hoy, ZONA_MADRID)
    q = RegistroJornada.query.filter(
        RegistroJornada.fecha_hora_servidor >= inicio,
        RegistroJornada.fecha_hora_servidor < fin,
        RegistroJornada.estado != EstadoRegistroJornada.ANULADO,
    )
    if empleado_ids is not None:
        if not empleado_ids:
            return 0
        q = q.filter(RegistroJornada.empleado_id.in_(empleado_ids))
    return q.count()


def jornadas_incompletas_hoy_ids(empleado_ids: list[int] | None = None) -> list[int]:
    """Empleados activos con entrada hoy pero sin salida (heurística simple)."""
    from app.fichajes.zona_trabajo import fecha_calendario_hoy_para_empleado, zona_trabajo_para_empleado

    q = Empleado.query.filter_by(activo=True)
    if empleado_ids is not None:
        if not empleado_ids:
            return []
        q = q.filter(Empleado.id.in_(empleado_ids))
    empleados = q.all()
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


def solicitudes_correccion_pendientes(empleado_ids: list[int] | None = None) -> int:
    q = SolicitudCorreccion.query.filter_by(estado="pendiente")
    if empleado_ids is not None:
        if not empleado_ids:
            return 0
        q = q.filter(SolicitudCorreccion.empleado_id.in_(empleado_ids))
    return q.count()


def vacaciones_pendientes_aprobar(empleado_ids: list[int] | None = None) -> int:
    q = SolicitudVacaciones.query.filter_by(
        estado=EstadoSolicitudVacaciones.PENDIENTE
    )
    if empleado_ids is not None:
        if not empleado_ids:
            return 0
        q = q.filter(SolicitudVacaciones.empleado_id.in_(empleado_ids))
    return q.count()


def resumen_panel_administrador(empleados: list[Empleado]) -> dict:
    """Datos para tarjetas del dashboard RRHH/admin (alcance empresa/equipo)."""
    ids = [e.id for e in empleados]
    return {
        "empleados_activos": len(empleados),
        "fichajes_hoy": contar_fichajes_hoy(ids),
        "jornadas_incompletas": len(jornadas_incompletas_hoy_ids(ids)),
        "incidencias_pendientes": solicitudes_correccion_pendientes(ids),
        "vacaciones_pendientes": vacaciones_pendientes_aprobar(ids),
    }


def _mapa_primera_entrada_ultima_salida_dia(
    empleado_ids: list[int],
    dia: date,
) -> dict[int, tuple[str, str]]:
    """
    Primera entrada y última salida del día de trabajo efectivo (incluye cierre de
    turnos nocturnos como en clasificar_dia), en hora local de la zona del empleado.
    """
    from app.fichajes.calculos import obtener_registros_dia_para_clasificacion
    from app.utilidades.fechas import formatear_hora_corta

    if not empleado_ids:
        return {}
    salida: dict[int, tuple[str, str]] = {}
    for eid in empleado_ids:
        lista = obtener_registros_dia_para_clasificacion(eid, dia)
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


def _rango_resumen_equipo(
    vista: str, fecha_dia: date | None = None
) -> tuple[date, date]:
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
        inicio = fecha_dia or hoy
        fin = inicio
    return inicio, fin


def resumen_equipo_para_empleados(
    empleados: list[Empleado],
    vista: str = "dia",
    fecha_dia: date | None = None,
) -> list[dict]:
    """
    Lista de empleados con estado actual y horas en el periodo (hoy / semana / mes).
    """
    from app.empleados.calendario_servicios import resolver_estado_dia_laboral
    from app.fichajes.calculos import calcular_resumen_periodo
    from app.fichajes.zona_trabajo import fecha_calendario_hoy_para_empleado

    inicio, fin = _rango_resumen_equipo(vista, fecha_dia)
    resultado = []
    ids = [e.id for e in empleados]
    dia_consulta = fecha_dia or inicio_dia_local()
    entradas_salidas = (
        _mapa_primera_entrada_ultima_salida_dia(ids, dia_consulta)
        if vista == "dia"
        else {}
    )
    for emp in empleados:
        if vista == "dia":
            h_e = dia_consulta
            res = calcular_resumen_periodo(emp.id, h_e, h_e)
        else:
            res = calcular_resumen_periodo(emp.id, inicio, fin)
        estado_dia = None
        if vista == "dia":
            estado_dia = resolver_estado_dia_laboral(emp.id, dia_consulta).get(
                "estado"
            )
        hent, hsal = ("—", "—")
        if vista == "dia":
            hent, hsal = entradas_salidas.get(emp.id, ("—", "—"))
        hoy_emp = (
            fecha_calendario_hoy_para_empleado(emp.id) if vista == "dia" else None
        )
        es_hoy_emp = vista == "dia" and dia_consulta == hoy_emp
        fila = {
            "id": emp.id,
            "nombre": emp.nombre_completo,
            "empresa": getattr(emp.empresa, "nombre", None),
            "dentro": empleado_dentro_jornada(emp.id) if es_hoy_emp else False,
            "horas": res.get("horas_trabajadas", 0),
            "estado_dia": estado_dia,
            "hora_entrada": hent,
            "hora_salida": hsal,
            "fecha_dia": dia_consulta if vista == "dia" else None,
            "es_hoy": es_hoy_emp,
        }
        fila["etiqueta_panel"] = etiqueta_estado_panel_equipo(fila, vista)
        resultado.append(fila)
    return resultado


# Umbral (horas) para mostrar «Jornada cerrada» frente a «En pausa» en el panel.
HORAS_MIN_JORNADA_CERRADA_PANEL = 6.5

_ETIQUETAS_MANUALES_PANEL = {
    "vacaciones": "Vacaciones",
    "libre": "Libre",
    "ausencia_justificada": "Ausencia justificada",
    "ausencia_no_justificada": "Ausencia no justificada",
}


def etiqueta_estado_panel_equipo(fila: dict, vista: str = "dia") -> str:
    """
    Etiqueta del listado Empleados en el panel (vista día).

    - «En pausa» solo si `es_hoy` (día consultado = hoy del empleado): fuera de jornada
      activa, con fichaje y horas ≤ 6,5 h.
    - «Jornada cerrada» en días pasados con fichaje (aunque < 6,5 h), o hoy con > 6,5 h.
    """
    horas = float(fila.get("horas") or 0)
    dentro = bool(fila.get("dentro"))
    ed = fila.get("estado_dia")
    es_hoy = bool(fila.get("es_hoy"))

    if vista == "dia" and ed in _ETIQUETAS_MANUALES_PANEL:
        return _ETIQUETAS_MANUALES_PANEL[ed]

    if vista == "dia":
        if not es_hoy:
            if ed == "pendiente" and horas == 0:
                return "Sin fichaje hoy"
            if horas > 0:
                return "Jornada cerrada"
            if ed == "pendiente":
                return "Sin fichaje hoy"
            return "Fuera"

        if ed == "en_jornada" or dentro:
            return "En jornada"
        if ed == "pendiente" and horas == 0:
            return "Sin fichaje hoy"
        if horas > HORAS_MIN_JORNADA_CERRADA_PANEL:
            return "Jornada cerrada"
        if horas > 0 and not dentro:
            return "En pausa"
        if ed == "pendiente":
            return "Sin fichaje hoy"

    if dentro:
        return "En jornada"
    if vista == "dia" and horas == 0:
        return "Sin fichaje hoy"
    return "Fuera"


def _etiqueta_estado_resumen_equipo(fila: dict, vista: str) -> str:
    """Texto de estado mostrado en la tabla (para ordenar por columna Estado)."""
    return etiqueta_estado_panel_equipo(fila, vista)


def _clave_orden_hora(texto: str) -> tuple[int, str]:
    """'—' al final; resto por cadena HH:MM."""
    s = (texto or "").strip()
    if not s or s == "—":
        return (1, "")
    return (0, s)


def _prioridad_estado_resumen_equipo(fila: dict, vista: str) -> int:
    """
    Orden en panel: 0 = Sin fichaje hoy, 1 = demás estados, 2 = En jornada (al final).
    """
    etiqueta = _etiqueta_estado_resumen_equipo(fila, vista)
    if etiqueta == "Sin fichaje hoy":
        return 0
    if etiqueta == "En jornada":
        return 2
    return 1


def ordenar_resumen_equipo(
    filas: list[dict],
    columna: str,
    direccion: str = "asc",
    vista: str = "dia",
) -> list[dict]:
    """Ordena filas del listado Empleados del panel (cabeceras clicables)."""
    columnas = {
        "nombre",
        "empresa",
        "estado",
        "entrada",
        "salida",
        "horas",
    }
    if columna not in columnas:
        columna = "estado"
    reverse = direccion == "desc"
    nombre_sec = lambda f: (f.get("nombre") or "").casefold()

    def clave(f: dict):
        if columna == "nombre":
            return (f.get("nombre") or "").casefold()
        if columna == "empresa":
            return (f.get("empresa") or "").casefold()
        if columna == "estado":
            return (
                _prioridad_estado_resumen_equipo(f, vista),
                _etiqueta_estado_resumen_equipo(f, vista).casefold(),
                nombre_sec(f),
            )
        if columna == "entrada":
            return _clave_orden_hora(f.get("hora_entrada", "—"))
        if columna == "salida":
            return _clave_orden_hora(f.get("hora_salida", "—"))
        return float(f.get("horas") or 0)

    return sorted(filas, key=clave, reverse=reverse)


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
