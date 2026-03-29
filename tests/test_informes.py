"""Construcción de informe vacío."""

from datetime import date

from app.informes.servicios import FiltrosInforme, construir_informe_empleado


def test_informe_sin_empleados(aplicacion):
    with aplicacion.app_context():
        f = FiltrosInforme(
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 1, 31),
            empleado_id=99999,
        )
        filas = construir_informe_empleado(f)
        assert filas == []
