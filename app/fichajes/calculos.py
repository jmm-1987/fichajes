"""
Cálculo de horas trabajadas y clasificación (normal, extra, nocturna, festiva).

La lógica es independiente de las vistas para facilitar tests.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Iterable, List, Optional, Tuple

from flask import current_app

from app.constantes import EstadoRegistroJornada, TipoRegistroJornada
from app.modelos import Empleado, Festivo, RegistroJornada
from app.utilidades.fechas import formatear_fecha


@dataclass
class SegmentoTrabajo:
    """Intervalo de trabajo continuo (entrada → salida menos pausas)."""

    inicio: datetime
    fin: datetime


def _utc(d: datetime) -> datetime:
    if d.tzinfo is None:
        return d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def obtener_registros_dia(empleado_id: int, dia: date) -> List[RegistroJornada]:
    """Fichajes del día (no anulados), ordenados."""
    inicio = datetime.combine(dia, time.min, tzinfo=timezone.utc)
    fin = inicio + timedelta(days=1)
    return (
        RegistroJornada.query.filter(
            RegistroJornada.empleado_id == empleado_id,
            RegistroJornada.fecha_hora_servidor >= inicio,
            RegistroJornada.fecha_hora_servidor < fin,
            RegistroJornada.estado != EstadoRegistroJornada.ANULADO,
        )
        .order_by(RegistroJornada.fecha_hora_servidor)
        .all()
    )


def construir_segmentos_trabajo(registros: List[RegistroJornada]) -> List[SegmentoTrabajo]:
    """
    A partir de marcas ordenadas, obtiene intervalos trabajados (descuenta pausas).
    """
    segmentos: List[SegmentoTrabajo] = []
    apertura: Optional[datetime] = None
    pausa_inicio: Optional[datetime] = None

    for r in registros:
        ts = _utc(r.fecha_hora_servidor)
        if r.tipo_registro == TipoRegistroJornada.ENTRADA:
            apertura = ts
            pausa_inicio = None
        elif r.tipo_registro == TipoRegistroJornada.PAUSA_INICIO:
            pausa_inicio = ts
        elif r.tipo_registro == TipoRegistroJornada.PAUSA_FIN:
            pausa_inicio = None
        elif r.tipo_registro == TipoRegistroJornada.SALIDA and apertura is not None:
            segmentos.append(SegmentoTrabajo(inicio=apertura, fin=ts))
            apertura = None
            pausa_inicio = None

    if apertura is not None:
        # Jornada abierta: hasta "ahora" para estimación del día en curso
        ahora = datetime.now(timezone.utc)
        segmentos.append(SegmentoTrabajo(inicio=apertura, fin=max(apertura, ahora)))

    return segmentos


def duracion_horas(inicio: datetime, fin: datetime) -> float:
    """Duración en horas (float)."""
    if fin <= inicio:
        return 0.0
    return (fin - inicio).total_seconds() / 3600.0


def parse_hora_config(cadena: str) -> time:
    """Convierte 'HH:MM' a time."""
    partes = cadena.strip().split(":")
    h = int(partes[0])
    m = int(partes[1]) if len(partes) > 1 else 0
    return time(h, m)


def obtener_ventana_nocturna(empresa_id: int | None) -> Tuple[time, time]:
    """Inicio y fin de franja nocturna, priorizando configuración por empresa."""
    from app.modelos import ConfiguracionHorasNocturnas

    if empresa_id is not None:
        cfg = (
            ConfiguracionHorasNocturnas.query.filter_by(
                empresa_id=empresa_id, activo=True
            )
            .order_by(ConfiguracionHorasNocturnas.id.desc())
            .first()
        )
        if cfg:
            return cfg.hora_inicio, cfg.hora_fin

    ini = current_app.config.get("HORAS_NOCTURNAS_INICIO", "22:00")
    fin = current_app.config.get("HORAS_NOCTURNAS_FIN", "06:00")
    return parse_hora_config(str(ini)), parse_hora_config(str(fin))


def es_festivo(d: date, empresa_id: int | None) -> bool:
    """True si la fecha está en calendario de festivos activos (por empresa) o fin de semana según config."""
    if current_app.config.get("FINES_DE_SEMANA_COMO_FESTIVO"):
        if d.weekday() >= 5:
            return True
    q = Festivo.query.filter_by(fecha=d, activo=True)
    if empresa_id is not None:
        q = q.filter(Festivo.empresa_id == empresa_id)
    existe = q.first() is not None
    return existe


def horas_en_ventana_nocturna(
    inicio: datetime, fin: datetime, noche_ini: time, noche_fin: time
) -> float:
    """
    Horas del intervalo [inicio, fin] que caen en franja nocturna.
    La franja puede cruzar medianoche (ini > fin en reloj).
    """
    total = 0.0
    t = inicio
    paso = timedelta(minutes=15)
    while t < fin:
        bloque_fin = min(t + paso, fin)
        if _punto_en_nocturna(t, noche_ini, noche_fin):
            total += duracion_horas(t, bloque_fin)
        t = bloque_fin
    return total


def _punto_en_nocturna(
    momento: datetime, noche_ini: time, noche_fin: time
) -> bool:
    """Comprueba si un instante cae en horario nocturno."""
    h = momento.time()
    if noche_ini <= noche_fin:
        return noche_ini <= h < noche_fin
    # Cruce medianoche: ej. 22:00–06:00
    return h >= noche_ini or h < noche_fin


def clasificar_dia(
    empleado_id: int,
    dia: date,
    jornada_teorica_dia: Optional[float] = None,
) -> dict:
    """
    Devuelve desglose de horas para un día concreto.
    """
    emp = Empleado.query.get(empleado_id)
    if jornada_teorica_dia is None:
        jornada_teorica_dia = float(
            current_app.config.get("JORNADA_TEORICA_HORAS_DIA", 8)
        )
    if emp and emp.horas_semanales:
        # Jornada diaria teórica a partir de horas semanales / 5
        jornada_teorica_dia = min(
            jornada_teorica_dia,
            float(Decimal(emp.horas_semanales)) / 5.0,
        )

    registros = obtener_registros_dia(empleado_id, dia)
    segmentos = construir_segmentos_trabajo(registros)
    empresa_id = emp.empresa_id if emp is not None else None
    noche_ini, noche_fin = obtener_ventana_nocturna(empresa_id)
    festivo = es_festivo(dia, empresa_id)

    horas_totales = sum(duracion_horas(s.inicio, s.fin) for s in segmentos)
    horas_nocturnas = sum(
        horas_en_ventana_nocturna(s.inicio, s.fin, noche_ini, noche_fin)
        for s in segmentos
    )

    if festivo:
        horas_festivas = horas_totales
        horas_nocturnas_festivas = horas_nocturnas
        horas_normales = 0.0
        horas_extras = 0.0
    else:
        horas_festivas = 0.0
        horas_nocturnas_festivas = 0.0
        horas_normales = min(horas_totales, jornada_teorica_dia)
        horas_extras = max(0.0, horas_totales - jornada_teorica_dia)

    incompleto = _dia_incompleto(registros)
    incidencias = incompleto or _detectar_solapes(registros)

    return {
        "fecha": formatear_fecha(dia),
        "horas_trabajadas": round(horas_totales, 2),
        "horas_normales": round(horas_normales, 2),
        "horas_extras": round(horas_extras, 2),
        "horas_nocturnas": round(horas_nocturnas, 2),
        "horas_festivas": round(horas_festivas, 2),
        "horas_nocturnas_festivas": round(horas_nocturnas_festivas, 2),
        "jornada_incompleta": incompleto,
        "posible_incidencia": incidencias,
    }


def _dia_incompleto(registros: List[RegistroJornada]) -> bool:
    tipos = [r.tipo_registro for r in registros]
    return TipoRegistroJornada.ENTRADA in tipos and TipoRegistroJornada.SALIDA not in tipos


def _detectar_solapes(registros: List[RegistroJornada]) -> bool:
    """Detección simple: dos entradas sin salida intermedia."""
    entradas = 0
    for r in registros:
        if r.tipo_registro == TipoRegistroJornada.ENTRADA:
            entradas += 1
            if entradas > 1:
                return True
        elif r.tipo_registro == TipoRegistroJornada.SALIDA:
            entradas = max(0, entradas - 1)
    return False


def calcular_resumen_periodo(
    empleado_id: int, fecha_inicio: date, fecha_fin: date
) -> dict:
    """Suma clasificación día a día en un rango."""
    acum = {
        "horas_trabajadas": 0.0,
        "horas_normales": 0.0,
        "horas_extras": 0.0,
        "horas_nocturnas": 0.0,
        "horas_festivas": 0.0,
        "horas_nocturnas_festivas": 0.0,
        "dias_incompletos": 0,
        "dias_con_incidencia": 0,
    }
    d = fecha_inicio
    while d <= fecha_fin:
        part = clasificar_dia(empleado_id, d)
        acum["horas_trabajadas"] += part["horas_trabajadas"]
        acum["horas_normales"] += part["horas_normales"]
        acum["horas_extras"] += part["horas_extras"]
        acum["horas_nocturnas"] += part["horas_nocturnas"]
        acum["horas_festivas"] += part["horas_festivas"]
        acum["horas_nocturnas_festivas"] += part["horas_nocturnas_festivas"]
        if part["jornada_incompleta"]:
            acum["dias_incompletos"] += 1
        if part["posible_incidencia"]:
            acum["dias_con_incidencia"] += 1
        d += timedelta(days=1)

    for k in list(acum.keys()):
        if k.startswith("horas_"):
            acum[k] = round(acum[k], 2)
    return acum


def iterar_dias(fecha_inicio: date, fecha_fin: date) -> Iterable[date]:
    d = fecha_inicio
    while d <= fecha_fin:
        yield d
        d += timedelta(days=1)
