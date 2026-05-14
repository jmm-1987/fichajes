"""Zona horaria de trabajo por empresa (día calendario para fichajes y resúmenes)."""

from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

from app.extensiones import db
from app.modelos import Empleado, Empresa
from app.utilidades.fechas import ZONA_MADRID, hoy_calendario_en_zona


def zona_trabajo_para_empresa_id(empresa_id: int | None) -> ZoneInfo:
    """IANA ZoneInfo; por defecto Europa/Madrid."""
    if empresa_id is None:
        return ZONA_MADRID
    empresa = db.session.get(Empresa, empresa_id)
    if empresa is None:
        return ZONA_MADRID
    raw = getattr(empresa, "zona_horaria", None)
    s = (str(raw).strip() if raw is not None else "") or ""
    if not s:
        return ZONA_MADRID
    try:
        return ZoneInfo(s)
    except Exception:
        return ZONA_MADRID


def zona_trabajo_para_empleado(empleado_id: int) -> ZoneInfo:
    """Zona de la empresa del empleado, o Madrid si no hay empresa o IANA inválida."""
    emp = db.session.get(Empleado, empleado_id)
    if emp is None:
        return ZONA_MADRID
    return zona_trabajo_para_empresa_id(emp.empresa_id)


def fecha_calendario_hoy_para_empleado(empleado_id: int) -> date:
    """Hoy según el reloj de la zona de trabajo del empleado."""
    return hoy_calendario_en_zona(zona_trabajo_para_empleado(empleado_id))
