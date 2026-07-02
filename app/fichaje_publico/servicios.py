"""Lógica del panel de fichaje público (terminal / código de barras)."""

from datetime import datetime, time, timedelta, timezone
from typing import Literal, Optional

from app.constantes import TipoRegistroJornada
from app.fichajes.servicios import datos_contador_portal_fichaje, obtener_registros_dia_ordenados
from app.fichajes.validadores import ahora_servidor
from app.fichajes.zona_trabajo import fecha_calendario_hoy_para_empleado, zona_trabajo_para_empleado
from app.modelos import Empleado
from app.utilidades.fechas import intervalo_utc_dia_en_zona

EstadoKiosk = Literal["fuera", "dentro", "pausa"]

NOTA_HORA_MANUAL_KIOSK = "Hora indicada manualmente en fichaje público"


def buscar_empleado_por_codigo(codigo: str) -> Empleado | None:
    """Localiza empleado activo por código interno (mismo valor que en código de barras)."""
    if not codigo or not str(codigo).strip():
        return None
    c = str(codigo).strip()
    return Empleado.query.filter_by(codigo_empleado=c, activo=True).first()


def hora_local_empleado_iso(empleado_id: int) -> str:
    """Hora actual del empleado en HH:MM (para valor por defecto del formulario)."""
    zona = zona_trabajo_para_empleado(empleado_id)
    return datetime.now(zona).strftime("%H:%M")


def resolver_hora_fichaje_kiosk(
    empleado_id: int,
    usar_manual: bool,
    hora_hhmm: str,
    tipo_registro: str,
) -> tuple[Optional[datetime], Optional[str]]:
    """
    Devuelve (fecha_hora_servidor UTC, error).
    Si no se usa hora manual, (None, None) indica fichar con la hora actual.
    """
    if not usar_manual:
        return None, None

    hora_txt = (hora_hhmm or "").strip()
    if not hora_txt:
        return None, "Indique la hora."

    partes = hora_txt.split(":")
    if len(partes) < 2:
        return None, "Formato de hora no válido (use HH:MM)."
    try:
        hh = int(partes[0])
        mm = int(partes[1])
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            raise ValueError
    except ValueError:
        return None, "Hora no válida."

    zona = zona_trabajo_para_empleado(empleado_id)
    dia = fecha_calendario_hoy_para_empleado(empleado_id)
    local_dt = datetime.combine(dia, time(hh, mm), tzinfo=zona)
    utc_dt = local_dt.astimezone(timezone.utc)
    ahora = ahora_servidor()

    if utc_dt > ahora + timedelta(minutes=2):
        return None, "La hora no puede ser futura."

    inicio_dia, _ = intervalo_utc_dia_en_zona(dia, zona)
    if utc_dt < inicio_dia:
        return None, "La hora debe corresponder al día de hoy."

    existentes = obtener_registros_dia_ordenados(empleado_id, dia)
    if existentes:
        ultimo = existentes[-1]
        ult_ts = ultimo.fecha_hora_servidor
        if ult_ts and ult_ts.tzinfo is None:
            ult_ts = ult_ts.replace(tzinfo=timezone.utc)
        if ult_ts and utc_dt <= ult_ts:
            return None, "La hora debe ser posterior a la última marca del día."

    if tipo_registro == TipoRegistroJornada.SALIDA and existentes:
        ultimo_tipo = existentes[-1].tipo_registro
        if ultimo_tipo not in (
            TipoRegistroJornada.ENTRADA,
            TipoRegistroJornada.PAUSA_FIN,
        ):
            return None, "No hay entrada abierta para cerrar a esa hora."

    return utc_dt, None


def estado_kiosk_empleado(empleado_id: int) -> EstadoKiosk:
    """
    fuera: puede fichar entrada.
    dentro: jornada activa (entrada o fin de pausa sin salida); puede fichar salida en el panel.
    pausa: pausa iniciada; el panel no cierra jornada hasta fin de pausa (usar app o RRHH).
    """
    hoy = fecha_calendario_hoy_para_empleado(empleado_id)
    regs = obtener_registros_dia_ordenados(empleado_id, hoy)
    cont = datos_contador_portal_fichaje(regs)
    if cont.get("en_pausa"):
        return "pausa"
    if cont.get("mostrar_contador") and cont.get("contador_inicio_iso"):
        return "dentro"
    return "fuera"


def puede_fichar_salida_kiosk(empleado_id: int) -> bool:
    """True si la secuencia del día permite una salida (misma regla que el portal)."""
    hoy = fecha_calendario_hoy_para_empleado(empleado_id)
    regs = obtener_registros_dia_ordenados(empleado_id, hoy)
    if not regs:
        return False
    ultimo = regs[-1].tipo_registro
    return ultimo in (TipoRegistroJornada.ENTRADA, TipoRegistroJornada.PAUSA_FIN)
