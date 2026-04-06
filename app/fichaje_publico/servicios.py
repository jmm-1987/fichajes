"""Lógica del panel de fichaje público (terminal / código de barras)."""

from typing import Literal

from app.constantes import TipoRegistroJornada
from app.fichajes.servicios import datos_contador_portal_fichaje, obtener_registros_dia_ordenados
from app.fichajes.validadores import ahora_servidor
from app.modelos import Empleado


EstadoKiosk = Literal["fuera", "dentro", "pausa"]


def buscar_empleado_por_codigo(codigo: str) -> Empleado | None:
    """Localiza empleado activo por código interno (mismo valor que en código de barras)."""
    if not codigo or not str(codigo).strip():
        return None
    c = str(codigo).strip()
    return Empleado.query.filter_by(codigo_empleado=c, activo=True).first()


def estado_kiosk_empleado(empleado_id: int) -> EstadoKiosk:
    """
    fuera: puede fichar entrada.
    dentro: jornada activa (entrada o fin de pausa sin salida); puede fichar salida en el panel.
    pausa: pausa iniciada; el panel no cierra jornada hasta fin de pausa (usar app o RRHH).
    """
    hoy = ahora_servidor().date()
    regs = obtener_registros_dia_ordenados(empleado_id, hoy)
    cont = datos_contador_portal_fichaje(regs)
    if cont.get("en_pausa"):
        return "pausa"
    if cont.get("mostrar_contador") and cont.get("contador_inicio_iso"):
        return "dentro"
    return "fuera"


def puede_fichar_salida_kiosk(empleado_id: int) -> bool:
    """True si la secuencia del día permite una salida (misma regla que el portal)."""
    hoy = ahora_servidor().date()
    regs = obtener_registros_dia_ordenados(empleado_id, hoy)
    if not regs:
        return False
    ultimo = regs[-1].tipo_registro
    return ultimo in (TipoRegistroJornada.ENTRADA, TipoRegistroJornada.PAUSA_FIN)
