"""
Formato de fechas en español (dd/mm/aaaa) y zona Europe/Madrid para fechas-hora.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional, Union
from zoneinfo import ZoneInfo

ZONA_MADRID = ZoneInfo("Europe/Madrid")

FORMATO_FECHA = "%d/%m/%Y"
FORMATO_FECHA_HORA = "%d/%m/%Y %H:%M"
FORMATO_FECHA_HORA_SEG = "%d/%m/%Y %H:%M:%S"


def _a_madrid_naive(dt: datetime) -> datetime:
    """Convierte a hora local Madrid sin tzinfo para strftime uniforme."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZONA_MADRID).replace(tzinfo=None)


def formatear_fecha(valor: Optional[Union[date, datetime, str]]) -> str:
    """Fecha como dd/mm/aaaa. Acepta date, datetime o cadena ISO/yyyy-mm-dd."""
    if valor is None:
        return "—"
    if isinstance(valor, str):
        s = valor.strip()
        if not s:
            return "—"
        if "T" in s or len(s) > 10:
            try:
                dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
                return formatear_fecha(dt.date())
            except ValueError:
                pass
        try:
            d = date.fromisoformat(s[:10])
            return d.strftime(FORMATO_FECHA)
        except ValueError:
            return s
    if isinstance(valor, datetime):
        return valor.date().strftime(FORMATO_FECHA)
    return valor.strftime(FORMATO_FECHA)


def formatear_fecha_hora(
    valor: Optional[datetime],
    con_segundos: bool = True,
) -> str:
    """Fecha y hora en Madrid como dd/mm/aaaa HH:MM[:SS]."""
    if valor is None:
        return "—"
    local = _a_madrid_naive(valor)
    fmt = FORMATO_FECHA_HORA_SEG if con_segundos else FORMATO_FECHA_HORA
    return local.strftime(fmt)


def parsear_fecha_es(cadena: Optional[str]) -> Optional[date]:
    """
    Parsea dd/mm/aaaa o yyyy-mm-dd (p. ej. querystring antigua).
    """
    if not cadena:
        return None
    s = str(cadena).strip()
    if not s:
        return None
    for fmt in (FORMATO_FECHA, "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def parsear_fecha_hora_es(cadena: Optional[str]) -> Optional[datetime]:
    """Parsea dd/mm/aaaa HH:MM:SS o HH:MM (interpretado en hora local Madrid)."""
    if not cadena:
        return None
    s = str(cadena).strip()
    if not s:
        return None
    for fmt in (FORMATO_FECHA_HORA_SEG, FORMATO_FECHA_HORA, f"{FORMATO_FECHA} %H:%M:%S"):
        try:
            naive = datetime.strptime(s, fmt)
            return naive.replace(tzinfo=ZONA_MADRID).astimezone(timezone.utc)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def periodo_texto(fecha_inicio: date, fecha_fin: date) -> str:
    """Texto de rango para informes/PDF."""
    return f"{fecha_inicio.strftime(FORMATO_FECHA)} — {fecha_fin.strftime(FORMATO_FECHA)}"


def valor_fecha_hora_edicion(dt: datetime) -> str:
    """Cadena para rellenar un DateTimeField en español (Madrid)."""
    return _a_madrid_naive(dt).strftime(FORMATO_FECHA_HORA_SEG)
