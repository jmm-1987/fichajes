"""Utilidades de geolocalización en el momento del fichaje (no seguimiento continuo)."""


def texto_ubicacion_humano(
    latitud: float | None,
    longitud: float | None,
    precision_metros: float | None,
) -> str:
    """
    Mensaje legible para el empleado. No hace geocodificación inversa por defecto
    para no depender de APIs externas; se puede ampliar con proveedor opcional.
    """
    if latitud is None or longitud is None:
        return "Ubicación no disponible (puede denegar permisos o usar escritorio)."
    prec = ""
    if precision_metros is not None:
        prec = f" Precisión aproximada: {int(precision_metros)} m."
    return (
        f"Coordenadas registradas: {float(latitud):.5f}, {float(longitud):.5f}.{prec}"
    )
