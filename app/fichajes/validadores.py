"""Validaciones de secuencia y consistencia de fichajes."""

from datetime import datetime, timezone
from typing import List, Optional, Tuple

from app.constantes import EstadoRegistroJornada, TipoRegistroJornada
from app.modelos import RegistroJornada


def validar_nuevo_tipo(
    registros_hoy_ordenados: List[RegistroJornada],
    tipo_propuesto: str,
) -> Tuple[bool, Optional[str]]:
    """
    Comprueba si el tipo de marca encaja en la secuencia del día.
    Devuelve (ok, mensaje_error).
    """
    if not registros_hoy_ordenados:
        if tipo_propuesto == TipoRegistroJornada.ENTRADA:
            return True, None
        if tipo_propuesto == TipoRegistroJornada.INCIDENCIA:
            return True, None
        return False, "Primero debe fichar la entrada."

    ultimo = registros_hoy_ordenados[-1].tipo_registro

    if tipo_propuesto == TipoRegistroJornada.ENTRADA:
        if ultimo == TipoRegistroJornada.SALIDA:
            return True, None
        return False, "Ya tiene una jornada abierta o incompleta."

    if tipo_propuesto == TipoRegistroJornada.SALIDA:
        if ultimo in (
            TipoRegistroJornada.ENTRADA,
            TipoRegistroJornada.PAUSA_FIN,
        ):
            return True, None
        return False, "No hay entrada abierta para cerrar."

    if tipo_propuesto == TipoRegistroJornada.PAUSA_INICIO:
        if ultimo == TipoRegistroJornada.ENTRADA:
            return True, None
        if ultimo == TipoRegistroJornada.PAUSA_FIN:
            return True, None
        return False, "La pausa solo tras entrada o fin de pausa anterior."

    if tipo_propuesto == TipoRegistroJornada.PAUSA_FIN:
        if ultimo == TipoRegistroJornada.PAUSA_INICIO:
            return True, None
        return False, "No hay pausa iniciada."

    if tipo_propuesto == TipoRegistroJornada.INCIDENCIA:
        return True, None

    return True, None


def filtrar_registros_validos(
    registros: List[RegistroJornada],
) -> List[RegistroJornada]:
    """Excluye anulados."""
    return [
        r
        for r in registros
        if r.estado != EstadoRegistroJornada.ANULADO
    ]


def ahora_servidor() -> datetime:
    return datetime.now(timezone.utc)
